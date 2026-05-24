import React from 'react'
import { useGame } from '../context/GameContext'
import PlayerSeat from './PlayerSeat'
import Card from './Card'
import PotDisplay from './PotDisplay'

const SEAT_POSITIONS_6 = {
  UTG: { x: 15, y: 78 },
  MP:  { x: 15, y: 22 },
  CO:  { x: 50, y: 8 },
  BU:  { x: 85, y: 22 },
  SB:  { x: 85, y: 78 },
  BB:  { x: 50, y: 92 },
}

/* Смещения для фишек — рядом с кружком игрока, ближе к центру стола */
const CHIP_OFFSETS = {
  UTG: { dx: 8, dy: -6 },
  MP:  { dx: 8, dy: 6 },
  CO:  { dx: 0, dy: 8 },
  BU:  { dx: -8, dy: 6 },
  SB:  { dx: -8, dy: -6 },
  BB:  { dx: 0, dy: -8 },
}

function DealerChip({ pos }) {
  const coords = SEAT_POSITIONS_6[pos]
  const off = CHIP_OFFSETS[pos] || { dx: 0, dy: 0 }
  if (!coords) return null
  return (
    <div
      className="absolute z-30 w-5 h-5 rounded-full bg-white border-2 border-gray-300 flex items-center justify-center text-[9px] font-black text-gray-800 shadow-md"
      style={{ left: `${coords.x + off.dx}%`, top: `${coords.y + off.dy}%`, transform: 'translate(-50%,-50%)' }}
    >
      D
    </div>
  )
}

function BlindChip({ pos, label, color }) {
  const coords = SEAT_POSITIONS_6[pos]
  const off = CHIP_OFFSETS[pos] || { dx: 0, dy: 0 }
  if (!coords) return null
  return (
    <div
      className={`absolute z-30 w-5 h-5 rounded-full border-2 flex items-center justify-center text-[8px] font-bold shadow-md ${color}`}
      style={{ left: `${coords.x + off.dx}%`, top: `${coords.y + off.dy}%`, transform: 'translate(-50%,-50%)' }}
    >
      {label}
    </div>
  )
}

export default function PokerTable() {
  const { state } = useGame()
  const positions = state.positions || []
  const board = state.board || []
  const gs = state.state

  return (
    <div className="relative w-full mt-8" style={{ paddingTop: 'min(58%, 320px)' }}>
      <div className="absolute inset-0">
        {/* Table felt */}
        <div className="absolute inset-[10%] rounded-[50%] bg-felt shadow-[inset_0_4px_30px_rgba(0,0,0,0.5)] border-4 border-felt-dark" />

        {/* Board cards */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex gap-1 z-10">
          {board.map((card, i) => (
            <Card key={`${card}-${i}`} card={card} size="sm" />
          ))}
          {board.length === 0 && gs && gs !== 'DEALING' && gs !== 'SHOWDOWN' && (
            <div className="text-gray-500 text-xs">Борд пуст</div>
          )}
        </div>

        {/* Pot */}
        <PotDisplay />

        {/* Dealer chip */}
        {state.dealer_pos && <DealerChip pos={state.dealer_pos} />}

        {/* Blind chips */}
        {state.sb_pos && state.sb_pos !== state.dealer_pos && (
          <BlindChip pos={state.sb_pos} label="SB" color="bg-blue-500 border-blue-300 text-white" />
        )}
        {state.bb_pos && (
          <BlindChip pos={state.bb_pos} label="BB" color="bg-yellow-500 border-yellow-300 text-gray-900" />
        )}
        {/* For 2-max: dealer is also SB — show combined chip */}
        {state.sb_pos && state.sb_pos === state.dealer_pos && (
          <BlindChip pos={state.sb_pos} label="D" color="bg-white border-blue-400 text-blue-600" />
        )}

        {/* Player seats */}
        {positions.map((pos) => {
          const coords = SEAT_POSITIONS_6[pos]
          if (!coords) return null
          const seat = state.seats?.[pos]
          return (
            <div
              key={pos}
              className="absolute -translate-x-1/2 -translate-y-1/2 z-20"
              style={{ left: `${coords.x}%`, top: `${coords.y}%` }}
            >
              <PlayerSeat pos={pos} seat={seat} isActive={state.current_turn === pos} />
            </div>
          )
        })}
      </div>
    </div>
  )
}
