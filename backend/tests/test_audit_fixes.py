"""Регресс-тесты на исправления из аудита (P0 + sizing).
Запуск: cd backend && python3 tests/test_audit_fixes.py
(без зависимости от pytest, чтобы гонять где угодно)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
import game_engine as ge

G = ge.GameState
_passed = 0
_failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


class FakeWS:
    def __init__(self):
        self.errors = []

    async def send_json(self, d):
        if d.get('type') == 'error':
            self.errors.append(d.get('message'))


def newgame():
    g = ge.make_game()
    g['positions'] = list(ge.TABLE_POSITIONS[6])
    g['table_size'] = 6
    g['seats'] = {p: {'type': 'empty'} for p in ge.ALL_POSITIONS}
    g['seat_claimed'] = {}
    for i, p in enumerate(['UTG', 'MP', 'CO']):
        g['seats'][p] = {'type': 'our', 'folded': False,
                         'player': {'number': i + 1, 'name': p, 'cards': [], 'user_id': 'u%d' % i}}
        g['seat_claimed']['u%d' % i] = p
    ge.build_seats_from_claimed(g)
    g['bb'] = 50
    g['sb'] = 25
    return g


async def main_tests():
    sid = 's-test'
    main.SESSIONS[sid] = {'game': None}
    main.CONNECTIONS[sid] = {}

    # P0: дубликаты карт
    g = newgame(); main.SESSIONS[sid]['game'] = g
    g['seats']['MP']['player']['cards'] = [(14, 's'), (13, 's')]
    ws = FakeWS()
    await main.handle_set_test_cards(sid, g, {'position': 'UTG', 'cards': ['As', 'Kd']}, ws)
    check("дубликат карты между игроками отклонён", bool(ws.errors))
    ws = FakeWS()
    await main.handle_set_test_cards(sid, g, {'position': 'UTG', 'cards': ['Qh', 'Qh']}, ws)
    check("две одинаковые карты в руке отклонены", bool(ws.errors))
    ws = FakeWS()
    await main.handle_set_test_cards(sid, g, {'position': 'UTG', 'cards': ['Qh', 'Jh']}, ws)
    check("корректная рука принята", g['seats']['UTG']['player']['cards'] == [(12, 'h'), (11, 'h')] and not ws.errors)

    # P0: число карт борда по улице
    g = newgame(); main.SESSIONS[sid]['game'] = g; g['state'] = G.PREFLOP; g['current_turn'] = None
    await main.handle_board(sid, g, {'cards': ['As', 'Kd', 'Qc', 'Jh', 'Ts']})
    check("флоп = ровно 3 карты даже если прислали 5", len(g['board']) == 3 and g['state'] == G.FLOP)

    # P0: очередь хода
    g = newgame(); main.SESSIONS[sid]['game'] = g; g['state'] = G.PREFLOP
    g['current_turn'] = 'UTG'; g['pot'] = 75
    ws = FakeWS()
    await main.handle_player_action(sid, 'u1', g, {'position': 'MP', 'act': 'check'}, ws)
    check("действие не в свою очередь отклонено", bool(ws.errors))

    # P1: размер ставки от банка ДО ставки
    g = newgame(); main.SESSIONS[sid]['game'] = g; g['state'] = G.FLOP
    g['pot'] = 100; g['current_turn'] = 'UTG'; g['street_contrib'] = {}
    await main.handle_player_action(sid, 'u0', g, {'position': 'UTG', 'act': 'bet', 'amount': 50}, FakeWS())
    check("бет 50 в банк 100 = 0.5 (а не 0.333)", abs(g['flop_bet_size'] - 0.5) < 0.01)

    # Команда: напарники — союзники (эквити vs оппоненты), не конкуренты
    our = [[(14, 's'), (14, 'h')], [(13, 's'), (13, 'h')]]
    opp = [('CO', '', '', [], False, ''), ('BU', '', '', [], False, '')]
    res = ge.simulate(our, opp, [], n_sim=3000)
    check("AA и KK рядом — у обоих высокое эквити (союзники)",
          res['individual'][0] > 45 and res['individual'][1] > 45)


def run():
    asyncio.run(main_tests())
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == '__main__':
    run()
