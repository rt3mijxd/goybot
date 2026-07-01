"""Регресс-набор командных сценариев (план аудита, шаг 5).

Курируемые раздачи с ожидаемым типом совета — ловит деградации стратегии и
даёт наблюдаемость. Прогон детерминирован (Monte-Carlo засеян по споту).

Запуск:
  cd backend && python3 tests/test_regression_scenarios.py            # PASS/FAIL
  cd backend && python3 tests/test_regression_scenarios.py --artifacts  # + дамп
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import game_engine as ge

G = ge.GameState
ARTIFACTS = '--artifacts' in sys.argv
_passed = _failed = 0
_C = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10, '9': 9, '8': 8, '7': 7,
      '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}


def h(s):
    """'AsKh' -> [(14,'s'),(13,'h')]"""
    return [(_C[s[0]], s[1]), (_C[s[2]], s[3])]


def kind(rec):
    if not rec:
        return 'NONE'
    head = rec.strip().upper()
    for k in ('ФОЛД', 'ДОНК', 'РЕЙЗ', 'БЕТ', 'КОЛЛ', 'ЧЕК', '3БЕТ', '4БЕТ'):
        if head.startswith(k):
            return 'РЕЙЗ' if k in ('БЕТ', 'ДОНК', '3БЕТ', '4БЕТ') else k
    return 'OTHER'


def mkgame(our, opp_seats, our_seats, state=G.PREFLOP, board=None, pot=75,
           last_bet=50, street_bet_to=50, agg=None, contrib=None, btn=None):
    g = ge.make_game()
    g['positions'] = list(ge.TABLE_POSITIONS[6])
    g['table_size'] = 6
    g['seats'] = {p: {'type': 'empty'} for p in ge.ALL_POSITIONS}
    g['seat_claimed'] = {}
    for i, p in enumerate(our_seats):
        g['seats'][p] = {'type': 'our', 'folded': False,
                         'player': {'number': i + 1, 'name': p, 'cards': [], 'user_id': 'u%d' % i}}
        g['seat_claimed']['u%d' % i] = p
    for p in opp_seats:
        g['seats'][p] = {'type': 'opponent', 'folded': False, 'player': {'number': 1}}
    ge.build_seats_from_claimed(g)
    if btn:
        g['button_pos'] = btn
    for p, c in our.items():
        g['seats'][p]['player']['cards'] = c
    g['bb'] = 50; g['sb'] = 25; g['state'] = state
    g['board'] = board or []
    g['pot'] = pot; g['last_bet'] = last_bet; g['street_bet_to'] = street_bet_to
    g['street_contrib'] = contrib or {}
    if agg:
        g['preflop_aggressor'] = agg
    return g


async def rec_for(g, pos):
    g['current_turn'] = pos
    await ge.recalc(g)
    return ge.build_recommendation(g)[0]


def expect(name, rec, allowed):
    global _passed, _failed
    k = kind(rec)
    ok = k in allowed
    _passed += ok; _failed += (not ok)
    tag = 'PASS' if ok else 'FAIL'
    print(f"  {tag}  {name}: {k} (ожидали {'/'.join(allowed)})")
    if ARTIFACTS:
        print(f"        rec: {rec}")


async def run():
    # ── ПРЕФЛОП ОТКРЫТИЕ (только блайнды) ──
    g = mkgame({'UTG': h('AsAh')}, ['MP', 'CO', 'BU', 'SB', 'BB'], ['UTG'], contrib={'SB': 25, 'BB': 50})
    expect("preflop open AA -> рейз", await rec_for(g, 'UTG'), ['РЕЙЗ'])

    g = mkgame({'UTG': h('7c2d')}, ['MP', 'CO', 'BU', 'SB', 'BB'], ['UTG'], contrib={'SB': 25, 'BB': 50})
    expect("preflop open 72o -> фолд", await rec_for(g, 'UTG'), ['ФОЛД'])

    # adjacency: UTG/MP/CO рядом -> MP по диапазону UTG; K8o вне -> фолд
    g = mkgame({'MP': h('Kc8h')}, ['BU', 'SB', 'BB'], ['UTG', 'MP', 'CO'], contrib={'SB': 25, 'BB': 50})
    expect("preflop adjacency MP K8o -> фолд", await rec_for(g, 'MP'), ['ФОЛД'])

    # ── ПРЕФЛОП ПРОТИВ РЕЙЗА ──
    raise_ctx = dict(pot=350, last_bet=150, street_bet_to=150, agg='SB',
                     contrib={'SB': 150, 'BB': 50})
    g = mkgame({'UTG': h('AsAh'), 'MP': h('KsKh')}, ['SB', 'BB'], ['UTG', 'MP'], **raise_ctx)
    expect("vs raise: AA continue", await rec_for(g, 'UTG'), ['КОЛЛ', 'РЕЙЗ'])
    expect("vs raise: KK continue", await rec_for(g, 'MP'), ['КОЛЛ', 'РЕЙЗ'])

    g = mkgame({'UTG': h('AsAh'), 'MP': h('7c2d')}, ['SB', 'BB'], ['UTG', 'MP'], **raise_ctx)
    expect("vs raise: AA continue (strong+weak)", await rec_for(g, 'UTG'), ['КОЛЛ', 'РЕЙЗ'])
    expect("vs raise: 72o fold (strong+weak)", await rec_for(g, 'MP'), ['ФОЛД'])

    # три одинаковых T8 -> блокеры роняют эквити -> все фолд
    g = mkgame({'UTG': h('Ts8s'), 'MP': h('Td8d'), 'CO': h('Th8h')}, ['BU', 'SB', 'BB'],
               ['UTG', 'MP', 'CO'], pot=450, last_bet=150, street_bet_to=150, agg='BU',
               contrib={'BU': 150, 'BB': 50})
    expect("vs raise: 3x T8 -> фолд (блокеры)", await rec_for(g, 'UTG'), ['ФОЛД'])

    # ── ФЛОП ──
    flop = [(14, 'h'), (13, 'd'), (7, 'c')]   # Ah Kd 7c
    # команда-агрессор, ходим первыми -> один ставит (по позиции), другой чек
    g = mkgame({'UTG': h('AcQc'), 'MP': h('9h9d')}, ['CO', 'BU', 'SB', 'BB'], ['UTG', 'MP'],
               state=G.FLOP, board=flop, pot=300, last_bet=0, street_bet_to=0, agg='UTG')
    recs = [kind(await rec_for(g, p)) for p in ['UTG', 'MP']]
    okc = ('РЕЙЗ' in recs and 'ЧЕК' in recs)
    globals()['_passed'] += okc
    globals()['_failed'] += (not okc)
    print(f"  {'PASS' if okc else 'FAIL'}  flop team-agg координация (один бет, другой чек): {recs}")

    # команда-коллер на флопе -> чек
    g = mkgame({'UTG': h('AcQc'), 'MP': h('9h9d')}, ['CO', 'BU', 'SB', 'BB'], ['UTG', 'MP'],
               state=G.FLOP, board=flop, pot=300, last_bet=0, street_bet_to=0, agg='CO')
    expect("flop team-caller -> чек", await rec_for(g, 'UTG'), ['ЧЕК'])

    # ── ТЁРН / РИВЕР: не падает, даёт действие ──
    turn = flop + [(2, 's')]
    g = mkgame({'UTG': h('AcQc'), 'MP': h('9h9d')}, ['CO', 'BU', 'SB', 'BB'], ['UTG', 'MP'],
               state=G.TURN, board=turn, pot=600, last_bet=0, street_bet_to=0, agg='UTG')
    g['flop_bet_size'] = 0.5
    expect("turn даёт совет", await rec_for(g, 'MP'), ['РЕЙЗ', 'ЧЕК'])

    river = turn + [(11, 'c')]
    g = mkgame({'UTG': h('AcQc'), 'MP': h('9h9d')}, ['CO', 'BU', 'SB', 'BB'], ['UTG', 'MP'],
               state=G.RIVER, board=river, pot=900, last_bet=0, street_bet_to=0, agg='UTG')
    g['flop_bet_size'] = 0.5; g['turn_bet_size'] = 0.5; g['agg_history'] = 'bb'
    expect("river даёт совет", await rec_for(g, 'MP'), ['РЕЙЗ', 'ЧЕК'])

    # ── DEAD CARDS: карты ушедших напарников мертвы (чистый контроль:
    # тот же расклад/оппоненты, отличается только dead_cards) ──
    our = [h('Th8h')]
    opp = [('BU', '', '', [], False, ''), ('SB', '', '', [], False, ''), ('BB', '', '', [], False, '')]
    eq_no = ge.simulate(our, opp, [], n_sim=6000, seed=42)['team']
    eq_dead = ge.simulate(our, opp, [], n_sim=6000, seed=42,
                          dead_cards=h('Ts8s') + h('Td8d'))['team']
    okd = eq_dead < eq_no
    globals()['_passed'] += okd
    globals()['_failed'] += (not okd)
    print(f"  {'PASS' if okd else 'FAIL'}  dead cards: T8 eq {eq_dead:.1f} < {eq_no:.1f} "
          f"(две мёртвые T8 убивают ауты)")

    # ── СТЕКИ / SPR: без стеков не блокирует; короткий стек -> кап/олл-ин ──
    import main
    g = mkgame({'UTG': h('AsAh')}, ['MP', 'CO', 'BU', 'SB', 'BB'], ['UTG'], contrib={'SB': 25, 'BB': 50})
    g['responsible_id'] = 'u0'; g['current_turn'] = 'UTG'
    await ge.recalc(g)
    p = main.serialize_game(g, 'u0')
    ra = p['rec_action'] or {}
    expect_ok = ra.get('kind') == 'raise' and not ra.get('allin')
    globals()['_passed'] += expect_ok; globals()['_failed'] += (not expect_ok)
    print(f"  {'PASS' if expect_ok else 'FAIL'}  без стеков: обычный рейз (не олл-ин), SPR={p['spr']}")

    g['stacks'] = {'UTG': 120}
    await ge.recalc(g)
    p = main.serialize_game(g, 'u0')
    ra = p['rec_action'] or {}
    oks = ra.get('allin') and ra.get('amount') == 120
    globals()['_passed'] += oks; globals()['_failed'] += (not oks)
    print(f"  {'PASS' if oks else 'FAIL'}  короткий стек 120: олл-ин {ra.get('amount')} (SPR={p['spr']})")


def main():
    asyncio.run(run())
    print(f"\n{_passed} passed, {_failed} failed")
    sys.exit(1 if _failed else 0)


if __name__ == '__main__':
    main()
