import React from 'react'
import { motion } from 'framer-motion'
import Card from './Card'

export default function PlayerSeat({ pos, seat, isActive }) {
  if (!seat || seat.type === 'empty') {
    return (
      <div className="w-20 text-center">
        <div className="w-10 h-10 mx-auto rounded-full bg-gray-700/50 border border-gray-600 flex items-center justify-center text-gray-500 text-[10px]">
          {pos}
        </div>
      </div>
    )
  }

  const isOur = seat.type === 'our'
  const isFolded = seat.folded
  const player = seat.player || {}
  const cards = player.cards || []
  const equity = player.equity_share
  const ev = player.ev
  const delta = player.equity_delta

  const name = isOur
    ? player.name || `Д${player.number}`
    : `В${player.number}`

  return (
    <motion.div
      animate={isActive ? { scale: 1.05 } : { scale: 1 }}
      className={`w-20 text-center ${isFolded ? 'opacity-40' : ''}`}
    >
      {/* Avatar */}
      <div
        className={`w-10 h-10 mx-auto rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all ${
          isActive
            ? 'border-yellow-400 bg-yellow-900/50 ring-2 ring-yellow-400/50'
            : isOur
            ? 'border-green-500 bg-green-900/50'
            : 'border-red-500 bg-red-900/50'
        }`}
      >
        <span className="text-[10px]">{pos}</span>
      </div>

      {/* Name */}
      <div className="text-[10px] font-semibold mt-0.5 truncate">{name}</div>

      {/* Cards */}
      {cards.length > 0 && (
        <div className="flex justify-center gap-0.5 mt-0.5">
          {cards.map((c, i) => (
            <Card key={i} card={c} size="xs" />
          ))}
        </div>
      )}

      {/* Equity/EV */}
      {isOur && equity > 0 && !isFolded && (
        <div className="mt-0.5 space-y-0">
          <div className="text-[10px]">
            <span className="text-green-400 font-mono">{equity.toFixed(1)}%</span>
            {delta !== 0 && (
              <span className={`ml-0.5 text-[9px] ${delta > 0 ? 'text-green-300' : 'text-red-400'}`}>
                {delta > 0 ? '+' : ''}{delta.toFixed(1)}
              </span>
            )}
          </div>
          {ev !== 0 && (
            <div className={`text-[9px] font-mono ${ev > 0 ? 'text-green-300' : 'text-red-400'}`}>
              EV: {ev > 0 ? '+' : ''}{ev.toFixed(0)}
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}
