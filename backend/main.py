"""
FastAPI WebSocket server for the poker assistant.
"""

import asyncio
import json
import re
import secrets
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from game_engine import (
    GameState, make_game, build_seats_from_claimed,
    start_preflop, start_street, advance_turn, end_street,
    active_positions, next_to_act, only_one_left, winner_name,
    to_call, pot_add, is_bb_option, reset_for_new_round,
    add_history, recalc, build_recommendation,
    parse_card, card_to_short, cards_str, card_str,
    get_preflop_order, get_postflop_order,
    position_labels_map, ring_positions, blind_positions, advance_button,
    place_initial_button,
    TABLE_POSITIONS, ALL_POSITIONS, STAGE_NAMES,
    SUIT_DISPLAY, RANK_DISPLAY,
)

BETTING_STATES = (GameState.PREFLOP, GameState.FLOP, GameState.TURN, GameState.RIVER)

SESSIONS: Dict[str, dict] = {}
CONNECTIONS: Dict[str, Dict[str, WebSocket]] = {}
PING_INTERVAL = 30


def new_session_id() -> str:
    return secrets.token_urlsafe(6)


def serialize_game(game: dict, user_id: str) -> dict:
    """Build JSON-safe snapshot of game state for a specific user."""
    g = game
    responsible = g.get('responsible_id')
    is_responsible = (user_id == responsible)

    # Список участников сессии (имена)
    members = g.get('members', {})

    seats_out = {}
    for pos in ALL_POSITIONS:
        raw = g['seats'].get(pos, {'type': 'empty'})
        s = {'type': raw.get('type', 'empty'), 'folded': raw.get('folded', False),
             'pending': raw.get('pending', False)}
        if raw.get('type') == 'our':
            p = raw.get('player', {})
            # Оператор видит все карты; наши игроки видят карты друг друга
            is_our_player = any(
                s.get('player', {}).get('user_id') == user_id
                for s in g['seats'].values()
                if s.get('type') == 'our'
            )
            cards_visible = is_responsible or is_our_player
            s['player'] = {
                'number': p.get('number'),
                'name': p.get('name', ''),
                'user_id': p.get('user_id', ''),
                'cards': [card_to_short(c) for c in p.get('cards', [])] if cards_visible else
                         (['??'] * len(p.get('cards', [])) if p.get('cards') else []),
                'equity_share': round(p.get('equity_share', 0), 4),
                'equity_delta': round(p.get('equity_delta', 0), 4),
                'ev': round(p.get('ev', 0), 2),
            }
        elif raw.get('type') == 'opponent':
            p = raw.get('player', {})
            s['player'] = {'number': p.get('number')}
            s['otype'] = raw.get('otype', 'normal')
        seats_out[pos] = s

    board_cards = [card_to_short(c) for c in g.get('board', [])]

    rec_text, rec_label, rec_phys = None, None, None
    try:
        rec_text, rec_label, rec_phys = build_recommendation(g)
    except Exception:
        pass

    # Структурированное действие из рекомендации (для кнопки «по совету»)
    rec_action = None
    if rec_text and rec_phys:
        head = rec_text.strip().upper()
        first_num = re.search(r'(\d+)', rec_text)
        amt = int(first_num.group(1)) if first_num else 0
        if head.startswith('ФОЛД'):
            rec_action = {'pos': rec_phys, 'kind': 'fold'}
        elif head.startswith('ЧЕК'):
            rec_action = {'pos': rec_phys, 'kind': 'check'}
        elif head.startswith('КОЛЛ'):
            rec_action = {'pos': rec_phys, 'kind': 'call', 'amount': amt}
        elif head.startswith(('РЕЙЗ', 'БЕТ', 'ДОНК', '3БЕТ', '4БЕТ', 'ОЛЛ')):
            if amt > 0:
                rec_action = {'pos': rec_phys, 'kind': 'raise', 'amount': amt}

    # Рекомендация для конкретного игрока (если он наш)
    my_recommendation = None
    for pos in g.get('player_positions', []):
        seat = g['seats'].get(pos, {})
        if seat.get('player', {}).get('user_id') == user_id:
            if rec_phys == pos:
                my_recommendation = rec_text
            break

    opp_actions_out = {}
    for pos, act in g.get('opp_actions', {}).items():
        opp_actions_out[pos] = act or ''

    # seat_claimed: {user_id: pos} -> для фронтенда
    claimed_out = {}
    for uid, pos in g.get('seat_claimed', {}).items():
        name = members.get(uid, uid[:6])
        claimed_out[pos] = {'user_id': uid, 'name': name}

    # Дилер, SB, BB и ярлыки позиций — по кольцу занятых мест (с учётом дыр/pending)
    positions = g.get('positions', [])
    position_labels = position_labels_map(g)   # физ.позиция -> ярлык (UTG/MP/CO/BU/SB/BB)
    dealer_pos = g.get('button_pos') if g.get('button_pos') in ring_positions(g) else None
    sb_pos, bb_pos = blind_positions(g)

    # Краткая рекомендация для каждого нашего игрока
    # Показывается ТОЛЬКО когда это ход игрока. Иначе — пусто.
    per_player_recs = {}
    for pos in g.get('player_positions', []):
        seat = g['seats'].get(pos, {})
        if seat.get('folded'):
            continue  # фолднувшие — без рекомендации (статус видно по opacity)
        cards = seat.get('player', {}).get('cards', [])
        if not cards or len(cards) < 2:
            continue

        # Рекомендация только когда это ход этого игрока
        if pos != rec_phys or not rec_text:
            continue

        # Извлекаем краткое действие из GTO-текста
        rt = rec_text.upper()
        if 'ФОЛД' in rt:
            per_player_recs[pos] = 'ФОЛД'
        elif any(w in rt for w in ('РЕЙЗ', 'БЕТ', '3БЕТ', '4БЕТ', 'ОТКРЫТ')):
            # Извлекаем сумму из GTO-текста ("до ~150", "до ~300")
            m = re.search(r'~(\d+)', rec_text)
            if m:
                per_player_recs[pos] = f'РЕЙЗ {m.group(1)}'
            else:
                per_player_recs[pos] = 'РЕЙЗ'
        elif 'КОЛЛ' in rt:
            call_amt = to_call(g, pos)
            per_player_recs[pos] = f'КОЛЛ {call_amt}' if call_amt > 0 else 'КОЛЛ'
        elif 'ЧЕК' in rt:
            per_player_recs[pos] = 'ЧЕК'
        else:
            per_player_recs[pos] = '—'

    # Порядок мест по очередности хода для текущей улицы (для панели действий)
    try:
        if g['state'] == GameState.PREFLOP:
            action_order = get_preflop_order(g)
        elif g['state'] in (GameState.FLOP, GameState.TURN, GameState.RIVER):
            action_order = get_postflop_order(g)
        else:
            action_order = list(positions)
    except Exception:
        action_order = list(positions)

    return {
        'state': g['state'].name,
        'table_size': g.get('table_size', 0),
        'positions': positions,
        'action_order': action_order,
        'player_positions': g.get('player_positions', []),
        'opponent_positions': g.get('opponent_positions', []),
        'seats': seats_out,
        'pot': g.get('pot', 0),
        'sb': g.get('sb', 0),
        'bb': g.get('bb', 0),
        'board': board_cards,
        'current_turn': g.get('current_turn'),
        'team_win_pct': round(g.get('team_win_pct', 0), 4),
        'history': g.get('history', [])[-15:],
        'recommendation': rec_text,
        'recommendation_pos': rec_label,
        'opp_actions': opp_actions_out,
        'is_responsible': is_responsible,
        'responsible_name': g.get('responsible_name', ''),
        'members': {uid: name for uid, name in members.items()},
        'seat_claimed': claimed_out,
        'dealer_pos': dealer_pos,
        'sb_pos': sb_pos,
        'bb_pos': bb_pos,
        'position_labels': position_labels,
        'per_player_recs': per_player_recs,
        'my_recommendation': my_recommendation,
        'rec_action': rec_action,
        'call_amount': to_call(g, g.get('current_turn', '')) if g.get('current_turn') else 0,
        'test_mode': g.get('test_mode', False),
        'street_complete': g.get('current_turn') is None and g['state'] not in (
            GameState.SETUP_RESPONSIBLE, GameState.SETUP_TABLE,
            GameState.SEAT_PICKING, GameState.SETUP_BLINDS, GameState.DEALING,
        ),
    }


async def broadcast(session_id: str):
    conns = CONNECTIONS.get(session_id, {})
    game = SESSIONS.get(session_id, {}).get('game')
    if not game or not conns:
        return
    dead = []
    for uid, ws in conns.items():
        try:
            payload = serialize_game(game, uid)
            await ws.send_json({'type': 'state', 'data': payload})
        except Exception:
            dead.append(uid)
    for uid in dead:
        conns.pop(uid, None)


async def send_error(ws: WebSocket, msg: str):
    try:
        await ws.send_json({'type': 'error', 'message': msg})
    except Exception:
        pass


async def send_event(ws: WebSocket, event: str, data: dict = None):
    try:
        await ws.send_json({'type': 'event', 'event': event, 'data': data or {}})
    except Exception:
        pass


async def ping_loop(ws: WebSocket, session_id: str, user_id: str):
    try:
        while True:
            await asyncio.sleep(PING_INTERVAL)
            if CONNECTIONS.get(session_id, {}).get(user_id) is not ws:
                break
            await ws.send_json({'type': 'ping', 'ts': int(time.time())})
    except Exception:
        pass


SESSION_TTL = 2 * 60 * 60  # 2 часа


async def cleanup_loop():
    """Фоновая задача: удаляет сессии без активности > 2 часов."""
    while True:
        await asyncio.sleep(300)  # проверяем каждые 5 минут
        now = time.time()
        expired = [
            sid for sid, sess in SESSIONS.items()
            if now - sess.get('last_activity', sess.get('created', 0)) > SESSION_TTL
        ]
        for sid in expired:
            SESSIONS.pop(sid, None)
            CONNECTIONS.pop(sid, None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    SESSIONS.clear()
    CONNECTIONS.clear()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.post("/api/session/new")
async def create_session():
    sid = new_session_id()
    game = make_game()
    SESSIONS[sid] = {'game': game, 'created': time.time()}
    CONNECTIONS[sid] = {}
    return {"session_id": sid}


@app.get("/api/session/{session_id}/state")
async def get_state(session_id: str, user_id: str = "anon"):
    sess = SESSIONS.get(session_id)
    if not sess:
        return {"error": "session not found"}
    return serialize_game(sess['game'], user_id)


# ────────────────────────────────────────────
#  WebSocket endpoint
# ────────────────────────────────────────────

@app.websocket("/ws/{session_id}/{user_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str, user_id: str):
    # Принимаем хендшейк, затем проверяем сессию — так клиент получает
    # понятное сообщение 'session_gone' (а не глухой 403), и может прекратить
    # бесконечные переподключения к мёртвой сессии (напр. после рестарта/деплоя).
    await websocket.accept()
    sess = SESSIONS.get(session_id)
    if not sess:
        try:
            await websocket.send_json({'type': 'session_gone'})
        except Exception:
            pass
        await websocket.close(code=4004)
        return

    CONNECTIONS.setdefault(session_id, {})[user_id] = websocket
    game = sess['game']

    ping_task = asyncio.create_task(ping_loop(websocket, session_id, user_id))

    try:
        await broadcast(session_id)
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send_error(websocket, "invalid JSON")
                continue

            await handle_message(session_id, user_id, msg, websocket)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ping_task.cancel()
        conns = CONNECTIONS.get(session_id, {})
        conns.pop(user_id, None)


async def handle_message(session_id: str, user_id: str, msg: dict, ws: WebSocket):
    action = msg.get('action')
    SESSIONS[session_id]['last_activity'] = time.time()
    game = SESSIONS[session_id]['game']
    is_responsible = (user_id == game.get('responsible_id'))

    if action == 'join':
        await handle_join(session_id, user_id, msg, ws)
    elif action == 'set_table':
        if not is_responsible:
            return await send_error(ws, "только оператор может настраивать стол")
        await handle_set_table(session_id, game, msg)
    elif action == 'claim_seat':
        # Игроки выбирают места (не оператор, кроме тест-режима)
        if is_responsible and not game.get('test_mode'):
            return await send_error(ws, "оператор не занимает место за столом")
        await handle_claim_seat(session_id, user_id, game, msg)
    elif action == 'confirm_seats':
        if not is_responsible:
            return await send_error(ws, "только оператор подтверждает рассадку")
        await handle_confirm_seats(session_id, game)
    elif action == 'set_blinds':
        if not is_responsible:
            return await send_error(ws, "только оператор может ставить блайнды")
        await handle_set_blinds(session_id, game, msg)
    elif action == 'set_my_cards':
        # Игрок сам вводит свои карты
        await handle_set_my_cards(session_id, user_id, game, msg, ws)
    elif action == 'set_test_cards':
        # Тест-режим: оператор вводит карты за игрока
        if not is_responsible or not game.get('test_mode'):
            return await send_error(ws, "только в тестовом режиме")
        await handle_set_test_cards(session_id, game, msg, ws)
    elif action == 'deal_cards':
        if not is_responsible:
            return await send_error(ws, "только оператор раздаёт карты")
        await handle_deal_cards(session_id, game, msg)
    elif action == 'skip_blinds':
        if not is_responsible:
            return await send_error(ws, "только оператор")
        await handle_skip_blinds(session_id, game)
    elif action == 'player_action':
        await handle_player_action(session_id, user_id, game, msg, ws)
    elif action == 'opp_action':
        if not is_responsible:
            return await send_error(ws, "только оператор управляет оппонентами")
        await handle_opp_action(session_id, game, msg)
    elif action == 'board':
        if not is_responsible:
            return await send_error(ws, "только оператор выкладывает борд")
        await handle_board(session_id, game, msg)
    elif action == 'board_replace':
        if not is_responsible:
            return await send_error(ws, "только оператор выкладывает борд")
        await handle_board_replace(session_id, game, msg)
    elif action == 'toggle_seat_out':
        if not is_responsible:
            return await send_error(ws, "только оператор управляет местами")
        await handle_toggle_seat_out(session_id, game, msg)
    elif action == 'grow_table':
        if not is_responsible:
            return await send_error(ws, "только оператор управляет местами")
        await handle_grow_table(session_id, game)
    elif action == 'set_opp_type':
        if not is_responsible:
            return await send_error(ws, "только оператор задаёт тип оппонента")
        await handle_set_opp_type(session_id, game, msg)
    elif action == 'next_round':
        if not is_responsible:
            return await send_error(ws, "только оператор начинает раунд")
        await handle_next_round(session_id, game)
    elif action == 'new_game':
        if not is_responsible:
            return await send_error(ws, "только оператор")
        await handle_new_game(session_id, game)
    elif action == 'reconfigure':
        if not is_responsible:
            return await send_error(ws, "только оператор")
        await handle_reconfigure(session_id, game)
    elif action == 'pong':
        pass
    else:
        await send_error(ws, f"unknown action: {action}")


# ────────────────────────────────────────────
#  Message handlers
# ────────────────────────────────────────────

async def handle_join(session_id: str, user_id: str, msg: dict, ws: WebSocket):
    game = SESSIONS[session_id]['game']
    name = msg.get('name', f'Игрок {user_id[:4]}')
    role = msg.get('role', 'player')  # 'operator' или 'player'

    members = game.setdefault('members', {})
    members[user_id] = name

    test_mode = msg.get('test_mode', False)

    if role == 'operator' and not game.get('responsible_id'):
        game['responsible_id'] = user_id
        game['responsible_name'] = name
        if test_mode:
            game['test_mode'] = True
        game['state'] = GameState.SETUP_TABLE
        add_history(game, f"{name} — оператор" + (" (тест)" if test_mode else ""))
    elif role == 'operator' and game.get('responsible_id') == user_id:
        # Переподключение оператора
        game['responsible_name'] = name
    else:
        add_history(game, f"{name} подключился")

    await broadcast(session_id)


async def handle_set_table(session_id: str, game: dict, msg: dict):
    size = msg.get('size', 6)
    size = max(2, min(6, int(size)))
    game['table_size'] = size
    # Стол на выбранное число мест. Сверх него врагов можно досадить по ходу
    # игры кнопкой «Добавить место» (до 6).
    game['positions'] = list(TABLE_POSITIONS.get(size, TABLE_POSITIONS[6]))
    game['seats'] = {pos: {'type': 'empty'} for pos in ALL_POSITIONS}
    game['seat_claimed'] = {}
    game['button_pos'] = None
    game['state'] = GameState.SEAT_PICKING
    add_history(game, f"Стол: {size} мест")
    await broadcast(session_id)


async def handle_claim_seat(session_id: str, user_id: str, game: dict, msg: dict):
    pos = msg.get('position', '').upper()
    if pos not in game.get('positions', []):
        return

    claimed = game.setdefault('seat_claimed', {})

    if game.get('test_mode'):
        # В тест-режиме оператор кликает на места — создаём виртуальных игроков
        # Проверяем: если это место уже занято, снимаем
        taken_uid = None
        for uid, p in list(claimed.items()):
            if p == pos:
                taken_uid = uid
                break
        if taken_uid:
            claimed.pop(taken_uid, None)
            game.get('members', {}).pop(taken_uid, None)
        else:
            # Создаём виртуального игрока
            virt_id = f"test_{pos.lower()}_{secrets.token_hex(3)}"
            test_counter = sum(1 for k in claimed if k.startswith('test_')) + 1
            virt_name = f"Тест-{test_counter}"
            game.setdefault('members', {})[virt_id] = virt_name
            # Снять если другой виртуальный на этом месте
            for uid, p in list(claimed.items()):
                if p == pos:
                    claimed.pop(uid, None)
            claimed[virt_id] = pos
    else:
        old_pos = claimed.get(user_id)
        if old_pos == pos:
            # Снять выбор
            claimed.pop(user_id, None)
        else:
            # Снять старое место если было
            for uid, p in list(claimed.items()):
                if p == pos:
                    claimed.pop(uid, None)
            claimed[user_id] = pos

    name = game.get('members', {}).get(user_id, user_id[:6])
    game.setdefault('known_players', {})[pos] = name

    build_seats_from_claimed(game)
    await broadcast(session_id)


async def handle_confirm_seats(session_id: str, game: dict):
    """Оператор подтверждает рассадку → переход к блайндам."""
    claimed = game.get('seat_claimed', {})
    if not claimed:
        return  # нет ни одного игрока

    build_seats_from_claimed(game)
    game['state'] = GameState.SETUP_BLINDS
    add_history(game, "Рассадка подтверждена")
    await broadcast(session_id)


async def handle_set_blinds(session_id: str, game: dict, msg: dict):
    sb = int(msg.get('sb', 0))
    bb = int(msg.get('bb', 0))
    if bb <= 0:
        return
    if sb <= 0:
        sb = bb // 2
    game['sb'] = sb
    game['bb'] = bb
    game['pot'] = sb + bb
    game['last_bet'] = bb
    game['street_bet_to'] = bb

    # Из SETUP_BLINDS → сразу в PREFLOP (карты вводятся параллельно)
    if game['state'] == GameState.SETUP_BLINDS:
        game['state'] = GameState.PREFLOP
        build_seats_from_claimed(game)
        start_preflop(game)

    add_history(game, f"Блайнды: {sb}/{bb}")
    await broadcast(session_id)


async def handle_skip_blinds(session_id: str, game: dict):
    """Пропуск ввода блайндов — сразу в PREFLOP."""
    game['sb'] = 0
    game['bb'] = 0
    game['pot'] = 0
    game['last_bet'] = 0
    game['street_bet_to'] = 0
    game['state'] = GameState.PREFLOP
    build_seats_from_claimed(game)
    start_preflop(game)
    add_history(game, "Блайнды пропущены")
    await broadcast(session_id)


def _known_cards_except(game: dict, except_pos=None) -> set:
    """Все известные карты (руки игроков, кроме except_pos, + борд) как кортежи."""
    used = set()
    for p, s in game.get('seats', {}).items():
        if p == except_pos:
            continue
        for c in s.get('player', {}).get('cards', []) or []:
            if c and c != '??':
                used.add(tuple(c))
    for c in game.get('board', []):
        used.add(tuple(c))
    return used


def _validate_hole_cards(game, parsed, except_pos):
    """Возвращает текст ошибки или None. Карты в руке уникальны и не заняты
    другими игроками/бордом (иначе эквити считается на невозможной колоде)."""
    if len(set(tuple(c) for c in parsed)) != len(parsed):
        return "две одинаковые карты в руке"
    known = _known_cards_except(game, except_pos)
    for c in parsed:
        if tuple(c) in known:
            return "карта уже занята другим игроком или на борде"
    return None


async def handle_set_my_cards(session_id: str, user_id: str, game: dict, msg: dict, ws: WebSocket):
    """Игрок сам вводит свои карты."""
    card_strs = msg.get('cards', [])
    if len(card_strs) != 2:
        return await send_error(ws, "нужно ровно 2 карты")

    # Найти позицию этого игрока
    pos = None
    for p in game.get('player_positions', []):
        s = game['seats'].get(p, {})
        if s.get('player', {}).get('user_id') == user_id:
            pos = p
            break
    if not pos:
        return await send_error(ws, "вы не сидите за столом")

    parsed = []
    for cs in card_strs:
        c = parse_card(cs)
        if c:
            parsed.append(c)
    if len(parsed) != 2:
        return await send_error(ws, "некорректные карты")

    err = _validate_hole_cards(game, parsed, pos)
    if err:
        return await send_error(ws, err)

    seat = game['seats'][pos]
    seat['player']['cards'] = parsed

    name = seat['player'].get('name', pos)
    add_history(game, f"{name} ввёл карты")

    # Пересчитать equity если есть карты
    all_have_cards = all(
        len(game['seats'].get(p, {}).get('player', {}).get('cards', [])) == 2
        for p in game.get('player_positions', [])
    )
    if all_have_cards:
        await recalc(game)

    await broadcast(session_id)


async def handle_set_test_cards(session_id: str, game: dict, msg: dict, ws: WebSocket):
    """Тест-режим: оператор вводит карты за конкретного игрока по позиции."""
    pos = msg.get('position', '').upper()
    card_strs = msg.get('cards', [])
    if len(card_strs) != 2:
        return await send_error(ws, "нужно ровно 2 карты")

    seat = game['seats'].get(pos)
    if not seat or seat.get('type') != 'our':
        return await send_error(ws, f"нет нашего игрока на {pos}")

    parsed = []
    for cs in card_strs:
        c = parse_card(cs)
        if c:
            parsed.append(c)
    if len(parsed) != 2:
        return await send_error(ws, "некорректные карты")

    err = _validate_hole_cards(game, parsed, pos)
    if err:
        return await send_error(ws, err)

    seat['player']['cards'] = parsed
    name = seat['player'].get('name', pos)
    add_history(game, f"{name} ({pos}) карты введены")

    all_have_cards = all(
        len(game['seats'].get(p, {}).get('player', {}).get('cards', [])) == 2
        for p in game.get('player_positions', [])
    )
    if all_have_cards:
        await recalc(game)

    await broadcast(session_id)


async def handle_deal_cards(session_id: str, game: dict, msg: dict):
    cards_map: dict = msg.get('cards', {})
    seen = set()  # карты, уже разданные в этом батче
    for pos, card_strs in cards_map.items():
        seat = game['seats'].get(pos)
        if not seat or seat.get('type') != 'our':
            continue
        parsed = []
        for cs in card_strs:
            c = parse_card(cs)
            if c:
                parsed.append(c)
        if not parsed:
            continue
        # уникальность и отсутствие конфликтов с уже известными картами
        if _validate_hole_cards(game, parsed, pos) or any(tuple(c) in seen for c in parsed):
            continue   # пропускаем невозможную руку, чтобы не портить колоду
        seat['player']['cards'] = parsed
        for c in parsed:
            seen.add(tuple(c))

    game['state'] = GameState.PREFLOP
    start_preflop(game)

    await recalc(game)
    add_history(game, "Карты розданы")
    await broadcast(session_id)


async def handle_player_action(session_id: str, user_id: str, game: dict, msg: dict, ws: WebSocket):
    act = msg.get('act', '').lower()
    pos = msg.get('position', '')
    is_responsible = (user_id == game.get('responsible_id'))

    if not pos and not is_responsible:
        for p in game.get('player_positions', []):
            s = game['seats'].get(p, {})
            if s.get('player', {}).get('user_id') == user_id:
                pos = p
                break
    if not pos:
        return await send_error(ws, "позиция не найдена")

    seat = game['seats'].get(pos)
    if not seat or seat.get('type') != 'our':
        return await send_error(ws, "это не место нашего игрока")

    # Защита очереди хода: действие должно прийти от того, чей сейчас ход
    if game.get('state') in BETTING_STATES and game.get('current_turn') != pos:
        return await send_error(ws, "сейчас не ход этого игрока")

    pot_before = game.get('pot', 0)   # банк ДО ставки — для корректного % сайзинга
    if act == 'fold':
        seat['folded'] = True
        add_history(game, f"{seat['player'].get('name', pos)} фолд")
    elif act == 'call':
        call_amt = to_call(game, pos)
        pot_add(game, pos, game.get('street_bet_to', 0))
        add_history(game, f"{seat['player'].get('name', pos)} колл {call_amt}")
    elif act == 'check':
        add_history(game, f"{seat['player'].get('name', pos)} чек")
    elif act == 'raise':
        amount = int(msg.get('amount', 0))
        if amount > 0:
            pot_add(game, pos, amount)
            game['last_bet'] = amount
            game['street_bet_to'] = amount
            if game['state'] == GameState.PREFLOP:
                game['preflop_aggressor'] = pos
            elif game['state'] == GameState.FLOP:
                game['flop_aggressor'] = pos
                game['flop_bet_size'] = amount / max(pot_before, 1)
            elif game['state'] == GameState.TURN:
                game['turn_bet_size'] = amount / max(pot_before, 1)
                game.setdefault('agg_history', '')
                game['agg_history'] += 'b'
            game['acted_this_street'] = set()
            add_history(game, f"{seat['player'].get('name', pos)} рейз {amount}")
        else:
            return await send_error(ws, "укажите сумму рейза")
    elif act == 'bet':
        amount = int(msg.get('amount', 0))
        if amount > 0:
            pot_add(game, pos, amount)
            game['last_bet'] = amount
            game['street_bet_to'] = amount
            if game['state'] == GameState.FLOP:
                game['flop_aggressor'] = pos
                game['flop_bet_size'] = amount / max(pot_before, 1)
            elif game['state'] == GameState.TURN:
                game['turn_bet_size'] = amount / max(pot_before, 1)
                game['agg_history'] = game.get('agg_history', '') + 'b'
            add_history(game, f"{seat['player'].get('name', pos)} бет {amount}")
        else:
            return await send_error(ws, "укажите сумму бета")
    else:
        return await send_error(ws, f"неизвестное действие: {act}")

    game.setdefault('acted_this_street', set()).add(pos)

    if only_one_left(game):
        w = winner_name(game)
        add_history(game, f"Победитель: {w}")
        game['state'] = GameState.SHOWDOWN
    else:
        nxt = next_to_act(game)
        if nxt is None:
            end_street(game)
        else:
            game['current_turn'] = nxt

    await recalc(game)
    await broadcast(session_id)


async def handle_opp_action(session_id: str, game: dict, msg: dict):
    pos = msg.get('position', '').upper()
    act = msg.get('act', '').lower()
    seat = game['seats'].get(pos)
    if not seat or seat.get('type') != 'opponent':
        return

    # Защита очереди хода
    if game.get('state') in BETTING_STATES and game.get('current_turn') != pos:
        return

    pot_before = game.get('pot', 0)   # банк ДО ставки
    if act == 'fold':
        seat['folded'] = True
        game.setdefault('opp_actions', {})[pos] = 'fold'
        add_history(game, f"В{seat['player'].get('number', '?')} ({pos}) фолд")
    elif act in ('call', 'limp'):
        call_amt = to_call(game, pos)
        pot_add(game, pos, game.get('street_bet_to', 0))
        game.setdefault('opp_actions', {})[pos] = act
        add_history(game, f"В{seat['player'].get('number', '?')} ({pos}) {act} {call_amt}")
    elif act == 'check':
        game.setdefault('opp_actions', {})[pos] = 'check'
        add_history(game, f"В{seat['player'].get('number', '?')} ({pos}) чек")
    elif act in ('raise', 'bet', '3bet'):
        amount = int(msg.get('amount', 0))
        if amount > 0:
            pot_add(game, pos, amount)
            game['last_bet'] = amount
            game['street_bet_to'] = amount
        game.setdefault('opp_actions', {})[pos] = act
        if game['state'] == GameState.PREFLOP:
            game['preflop_aggressor'] = pos
        elif game['state'] == GameState.FLOP:
            game['flop_aggressor'] = pos
            game['flop_bet_size'] = amount / max(pot_before, 1) if amount else 0.5
        elif game['state'] == GameState.TURN:
            game['turn_bet_size'] = amount / max(pot_before, 1) if amount else 0.5
            game['agg_history'] = game.get('agg_history', '') + 'b'
        game['acted_this_street'] = set()
        label = f"рейз {amount}" if amount else act
        add_history(game, f"В{seat['player'].get('number', '?')} ({pos}) {label}")
    else:
        return

    game.setdefault('acted_this_street', set()).add(pos)

    if only_one_left(game):
        w = winner_name(game)
        add_history(game, f"Победитель: {w}")
        game['state'] = GameState.SHOWDOWN
    else:
        nxt = next_to_act(game)
        if nxt is None:
            end_street(game)
        else:
            game['current_turn'] = nxt

    await recalc(game)
    await broadcast(session_id)


async def handle_board(session_id: str, game: dict, msg: dict):
    # Проверяем, что все действия на текущей улице завершены
    if game.get('current_turn') is not None:
        return  # нельзя вводить борд пока не все действия завершены

    card_strs: list = msg.get('cards', [])
    parsed = []
    for cs in card_strs:
        c = parse_card(cs)
        if c:
            parsed.append(c)
    if not parsed:
        return

    # Защита от дубликатов: внутри выборки, против борда и карт игроков
    if len(set(parsed)) != len(parsed):
        return
    blocked = _player_cards_set(game) | set(game.get('board', []))
    if any(c in blocked for c in parsed):
        return

    if game['state'] in (GameState.PREFLOP, GameState.DEALING):
        if len(parsed) >= 3:
            game['board'] = parsed[:3]      # флоп — РОВНО 3 карты (не больше)
            game['state'] = GameState.FLOP
            start_street(game)
            add_history(game, f"Флоп: {' '.join(card_to_short(c) for c in game['board'][:3])}")
    elif game['state'] == GameState.FLOP:
        game['board'].append(parsed[0])
        game['state'] = GameState.TURN
        start_street(game)
        add_history(game, f"Тёрн: {card_to_short(parsed[0])}")
    elif game['state'] == GameState.TURN:
        game['board'].append(parsed[0])
        game['state'] = GameState.RIVER
        start_street(game)
        add_history(game, f"Ривер: {card_to_short(parsed[0])}")

    await recalc(game)
    await broadcast(session_id)


def _player_cards_set(game: dict) -> set:
    """Все карты на руках игроков (без '??')."""
    used = set()
    for s in game['seats'].values():
        for c in s.get('player', {}).get('cards', []) or []:
            if c and c != '??':
                used.add(c)
    return used


async def handle_board_replace(session_id: str, game: dict, msg: dict):
    """Заменяет существующие карты борда без смены состояния игры.
    Доступно в любой момент. Отклоняет дубликаты и карты, занятые игроками."""
    card_strs: list = msg.get('cards', [])
    parsed = [c for c in (parse_card(cs) for cs in card_strs) if c]
    if not parsed:
        return
    n = len(parsed)
    if n > len(game.get('board', [])):
        return
    # Защита от дубликатов: внутри новой выборки и против карт игроков
    if len(set(parsed)) != len(parsed):
        return
    player_cards = _player_cards_set(game)
    # Карты борда, которые НЕ заменяются (хвост), тоже не должны конфликтовать
    untouched = set(game['board'][n:])
    blocked = player_cards | untouched
    if any(c in blocked for c in parsed):
        return
    game['board'][:n] = parsed
    await recalc(game)
    await broadcast(session_id)


def _renumber_opponents(game: dict):
    """Перенумеровать врагов слева направо по порядку позиций (В1, В2, ...)."""
    num = 1
    opp_positions = []
    for pos in game.get('positions', []):
        s = game['seats'].get(pos, {})
        if s.get('type') == 'opponent':
            s.setdefault('player', {})['number'] = num
            opp_positions.append(pos)
            num += 1
    game['opponent_positions'] = opp_positions


async def handle_toggle_seat_out(session_id: str, game: dict, msg: dict):
    """Посадить врага на пустое место / убрать врага (место становится пустым).
    Наших игроков не трогает."""
    pos = msg.get('position', '').upper()
    if pos not in game.get('positions', []):
        return
    seat = game['seats'].get(pos, {'type': 'empty'})
    seat_type = seat.get('type', 'empty')

    if seat_type == 'our':
        return  # наших игроков убирать нельзя

    if seat_type == 'opponent':
        # Убрать врага → место становится пустым/задисейбленным
        was_turn = (game.get('current_turn') == pos)
        game['seats'][pos] = {'type': 'empty'}
        game.get('opp_actions', {}).pop(pos, None)
        game.get('opp_preflop_action', {}).pop(pos, None)
        game.get('acted_this_street', set()).discard(pos)
        _renumber_opponents(game)
        add_history(game, f"Враг ({pos}) убран со стула")
        if was_turn:
            nxt = next_to_act(game)
            if nxt is None:
                end_street(game)
            else:
                game['current_turn'] = nxt
        if only_one_left(game) and game['state'] != GameState.SHOWDOWN:
            w = winner_name(game)
            add_history(game, f"Победитель: {w}")
            game['state'] = GameState.SHOWDOWN
            game['current_turn'] = None
    else:
        # Пустое место → посадить нового врага (максимум 6 игроков за столом).
        occupied = sum(1 for p in game.get('positions', [])
                       if game['seats'].get(p, {}).get('type') in ('our', 'opponent'))
        if occupied >= 6:
            return
        # Если раздача уже идёт — он входит в игру со следующего раунда (pending).
        in_hand = game['state'] in (
            GameState.PREFLOP, GameState.FLOP, GameState.TURN, GameState.RIVER
        )
        seat_obj = {'type': 'opponent', 'folded': False, 'player': {'number': 0}}
        if in_hand:
            seat_obj['pending'] = True
        game['seats'][pos] = seat_obj
        _renumber_opponents(game)
        num = game['seats'][pos]['player']['number']
        if in_hand:
            add_history(game, f"В{num} ({pos}) сядет со следующего раунда")
        else:
            add_history(game, f"В{num} ({pos}) сел за стол")

    await recalc(game)
    await broadcast(session_id)


_OPP_TYPES = ('tight', 'passive', 'normal', 'aggressive', 'loose')


async def handle_set_opp_type(session_id: str, game: dict, msg: dict):
    """Оператор помечает тип оппонента — это меняет ширину его диапазона."""
    pos = msg.get('position', '').upper()
    otype = msg.get('otype', 'normal')
    if otype not in _OPP_TYPES:
        return
    seat = game['seats'].get(pos)
    if not seat or seat.get('type') != 'opponent':
        return
    seat['otype'] = otype
    add_history(game, f"В{seat.get('player', {}).get('number', '?')} ({pos}): тип {otype}")
    await recalc(game)
    await broadcast(session_id)


async def handle_grow_table(session_id: str, game: dict):
    """Расширить стол на одно стандартное место (до 6) и посадить туда врага.
    Если раздача уже идёт — враг входит со следующего раунда (pending)."""
    cur = list(game.get('positions', []))
    n = len(cur)
    if n >= 6:
        return
    new_positions = list(TABLE_POSITIONS[n + 1])
    new_seat = next((p for p in new_positions if p not in cur), None)
    if not new_seat:
        return
    game['positions'] = new_positions
    in_hand = game['state'] in (
        GameState.PREFLOP, GameState.FLOP, GameState.TURN, GameState.RIVER
    )
    seat_obj = {'type': 'opponent', 'folded': False, 'player': {'number': 0}}
    if in_hand:
        seat_obj['pending'] = True
    game['seats'][new_seat] = seat_obj
    # места, которые были в раскладке, но остались пустыми, тоже делаем врагами
    for p in new_positions:
        if game['seats'].get(p, {}).get('type') == 'empty':
            game['seats'][p] = {'type': 'opponent', 'folded': False, 'player': {'number': 0}}
    _renumber_opponents(game)
    game['table_size'] = n + 1
    if game.get('button_pos') not in ring_positions(game):
        place_initial_button(game)
    add_history(game, f"Добавлено место {new_seat} (стол на {n + 1})")
    await recalc(game)
    await broadcast(session_id)


async def handle_next_round(session_id: str, game: dict):
    reset_for_new_round(game)
    add_history(game, "Новый раунд")
    await broadcast(session_id)


async def handle_new_game(session_id: str, game: dict):
    """Полный сброс — но участники остаются в сессии."""
    members = dict(game.get('members', {}))
    responsible_id = game.get('responsible_id')
    responsible_name = game.get('responsible_name')
    test_mode = game.get('test_mode', False)

    new = make_game()
    new['members'] = members
    new['responsible_id'] = responsible_id
    new['responsible_name'] = responsible_name
    new['test_mode'] = test_mode
    new['state'] = GameState.SETUP_TABLE

    SESSIONS[session_id]['game'] = new
    add_history(new, "Новая игра")
    await broadcast(session_id)


async def handle_reconfigure(session_id: str, game: dict):
    """Сброс размера стола и рассадки, блайнды сохраняются."""
    members = dict(game.get('members', {}))
    responsible_id = game.get('responsible_id')
    responsible_name = game.get('responsible_name')
    sb = game.get('sb', 0)
    bb = game.get('bb', 0)
    test_mode = game.get('test_mode', False)

    new = make_game()
    new['members'] = members
    new['responsible_id'] = responsible_id
    new['responsible_name'] = responsible_name
    new['sb'] = sb
    new['bb'] = bb
    new['test_mode'] = test_mode
    new['state'] = GameState.SETUP_TABLE

    SESSIONS[session_id]['game'] = new
    add_history(new, "Реконфигурация")
    await broadcast(session_id)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
