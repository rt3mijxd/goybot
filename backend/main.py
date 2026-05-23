"""
FastAPI WebSocket server for the poker assistant.
"""

import asyncio
import json
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
    TABLE_POSITIONS, ALL_POSITIONS, STAGE_NAMES,
    SUIT_DISPLAY, RANK_DISPLAY,
)

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

    seats_out = {}
    for pos in ALL_POSITIONS:
        raw = g['seats'].get(pos, {'type': 'empty'})
        s = {'type': raw.get('type', 'empty'), 'folded': raw.get('folded', False)}
        if raw.get('type') == 'our':
            p = raw.get('player', {})
            cards_visible = (
                is_responsible
                or p.get('user_id') == user_id
            )
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
        seats_out[pos] = s

    board_cards = [card_to_short(c) for c in g.get('board', [])]

    rec_text, rec_pos = None, None
    try:
        rec_text, rec_pos = build_recommendation(g)
    except Exception:
        pass

    opp_actions_out = {}
    for pos, act in g.get('opp_actions', {}).items():
        opp_actions_out[pos] = act or ''

    return {
        'state': g['state'].name,
        'table_size': g.get('table_size', 0),
        'positions': g.get('positions', []),
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
        'recommendation_pos': rec_pos,
        'opp_actions': opp_actions_out,
        'is_responsible': is_responsible,
        'responsible_name': g.get('responsible_name', ''),
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
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
    sess = SESSIONS.get(session_id)
    if not sess:
        await websocket.close(code=4004, reason="session not found")
        return

    await websocket.accept()
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
    game = SESSIONS[session_id]['game']
    is_responsible = (user_id == game.get('responsible_id'))

    if action == 'join':
        await handle_join(session_id, user_id, msg, ws)
    elif action == 'set_table':
        if not is_responsible:
            return await send_error(ws, "только ведущий может настраивать стол")
        await handle_set_table(session_id, game, msg)
    elif action == 'claim_seat':
        await handle_claim_seat(session_id, user_id, game, msg)
    elif action == 'ready_for_blinds':
        if not is_responsible:
            return await send_error(ws, "только ведущий")
        game['state'] = GameState.SETUP_BLINDS
        await broadcast(session_id)
    elif action == 'set_blinds':
        if not is_responsible:
            return await send_error(ws, "только ведущий может ставить блайнды")
        await handle_set_blinds(session_id, game, msg)
    elif action == 'deal_cards':
        if not is_responsible:
            return await send_error(ws, "только ведущий раздаёт карты")
        await handle_deal_cards(session_id, game, msg)
    elif action == 'player_action':
        await handle_player_action(session_id, user_id, game, msg, ws)
    elif action == 'opp_action':
        if not is_responsible:
            return await send_error(ws, "только ведущий управляет оппонентами")
        await handle_opp_action(session_id, game, msg)
    elif action == 'board':
        if not is_responsible:
            return await send_error(ws, "только ведущий выкладывает борд")
        await handle_board(session_id, game, msg)
    elif action == 'next_round':
        if not is_responsible:
            return await send_error(ws, "только ведущий начинает раунд")
        await handle_next_round(session_id, game)
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

    if game['state'] == GameState.SETUP_RESPONSIBLE and not game.get('responsible_id'):
        game['responsible_id'] = user_id
        game['responsible_name'] = name
        game['state'] = GameState.SETUP_TABLE
        add_history(game, f"{name} — ведущий")
    else:
        add_history(game, f"{name} подключился")

    await broadcast(session_id)


async def handle_set_table(session_id: str, game: dict, msg: dict):
    size = msg.get('size', 6)
    size = max(2, min(6, int(size)))
    game['table_size'] = size
    game['positions'] = list(TABLE_POSITIONS.get(size, TABLE_POSITIONS[6]))
    game['seats'] = {pos: {'type': 'empty'} for pos in ALL_POSITIONS}
    game['state'] = GameState.SEAT_PICKING
    add_history(game, f"Стол: {size} мест")
    await broadcast(session_id)


async def handle_claim_seat(session_id: str, user_id: str, game: dict, msg: dict):
    pos = msg.get('position', '').upper()
    if pos not in game.get('positions', []):
        return

    claimed = game.setdefault('seat_claimed', {})
    old_pos = claimed.get(user_id)
    if old_pos == pos:
        claimed.pop(user_id, None)
    else:
        for uid, p in list(claimed.items()):
            if p == pos:
                claimed.pop(uid, None)
        claimed[user_id] = pos

    name = msg.get('name', '')
    if name:
        game.setdefault('known_players', {})[pos] = name

    build_seats_from_claimed(game)
    add_history(game, f"Место {pos} → {name or user_id[:6]}")
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
    game['state'] = GameState.DEALING

    build_seats_from_claimed(game)
    add_history(game, f"Блайнды: {sb}/{bb}")
    await broadcast(session_id)


async def handle_deal_cards(session_id: str, game: dict, msg: dict):
    cards_map: dict = msg.get('cards', {})
    for pos, card_strs in cards_map.items():
        seat = game['seats'].get(pos)
        if not seat or seat.get('type') != 'our':
            continue
        parsed = []
        for cs in card_strs:
            c = parse_card(cs)
            if c:
                parsed.append(c)
        if parsed:
            seat['player']['cards'] = parsed

    game['state'] = GameState.PREFLOP
    start_preflop(game)

    await recalc(game)
    add_history(game, "Карты розданы")
    await broadcast(session_id)


async def handle_player_action(session_id: str, user_id: str, game: dict, msg: dict, ws: WebSocket):
    act = msg.get('act', '').lower()
    pos = msg.get('position', '')

    if not pos:
        for p in game.get('player_positions', []):
            s = game['seats'].get(p, {})
            if s.get('player', {}).get('user_id') == user_id:
                pos = p
                break
    if not pos:
        return await send_error(ws, "позиция не найдена")

    seat = game['seats'].get(pos)
    if not seat or seat.get('type') != 'our':
        return await send_error(ws, "это не ваше место")

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
                game['flop_bet_size'] = amount / max(game.get('pot', 1), 1)
            elif game['state'] == GameState.TURN:
                game['turn_bet_size'] = amount / max(game.get('pot', 1), 1)
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
                game['flop_bet_size'] = amount / max(game.get('pot', 1), 1)
            elif game['state'] == GameState.TURN:
                game['turn_bet_size'] = amount / max(game.get('pot', 1), 1)
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
            game['flop_bet_size'] = amount / max(game.get('pot', 1), 1) if amount else 0.5
        elif game['state'] == GameState.TURN:
            game['turn_bet_size'] = amount / max(game.get('pot', 1), 1) if amount else 0.5
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
    card_strs: list = msg.get('cards', [])
    parsed = []
    for cs in card_strs:
        c = parse_card(cs)
        if c:
            parsed.append(c)
    if not parsed:
        return

    if game['state'] in (GameState.PREFLOP, GameState.DEALING):
        if len(parsed) >= 3:
            game['board'] = parsed[:5]
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


async def handle_next_round(session_id: str, game: dict):
    reset_for_new_round(game)
    add_history(game, "Новый раунд")
    await broadcast(session_id)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
