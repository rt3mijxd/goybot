"""
Poker game engine — extracted from poker_bot.py (Telegram-free).
All GTO ranges, simulation, recommendation logic preserved.
"""

import asyncio
import random
from concurrent.futures import ThreadPoolExecutor
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

_SIM_SEMAPHORE: asyncio.Semaphore | None = None
_SIM_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix='sim')

def _get_sim_sem() -> asyncio.Semaphore:
    global _SIM_SEMAPHORE
    if _SIM_SEMAPHORE is None:
        _SIM_SEMAPHORE = asyncio.Semaphore(1)
    return _SIM_SEMAPHORE

ALL_POSITIONS = ['UTG', 'MP', 'CO', 'BU', 'SB', 'BB']

TABLE_POSITIONS: Dict[int, List[str]] = {
    2: ['BU', 'BB'],
    3: ['BU', 'SB', 'BB'],
    4: ['UTG', 'BU', 'SB', 'BB'],
    5: ['UTG', 'CO', 'BU', 'SB', 'BB'],
    6: ['UTG', 'MP', 'CO', 'BU', 'SB', 'BB'],
}

PREFLOP_ORDERS: Dict[int, List[str]] = {
    2: ['BU', 'BB'],
    3: ['BU', 'SB', 'BB'],
    4: ['UTG', 'BU', 'SB', 'BB'],
    5: ['UTG', 'CO', 'BU', 'SB', 'BB'],
    6: ['UTG', 'MP', 'CO', 'BU', 'SB', 'BB'],
}

POSTFLOP_ORDERS: Dict[int, List[str]] = {
    2: ['BB', 'BU'],
    3: ['SB', 'BB', 'BU'],
    4: ['SB', 'BB', 'UTG', 'BU'],
    5: ['SB', 'BB', 'UTG', 'CO', 'BU'],
    6: ['SB', 'BB', 'UTG', 'MP', 'CO', 'BU'],
}

RANK_VALUES: Dict[str, int] = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    '8': 8, '9': 9, 'T': 10, '10': 10,
    'J': 11, 'Q': 12, 'K': 13, 'A': 14,
    'В': 11, 'Д': 12, 'К': 13, 'Т': 14, 'А': 14,
}
RANK_DISPLAY = {14:'A', 13:'K', 12:'Q', 11:'J', 10:'T',
                9:'9', 8:'8', 7:'7', 6:'6', 5:'5', 4:'4', 3:'3', 2:'2'}

SUIT_MAP: Dict[str, str] = {
    'H':'h','D':'d','C':'c','S':'s',
    'Ч':'h','Б':'d','К':'c','П':'s',
    '♥':'h','♦':'d','♣':'c','♠':'s',
}
SUIT_DISPLAY = {'h':'♥','d':'♦','c':'♣','s':'♠'}

POSITION_EV_MULT = {
    'UTG':0.85,'MP':1.00,'CO':1.15,'BU':1.30,'SB':0.90,'BB':1.00,
}

Card = Tuple[int, str]
FULL_DECK: List[Card] = [(r, s) for r in range(2, 15) for s in 'hdcs']


class GameState(Enum):
    SETUP_RESPONSIBLE = auto()
    SETUP_TABLE       = auto()
    SEAT_PICKING      = auto()
    SETUP_BLINDS      = auto()
    DEALING           = auto()
    PREFLOP           = auto()
    FLOP              = auto()
    TURN              = auto()
    RIVER             = auto()
    SHOWDOWN          = auto()


STAGE_NAMES = {
    GameState.PREFLOP:  "ПРЕФЛОП",
    GameState.FLOP:     "ФЛОП",
    GameState.TURN:     "ТЁРН",
    GameState.RIVER:    "РИВЕР",
    GameState.SHOWDOWN: "ШОУДАУН",
    GameState.DEALING:  "РАЗДАЧА",
}


# ════════════════════════════════════════════════
#  CARDS
# ════════════════════════════════════════════════

def parse_card(token: str) -> Optional[Card]:
    t = token.strip().upper()
    if len(t) < 2:
        return None
    suit = SUIT_MAP.get(t[-1])
    if suit is None:
        return None
    rank = RANK_VALUES.get(t[:-1])
    if rank is None:
        return None
    return (rank, suit)


def card_str(c: Card) -> str:
    return RANK_DISPLAY.get(c[0], '?') + SUIT_DISPLAY.get(c[1], '?')


def cards_str(cards: List[Card]) -> str:
    return ' '.join(card_str(c) for c in cards)


def card_to_short(c: Card) -> str:
    return RANK_DISPLAY.get(c[0], '?') + c[1]


# ════════════════════════════════════════════════
#  HAND EVALUATOR
# ════════════════════════════════════════════════

def hand_rank(seven: List[Card]) -> Tuple:
    ranks = [c[0] for c in seven]
    suits = [c[1] for c in seven]

    rcnt: Dict[int,int] = {}
    for r in ranks:
        rcnt[r] = rcnt.get(r, 0) + 1

    scnt: Dict[str,int] = {}
    for s in suits:
        scnt[s] = scnt.get(s, 0) + 1

    fsut  = next((s for s,n in scnt.items() if n >= 5), None)
    fcards = sorted([c[0] for c in seven if c[1]==fsut], reverse=True) if fsut else []

    def best_str(rs):
        us = sorted(set(rs), reverse=True)
        if 14 in us:
            us = us + [1]
        for i in range(len(us)-4):
            if us[i]-us[i+4] == 4 and len(set(us[i:i+5])) == 5:
                return us[i]
        return 0

    sf = best_str(fcards) if fsut else 0
    st = best_str(ranks)
    by_c = sorted(rcnt.items(), key=lambda x: (x[1], x[0]), reverse=True)
    grp  = [c for _,c in by_c]
    top  = [r for r,_ in by_c]

    if sf:                                         return (8, sf)
    if grp[0] == 4:
        k = max(r for r in ranks if r != top[0])
        return (7, top[0], k)
    if grp[0] == 3 and len(grp) > 1 and grp[1] >= 2:
        return (6, top[0], top[1])
    if fsut:
        return (5,) + tuple(fcards[:5])
    if st:
        return (4, st)
    if grp[0] == 3:
        ks = sorted([r for r in ranks if r != top[0]], reverse=True)[:2]
        return (3, top[0]) + tuple(ks)
    if grp[0] == 2 and len(grp) > 1 and grp[1] == 2:
        p1, p2 = sorted([top[0], top[1]], reverse=True)
        k = max(r for r in ranks if r not in (p1, p2))
        return (2, p1, p2, k)
    if grp[0] == 2:
        ks = sorted([r for r in ranks if r != top[0]], reverse=True)[:3]
        return (1, top[0]) + tuple(ks)
    return (0,) + tuple(sorted(ranks, reverse=True)[:5])


# ════════════════════════════════════════════════
#  RANGES
# ════════════════════════════════════════════════

A, K, Q, J, T = 14, 13, 12, 11, 10

def _pge(lo):    return [(r,r,'p') for r in range(lo, 15)]
def _pre(lo,hi): return [(r,r,'p') for r in range(lo, hi+1)]
def _axs(lo):    return [(14,r,'s') for r in range(lo, 14)]
def _axo(lo):    return [(14,r,'o') for r in range(lo, 14)]
def _kxs(lo):    return [(13,r,'s') for r in range(lo, 13)]
def _kxo(lo):    return [(13,r,'o') for r in range(lo, 13)]
def _qxs(lo):    return [(12,r,'s') for r in range(lo, 12)]
def _qxo(lo):    return [(12,r,'o') for r in range(lo, 12)]
def _jxs(lo):    return [(11,r,'s') for r in range(lo, 11)]
def _jxo(lo):    return [(11,r,'o') for r in range(lo, 11)]
def _txs(lo):    return [(10,r,'s') for r in range(lo, 10)]
def _txo(lo):    return [(10,r,'o') for r in range(lo, 10)]
def _9xs(lo):    return [(9, r,'s') for r in range(lo, 9)]
def _8xs(lo):    return [(8, r,'s') for r in range(lo, 8)]
def _7xs(lo):    return [(7, r,'s') for r in range(lo, 7)]
def _6xs(lo):    return [(6, r,'s') for r in range(lo, 6)]
def _5xs(lo):    return [(5, r,'s') for r in range(lo, 5)]
def _4xs(lo):    return [(4, r,'s') for r in range(lo, 4)]
def _ss(r1, r2): return [(r1, r2, 's')]
def _oo(r1, r2): return [(r1, r2, 'o')]
def _hh(r1, r2): return [(r1, r2, 's'), (r1, r2, 'o')]
def cat(*parts): return sum((list(p) for p in parts), [])

HAND_RANGES: Dict[str, Dict[str, tuple]] = {
'UTG': {
    'open': ("99+ A2s+ ATo+ K9s+ KTo+ QTs+ QJo JTs",
             cat(_pre(9,14), _axs(2), _axo(10), _ss(K,9),_ss(K,T),_ss(K,J),_ss(K,Q),
                 _oo(K,Q),_oo(K,J),_oo(K,T), _ss(Q,J),_ss(Q,T), _oo(Q,J), _ss(J,T))),
},
'MP': {
    'open': ("88+ A2s+ ATo+ A9o A8o A5o K7s+ KTo+ Q9s+ QJo QTo J9s+ T9s",
             cat(_pre(8,14), _axs(2),
                 _oo(A,K),_oo(A,Q),_oo(A,J),_oo(A,T),_oo(A,9),_oo(A,8),_oo(A,5),
                 _kxs(7), _oo(K,Q),_oo(K,J),_oo(K,T),
                 _qxs(9), _oo(Q,J),_oo(Q,T),
                 _ss(J,T),_ss(J,9), _ss(T,9))),
},
'CO': {
    'open': ("55+ A2s+ A5o+ K5s+ K9o+ Q8s+ QJo QTo J9s+ JTo T8s+",
             cat(_pre(5,14), _axs(2), _axo(5),
                 _kxs(5), _oo(K,Q),_oo(K,J),_oo(K,T),_oo(K,9),
                 _qxs(8), _oo(Q,J),_oo(Q,T),
                 _ss(J,T),_ss(J,9), _oo(J,T),
                 _txs(8))),
},
'BU': {
    'open': ("44+ A2s+ A2o+ K2s+ K8o+ Q4s+ Q9o+ J7s+ J9o+ T7s+ T9o 97s+ 87s",
             cat(_pre(4,14), _axs(2),
                 _oo(A,K),_oo(A,Q),_oo(A,J),_oo(A,T),_oo(A,9),_oo(A,8),_oo(A,7),_oo(A,5),_oo(A,4),_oo(A,3),_oo(A,2),
                 _kxs(2), _oo(K,Q),_oo(K,J),_oo(K,T),_oo(K,9),_oo(K,8),
                 _qxs(4), _oo(Q,J),_oo(Q,T),_oo(Q,9),
                 _jxs(7), _oo(J,T),_oo(J,9),
                 _txs(7), _oo(T,9),
                 _ss(9,8),_ss(9,7), _ss(8,7))),
},
'SB': {
    'open': ("22+ A2s+ A2o+ K2s+ K7o+ Q2s+ Q8o+ J3s+ J8o+ T5s+ T8o+ 96s+ 85s+ 75s+ 64s+ 54s",
             cat(_pre(2,14), _axs(2),
                 _oo(A,K),_oo(A,Q),_oo(A,J),_oo(A,T),_oo(A,9),_oo(A,8),_oo(A,7),_oo(A,5),_oo(A,4),_oo(A,3),_oo(A,2),
                 _kxs(2), _oo(K,Q),_oo(K,J),_oo(K,T),_oo(K,9),_oo(K,8),_oo(K,7),
                 _qxs(2), _oo(Q,J),_oo(Q,T),_oo(Q,9),_oo(Q,8),
                 _jxs(3), _oo(J,T),_oo(J,9),_oo(J,8),
                 _txs(5), _oo(T,9),_oo(T,8),
                 _9xs(6), _8xs(5), _ss(7,6),_ss(7,5), _ss(6,5),_ss(6,4), _ss(5,4))),
},
'BB': {
    'open': ("22+ A2s+ A2o+ K2s+ K8o+ Q2s+ Q9o+ J2s+ J9o+ T2s+ T8o+ 92s+ 82s+ 72s+ 62s+ 52s+ 42s+",
             cat(_pre(2,14), _axs(2), _axo(2), _kxs(2), _kxo(8),
                 _qxs(2), _qxo(9), _jxs(2), _jxo(9), _txs(2), _txo(8),
                 _9xs(2), _8xs(2), _7xs(2), _6xs(2), _5xs(2), _4xs(2))),
},
}

# ════════════════════════════════════════════════
#  COLLUSION OPEN RANGES (команда = один суперигрок)
#  Диапазон открытия выбирается по ЧИСЛУ ПРОТИВНИКОВ за столом,
#  а не по формальной позиции — союзники между нами и оппонентами
#  не считаются противниками.
#    3 противника → «UTG»-список (тайтовый), для наших UTG/MP/CO
#    2 противника → «BU»-список (шире),     для наших UTG/MP/CO/BU
#  Условие: применяется, только если есть ещё противник, ходящий ПОСЛЕ нас.
# ════════════════════════════════════════════════

# Open raise при 3 противниках (тайтовый, «UTG»)
COLLUSION_OPEN_3OPP = cat(
    _pre(5, 14),                                  # 55+
    _axs(2),                                      # A2s+
    _axo(7), _oo(A, 5),                           # AKo..A7o, A5o
    _kxs(5),                                      # K5s+
    _kxo(9),                                      # K9o+
    _qxs(8),                                      # Q8s+
    _oo(Q, J), _oo(Q, T),                         # QJo, QTo
    _jxs(9),                                      # J9s+
    _oo(J, T),                                    # JTo
    _txs(8),                                      # T8s+
)

# Open raise при 2 противниках (шире, «BU»)
COLLUSION_OPEN_2OPP = cat(
    _pre(2, 14),                                  # 22+
    _axs(2),                                      # A2s+
    _axo(7), _oo(A, 5), _oo(A, 4), _oo(A, 3), _oo(A, 2),  # AKo..A7o, A5o-A2o (без A6o)
    _kxs(2),                                      # K2s+
    _kxo(7),                                      # K7o+
    _qxs(2),                                      # Q2s+
    _qxo(8),                                      # Q8o+
    _jxs(3),                                      # J3s+
    _oo(J, T), _oo(J, 9), _oo(J, 8),              # JTo, J9o, J8o
    _txs(5),                                      # T5s+
    _oo(T, 9), _oo(T, 8),                         # T9o, T8o
    _9xs(6),                                      # 96s+
    _8xs(5),                                      # 85s+
    _7xs(5),                                      # 75s+
    _6xs(4),                                      # 64s+
    _5xs(4),                                      # 54s
)

THREEBET_RANGES: Dict[str, Dict[str, Dict[str, list]]] = {
'UTG': {
    'MP': {'3bet': cat(_pre(10,14), _ss(A,K),_ss(A,Q),_ss(A,J),_ss(A,T),_ss(A,5),
                       _oo(A,K),_oo(A,Q), _ss(K,Q),_ss(K,J),_ss(K,T), _oo(K,Q)),
            'call': []},
    'CO': {'3bet': cat(_pre(10,14), _ss(A,K),_ss(A,Q),_ss(A,J),_ss(A,T),_ss(A,5),
                       _oo(A,K),_oo(A,Q), _ss(K,Q),_ss(K,J),_ss(K,T), _oo(K,Q)),
            'call': []},
    'BU': {'3bet': cat(_pre(10,14), _ss(A,K),_ss(A,Q),_ss(A,J),_ss(A,T),_ss(A,5),
                       _oo(A,K),_oo(A,Q), _ss(K,Q),_ss(K,J),_ss(K,T), _oo(K,Q)),
            'call': []},
    'SB': {'3bet': cat(_pre(10,14), _ss(A,K),_ss(A,Q),_ss(A,J),_ss(A,T),_ss(A,5),
                       _oo(A,K),_oo(A,Q), _ss(K,Q),_ss(K,J),_ss(K,T), _oo(K,Q)),
            'call': []},
    'BB': {'3bet': cat(_pre(11,14), _ss(A,K),_ss(A,7),_ss(A,6),_ss(A,3),_ss(A,2),
                       _oo(A,K),_oo(A,T), _ss(K,7),_ss(K,6),_ss(K,5), _oo(K,Q), _ss(Q,8)),
            'call': cat(_pre(2,10), _ss(A,Q),_ss(A,J),_ss(A,T),_ss(A,9),_ss(A,8),_ss(A,5),_ss(A,4),
                        _oo(A,Q),_oo(A,J),
                        _ss(K,Q),_ss(K,J),_ss(K,T),_ss(K,9),_ss(K,8), _oo(K,J),
                        _ss(Q,J),_ss(Q,T),_ss(Q,9),
                        _ss(J,T),_ss(J,9), _ss(T,9),_ss(T,8),
                        _ss(9,8),_ss(9,7), _ss(8,7),_ss(8,6), _ss(7,6),_ss(7,5),
                        _ss(6,5),_ss(6,4), _ss(5,4),_ss(5,3), _ss(4,3))},
},
'MP': {
    'CO': {'3bet': cat(_pre(9,14), _ss(A,K),_ss(A,Q),_ss(A,J),_ss(A,T),_ss(A,9),_ss(A,5),
                       _oo(A,K),_oo(A,Q),_oo(A,J), _ss(K,Q),_ss(K,J),_ss(K,T), _oo(K,Q), _ss(Q,J)),
            'call': []},
    'BU': {'3bet': cat(_pre(9,14), _ss(A,K),_ss(A,Q),_ss(A,J),_ss(A,T),_ss(A,9),_ss(A,5),
                       _oo(A,K),_oo(A,Q),_oo(A,J), _ss(K,Q),_ss(K,J),_ss(K,T), _oo(K,Q), _ss(Q,J)),
            'call': []},
    'SB': {'3bet': cat(_pre(9,14), _ss(A,K),_ss(A,Q),_ss(A,J),_ss(A,T),_ss(A,9),_ss(A,5),
                       _oo(A,K),_oo(A,Q),_oo(A,J), _ss(K,Q),_ss(K,J),_ss(K,T), _oo(K,Q), _ss(Q,J)),
            'call': []},
    'BB': {'3bet': cat(_pre(10,14), _ss(A,K),_ss(A,Q),_ss(A,6),_ss(A,2),
                       _oo(A,K), _ss(K,5),_ss(K,4), _ss(Q,8), _oo(Q,J)),
            'call': cat(_pre(2,9), _ss(A,J),_ss(A,T),_ss(A,9),_ss(A,8),_ss(A,7),_ss(A,5),_ss(A,4),_ss(A,3),
                        _oo(A,Q),_oo(A,J),
                        _ss(K,Q),_ss(K,J),_ss(K,T),_ss(K,9),_ss(K,8),_ss(K,7),_ss(K,6), _oo(K,Q),_oo(K,J),
                        _ss(Q,J),_ss(Q,T),_ss(Q,9),
                        _ss(J,T),_ss(J,9),_ss(J,8), _ss(T,9),_ss(T,8),
                        _ss(9,8),_ss(9,7), _ss(8,7),_ss(8,6), _ss(7,6),_ss(7,5),
                        _ss(6,5),_ss(6,4), _ss(5,4),_ss(5,3), _ss(4,3))},
},
'CO': {
    'BU': {'3bet': cat(_pre(8,14), _axs(5), _oo(A,K),_oo(A,Q),_oo(A,J),_oo(A,T),
                       _ss(K,Q),_ss(K,J),_ss(K,T),_ss(K,9), _oo(K,Q),
                       _ss(Q,J),_ss(Q,T),_ss(Q,9)),
            'call': []},
    'SB': {'3bet': cat(_pre(8,14), _ss(A,K),_ss(A,Q),_ss(A,J),_ss(A,T),_ss(A,9),_ss(A,8),_ss(A,5),
                       _oo(A,K),_oo(A,Q),_oo(A,J),_oo(A,T),
                       _ss(K,Q),_ss(K,J),_ss(K,T),_ss(K,9), _oo(K,Q),
                       _ss(Q,J),_ss(Q,T),_ss(Q,9), _ss(J,T)),
            'call': []},
    'BB': {'3bet': cat(_pre(9,14), _ss(A,K),_ss(A,Q),_ss(A,6),_ss(A,2),
                       _oo(A,K),_oo(A,Q),_oo(A,9),_oo(A,5),
                       _ss(K,J),_ss(K,6),_ss(K,5),_ss(K,4), _oo(K,T),
                       _ss(Q,7),_ss(Q,6), _oo(Q,J),_oo(Q,T)),
            'call': cat(_pre(2,8), _ss(A,J),_ss(A,T),_ss(A,9),_ss(A,8),_ss(A,7),_ss(A,5),_ss(A,4),_ss(A,3),
                        _oo(A,J),_oo(A,T),
                        _ss(K,Q),_ss(K,T),_ss(K,9),_ss(K,8),_ss(K,7),_ss(K,3), _oo(K,Q),_oo(K,J),
                        _ss(Q,J),_ss(Q,T),_ss(Q,9),_ss(Q,8),
                        _ss(J,T),_ss(J,9),_ss(J,8), _ss(T,9),_ss(T,8),_ss(T,7),
                        _ss(9,8),_ss(9,7),_ss(9,6), _ss(8,7),_ss(8,6),
                        _ss(7,6),_ss(7,5), _ss(6,5),_ss(6,4), _ss(5,4),_ss(5,3), _ss(4,3))},
},
'BU': {
    'SB': {'3bet': cat(_pre(7,14), _ss(A,K),_ss(A,Q),_ss(A,J),_ss(A,T),_ss(A,9),_ss(A,8),_ss(A,5),_ss(A,4),
                       _oo(A,K),_oo(A,Q),_oo(A,J),_oo(A,T),
                       _ss(K,Q),_ss(K,J),_ss(K,T),_ss(K,9), _oo(K,Q),_oo(K,J),
                       _ss(Q,J),_ss(Q,T),_ss(Q,9), _oo(Q,J), _ss(J,T)),
            'call': []},
    'BB': {'3bet': cat(_pre(7,14), _ss(A,K),_ss(A,Q),_ss(A,J),
                       _oo(A,K),_oo(A,Q),_oo(A,J),_oo(A,7),_oo(A,5),_oo(A,4),
                       _ss(K,Q),_ss(K,T),_ss(K,3), _oo(K,9),
                       _ss(Q,T),_ss(Q,4),_ss(Q,3), _ss(J,T),_ss(J,6),_ss(J,5)),
            'call': cat(_pre(2,6), _ss(A,T),_ss(A,9),_ss(A,8),_ss(A,7),_ss(A,5),_ss(A,4),_ss(A,3),
                        _oo(A,T),_oo(A,9),
                        _ss(K,J),_ss(K,9),_ss(K,8),_ss(K,7),_ss(K,6),_ss(K,5),_ss(K,4),_ss(K,2),
                        _oo(K,Q),_oo(K,J),_oo(K,T),
                        _ss(Q,J),_ss(Q,T),_ss(Q,9),_ss(Q,8),_ss(Q,7),_ss(Q,6),_ss(Q,5),
                        _oo(Q,J),_oo(Q,T),
                        _ss(J,9),_ss(J,8),_ss(J,7), _oo(J,T),
                        _ss(T,9),_ss(T,8),_ss(T,7), _ss(9,8),_ss(9,7),_ss(9,6),
                        _ss(8,7),_ss(8,6),_ss(8,5), _ss(7,6),_ss(7,5),
                        _ss(6,5),_ss(6,4), _ss(5,4),_ss(5,3), _ss(4,3))},
},
'SB': {
    'BB': {'3bet': cat(_pre(6,14), _ss(A,K),_ss(A,Q),_ss(A,J),_ss(A,T),
                       _oo(A,K),_oo(A,Q),_oo(A,J),_oo(A,6),_oo(A,3),_oo(A,2),
                       _ss(K,Q), _oo(K,8),_oo(K,7),
                       _oo(Q,9),_oo(Q,8), _ss(J,3), _oo(J,9),
                       _ss(T,5),_ss(T,4)),
            'call': cat(_pre(2,5), _ss(A,9),_ss(A,8),_ss(A,7),_ss(A,5),_ss(A,4),_ss(A,3),_ss(A,2),
                        _oo(A,T),_oo(A,9),_oo(A,8),_oo(A,7),_oo(A,5),_oo(A,4),
                        _ss(K,J),_ss(K,T),_ss(K,9),_ss(K,8),_ss(K,7),_ss(K,6),_ss(K,5),_ss(K,4),_ss(K,3),_ss(K,2),
                        _oo(K,J),_oo(K,T),_oo(K,9),
                        _ss(Q,J),_ss(Q,T),_ss(Q,9),_ss(Q,8),_ss(Q,7),_ss(Q,6),_ss(Q,5),_ss(Q,4),_ss(Q,3),_ss(Q,2),
                        _oo(Q,J),_oo(Q,T),
                        _ss(J,T),_ss(J,9),_ss(J,8),_ss(J,7),_ss(J,6),_ss(J,5),_ss(J,4),_ss(J,2), _oo(J,T),
                        _txs(6), _ss(9,8),_ss(9,7),_ss(9,6),_ss(9,5),
                        _ss(8,7),_ss(8,6),_ss(8,5), _ss(7,6),_ss(7,5),_ss(7,4),
                        _ss(6,5),_ss(6,4),_ss(6,3), _ss(5,4),_ss(5,3),_ss(5,2), _ss(4,3))},
},
}


def get_3bet_specs(opener_pos: str, defender_pos: str, action: str) -> list:
    opener_ranges = THREEBET_RANGES.get(opener_pos, {})
    defender_data = opener_ranges.get(defender_pos, {})
    return defender_data.get(action, [])


def expand_combos(specs: list, known_set: set) -> List[List[Card]]:
    SUITS = 'hdcs'
    seen:   set = set()
    result: List[List[Card]] = []
    for r1, r2, t in specs:
        if t == 'p':
            for i, s1 in enumerate(SUITS):
                for s2 in SUITS[i+1:]:
                    c1, c2 = (r1, s1), (r2, s2)
                    key = frozenset((c1, c2))
                    if key not in seen and c1 not in known_set and c2 not in known_set:
                        seen.add(key); result.append([c1, c2])
        elif t == 's':
            for s in SUITS:
                c1, c2 = (r1, s), (r2, s)
                key = frozenset((c1, c2))
                if key not in seen and c1 not in known_set and c2 not in known_set:
                    seen.add(key); result.append([c1, c2])
        else:
            for s1 in SUITS:
                for s2 in SUITS:
                    if s1 == s2: continue
                    c1, c2 = (r1, s1), (r2, s2)
                    key = frozenset((c1, c2))
                    if key not in seen and c1 not in known_set and c2 not in known_set:
                        seen.add(key); result.append([c1, c2])
    return result


def narrow_range_by_board(combos, board, action):
    if not board or not combos or not action:
        return combos
    if action not in ('raise', 'bet', 'call'):
        return combos
    n = len(board)
    if n < 3:
        return combos
    ranked = sorted(combos, key=lambda c: hand_rank(list(c) + board), reverse=True)
    if action in ('raise', 'bet'):
        if n >= 5:   cut = max(3, int(len(ranked) * 0.35))
        elif n >= 4: cut = max(3, int(len(ranked) * 0.45))
        else:        cut = max(3, int(len(ranked) * 0.55))
        return ranked[:cut]
    elif action == 'call':
        if n >= 4:
            cut = max(3, int(len(ranked) * 0.65))
            return ranked[:cut]
    return combos


def get_range_combos(pos, action, known_set, preflop_action='',
                     board=None, is_postflop=False, opener_pos=''):
    if is_postflop and board:
        return get_postflop_range(action, known_set, board)
    akey_raw = action if action else preflop_action
    if akey_raw in ('raise', 'reraise', '3bet') and opener_pos:
        specs = get_3bet_specs(opener_pos, pos, '3bet')
        if specs:
            return expand_combos(specs, known_set)
    if akey_raw == 'call' and opener_pos:
        specs = get_3bet_specs(opener_pos, pos, 'call')
        if specs:
            return expand_combos(specs, known_set)
    entry = HAND_RANGES.get(pos, HAND_RANGES['CO'])
    _, specs = entry.get('open', ('',[]))
    return expand_combos(specs, known_set)


def get_postflop_range(action, known_set, board):
    deck = [c for c in FULL_DECK if c not in known_set]
    if len(deck) < 2:
        return []
    combo_ranks = []
    seen = set()
    for i in range(len(deck)):
        for j in range(i+1, len(deck)):
            c1, c2 = deck[i], deck[j]
            key = frozenset((c1, c2))
            if key in seen: continue
            seen.add(key)
            seven = [c1, c2] + list(board)
            rank = hand_rank(seven)
            combo_ranks.append(([c1, c2], rank))
    if not combo_ranks:
        return []
    combo_ranks.sort(key=lambda x: x[1], reverse=True)
    n = len(combo_ranks)
    if action == 'reraise':   top_pct = 0.05
    elif action == 'raise':   top_pct = 0.20
    elif action == 'call':    top_pct = 0.55
    else:                     top_pct = 1.0
    cutoff = max(1, int(n * top_pct))
    return [combo for combo, _ in combo_ranks[:cutoff]]


# ════════════════════════════════════════════════
#  SIMULATION
# ════════════════════════════════════════════════

def simulate(our_hands, opp_data, board, n_sim=4000):
    if not our_hands:
        return {'individual': [], 'team': 0.0}
    if not opp_data:
        return {'individual': [100.0]*len(our_hands), 'team': 100.0}

    known_base_list = [c for h in our_hands for c in h] + list(board)
    known_base_set  = set(known_base_list)

    opp_ranges = []
    for entry in opp_data:
        pos    = entry[0]
        action = entry[1] if len(entry) > 1 else ''
        pf_act = entry[2] if len(entry) > 2 else ''
        brd    = list(entry[3]) if len(entry) > 3 else []
        is_pf  = bool(entry[4]) if len(entry) > 4 else False
        opener = entry[5] if len(entry) > 5 else ''
        opp_ranges.append(get_range_combos(pos, action, known_base_set, pf_act, brd, is_pf, opener))

    ind_wins  = [0.0] * len(our_hands)
    team_wins = 0.0
    valid     = 0

    for _ in range(n_sim):
        known_sim = set(known_base_set)
        opp_sim = []
        skip = False
        for rng in opp_ranges:
            eligible = [c for c in rng if c[0] not in known_sim and c[1] not in known_sim]
            if not eligible:
                deck_rem = [c for c in FULL_DECK if c not in known_sim]
                if len(deck_rem) < 2:
                    skip = True; break
                eligible = [[deck_rem[i], deck_rem[j]]
                            for i in range(min(len(deck_rem), 8))
                            for j in range(i+1, min(len(deck_rem), 9))]
            chosen = random.choice(eligible)
            opp_sim.append(chosen)
            known_sim.update(chosen)
        if skip: continue
        rem = [c for c in FULL_DECK if c not in known_sim]
        random.shuffle(rem)
        needed = 5 - len(board)
        if len(rem) < needed: continue
        full_board = list(board) + rem[:needed]
        valid += 1
        all_hands = our_hands + opp_sim
        all_ranks = [hand_rank(list(h) + full_board) for h in all_hands]
        best      = max(all_ranks)
        n_best    = sum(1 for r in all_ranks if r == best)
        if any(all_ranks[i] == best for i in range(len(our_hands))):
            team_wins += 1
        for i in range(len(our_hands)):
            if all_ranks[i] == best:
                ind_wins[i] += 1.0 / n_best
    if valid == 0:
        return {'individual': [33.0]*len(our_hands), 'team': 33.0}
    return {
        'individual': [(w/valid)*100 for w in ind_wins],
        'team':       (team_wins/valid)*100,
    }


def calc_ev(wp, pot, call_amt, pos=''):
    w = wp / 100
    if call_amt > 0:
        return w * (pot + call_amt) - (1 - w) * call_amt
    return w * pot


def calc_ev_raise(wp, pot, raise_to, n_opp, equity_hu=None):
    if n_opp <= 0:
        return wp / 100 * pot
    fold_prob = 0.72
    p_all_fold = fold_prob ** n_opp
    p_call = 1.0 - p_all_fold
    ev_fold = pot
    hu_wp = equity_hu if equity_hu is not None else min(wp * (n_opp ** 0.5), 65.0)
    w_hu = hu_wp / 100.0
    new_pot_hu = pot + 2 * raise_to
    ev_call = w_hu * new_pot_hu - raise_to
    return p_all_fold * ev_fold + p_call * ev_call


RAKE_RATE = 0.05          # 5% рейк с банка
RAKE_CAP_BB = 3.0         # потолок рейка = 3 больших блайнда


def _rake(pot, bb):
    cap = RAKE_CAP_BB * bb if bb else pot
    return min(pot * RAKE_RATE, cap)


def eval_collusion_continue(our_hands, opp_data, board, pot, calls, bb,
                            n_sim_full=4000, n_sim_sub=2500):
    """Сговор: команда = один суперигрок. Решаем, какое подмножество наших рук
    выгоднее всего оставить в игре, когда есть ставка для колла.

    Идея: руки уже вложившихся игроков (calls[i]==0) зафиксированы в банке.
    Среди игроков, которым нужно доставлять (calls[i]>0), выбираем оптимальный
    набор «сверху по эквити»: от никого до всех. Для каждого варианта считаем
    командное EV с учётом банка, размеров ставок и рейка, и берём максимум.

    Возвращает: individual (эквити каждой руки vs оппоненты), team (полный набор),
    flags (list[bool] — продолжать ли каждой рукой), best_m, evs (по числу
    доставляющих игроков)."""
    k = len(our_hands)
    full = simulate(our_hands, opp_data, board, n_sim=n_sim_full)
    individual = full['individual']
    team_full = full['team']

    locked = [i for i in range(k) if calls[i] <= 0]        # уже в банке
    deciding = [i for i in range(k) if calls[i] > 0]        # нужно решение
    # дециды по убыванию эквити
    deciding.sort(key=lambda i: individual[i], reverse=True)

    locked_hands = [our_hands[i] for i in locked]

    def team_eq(continue_idx):
        idxs = locked + continue_idx
        if not idxs:
            return 0.0
        if len(idxs) == k:
            return team_full
        subset = [our_hands[i] for i in idxs]
        return simulate(subset, opp_data, board, n_sim=n_sim_sub)['team']

    best_m, best_ev, evs = 0, None, {}
    for m in range(0, len(deciding) + 1):
        cont = deciding[:m]
        cost = sum(calls[i] for i in cont)
        p = team_eq(cont) / 100.0
        pot_final = pot + cost
        if not locked and m == 0:
            ev = 0.0                                        # команда пасует — банк не наш
        else:
            ev = p * (pot_final - _rake(pot_final, bb)) - cost
        evs[m] = ev
        if best_ev is None or ev > best_ev + 1e-9:
            best_ev, best_m = ev, m

    flags = [False] * k
    for i in locked:
        flags[i] = True
    for i in deciding[:best_m]:
        flags[i] = True
    return {'individual': individual, 'team': team_full,
            'flags': flags, 'best_m': best_m, 'evs': evs,
            'deciding': deciding, 'locked': locked}


def hand_in_range(cards, pos, action):
    if not cards or len(cards) < 2:
        return False
    known = set()
    combos = get_range_combos(pos, action, known)
    hand_fs = frozenset(cards)
    return any(frozenset(c) == hand_fs for c in combos)


def classify_hand_preflop(cards, pos, bb, last_bet, opener_pos='', bet_level=1, open_specs=None):
    """
    bet_level: 1 = открытый рейз (первая ставка), 2 = 3-бет, 3 = 4-бет+
    open_specs: если задан — используется как диапазон открытия (сговор),
                иначе берётся обычный диапазон позиции.
    """
    if last_bet == 0 or last_bet == bb:
        # Никто не рейзил — опен или ББ-опция
        if open_specs is not None:
            return 'raise' if _hand_in_specs(cards, open_specs) else 'fold'
        if hand_in_range(cards, pos, ''):
            return 'raise'
        return 'fold'

    if bet_level >= 3:
        # Против 4-бета: только монстры идут олл-ин, остальные фолдят
        # Монстры: TT+, AK
        if cards and len(cards) == 2:
            r1, r2 = sorted([cards[0][0], cards[1][0]], reverse=True)
            suited = cards[0][1] == cards[1][1]
            is_pair = r1 == r2
            is_ak = (r1 == 14 and r2 == 13)
            if is_pair and r1 >= 10:  # TT+
                return '4bet'
            if is_ak:
                return '4bet'
        return 'fold'

    if bet_level == 2:
        # Против 3-бета: очень узкий диапазон для 4-бета, остальное фолд/колл
        if cards and len(cards) == 2:
            r1, r2 = sorted([cards[0][0], cards[1][0]], reverse=True)
            suited = cards[0][1] == cards[1][1]
            is_pair = r1 == r2
            is_ak = (r1 == 14 and r2 == 13)
            # 4-бет: QQ+, AK
            if is_pair and r1 >= 12:
                return '4bet'
            if is_ak:
                return '4bet'
            # Колл: JJ, TT, AQs
            if is_pair and r1 >= 10:
                return 'call'
            if r1 == 14 and r2 == 12 and suited:
                return 'call'
        return 'fold'

    # bet_level == 1: против первого рейза (3-бет ситуация)
    if opener_pos:
        specs_3bet = get_3bet_specs(opener_pos, pos, '3bet')
        if specs_3bet and _hand_in_specs(cards, specs_3bet):
            return '3bet'
        specs_call = get_3bet_specs(opener_pos, pos, 'call')
        if specs_call and _hand_in_specs(cards, specs_call):
            return 'call'
    else:
        if hand_in_range(cards, pos, 'raise'):
            return '3bet'
        if hand_in_range(cards, pos, 'call'):
            return 'call'
    return 'fold'


def _hand_in_specs(cards, specs):
    if not cards or len(cards) < 2 or not specs:
        return False
    combos = expand_combos(specs, set())
    hand_fs = frozenset(cards)
    return any(frozenset(c) == hand_fs for c in combos)


# ════════════════════════════════════════════════
#  BOARD TEXTURE + RECOMMENDATIONS
# ════════════════════════════════════════════════

def board_texture(board):
    if not board:
        return {'cat': 'empty', 'suits': 'unknown', 'connectivity': 'unknown',
                'pairing': 'unpaired', 'height': 'unknown',
                'monotone': False, 'two_tone': False, 'rainbow': False,
                'paired': False, 'trips': False, 'connected': False,
                'broadway': False, 'has_ace': False, 'high': 0, 'n_cards': 0,
                'flush_draw': False, 'straight_draw': False}

    ranks = [c[0] for c in board]
    suits_list = [c[1] for c in board]
    n     = len(board)
    high  = max(ranks)
    has_ace = 14 in ranks

    sc = {}
    for s in suits_list:
        sc[s] = sc.get(s, 0) + 1
    max_suit = max(sc.values())
    monotone = (max_suit >= 3)
    two_tone = (max_suit == 2 and not monotone)
    rainbow  = (max(sc.values()) == 1 and n >= 3)

    if monotone:    suits_cat = 'monotone'
    elif two_tone:  suits_cat = 'two_tone'
    elif rainbow:   suits_cat = 'rainbow'
    else:           suits_cat = 'rainbow' if n <= 2 else 'two_tone'

    flush_draw = two_tone

    rc = {}
    for r in ranks:
        rc[r] = rc.get(r, 0) + 1
    max_rank_count = max(rc.values())
    trips  = (max_rank_count >= 3)
    paired = (max_rank_count == 2)

    if trips:        pairing_cat = 'trips'
    elif paired:     pairing_cat = 'paired'
    else:            pairing_cat = 'unpaired'

    sorted_unique = sorted(set(ranks))
    if 14 in sorted_unique:
        sorted_unique_ext = [1] + sorted_unique
    else:
        sorted_unique_ext = list(sorted_unique)

    gaps = [sorted_unique[i+1] - sorted_unique[i]
            for i in range(len(sorted_unique)-1)] if len(sorted_unique) > 1 else [99]
    all_connected = (len(sorted_unique) >= 2 and all(g <= 1 for g in gaps))
    some_connected = (len(sorted_unique) >= 2 and all(g <= 2 for g in gaps))

    two_way = False
    one_way = False
    if all_connected and len(sorted_unique) >= 3:
        lo, hi = sorted_unique[0], sorted_unique[-1]
        can_extend_low  = (lo > 2)
        can_extend_high = (hi < 14)
        two_way = can_extend_low and can_extend_high
        one_way = can_extend_low or can_extend_high
    elif some_connected and len(sorted_unique) >= 2:
        one_way = True

    if two_way:       connectivity = 'two_way_straight'
    elif one_way:     connectivity = 'straight_draw'
    else:             connectivity = 'disconnected'

    straight_draw_possible = (connectivity != 'disconnected')

    broadway = all(r >= 10 for r in ranks)
    medium   = any(r >= 7 for r in ranks)
    low_all  = all(r <= 8 for r in ranks)

    if has_ace and broadway:       height = 'ace_broadway'
    elif has_ace and not broadway:  height = 'ace_low'
    elif broadway:                  height = 'broadway_no_ace'
    elif low_all:                   height = 'low'
    else:                           height = 'medium'

    if monotone:                                       cat_val = 'monotone'
    elif trips:                                        cat_val = 'trips'
    elif paired:                                       cat_val = 'paired'
    elif two_way and two_tone:                         cat_val = 'connected_twotone'
    elif two_way and rainbow:
        if low_all:                                    cat_val = 'connected_low'
        elif broadway:                                 cat_val = 'broadway_rainbow'
        else:                                          cat_val = 'connected_rainbow'
    elif one_way and two_tone:                         cat_val = 'semi_connected_twotone'
    elif has_ace and rainbow:
        if broadway:                                   cat_val = 'ace_broadway_rainbow'
        else:                                          cat_val = 'ace_low_rainbow'
    elif high >= 13 and rainbow and not some_connected: cat_val = 'king_high_rainbow'
    elif broadway and rainbow:                         cat_val = 'broadway_rainbow'
    elif two_tone and not some_connected:              cat_val = 'twotone_disconnected'
    elif two_tone:                                     cat_val = 'twotone'
    elif low_all and rainbow:                          cat_val = 'low_rainbow'
    elif rainbow:                                      cat_val = 'medium_rainbow'
    else:                                              cat_val = 'other'

    return {
        'cat': cat_val,
        'suits': suits_cat, 'monotone': monotone, 'two_tone': two_tone,
        'rainbow': rainbow, 'flush_draw': flush_draw,
        'pairing': pairing_cat, 'paired': paired, 'trips': trips,
        'connectivity': connectivity, 'connected': all_connected,
        'straight_draw': straight_draw_possible, 'two_way': two_way,
        'height': height, 'broadway': broadway, 'has_ace': has_ace,
        'high': high, 'n_cards': n,
    }


_BOARD_GTO = {
    'ace_broadway_rainbow':   (80, 75, 0,  0),
    'ace_low_rainbow':        (65, 33, 0,  0),
    'king_high_rainbow':      (65, 33, 0,  0),
    'broadway_rainbow':       (65, 33, 0,  0),
    'connected_rainbow':      (65, 33, 0,  0),
    'connected_low':          (65, 33, 0,  33),
    'semi_connected_twotone': (65, 50, 0,  0),
    'connected_twotone':      (65, 50, 80, 0),
    'twotone_disconnected':   (65, 50, 0,  0),
    'twotone':                (65, 50, 0,  0),
    'monotone':               (65, 33, 0,  0),
    'paired':                 (55, 33, 0,  0),
    'trips':                  (60, 25, 0,  0),
    'medium_rainbow':         (65, 33, 0,  0),
    'low_rainbow':            (65, 33, 0,  33),
    'broadway_no_ace_rainbow':(65, 50, 0,  0),
    'other':                  (65, 33, 0,  0),
}

_BOARD_GTO_MULTI = {
    'ace_broadway_rainbow':   (62, 58, 0,  0),
    'ace_low_rainbow':        (50, 29, 0,  0),
    'king_high_rainbow':      (50, 29, 0,  0),
    'broadway_rainbow':       (50, 29, 0,  0),
    'connected_rainbow':      (45, 29, 0,  0),
    'connected_low':          (30, 25, 0,  0),
    'semi_connected_twotone': (45, 45, 0,  0),
    'connected_twotone':      (42, 42, 0,  0),
    'twotone_disconnected':   (37, 37, 0,  0),
    'twotone':                (37, 37, 0,  0),
    'monotone':               (29, 29, 0,  0),
    'paired':                 (29, 29, 0,  0),
    'trips':                  (29, 25, 0,  0),
    'medium_rainbow':         (45, 29, 0,  0),
    'low_rainbow':            (37, 29, 0,  0),
    'broadway_no_ace_rainbow':(50, 45, 0,  0),
    'other':                  (33, 29, 0,  0),
}

_BOARD_LABELS = {
    'ace_broadway_rainbow':  'A-high бродвей радуга',
    'ace_low_rainbow':       'A-low радуга',
    'king_high_rainbow':     'K-high радуга',
    'broadway_rainbow':      'Бродвейная радуга',
    'connected_low':         'Скоор. низкие',
    'connected_rainbow':     'Скоор. радуга',
    'connected_twotone':     'Скоор. дрова',
    'semi_connected_twotone':'Полусвязная дрова',
    'twotone_disconnected':  'Несвяз. дрова',
    'twotone':               'Двумасть',
    'monotone':              'Монотонный',
    'trips':                 'Трипс на борде',
    'paired':                'Парный борд',
    'low_rainbow':           'Низкая радуга',
    'medium_rainbow':        'Средняя радуга',
    'other':                 'Смешанная текстура',
}


def classify_turn_card(flop, turn):
    if not flop or turn is None:
        return 'blank'
    flop_ranks = [c[0] for c in flop]
    flop_suits = [c[1] for c in flop]
    turn_rank, turn_suit = turn

    if turn_rank in flop_ranks:
        sorted_flop = sorted(flop_ranks)
        if len(sorted_flop) >= 2 and sorted_flop[-1] == sorted_flop[-2]:
            return 'double_pair'
        if turn_rank == sorted_flop[-1]:
            return 'pair_top'
        elif len(sorted_flop) >= 3 and turn_rank == sorted_flop[1]:
            return 'pair_middle'
        else:
            return 'pair_low'

    suit_counts = {}
    for s in flop_suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    flop_max_suit_cnt = max(suit_counts.values()) if suit_counts else 0

    if suit_counts.get(turn_suit, 0) >= 2:
        if flop_max_suit_cnt >= 3:
            return 'complete_flush'
        all4 = flop + [turn]
        all4_ranks = sorted(set(c[0] for c in all4))
        gaps4 = [all4_ranks[i+1]-all4_ranks[i] for i in range(len(all4_ranks)-1)]
        if len(all4_ranks) >= 3 and all(g <= 2 for g in gaps4):
            return 'complete_combo'
        return 'flush_draw'

    all4 = flop + [turn]
    all4_ranks_raw = [c[0] for c in all4]
    sr_flop = sorted(set([c[0] for c in flop]))
    sr_all4 = sorted(set(all4_ranks_raw))
    ext_flop = ([1] + sr_flop) if 14 in sr_flop else list(sr_flop)
    ext_all4 = ([1] + sr_all4) if 14 in sr_all4 else list(sr_all4)

    for lo in range(1, 11):
        straight_set = set(range(lo, lo+5))
        have_all4 = set(ext_all4) & straight_set
        have_flop = set(ext_flop) & straight_set
        turn_r = turn_rank if turn_rank != 14 else turn_rank
        turn_in_str = (turn_r in straight_set) or (turn_r == 14 and 1 in straight_set)
        if len(have_all4) >= 4 and len(have_flop) == 3 and turn_in_str:
            missing = straight_set - have_all4
            if len(missing) == 1:
                miss = list(missing)[0]
                lo_s, hi_s = lo, lo + 4
                if miss == lo_s or miss == hi_s:
                    return 'complete_oesd'
                else:
                    return 'complete_gutshot'
            elif len(missing) == 0:
                lo_s, hi_s = lo, lo + 4
                if turn_rank == lo_s or turn_rank == hi_s:
                    return 'complete_oesd'
                else:
                    return 'complete_gutshot'

    if turn_rank > max(flop_ranks):
        return 'overcard'
    return 'blank'


def classify_hand_strength(our_hand, board):
    if not our_hand or not board:
        return 'air'
    all7 = our_hand + board
    rank_tuple = hand_rank(all7)
    hand_cat = rank_tuple[0]
    board_ranks = [c[0] for c in board]
    board_max   = max(board_ranks)
    hand_ranks_list = [c[0] for c in our_hand]

    if hand_cat >= 4: return 'value'
    if hand_cat == 3: return 'value'
    if hand_cat == 2: return 'value'
    if hand_cat == 1:
        pair_rank = rank_tuple[1]
        if pair_rank == board_max:
            kicker = max((r for r in hand_ranks_list if r != pair_rank), default=pair_rank)
            if kicker >= 10 or pair_rank >= 11:
                return 'value'
            else:
                return 'medium'
        elif pair_rank in board_ranks:
            return 'medium'
        else:
            return 'medium'

    all_suits = [c[1] for c in all7]
    for suit in set(all_suits):
        if all_suits.count(suit) >= 4:
            return 'draw'
    all_ranks = sorted(set(c[0] for c in all7))
    if 14 in all_ranks:
        all_ranks_ext = [1] + all_ranks
    else:
        all_ranks_ext = list(all_ranks)
    for lo in range(1, 11):
        window = [r for r in all_ranks_ext if lo <= r <= lo+4]
        if len(window) >= 4:
            return 'draw'
    return 'air'


def _size_bucket(size):
    if size <= 0.4:   return 'small'
    if size <= 0.6:   return 'medium'
    return 'large'


_TURN_AGG_TABLE = {
    ('blank','value','small'):(0.8,''),('blank','value','medium'):(0.8,''),('blank','value','large'):(0.8,''),
    ('blank','medium','small'):('check',''),('blank','medium','medium'):('check',''),('blank','medium','large'):('check',''),
    ('blank','draw','small'):(0.8,''),('blank','draw','medium'):(0.5,'гатшот → чек'),('blank','draw','large'):(0.5,'только флеш/комбо, иначе чек'),
    ('blank','air','small'):(0.5,'при наличии блокеров'),('blank','air','medium'):('check',''),('blank','air','large'):('check',''),
    ('overcard','value','small'):(0.8,''),('overcard','value','medium'):(0.8,''),('overcard','value','large'):(0.8,''),
    ('overcard','medium','small'):('check',''),('overcard','medium','medium'):('check',''),('overcard','medium','large'):('check',''),
    ('overcard','draw','small'):(0.8,'50% если гатшот'),('overcard','draw','medium'):(0.8,'33% если гатшот'),('overcard','draw','large'):(0.5,'чек если гатшот'),
    ('overcard','air','small'):(0.5,'при наличии блокеров'),('overcard','air','medium'):(0.5,'при наличии блокеров'),('overcard','air','large'):('check',''),
    ('pair_top','value','small'):(0.5,''),('pair_top','value','medium'):(0.5,''),('pair_top','value','large'):(0.5,''),
    ('pair_top','medium','small'):('check',''),('pair_top','medium','medium'):('check',''),('pair_top','medium','large'):('check',''),
    ('pair_top','draw','small'):(0.5,'33% если гатшот'),('pair_top','draw','medium'):(0.5,'чек если гатшот'),('pair_top','draw','large'):(0.5,'чек если гатшот'),
    ('pair_top','air','small'):(0.33,'при наличии блокеров'),('pair_top','air','medium'):('check',''),('pair_top','air','large'):('check',''),
    ('pair_low','value','small'):(0.5,''),('pair_low','value','medium'):(0.5,''),('pair_low','value','large'):(0.5,''),
    ('pair_low','medium','small'):('check',''),('pair_low','medium','medium'):('check',''),('pair_low','medium','large'):('check',''),
    ('pair_low','draw','small'):('check',''),('pair_low','draw','medium'):('check',''),('pair_low','draw','large'):('check',''),
    ('pair_low','air','small'):('check',''),('pair_low','air','medium'):('check',''),('pair_low','air','large'):('check',''),
    ('flush_draw','value','small'):(0.8,''),('flush_draw','value','medium'):(0.8,''),('flush_draw','value','large'):(0.8,''),
    ('flush_draw','medium','small'):('check',''),('flush_draw','medium','medium'):('check',''),('flush_draw','medium','large'):('check',''),
    ('flush_draw','draw','small'):(0.8,'чек если гатшот'),('flush_draw','draw','medium'):(0.8,'чек если гатшот'),('flush_draw','draw','large'):(0.5,'чек если гатшот'),
    ('flush_draw','air','small'):('check',''),('flush_draw','air','medium'):('check',''),('flush_draw','air','large'):('check',''),
    ('straight_draw','value','small'):(0.5,''),('straight_draw','value','medium'):(0.5,''),('straight_draw','value','large'):(0.5,''),
    ('straight_draw','medium','small'):('check',''),('straight_draw','medium','medium'):('check',''),('straight_draw','medium','large'):('check',''),
    ('straight_draw','draw','small'):(0.5,'чек если гатшот'),('straight_draw','draw','medium'):(0.5,'чек если гатшот'),('straight_draw','draw','large'):(0.5,'чек если гатшот'),
    ('straight_draw','air','small'):('check',''),('straight_draw','air','medium'):('check',''),('straight_draw','air','large'):('check',''),
    ('complete_oesd','value','small'):('check','если нет стрита у нас; 50% если есть'),('complete_oesd','value','medium'):('check','если нет стрита у нас; 50% если есть'),('complete_oesd','value','large'):('check','если нет стрита у нас; 50% если есть'),
    ('complete_oesd','medium','small'):('check',''),('complete_oesd','medium','medium'):('check',''),('complete_oesd','medium','large'):('check',''),
    ('complete_oesd','draw','small'):('check',''),('complete_oesd','draw','medium'):('check',''),('complete_oesd','draw','large'):('check',''),
    ('complete_oesd','air','small'):('check',''),('complete_oesd','air','medium'):('check',''),('complete_oesd','air','large'):('check',''),
    ('complete_gutshot','value','small'):(0.5,'если нет стрита; 80% если стрит'),('complete_gutshot','value','medium'):(0.5,'если нет стрита; 80% если стрит'),('complete_gutshot','value','large'):(0.5,'если нет стрита; 80% если стрит'),
    ('complete_gutshot','medium','small'):('check',''),('complete_gutshot','medium','medium'):('check',''),('complete_gutshot','medium','large'):('check',''),
    ('complete_gutshot','draw','small'):(0.5,'чек если гатшот'),('complete_gutshot','draw','medium'):(0.5,'чек если гатшот'),('complete_gutshot','draw','large'):('check',''),
    ('complete_gutshot','air','small'):(0.33,'при наличии блокеров'),('complete_gutshot','air','medium'):('check',''),('complete_gutshot','air','large'):('check',''),
    ('complete_combo','value','small'):('check','если нет натсового флеша; 50% если натс'),('complete_combo','value','medium'):('check',''),('complete_combo','value','large'):('check',''),
    ('complete_combo','medium','small'):('check',''),('complete_combo','medium','medium'):('check',''),('complete_combo','medium','large'):('check',''),
    ('complete_combo','draw','small'):('check',''),('complete_combo','draw','medium'):('check',''),('complete_combo','draw','large'):('check',''),
    ('complete_combo','air','small'):('check',''),('complete_combo','air','medium'):('check',''),('complete_combo','air','large'):('check',''),
    ('complete_flush','value','small'):('check','чек если не натс; 50% если натс'),('complete_flush','value','medium'):('check','чек если не натс; 50% если натс'),('complete_flush','value','large'):('check','чек если не натс; 50% если натс'),
    ('complete_flush','medium','small'):('check',''),('complete_flush','medium','medium'):('check',''),('complete_flush','medium','large'):('check',''),
    ('complete_flush','draw','small'):(0.5,'флеш-дро'),('complete_flush','draw','medium'):(0.5,'флеш-дро'),('complete_flush','draw','large'):(0.33,'флеш-дро'),
    ('complete_flush','air','small'):('check',''),('complete_flush','air','medium'):('check',''),('complete_flush','air','large'):('check',''),
    ('pair_middle','value','small'):(0.5,''),('pair_middle','value','medium'):(0.5,''),('pair_middle','value','large'):(0.5,''),
    ('pair_middle','medium','small'):('check',''),('pair_middle','medium','medium'):('check',''),('pair_middle','medium','large'):('check',''),
    ('pair_middle','draw','small'):('check',''),('pair_middle','draw','medium'):('check',''),('pair_middle','draw','large'):('check',''),
    ('pair_middle','air','small'):('check',''),('pair_middle','air','medium'):('check',''),('pair_middle','air','large'):('check',''),
    ('overcard_draw','value','small'):(0.8,''),('overcard_draw','value','medium'):(0.8,''),('overcard_draw','value','large'):(0.5,''),
    ('overcard_draw','medium','small'):('check',''),('overcard_draw','medium','medium'):('check',''),('overcard_draw','medium','large'):('check',''),
    ('overcard_draw','draw','small'):(0.5,''),('overcard_draw','draw','medium'):(0.5,''),('overcard_draw','draw','large'):('check',''),
    ('overcard_draw','air','small'):(0.5,''),('overcard_draw','air','medium'):('check',''),('overcard_draw','air','large'):('check',''),
    ('double_pair','value','small'):(0.33,''),('double_pair','value','medium'):(0.33,''),('double_pair','value','large'):(0.33,''),
    ('double_pair','medium','small'):('check',''),('double_pair','medium','medium'):('check',''),('double_pair','medium','large'):('check',''),
    ('double_pair','air','small'):('check',''),('double_pair','air','medium'):('check',''),('double_pair','air','large'):('check',''),
}

_TURN_AGG_TABLE_MULTI = {
    ('blank','value','small'):(0.58,''),('blank','value','medium'):(0.58,''),('blank','value','large'):(0.5,''),
    ('blank','medium','small'):('check',''),('blank','medium','medium'):('check',''),('blank','medium','large'):('check',''),
    ('blank','draw','small'):(0.58,'сильное дро'),('blank','draw','medium'):(0.5,''),('blank','draw','large'):('check',''),
    ('blank','air','small'):('check',''),('blank','air','medium'):('check',''),('blank','air','large'):('check',''),
    ('overcard','value','small'):(0.58,''),('overcard','value','medium'):(0.58,''),('overcard','value','large'):(0.5,''),
    ('overcard','medium','small'):('check',''),('overcard','medium','medium'):('check',''),('overcard','medium','large'):('check',''),
    ('overcard','draw','small'):(0.58,'сильное дро'),('overcard','draw','medium'):(0.5,''),('overcard','draw','large'):('check',''),
    ('overcard','air','small'):('check',''),('overcard','air','medium'):('check',''),('overcard','air','large'):('check',''),
    ('pair_top','value','small'):(0.42,''),('pair_top','value','medium'):(0.42,''),('pair_top','value','large'):(0.33,''),
    ('pair_top','medium','small'):('check',''),('pair_top','medium','medium'):('check',''),('pair_top','medium','large'):('check',''),
    ('pair_top','draw','small'):('check',''),('pair_top','draw','medium'):('check',''),('pair_top','draw','large'):('check',''),
    ('pair_top','air','small'):('check',''),('pair_top','air','medium'):('check',''),('pair_top','air','large'):('check',''),
    ('pair_low','value','small'):(0.42,''),('pair_low','value','medium'):(0.42,''),('pair_low','value','large'):('check',''),
    ('pair_low','medium','small'):('check',''),('pair_low','medium','medium'):('check',''),('pair_low','medium','large'):('check',''),
    ('pair_low','draw','small'):('check',''),('pair_low','draw','medium'):('check',''),('pair_low','draw','large'):('check',''),
    ('pair_low','air','small'):('check',''),('pair_low','air','medium'):('check',''),('pair_low','air','large'):('check',''),
    ('flush_draw','value','small'):(0.58,''),('flush_draw','value','medium'):(0.58,''),('flush_draw','value','large'):(0.5,''),
    ('flush_draw','medium','small'):('check',''),('flush_draw','medium','medium'):('check',''),('flush_draw','medium','large'):('check',''),
    ('flush_draw','draw','small'):(0.58,'флеш-дро'),('flush_draw','draw','medium'):(0.5,''),('flush_draw','draw','large'):('check',''),
    ('flush_draw','air','small'):('check',''),('flush_draw','air','medium'):('check',''),('flush_draw','air','large'):('check',''),
    ('straight_draw','value','small'):(0.42,''),('straight_draw','value','medium'):(0.42,''),('straight_draw','value','large'):(0.33,''),
    ('straight_draw','medium','small'):('check',''),('straight_draw','medium','medium'):('check',''),('straight_draw','medium','large'):('check',''),
    ('straight_draw','draw','small'):(0.42,'стрит-дро'),('straight_draw','draw','medium'):(0.33,''),('straight_draw','draw','large'):('check',''),
    ('straight_draw','air','small'):('check',''),('straight_draw','air','medium'):('check',''),('straight_draw','air','large'):('check',''),
    ('complete_oesd','value','small'):(0.58,'стрит'),('complete_oesd','value','medium'):(0.5,''),('complete_oesd','value','large'):(0.42,''),
    ('complete_oesd','medium','small'):('check',''),('complete_oesd','medium','medium'):('check',''),('complete_oesd','medium','large'):('check',''),
    ('complete_oesd','draw','small'):('check',''),('complete_oesd','draw','medium'):('check',''),('complete_oesd','draw','large'):('check',''),
    ('complete_oesd','air','small'):('check',''),('complete_oesd','air','medium'):('check',''),('complete_oesd','air','large'):('check',''),
    ('complete_gutshot','value','small'):(0.58,'стрит'),('complete_gutshot','value','medium'):(0.58,''),('complete_gutshot','value','large'):(0.42,''),
    ('complete_gutshot','medium','small'):('check',''),('complete_gutshot','medium','medium'):('check',''),('complete_gutshot','medium','large'):('check',''),
    ('complete_gutshot','draw','small'):('check',''),('complete_gutshot','draw','medium'):('check',''),('complete_gutshot','draw','large'):('check',''),
    ('complete_gutshot','air','small'):('check',''),('complete_gutshot','air','medium'):('check',''),('complete_gutshot','air','large'):('check',''),
    ('complete_combo','value','small'):(0.42,'натс'),('complete_combo','value','medium'):(0.42,''),('complete_combo','value','large'):(0.33,''),
    ('complete_combo','medium','small'):('check',''),('complete_combo','medium','medium'):('check',''),('complete_combo','medium','large'):('check',''),
    ('complete_combo','draw','small'):('check',''),('complete_combo','draw','medium'):('check',''),('complete_combo','draw','large'):('check',''),
    ('complete_combo','air','small'):('check',''),('complete_combo','air','medium'):('check',''),('complete_combo','air','large'):('check',''),
    ('complete_flush','value','small'):(0.58,'натс'),('complete_flush','value','medium'):(0.5,''),('complete_flush','value','large'):(0.42,''),
    ('complete_flush','medium','small'):('check',''),('complete_flush','medium','medium'):('check',''),('complete_flush','medium','large'):('check',''),
    ('complete_flush','draw','small'):(0.42,'флеш-дро'),('complete_flush','draw','medium'):(0.33,''),('complete_flush','draw','large'):('check',''),
    ('complete_flush','air','small'):('check',''),('complete_flush','air','medium'):('check',''),('complete_flush','air','large'):('check',''),
    ('pair_middle','value','small'):(0.42,''),('pair_middle','value','medium'):(0.42,''),('pair_middle','value','large'):('check',''),
    ('pair_middle','medium','small'):('check',''),('pair_middle','medium','medium'):('check',''),('pair_middle','medium','large'):('check',''),
    ('pair_middle','draw','small'):('check',''),('pair_middle','draw','medium'):('check',''),('pair_middle','draw','large'):('check',''),
    ('pair_middle','air','small'):('check',''),('pair_middle','air','medium'):('check',''),('pair_middle','air','large'):('check',''),
    ('double_pair','value','small'):(0.29,'фулл-хаус'),('double_pair','value','medium'):(0.29,''),('double_pair','value','large'):('check',''),
    ('double_pair','medium','small'):('check',''),('double_pair','medium','medium'):('check',''),('double_pair','medium','large'):('check',''),
    ('double_pair','air','small'):('check',''),('double_pair','air','medium'):('check',''),('double_pair','air','large'):('check',''),
}

_TURN_CALLER_TABLE = {
    ('blank','value'):('check_raise',''),('blank','medium'):('check_call_fold','математика пот-оддов'),('blank','draw'):('check_call_fold','математика пот-оддов'),('blank','air'):('check_fold',''),
    ('overcard','value'):('check_raise',''),('overcard','medium'):('check_call_fold','математика пот-оддов'),('overcard','draw'):('check_call_fold','математика пот-оддов'),('overcard','air'):('check_fold',''),
    ('pair_top','value'):('check_raise',''),('pair_top','medium'):('check_call_fold','математика пот-оддов'),('pair_top','draw'):('check_call_fold','математика пот-оддов'),('pair_top','air'):('check_fold',''),
    ('pair_low','value'):('check_raise',''),('pair_low','medium'):('donk_33',''),('pair_low','draw'):('donk_33',''),('pair_low','air'):('donk_33','в ~15% случаев'),
    ('flush_draw','value'):('check_raise',''),('flush_draw','medium'):('check_call_fold','математика пот-оддов'),('flush_draw','draw'):('check_call_fold','математика пот-оддов'),('flush_draw','air'):('check_fold',''),
    ('straight_draw','value'):('check_raise',''),('straight_draw','medium'):('check_call_fold','математика пот-оддов'),('straight_draw','draw'):('check_call_fold','математика пот-оддов'),('straight_draw','air'):('check_fold',''),
    ('complete_oesd','value'):('check_raise',''),('complete_oesd','medium'):('check_fold',''),('complete_oesd','draw'):('donk_33',''),('complete_oesd','air'):('donk_33','в ~15% случаев'),
    ('complete_gutshot','value'):('check_raise',''),('complete_gutshot','medium'):('check_fold',''),('complete_gutshot','draw'):('donk_33',''),('complete_gutshot','air'):('donk_33','в ~15% случаев'),
    ('complete_combo','value'):('check_raise',''),('complete_combo','medium'):('check_fold',''),('complete_combo','draw'):('donk_33',''),('complete_combo','air'):('check_fold',''),
    ('complete_flush','value'):('check_raise',''),('complete_flush','medium'):('check_fold',''),('complete_flush','draw'):('donk_33','если есть блокер на натс'),('complete_flush','air'):('donk_33','если есть блокер на натс'),
    ('pair_middle','value'):('check_raise',''),('pair_middle','medium'):('check_call_fold',''),('pair_middle','draw'):('check_call',''),('pair_middle','air'):('donk_33','в ~15% случаев'),
    ('overcard_draw','value'):('check_raise',''),('overcard_draw','medium'):('check_fold',''),('overcard_draw','draw'):('check_call_fold',''),('overcard_draw','air'):('check_fold',''),
    ('double_pair','value'):('check_raise','с фулл-хаусом; иначе чек-колл'),('double_pair','medium'):('check_fold',''),('double_pair','draw'):('check_fold',''),('double_pair','air'):('check_fold',''),
}

_TURN_CALLER_TABLE_MULTI = {
    ('blank','value'):('check_raise_or_call','сет, две пары → рейз; топ-пара → колл'),('blank','medium'):('check_fold',''),('blank','draw'):('check_call_fold','флеш-дро, двуст → колл; гатшот → фолд'),('blank','air'):('check_fold',''),
    ('overcard','value'):('check_raise_or_call','сет → рейз; топ-пара → колл'),('overcard','medium'):('check_fold',''),('overcard','draw'):('check_fold','оверкарта усилила агрессора'),('overcard','air'):('check_fold',''),
    ('pair_top','value'):('check_raise_or_call','трипс, фулл → рейз; топ-пара → колл'),('pair_top','medium'):('check_fold',''),('pair_top','draw'):('check_fold',''),('pair_top','air'):('check_fold',''),
    ('pair_low','value'):('check_raise_or_donk','трипс → рейз/донк'),('pair_low','medium'):('check_call_fold',''),('pair_low','draw'):('check_fold','фолд-эквити мало'),('pair_low','air'):('check_fold',''),
    ('flush_draw','value'):('check_raise_or_call','сет, две пары → рейз'),('flush_draw','medium'):('check_fold',''),('flush_draw','draw'):('check_call','флеш-дро → колл; без флеша → фолд'),('flush_draw','air'):('check_fold',''),
    ('straight_draw','value'):('check_raise_or_call',''),('straight_draw','medium'):('check_fold',''),('straight_draw','draw'):('check_call_fold','флеш+стрит → колл; чист → фолд'),('straight_draw','air'):('check_fold',''),
    ('complete_oesd','value'):('check_raise_or_call','старший → рейз; младший → колл'),('complete_oesd','medium'):('check_fold',''),('complete_oesd','draw'):('check_fold',''),('complete_oesd','air'):('check_fold',''),
    ('complete_gutshot','value'):('check_raise_or_call','стрит → рейз; две пары → колл'),('complete_gutshot','medium'):('check_fold',''),('complete_gutshot','draw'):('check_fold','донк 25% с блокерами'),('complete_gutshot','air'):('check_fold',''),
    ('complete_combo','value'):('check_raise_or_call','натс → рейз; не натс → колл'),('complete_combo','medium'):('check_fold',''),('complete_combo','draw'):('check_fold',''),('complete_combo','air'):('check_fold',''),
    ('complete_flush','value'):('check_raise_or_call','натс → рейз; не натс → колл'),('complete_flush','medium'):('check_fold',''),('complete_flush','draw'):('check_fold','донк 25% с A в масть'),('complete_flush','air'):('check_fold',''),
    ('pair_middle','value'):('check_raise_or_call','трипс → рейз; топ-пара → колл'),('pair_middle','medium'):('check_fold',''),('pair_middle','draw'):('check_fold',''),('pair_middle','air'):('check_fold',''),
    ('double_pair','value'):('check_raise_or_call','фулл → рейз; трипс → колл'),('double_pair','medium'):('check_fold',''),('double_pair','draw'):('check_fold',''),('double_pair','air'):('check_fold',''),
}

_TURN_TYPE_LABELS = {
    'blank':'Бланк','overcard':'Оверкарта','overcard_draw':'Оверкарта+дро',
    'pair_top':'Спарила верх','pair_middle':'Спарила среднюю','pair_low':'Спарила низ',
    'double_pair':'Двойное спаривание','flush_draw':'Флеш-дро','complete_flush':'Закрыла флеш',
    'straight_draw':'Стрит-дро','complete_oesd':'Закрыла открытый стрит',
    'complete_gutshot':'Закрыла дырявый стрит','complete_combo':'Закрыла комбо-дро',
}
_HAND_STR_LABELS = {'value':'вэлью','medium':'средняя','draw':'дро','air':'ничего'}


def turn_recommend(wp, pot, call_amt, board, our_hand, our_pos, flop_aggressor, flop_bet_size, n_opp):
    if len(board) < 4 or not our_hand:
        return postflop_recommend(wp, pot, call_amt, board, our_pos, flop_aggressor, n_opp)
    flop = board[:3]; turn = board[3]; pot = max(pot, 1)
    turn_type = classify_turn_card(flop, turn)
    hand_str = classify_hand_strength(our_hand, board)
    we_are_agg = (flop_aggressor is not None and flop_aggressor == our_pos)
    size_bkt = _size_bucket(flop_bet_size) if flop_bet_size else 'medium'
    turn_lbl = _TURN_TYPE_LABELS.get(turn_type, 'тёрн')
    hand_lbl = _HAND_STR_LABELS.get(hand_str, hand_str)

    if call_amt > 0:
        pot_odds = call_amt / (pot + call_amt) * 100
        ev = wp / 100 * (pot + call_amt) - (1 - wp / 100) * call_amt
        ev_txt = f"EV+{ev:.0f}" if ev >= 0 else f"EV{ev:.0f}"
        if wp >= pot_odds + 20 and ev > 0:
            return f"РЕЙЗ ~{int(pot*0.75)} (75%) — {turn_lbl}, {hand_lbl}, {ev_txt}, {wp:.0f}% >> пот-одды {pot_odds:.0f}%"
        if ev > 0:
            return f"КОЛЛ — {turn_lbl}, {hand_lbl}, {ev_txt}, {wp:.0f}% vs пот-одды {pot_odds:.0f}%"
        if wp >= pot_odds - 4:
            return f"КОЛЛ (граница) — {turn_lbl}, {hand_lbl}, {ev_txt}"
        return f"ФОЛД — {turn_lbl}, {hand_lbl}, {ev_txt}, {wp:.0f}% при пот-оддах {pot_odds:.0f}%"

    is_multi = (n_opp >= 2)
    multi_tag = " (мультипот)" if is_multi else ""
    if we_are_agg:
        tbl = _TURN_AGG_TABLE_MULTI if is_multi else _TURN_AGG_TABLE
        action, note = tbl.get((turn_type, hand_str, size_bkt), ('check', ''))
        note_txt = f" ({note})" if note else ""
        if action == 'check':
            return f"ЧЕК — {turn_lbl} | {hand_lbl}{note_txt}{multi_tag}"
        elif isinstance(action, float):
            bet_amt = int(pot * action)
            return f"БЕТ {int(action*100)}% банка (~{bet_amt}) — {turn_lbl} | {hand_lbl}{note_txt}{multi_tag}"
    else:
        if is_multi:
            action, note = _TURN_CALLER_TABLE_MULTI.get((turn_type, hand_str), ('check_fold', ''))
        else:
            action, note = _TURN_CALLER_TABLE.get((turn_type, hand_str), ('check_fold', ''))
        note_txt = f" ({note})" if note else ""
        if action == 'check_raise':
            return f"ЧЕК-РЕЙЗ (~{int(pot*0.75)}) — {turn_lbl} | {hand_lbl}, вэлью-рейз{note_txt}{multi_tag}"
        elif action == 'check_raise_or_call':
            return f"ЧЕК-РЕЙЗ / ЧЕК-КОЛЛ — {turn_lbl} | {hand_lbl}{note_txt}{multi_tag}"
        elif action == 'check_raise_or_donk':
            return f"ЧЕК-РЕЙЗ / ДОНК 33% (~{int(pot*0.33)}) — {turn_lbl} | {hand_lbl}{note_txt}{multi_tag}"
        elif action == 'donk_33':
            return f"ДОНК-БЕТ 33% (~{int(pot*0.33)}) — {turn_lbl} | {hand_lbl}{note_txt}{multi_tag}"
        elif action == 'check_call_fold':
            return f"ЧЕК → КОЛЛ/ФОЛД по пот-оддам — {turn_lbl} | {hand_lbl}{note_txt}{multi_tag}"
        elif action == 'check_call':
            return f"ЧЕК → КОЛЛ — {turn_lbl} | {hand_lbl}{note_txt}{multi_tag}"
        elif action == 'check_fold':
            return f"ЧЕК → ФОЛД при ставке — {turn_lbl} | {hand_lbl}{note_txt}{multi_tag}"
        else:
            return f"ЧЕК — {turn_lbl} | {hand_lbl}{note_txt}{multi_tag}"
    return f"ЧЕК — {turn_lbl} | {hand_lbl}{multi_tag}"


_RIVER_AGG_TABLE = {
    ('blank','value','large'):(0.8,''),('blank','value','medium'):(0.8,''),('blank','value','small'):(0.5,''),('blank','value','check'):(0.5,''),
    ('blank','medium','large'):('check',''),('blank','medium','medium'):('check',''),('blank','medium','small'):('check',''),('blank','medium','check'):('check',''),
    ('blank','air','large'):('check','блокеры → 50%'),('blank','air','medium'):('check','блокеры → 50%'),('blank','air','small'):('check',''),('blank','air','check'):(0.5,''),
    ('overcard','value','large'):(0.5,''),('overcard','value','medium'):(0.5,''),('overcard','value','small'):(0.5,''),('overcard','value','check'):(0.5,''),
    ('overcard','medium','large'):('check',''),('overcard','medium','medium'):('check',''),('overcard','medium','small'):('check',''),('overcard','medium','check'):('check',''),
    ('overcard','air','large'):('check',''),('overcard','air','medium'):('check','блокеры → 80%'),('overcard','air','small'):('check','блокеры → 50%'),('overcard','air','check'):('check','блокеры → 50%'),
    ('pair_top','value','large'):(0.5,''),('pair_top','value','medium'):(0.5,''),('pair_top','value','small'):(0.5,''),('pair_top','value','check'):(0.5,''),
    ('pair_top','medium','large'):('check',''),('pair_top','medium','medium'):('check',''),('pair_top','medium','small'):('check',''),('pair_top','medium','check'):('check',''),
    ('pair_top','air','large'):('check',''),('pair_top','air','medium'):('check',''),('pair_top','air','small'):('check',''),('pair_top','air','check'):('check',''),
    ('pair_low','value','large'):('check',''),('pair_low','value','medium'):('check',''),('pair_low','value','small'):(0.33,''),('pair_low','value','check'):('check',''),
    ('pair_low','medium','large'):('check',''),('pair_low','medium','medium'):('check',''),('pair_low','medium','small'):('check',''),('pair_low','medium','check'):('check',''),
    ('pair_low','air','large'):('check',''),('pair_low','air','medium'):('check',''),('pair_low','air','small'):('check',''),('pair_low','air','check'):('check',''),
    ('complete_oesd','value','large'):(0.5,'натс → 80%'),('complete_oesd','value','medium'):(0.5,'натс → 80%'),('complete_oesd','value','small'):(0.5,'натс → 80%'),('complete_oesd','value','check'):(0.5,'натс → 80%'),
    ('complete_oesd','medium','large'):('check',''),('complete_oesd','medium','medium'):('check',''),('complete_oesd','medium','small'):('check',''),('complete_oesd','medium','check'):('check',''),
    ('complete_oesd','air','large'):('check',''),('complete_oesd','air','medium'):('check',''),('complete_oesd','air','small'):('check',''),('complete_oesd','air','check'):('check',''),
    ('complete_gutshot','value','large'):('check','стрит → 80%'),('complete_gutshot','value','medium'):(0.5,'стрит → 80%'),('complete_gutshot','value','small'):(0.5,'стрит → 80%'),('complete_gutshot','value','check'):(0.5,'стрит → 80%'),
    ('complete_gutshot','medium','large'):('check',''),('complete_gutshot','medium','medium'):('check',''),('complete_gutshot','medium','small'):('check',''),('complete_gutshot','medium','check'):('check',''),
    ('complete_gutshot','air','large'):('check','блокеры → 50%'),('complete_gutshot','air','medium'):('check','блокеры → 50%'),('complete_gutshot','air','small'):(0.5,''),('complete_gutshot','air','check'):(0.5,''),
    ('complete_combo','value','large'):(0.5,'только натс флеш'),('complete_combo','value','medium'):(0.5,'только натс флеш'),('complete_combo','value','small'):(0.5,'только натс флеш'),('complete_combo','value','check'):(0.5,'только натс флеш'),
    ('complete_combo','medium','large'):('check',''),('complete_combo','medium','medium'):('check',''),('complete_combo','medium','small'):('check',''),('complete_combo','medium','check'):('check',''),
    ('complete_combo','air','large'):('check',''),('complete_combo','air','medium'):('check',''),('complete_combo','air','small'):('check',''),('complete_combo','air','check'):('check',''),
    ('complete_flush','value','large'):('check','натс → 80%'),('complete_flush','value','medium'):('check','натс → 80%'),('complete_flush','value','small'):(0.33,'натс → 80%'),('complete_flush','value','check'):(0.5,'натс → 80%'),
    ('complete_flush','medium','large'):('check',''),('complete_flush','medium','medium'):('check',''),('complete_flush','medium','small'):('check',''),('complete_flush','medium','check'):('check',''),
    ('complete_flush','air','large'):('check',''),('complete_flush','air','medium'):('check','блокеры → 50%'),('complete_flush','air','small'):('check','блокеры → 50%'),('complete_flush','air','check'):('check','блокеры → 50%'),
}

_RIVER_CALLER_TABLE = {
    ('blank','value','bb'):'check_raise',('blank','value','bc'):'donk_66',('blank','value','cb'):'check_raise',('blank','value','cc'):'donk_66',
    ('blank','medium','bb'):'check_call_fold',('blank','medium','bc'):'check_call',('blank','medium','cb'):'check_call',('blank','medium','cc'):'check_call',
    ('blank','air','bb'):'check_fold',('blank','air','bc'):'donk_66',('blank','air','cb'):'check_fold',('blank','air','cc'):'donk_66',
    ('overcard','value','bb'):'check_raise',('overcard','value','bc'):'donk_50',('overcard','value','cb'):'check_raise',('overcard','value','cc'):'donk_50',
    ('overcard','medium','bb'):'check_fold',('overcard','medium','bc'):'check_call',('overcard','medium','cb'):'check_call',('overcard','medium','cc'):'check_call',
    ('overcard','air','bb'):'check_fold',('overcard','air','bc'):'donk_50',('overcard','air','cb'):'check_fold',('overcard','air','cc'):'donk_66',
    ('pair_top','value','bb'):'check_raise',('pair_top','value','bc'):'donk_50',('pair_top','value','cb'):'check_raise',('pair_top','value','cc'):'donk_50',
    ('pair_top','medium','bb'):'check_fold',('pair_top','medium','bc'):'check_call_fold',('pair_top','medium','cb'):'check_fold',('pair_top','medium','cc'):'check_call',
    ('pair_top','air','bb'):'check_fold',('pair_top','air','bc'):'check_fold',('pair_top','air','cb'):'check_fold',('pair_top','air','cc'):'donk_50',
    ('pair_low','value','bb'):'check_raise',('pair_low','value','bc'):'donk_66',('pair_low','value','cb'):'check_raise',('pair_low','value','cc'):'donk_66',
    ('pair_low','medium','bb'):'check_call',('pair_low','medium','bc'):'donk_33',('pair_low','medium','cb'):'check_call',('pair_low','medium','cc'):'donk_33',
    ('pair_low','air','bb'):'check_fold',('pair_low','air','bc'):'donk_50',('pair_low','air','cb'):'donk_50',('pair_low','air','cc'):'donk_50',
    ('complete_oesd','value','bb'):'check_raise',('complete_oesd','value','bc'):'donk_66',('complete_oesd','value','cb'):'check_raise',('complete_oesd','value','cc'):'donk_66',
    ('complete_oesd','medium','bb'):'check_fold',('complete_oesd','medium','bc'):'check_fold',('complete_oesd','medium','cb'):'check_fold',('complete_oesd','medium','cc'):'check_fold',
    ('complete_oesd','air','bb'):'check_fold',('complete_oesd','air','bc'):'donk_50',('complete_oesd','air','cb'):'check_fold',('complete_oesd','air','cc'):'donk_50',
    ('complete_gutshot','value','bb'):'check_raise',('complete_gutshot','value','bc'):'donk_66',('complete_gutshot','value','cb'):'check_raise',('complete_gutshot','value','cc'):'donk_66',
    ('complete_gutshot','medium','bb'):'check_fold',('complete_gutshot','medium','bc'):'check_call',('complete_gutshot','medium','cb'):'check_fold',('complete_gutshot','medium','cc'):'check_call',
    ('complete_gutshot','air','bb'):'check_fold',('complete_gutshot','air','bc'):'donk_50',('complete_gutshot','air','cb'):'donk_50',('complete_gutshot','air','cc'):'donk_50',
    ('complete_combo','value','bb'):'check_raise',('complete_combo','value','bc'):'donk_50',('complete_combo','value','cb'):'check_raise',('complete_combo','value','cc'):'donk_50',
    ('complete_combo','medium','bb'):'check_fold',('complete_combo','medium','bc'):'check_fold',('complete_combo','medium','cb'):'check_fold',('complete_combo','medium','cc'):'check_fold',
    ('complete_combo','air','bb'):'check_fold',('complete_combo','air','bc'):'check_fold',('complete_combo','air','cb'):'check_fold',('complete_combo','air','cc'):'check_fold',
    ('complete_flush','value','bb'):'check_raise',('complete_flush','value','bc'):'donk_66',('complete_flush','value','cb'):'check_raise',('complete_flush','value','cc'):'donk_66',
    ('complete_flush','medium','bb'):'check_fold',('complete_flush','medium','bc'):'check_fold',('complete_flush','medium','cb'):'check_fold',('complete_flush','medium','cc'):'check_fold',
    ('complete_flush','air','bb'):'check_fold',('complete_flush','air','bc'):'donk_66',('complete_flush','air','cb'):'check_fold',('complete_flush','air','cc'):'donk_66',
}


def _turn_size_bucket(size):
    if not size or size == 0: return 'check'
    if isinstance(size, str): return 'check'
    if size >= 0.7: return 'large'
    if size >= 0.4: return 'medium'
    return 'small'


def _norm_agg_history(hist):
    h = (hist or '').lower().strip()
    if len(h) >= 2: return h[-2:]
    if h == 'b': return 'bb'
    return 'cc'


def river_recommend(wp, pot, call_amt, board, our_hand, our_pos, flop_aggressor, turn_bet_size, agg_history, n_opp):
    if len(board) < 5 or not our_hand:
        return postflop_recommend(wp, pot, call_amt, board, our_pos, flop_aggressor, n_opp)
    flop = board[:3]; turn = board[3]; river = board[4]; pot = max(pot, 1)
    river_type = classify_turn_card(flop + [turn], river)
    hand_str = classify_hand_strength(our_hand, board)
    we_are_agg = (flop_aggressor is not None and flop_aggressor == our_pos)
    river_lbl = _TURN_TYPE_LABELS.get(river_type, 'ривер')
    hand_lbl = _HAND_STR_LABELS.get(hand_str, hand_str)

    if call_amt > 0:
        pot_odds = call_amt / (pot + call_amt) * 100
        ev = wp / 100 * (pot + call_amt) - (1 - wp / 100) * call_amt
        ev_txt = f"EV+{ev:.0f}" if ev >= 0 else f"EV{ev:.0f}"
        if wp >= pot_odds + 20 and ev > 0:
            return f"РЕЙЗ ~{int(pot*0.75)} (75%) — {river_lbl}, {hand_lbl}, {ev_txt}"
        if ev > 0:
            return f"КОЛЛ — {river_lbl}, {hand_lbl}, {ev_txt}, {wp:.0f}% vs {pot_odds:.0f}%"
        if wp >= pot_odds - 4:
            return f"КОЛЛ (граница) — {river_lbl}, {hand_lbl}, {ev_txt}"
        return f"ФОЛД — {river_lbl}, {hand_lbl}, {ev_txt}, {wp:.0f}% при пот-оддах {pot_odds:.0f}%"

    is_multi = (n_opp >= 2)
    multi_tag = " (мультипот)" if is_multi else ""
    if we_are_agg:
        bkt = _turn_size_bucket(turn_bet_size)
        action, note = _RIVER_AGG_TABLE.get((river_type, hand_str, bkt), ('check', ''))
        note_txt = f" ({note})" if note else ""
        if is_multi and isinstance(action, float):
            action = max(0.33, round(action * 0.75, 2))
        if action == 'check':
            return f"ЧЕК — {river_lbl} | {hand_lbl}{note_txt}{multi_tag}"
        bet_amt = int(pot * action)
        return f"БЕТ {int(action*100)}% банка (~{bet_amt}) — {river_lbl} | {hand_lbl}{note_txt}{multi_tag}"
    else:
        hist_key = _norm_agg_history(agg_history)
        act = _RIVER_CALLER_TABLE.get((river_type, hand_str, hist_key), 'check_fold')
        hl = {'bb':'ББ','bc':'БЧ','cb':'ЧБ','cc':'ЧЧ'}.get(hist_key, hist_key)
        if is_multi and act in ('check_call', 'donk_66', 'donk_50') and hand_str != 'value':
            act = 'check_fold'
        if act == 'check_raise':
            return f"ЧЕК-РЕЙЗ (~{int(pot*0.75)}) — {river_lbl} | {hand_lbl}, история {hl}{multi_tag}"
        elif act == 'donk_66':
            donk_pct = 55 if is_multi else 66
            return f"ДОНК {donk_pct}% (~{int(pot*donk_pct/100)}) — {river_lbl} | {hand_lbl}, история {hl}{multi_tag}"
        elif act == 'donk_50':
            return f"ДОНК 50% (~{int(pot*0.5)}) — {river_lbl} | {hand_lbl}, история {hl}{multi_tag}"
        elif act == 'donk_33':
            return f"ДОНК 33% (~{int(pot*0.33)}) — {river_lbl} | {hand_lbl}, история {hl}{multi_tag}"
        elif act == 'check_call':
            return f"ЧЕК → КОЛЛ — {river_lbl} | {hand_lbl}, история {hl}{multi_tag}"
        elif act == 'check_call_fold':
            return f"ЧЕК → КОЛЛ/ФОЛД по пот-оддам — {river_lbl} | {hand_lbl}, история {hl}{multi_tag}"
        else:
            return f"ЧЕК → ФОЛД при ставке — {river_lbl} | {hand_lbl}, история {hl}{multi_tag}"


def postflop_recommend(wp, pot, call_amt, board, our_pos, aggressor, n_opp):
    if pot == 0: pot = 1
    if n_opp <= 0: n_opp = 1
    tex = board_texture(board)
    cat_val = tex['cat']
    we_are_aggressor = (aggressor is not None and aggressor == our_pos)
    freq_adj = 1.0 if n_opp == 1 else (0.82 if n_opp == 2 else 0.68)

    if call_amt > 0:
        pot_odds = call_amt / (pot + call_amt) * 100
        ev = wp / 100 * (pot + call_amt) - (1 - wp / 100) * call_amt
        ev_txt = f"EV+{ev:.0f}" if ev >= 0 else f"EV{ev:.0f}"
        tex_lbl = _BOARD_LABELS.get(cat_val, 'борд')
        if wp >= pot_odds + 20 and ev > 0:
            return f"РЕЙЗ ~{int(pot*0.75)} (75% банка) — {ev_txt}, {wp:.0f}% >> пот-одды {pot_odds:.0f}%"
        if ev > 0:
            return f"КОЛЛ — {ev_txt}, {wp:.0f}% vs пот-одды {pot_odds:.0f}%"
        if wp >= pot_odds - 4:
            return f"КОЛЛ (граница) — {ev_txt}, {wp:.0f}% ≈ пот-одды {pot_odds:.0f}%"
        return f"ФОЛД — {ev_txt}, {wp:.0f}% при пот-оддах {pot_odds:.0f}%"

    gto_table = _BOARD_GTO_MULTI if n_opp >= 2 else _BOARD_GTO
    freq_agg, size_agg, freq_pas, size_pas = gto_table.get(cat_val, gto_table.get('other', (45,33,0,0)))
    multipot_note = " (мультипот)" if n_opp >= 2 else ""
    role_lbl = "агрессор" if we_are_aggressor else "коллер"
    bet_freq = (freq_agg if we_are_aggressor else freq_pas) * freq_adj / 100
    bet_size = size_agg if we_are_aggressor else size_pas
    bet_amt = int(pot * bet_size / 100)
    tex_lbl = _BOARD_LABELS.get(cat_val, 'борд')
    eq_threshold = 55 - (bet_freq - 0.35) * 50
    eq_threshold = max(25, min(65, eq_threshold))

    if tex['monotone'] and wp < 60:
        return f"ЧЕК — {tex_lbl}, монотонный борд опасен без флеша, {wp:.0f}%"
    if wp >= eq_threshold + 18:
        if tex['monotone']:
            return f"БЕТ 33% банка (~{int(pot*0.33)}) — {tex_lbl}, вероятно флеш/сильная рука{multipot_note}, {wp:.0f}%"
        return f"БЕТ {bet_size}% банка (~{bet_amt}) — {tex_lbl}, {role_lbl}{multipot_note}, {wp:.0f}% equity"
    elif wp >= eq_threshold:
        if tex['monotone'] and wp >= 60:
            return f"БЕТ 33% банка (~{int(pot*0.33)}) — {tex_lbl}, вероятно флеш{multipot_note}, {wp:.0f}%"
        if bet_freq >= 0.42:
            return f"БЕТ {bet_size}% банка (~{bet_amt}) — {tex_lbl}, {role_lbl}{multipot_note}, {wp:.0f}%"
        return f"ЧЕК — {tex_lbl} ({role_lbl}){multipot_note}, доска не для бета, {wp:.0f}%"
    elif wp >= 35:
        if we_are_aggressor and cat_val in ('ace_high_rainbow', 'king_high_rainbow') and bet_freq >= 0.5:
            bluff_size = min(bet_size, 33)
            return f"БЕТ {bluff_size}% (~{int(pot*bluff_size/100)}) или ЧЕК — {tex_lbl}, блеф-кандидат, {wp:.0f}%"
        return f"ЧЕК — {tex_lbl}, {wp:.0f}%, берём карту бесплатно"
    else:
        if we_are_aggressor and cat_val in ('ace_high_rainbow', 'king_high_rainbow', 'paired'):
            return f"БЕТ 33% (~{int(pot*0.33)}) или ЧЕК — блеф агрессора на {tex_lbl}, {wp:.0f}%"
        return f"ЧЕК — слабая рука ({wp:.0f}%), {tex_lbl}, не вкладываем"


def recommend_action(wp, ev, pot, call_amt, pos='', cards=None, is_preflop=False, bb=0, n_opp=0, opener_pos='', bet_level=1, open_specs=None):
    if pot == 0: pot = 1
    def opp_txt():
        n = n_opp
        if n <= 0: return "оппонентов"
        if n == 1: return "1 оппонент"
        if n in (2,3,4): return f"{n} оппонента"
        return f"{n} оппонентов"

    if is_preflop and cards and pos:
        decision = classify_hand_preflop(cards, pos, bb or 1, call_amt, opener_pos=opener_pos, bet_level=bet_level, open_specs=open_specs)
        if decision == 'raise':
            raise_to = max(call_amt * 3, bb * 3) if call_amt > 0 else bb * 3
            ev_raise = calc_ev_raise(wp, pot, raise_to, n_opp)
            ev_txt = f"EV+{ev_raise:.0f}" if ev_raise >= 0 else f"EV{ev_raise:.0f}"
            return f"РЕЙЗ до ~{raise_to} — рука в диапазоне открытия {pos} ({ev_txt}, {wp:.0f}% equity vs {opp_txt()})"
        if decision == '3bet':
            raise_to = max(call_amt * 3, bb * 3)
            return f"3БЕТ до ~{raise_to} — сильная рука против рейза ({wp:.0f}% vs {opp_txt()})"
        if decision == '4bet':
            raise_to = max(call_amt * 2, bb * 4)
            if bet_level >= 3:
                return f"КОЛЛ/ОЛЛ-ИН — топ-диапазон, рентабельно идти ва-банк ({wp:.0f}% vs {opp_txt()})"
            return f"4БЕТ до ~{raise_to} — топ-диапазон против 3бета ({wp:.0f}% vs {opp_txt()})"
        if decision == 'call':
            pot_odds_pct = call_amt / (pot + call_amt) * 100
            return f"КОЛЛ — рука в call-диапазоне {pos} ({wp:.0f}% vs пот-одды {pot_odds_pct:.0f}%)"
        if call_amt <= bb:
            return f"ФОЛД — рука вне диапазона открытия {pos} ({wp:.0f}% vs {opp_txt()})"
        pot_odds_pct = call_amt / (pot + call_amt) * 100
        level_txt = {1: "рейз", 2: "3-бет", 3: "4-бет"}.get(bet_level, "рейз")
        return f"ФОЛД — рука вне диапазона {pos} vs {level_txt} ({wp:.0f}% vs пот-одды {pot_odds_pct:.0f}%)"

    pot_odds_pct = call_amt / (pot + call_amt) * 100 if call_amt > 0 else 0
    if call_amt == 0:
        if wp >= 70: return f"РЕЙЗ/БЕТ — очень сильная рука ({wp:.0f}%), строим банк"
        if wp >= 55: return f"БЕТ — хорошая рука ({wp:.0f}%), строим банк"
        if wp >= 40: return f"ЧЕК — средняя рука ({wp:.0f}%), смотрим бесплатно"
        return f"ЧЕК — слабая рука ({wp:.0f}%), не вкладываем"
    else:
        margin = 4.0
        ev_pos = ev > 0
        if wp >= pot_odds_pct + 12 and ev_pos:
            return f"РЕЙЗ/КОЛЛ — EV+{ev:.0f}, {wp:.0f}% >> пот-одды {pot_odds_pct:.0f}%"
        if wp >= pot_odds_pct - margin and ev_pos:
            return f"КОЛЛ — EV+{ev:.0f}, {wp:.0f}% покрывает пот-одды {pot_odds_pct:.0f}%"
        if wp >= pot_odds_pct - margin and not ev_pos:
            return f"КОЛЛ (граница) — EV{ev:+.0f}, {wp:.0f}% ≈ пот-одды {pot_odds_pct:.0f}%"
        return f"ФОЛД — EV{ev:.0f}, {wp:.0f}% vs пот-одды {pot_odds_pct:.0f}%"


# ════════════════════════════════════════════════
#  GAME STRUCTURE
# ════════════════════════════════════════════════

def make_game():
    return {
        'state':              GameState.SETUP_RESPONSIBLE,
        'responsible_id':     None,
        'responsible_name':   None,
        'table_size':         0,
        'positions':          [],
        'button_pos':         None,
        'player_positions':   [],
        'opponent_positions': [],
        'seats':              {pos: {'type': 'empty'} for pos in ALL_POSITIONS},
        'pot':                0,
        'sb':                 0,
        'bb':                 0,
        'last_bet':           0,
        'board':              [],
        'current_turn':       None,
        'acted_this_street':  set(),
        'team_win_pct':       0.0,
        'opp_actions':        {},
        'opp_preflop_action': {},
        'preflop_aggressor':  None,
        'flop_aggressor':     None,
        'flop_bet_size':      0.0,
        'turn_bet_size':      0.0,
        'agg_history':        '',
        'known_players':      {},
        'history':            [],
        'seat_claimed':       {},
        'street_contrib':     {},
        'street_bet_to':      0,
    }


def ring_positions(game):
    """Места, участвующие в ТЕКУЩЕЙ раздаче: заняты (наш/враг) и не ожидают
    следующего раунда (pending). Пустые места (дыры) пропускаются."""
    return [p for p in game.get('positions', [])
            if game['seats'].get(p, {}).get('type') in ('our', 'opponent')
            and not game['seats'].get(p, {}).get('pending', False)]


def _button_idx(ring, game):
    bp = game.get('button_pos')
    if bp in ring:
        return ring.index(bp)
    return 0


def position_labels_map(game):
    """Покерные ярлыки (UTG/MP/CO/BU/SB/BB) по кольцу занятых мест.
    Кнопка = BU; дальше по часовой SB, BB, затем ранние позиции."""
    ring = ring_positions(game)
    m = len(ring)
    labels = {}
    if m == 0:
        return labels
    btn = _button_idx(ring, game)
    if m == 1:
        labels[ring[btn]] = 'BU'
        return labels
    if m == 2:
        labels[ring[btn]] = 'BU'              # дилер = SB в хедз-апе
        labels[ring[(btn + 1) % m]] = 'BB'
        return labels
    template = TABLE_POSITIONS.get(m, TABLE_POSITIONS[6])
    bu_t = template.index('BU')
    for i in range(m):
        seat = ring[(btn + 1 + i) % m]
        labels[seat] = template[(bu_t + 1 + i) % m]
    return labels


def blind_positions(game):
    """Физические позиции SB и BB по кольцу занятых мест."""
    ring = ring_positions(game)
    m = len(ring)
    if m < 2:
        return (None, None)
    btn = _button_idx(ring, game)
    if m == 2:
        return (ring[btn], ring[(btn + 1) % m])           # SB = дилер
    return (ring[(btn + 1) % m], ring[(btn + 2) % m])


def advance_button(game):
    """Передвинуть кнопку дилера на следующее занятое место."""
    positions = game.get('positions', [])
    occ = [p for p in positions
           if game['seats'].get(p, {}).get('type') in ('our', 'opponent')]
    if not occ:
        game['button_pos'] = None
        return
    cur = game.get('button_pos')
    if cur not in occ:
        game['button_pos'] = occ[0]
        return
    n = len(positions)
    idx = positions.index(cur)
    for k in range(1, n + 1):
        cand = positions[(idx + k) % n]
        if cand in occ:
            game['button_pos'] = cand
            return


def get_preflop_order(game):
    """Preflop: первый ходит игрок после BB (UTG), последний BB.
    Для 2 игроков: BU/SB ходит первым, BB вторым."""
    ring = ring_positions(game)
    m = len(ring)
    if m < 2:
        return ring[:]
    btn = _button_idx(ring, game)
    if m == 2:
        return [ring[btn], ring[(btn + 1) % m]]
    return [ring[(btn + i) % m] for i in range(3, 3 + m)]


def get_postflop_order(game):
    """Postflop: первый ходит SB, последний BU.
    Для 2 игроков: BB ходит первым, BU/SB вторым."""
    ring = ring_positions(game)
    m = len(ring)
    if m < 2:
        return ring[:]
    btn = _button_idx(ring, game)
    if m == 2:
        return [ring[(btn + 1) % m], ring[btn]]
    return [ring[(btn + i) % m] for i in range(1, 1 + m)]


def active_positions(game):
    return [p for p in game['positions']
            if game['seats'].get(p, {}).get('type') in ('our', 'opponent')
            and not game['seats'].get(p, {}).get('folded', False)
            and not game['seats'].get(p, {}).get('pending', False)]


def _ordered_active(game, order):
    active_set = set(active_positions(game))
    return [p for p in order if p in active_set]


def is_bb_option(game, pos):
    """BB может чекнуть если никто не рейзнул (last_bet == bb)."""
    _, bb_pos = blind_positions(game)
    return (game.get('state') == GameState.PREFLOP
            and pos == bb_pos
            and game.get('last_bet', 0) <= game.get('bb', 0))


def next_to_act(game):
    is_preflop = (game['state'] == GameState.PREFLOP)
    order  = get_preflop_order(game) if is_preflop else get_postflop_order(game)
    active = _ordered_active(game, order)
    if not active:
        return None
    active_set = set(active)
    acted  = game.get('acted_this_street', set())
    cur    = game.get('current_turn')
    if cur and cur in order:
        idx = order.index(cur)
        n   = len(order)
        ordered = [order[(idx + i) % n] for i in range(1, n + 1)
                   if order[(idx + i) % n] in active_set]
    else:
        ordered = active
    for pos in ordered:
        if pos not in acted:
            return pos
    return None


def start_preflop(game):
    bb_val = game.get('bb', 0)
    sb_val = game.get('sb', 0)
    positions = game.get('positions', [])
    n = len(positions)
    if not game.get('street_contrib'):
        game['street_contrib'] = {}
    if not game.get('street_bet_to'):
        game['street_bet_to'] = bb_val
    if not game.get('last_bet'):
        game['last_bet'] = bb_val

    # Кнопка дилера должна стоять на занятом месте
    if game.get('button_pos') not in ring_positions(game):
        advance_button(game)

    # Определяем SB/BB по кольцу занятых мест
    sb_pos, bb_pos = blind_positions(game)

    if sb_pos and sb_pos not in game['street_contrib']:
        game['street_contrib'][sb_pos] = sb_val
    if bb_pos and bb_pos not in game['street_contrib']:
        game['street_contrib'][bb_pos] = bb_val

    already_acted = set()
    for pos, act in game.get('opp_actions', {}).items():
        if act:
            already_acted.add(pos)
    game['acted_this_street'] = already_acted
    order = get_preflop_order(game)
    active = [p for p in order
              if p not in already_acted
              and game['seats'].get(p, {}).get('type') in ('our', 'opponent')
              and not game['seats'].get(p, {}).get('folded', False)
              and not game['seats'].get(p, {}).get('pending', False)]
    game['current_turn'] = active[0] if active else None


def start_street(game):
    if game.get('state') == GameState.TURN:
        prev = game.get('agg_history', '')
        if len(prev) == 1:
            game['agg_history'] = prev + 'c'
        elif not prev:
            game['agg_history'] = 'cc'
    game['acted_this_street'] = set()
    game['last_bet']       = 0
    game['street_bet_to']  = 0
    game['street_contrib'] = {}
    for pos, act in list(game.get('opp_actions', {}).items()):
        if act and act != 'fold':
            game.setdefault('opp_preflop_action', {})[pos] = act
    game['opp_actions'] = {p: a for p, a in game.get('opp_actions', {}).items() if a == 'fold'}
    order  = get_postflop_order(game)
    active = _ordered_active(game, order)
    game['current_turn'] = active[0] if active else None


def advance_turn(game):
    nxt = next_to_act(game)
    if nxt is None:
        game['current_turn'] = None
        return False
    game['current_turn'] = nxt
    return True


def end_street(game):
    game['current_turn'] = None
    if game['state'] == GameState.RIVER:
        game['state'] = GameState.SHOWDOWN


def to_call(game, pos):
    bet_to  = game.get('street_bet_to', game.get('last_bet', 0))
    contrib = game.get('street_contrib', {}).get(pos, 0)
    return max(0, bet_to - contrib)


def pot_add(game, pos, amount_to):
    sc = game.setdefault('street_contrib', {})
    already = sc.get(pos, 0)
    delta = max(0, amount_to - already)
    game['pot'] += delta
    sc[pos] = amount_to
    if amount_to > game.get('street_bet_to', 0):
        game['street_bet_to'] = amount_to
        game['last_bet']       = amount_to


def only_one_left(game):
    active = [p for p in game['positions']
              if game['seats'].get(p, {}).get('type') in ('our', 'opponent')
              and not game['seats'].get(p, {}).get('folded', False)
              and not game['seats'].get(p, {}).get('pending', False)]
    return len(active) <= 1


def winner_name(game):
    for p in game['positions']:
        s = game['seats'].get(p, {})
        if (s.get('type') in ('our', 'opponent') and not s.get('folded', False)
                and not s.get('pending', False)):
            if s['type'] == 'our':
                name = s['player'].get('name') or f"Д{s['player'].get('number','?')}"
                return f"{name} ({p})"
            return f"В{s['player'].get('number','?')} ({p})"
    return "?"


def add_history(game, entry):
    hist = game.setdefault('history', [])
    stage = STAGE_NAMES.get(game['state'], '')
    hist.append(f"[{stage}] {entry}" if stage else entry)
    if len(hist) > 30:
        hist.pop(0)


def reset_for_new_round(game):
    """Сброс для нового раунда. Позиции игроков НЕ меняются, двигается только дилер."""
    positions = game['positions']
    # Игроки, добавленные в прошлом раунде, со следующего раунда — в игре
    for pos in positions:
        s = game['seats'].get(pos)
        if s:
            s.pop('pending', None)
    # Ротация дилера: кнопка переходит к следующему занятому месту
    advance_button(game)

    for pos in positions:
        s = game['seats'].get(pos)
        if not s: continue
        if s['type'] == 'our':
            s['folded'] = False
            s['player']['cards'] = []
            s['player']['equity_share'] = 0.0
            s['player']['equity_delta'] = 0.0
            s['player']['ev'] = 0.0
        elif s['type'] == 'opponent':
            s['folded'] = False
    game['board'] = []
    game['pot'] = game['sb'] + game['bb']
    game['last_bet'] = game['bb']
    game['team_win_pct'] = 0.0
    game['opp_actions'] = {}
    game['opp_preflop_action'] = {}
    game['preflop_aggressor'] = None
    game['flop_aggressor'] = None
    game['flop_bet_size'] = 0.0
    game['turn_bet_size'] = 0.0
    game['agg_history'] = ''
    game['acted_this_street'] = set()
    game['history'] = []
    game['state'] = GameState.PREFLOP
    game['street_contrib'] = {}
    game['street_bet_to'] = game['bb']
    game['recommendation'] = None
    game['recommendation_pos'] = None
    start_preflop(game)


def build_seats_from_claimed(game):
    positions = game['positions']
    seats = game['seats']
    for pos in ALL_POSITIONS:
        seats[pos] = {'type': 'empty'}
    claimed = game.get('seat_claimed', {})
    members = game.get('members', {})
    our_num = 1
    for uid, pos in claimed.items():
        if pos not in positions: continue
        name = members.get(uid) or f"Д{our_num}"
        seats[pos] = {
            'type': 'our', 'folded': False,
            'player': {
                'number': our_num, 'user_id': uid, 'name': name,
                'cards': [], 'equity_share': 0.0, 'equity_delta': 0.0, 'ev': 0.0,
            }
        }
        our_num += 1
    # Стол всегда имеет 6 физических мест. Изначально занято table_size мест:
    # наши игроки + враги добиваются до table_size. Места заполняются со стороны
    # блайндов (с конца), чтобы SB/BB были заняты, а ранние места (UTG/MP)
    # оставались пустыми и доступными для досадки врагов по ходу игры (до 6).
    target = game.get('table_size') or len(positions)
    occupied = sum(1 for p in positions if seats[p].get('type') == 'our')
    for pos in reversed(positions):
        if occupied >= target:
            break
        if seats[pos].get('type') == 'empty':
            seats[pos] = {'type': 'opponent', 'folded': False, 'player': {'number': 0}}
            occupied += 1
    _renumber_opponents_engine(game)
    game['player_positions'] = [p for p in positions if seats[p].get('type') == 'our']
    game['opponent_positions'] = [p for p in positions if seats[p].get('type') == 'opponent']
    if game.get('button_pos') not in ring_positions(game):
        advance_button(game)


def _renumber_opponents_engine(game):
    """Перенумеровать врагов слева направо (В1, В2, ...)."""
    num = 1
    for pos in game.get('positions', []):
        s = game['seats'].get(pos, {})
        if s.get('type') == 'opponent':
            s.setdefault('player', {})['number'] = num
            num += 1


async def recalc(game):
    seats = game['seats']
    board = game.get('board', [])
    our_entries = []
    our_hands = []
    for pos in game.get('positions', ALL_POSITIONS):
        s = seats.get(pos)
        if s and s['type'] == 'our' and not s.get('folded', False) and not s.get('pending', False):
            cards = s['player'].get('cards', [])
            if cards and len(cards) == 2:
                our_entries.append((pos, s))
                our_hands.append(cards)
    opp_data = []
    opp_actions = game.get('opp_actions', {})
    opp_pf_actions = game.get('opp_preflop_action', {})
    is_postflop = game.get('state') not in (GameState.PREFLOP, GameState.DEALING)
    for pos in game.get('positions', ALL_POSITIONS):
        s = seats.get(pos, {})
        if s.get('type') == 'opponent' and not s.get('folded', False) and not s.get('pending', False):
            cur_act = opp_actions.get(pos, '')
            pf_act = opp_pf_actions.get(pos, '')
            opener = game.get('preflop_aggressor', '')
            opp_data.append((pos, cur_act, pf_act, board, is_postflop, opener))
    if not our_hands:
        game['team_win_pct'] = 0.0
        return
    pot = game.get('pot', 0)
    is_pf = game.get('state') == GameState.PREFLOP
    bb = game.get('bb', 0)

    # Суммы для колла по нашим рукам (для модели сговора)
    calls = []
    for pos, s in our_entries:
        c = 0 if is_bb_option(game, pos) else to_call(game, pos)
        calls.append(c)
    facing_bet = any(c > 0 for c in calls)
    use_collusion = facing_bet and len(our_hands) >= 2

    sem = _get_sim_sem()
    async with sem:
        if use_collusion:
            result = await asyncio.get_event_loop().run_in_executor(
                _SIM_EXECUTOR,
                lambda: eval_collusion_continue(our_hands, opp_data, board, pot, calls, bb)
            )
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                _SIM_EXECUTOR,
                lambda: simulate(our_hands, opp_data, board, n_sim=4000)
            )
    game['team_win_pct'] = result['team']
    n_opp_active = sum(1 for s in game['seats'].values()
                       if s.get('type') == 'opponent' and not s.get('folded', False)
                       and not s.get('pending', False))
    pf_agg_recalc = game.get('preflop_aggressor', '')
    flags = result.get('flags')
    for i, (pos, s) in enumerate(our_entries):
        wp = result['individual'][i]
        poker_label = _get_poker_label(game, pos)
        seat_call = calls[i]
        # Решение сговора (продолжать рукой или фолд) — когда есть ставка для колла
        if use_collusion and flags is not None:
            s['player']['team_continue'] = bool(flags[i])
        else:
            s['player']['team_continue'] = None
        # Диапазон открытия с учётом сговора (если это открытие)
        cards_i = s['player'].get('cards', [])
        if is_pf and seat_call <= bb and not use_collusion:
            open_specs_i = None if pf_agg_recalc else collusion_open_specs(game, pos, poker_label)
            in_open = (_hand_in_specs(cards_i, open_specs_i) if open_specs_i is not None
                       else hand_in_range(cards_i, poker_label, ''))
        else:
            in_open = False
        if in_open:
            raise_to = max(bb * 3, 150)
            ev = calc_ev_raise(wp, pot, raise_to, n_opp_active)
        else:
            ev = calc_ev(wp, pot, seat_call, poker_label)
        prev = s['player'].get('equity_share', 0.0)
        s['player']['equity_share'] = wp
        s['player']['equity_delta'] = wp - prev
        s['player']['ev'] = ev


def _get_poker_label(game, phys_pos):
    """Получить покерный ярлык (UTG/CO/BU/SB/BB) для физической позиции."""
    return position_labels_map(game).get(phys_pos, phys_pos)


def _active_opponents(game):
    """Число противников в текущей раздаче (заняты, не сфолдили, не pending)."""
    return sum(1 for p in game.get('positions', [])
               if game['seats'].get(p, {}).get('type') == 'opponent'
               and not game['seats'].get(p, {}).get('folded', False)
               and not game['seats'].get(p, {}).get('pending', False))


def _opponents_behind(game, pos):
    """Сколько противников ходят ПОСЛЕ нас на префлопе (ещё не действовали)."""
    order = get_preflop_order(game)
    if pos not in order:
        return 0
    idx = order.index(pos)
    cnt = 0
    for p in order[idx + 1:]:
        s = game['seats'].get(p, {})
        if (s.get('type') == 'opponent' and not s.get('folded', False)
                and not s.get('pending', False)):
            cnt += 1
    return cnt


def collusion_open_specs(game, pos, poker_label):
    """Диапазон открытия с учётом сговора (команда = один суперигрок).
    Возвращает spec-список или None (тогда применяется обычный диапазон позиции).

    Выбор по ЧИСЛУ противников за столом; применяется только если есть
    противник, ходящий после нас (мы «впереди» оппонента)."""
    if _opponents_behind(game, pos) < 1:
        return None
    total_opp = _active_opponents(game)
    if total_opp == 3 and poker_label in ('UTG', 'MP', 'CO'):
        return COLLUSION_OPEN_3OPP
    if total_opp == 2 and poker_label in ('UTG', 'MP', 'CO', 'BU'):
        return COLLUSION_OPEN_2OPP
    return None


def build_recommendation(game):
    """Рекомендация показывается ТОЛЬКО когда ходит наш игрок.
    Возвращает (текст, покерный_ярлык, физическая_позиция)."""
    cur = game.get('current_turn')
    if not cur:
        return None, None, None
    s = game['seats'].get(cur, {})
    if s.get('type') != 'our' or not s.get('player', {}).get('cards'):
        return None, None, None
    rec_pos = cur
    # Покерный ярлык для GTO-функций (учитывает ротацию дилера)
    poker_label = _get_poker_label(game, rec_pos)

    # Ярлык агрессора тоже переводим
    pf_agg = game.get('preflop_aggressor', '')
    pf_agg_label = _get_poker_label(game, pf_agg) if pf_agg else ''
    flop_agg = game.get('flop_aggressor', '')
    flop_agg_label = _get_poker_label(game, flop_agg) if flop_agg else ''

    p = game['seats'][rec_pos]['player']
    is_pf = game['state'] == GameState.PREFLOP
    n_opp = sum(1 for s in game['seats'].values()
                if s.get('type') == 'opponent' and not s.get('folded', False))

    # ── СГОВОР: команда = один суперигрок ──
    # Если против ставки решает модель совместного EV (какие наши руки оставить
    # в игре), используем её решение, а НЕ диапазоны «vs 3-бет» (3-бет часто
    # делают наши же игроки, и защищаться против них бессмысленно).
    team_continue = p.get('team_continue')
    if team_continue is not None:
        wp = p.get('equity_share', 0)
        rec_call = to_call(game, rec_pos)
        n_team_in = sum(1 for s2 in game['seats'].values()
                        if s2.get('type') == 'our' and not s2.get('folded', False)
                        and s2.get('player', {}).get('team_continue'))
        if team_continue:
            if wp >= 62:
                raise_to = max(rec_call * 3, game.get('bb', 0) * 3)
                rec = (f"РЕЙЗ до ~{raise_to} — сильнейшая рука команды, "
                       f"строим банк против оппонентов ({wp:.0f}% equity)")
            else:
                rec = (f"КОЛЛ {rec_call} — рука в оптимальном наборе команды "
                       f"(сговор: продолжаем {n_team_in} рук, {wp:.0f}% equity)")
        else:
            rec = (f"ФОЛД — вне оптимального набора команды: выгоднее, чтобы "
                   f"банк добирали более сильные руки напарников ({wp:.0f}% equity)")
        return rec, poker_label, rec_pos

    if is_pf:
        rec_call = to_call(game, rec_pos)
        bb_val = game.get('bb', 0) or 1
        last_bet = game.get('last_bet', 0)
        # bet_level: 1=open/first_raise, 2=3bet, 3=4bet+
        if last_bet <= bb_val:
            bet_level = 1
        elif last_bet <= bb_val * 5:
            bet_level = 2  # типичный 3-бет диапазон
        else:
            bet_level = 3  # 4-бет и выше
        # Сговор: при открытии диапазон выбирается по числу противников
        open_specs = None
        if bet_level == 1 and not pf_agg:
            open_specs = collusion_open_specs(game, rec_pos, poker_label)
        rec = recommend_action(
            p.get('equity_share', 0), p.get('ev', 0),
            game.get('pot', 0), rec_call,
            pos=poker_label, cards=p.get('cards', []),
            is_preflop=True, bb=bb_val, n_opp=n_opp,
            opener_pos=pf_agg_label, bet_level=bet_level, open_specs=open_specs)
    else:
        rec_call = to_call(game, rec_pos)
        board_b = game.get('board', [])
        if len(board_b) >= 5 and p.get('cards'):
            rec = river_recommend(
                p.get('equity_share', 0), game.get('pot', 0), rec_call,
                board_b, p.get('cards', []), our_pos=poker_label,
                flop_aggressor=flop_agg_label,
                turn_bet_size=game.get('turn_bet_size', 0),
                agg_history=game.get('agg_history', ''), n_opp=n_opp)
        elif len(board_b) >= 4 and p.get('cards'):
            rec = turn_recommend(
                p.get('equity_share', 0), game.get('pot', 0), rec_call,
                board_b, p.get('cards', []), our_pos=poker_label,
                flop_aggressor=flop_agg_label,
                flop_bet_size=game.get('flop_bet_size', 0.5), n_opp=n_opp)
        else:
            rec = postflop_recommend(
                p.get('equity_share', 0), game.get('pot', 0), rec_call,
                board_b, our_pos=poker_label,
                aggressor=pf_agg_label, n_opp=n_opp)
    return rec, poker_label, rec_pos
