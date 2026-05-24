import React from 'react'
import { useGame } from '../context/GameContext'
import PlayerSeat from './PlayerSeat'
import Card from './Card'
import PotDisplay from './PotDisplay'

const SEAT_POSITIONS_6 = {
  UTG: { x: 15, y: 80 },
  MP:  { x: 15, y: 20 },
  CO:  { x: 50, y: 5 },
  BU:  { x: 85, y: 20 },
  SB:  { x: 85, y: 80 },
  BB:  { x: 50, y: 95 },
}

export default function PokerTable() {
  const { state } = useGame()
  const positions = state.positions || []
  const board = state.board || []
  const gs = state.state

  return (
    <div className="relative w-full" style={{ paddingTop: '50%' }}>
      <div className="absolute inset-0">
        {/* Table felt */}
        <div className="absolute inset-[10%] rounded-[50%] bg-felt shadow-[inset_0_4px_30px_rgba(0,0,0,0.5)] border-4 border-felt-dark" />

        {/* Board cards */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex gap-1.5 z-10">
          {board.map((card, i) => (
            <Card key={`${card}-${i}`} card={card} size="md" />
          ))}
          {board.length === 0 && gs && gs !== 'DEALING' && gs !== 'SHOWDOWN' && (
            <div className="text-gray-500 text-sm">Борд пуст</div>
          )}
        </div>

        {/* Pot */}
        <PotDisplay />

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
