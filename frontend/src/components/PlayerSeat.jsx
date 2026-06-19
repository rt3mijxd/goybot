import React from 'react'
import { motion } from 'framer-motion'
import Card from './Card'

export default function PlayerSeat({ pos, seat, isActive, label, onToggleSeat = null }) {
  const displayLabel = label || pos

  if (!seat || seat.type === 'empty') {
    // Пустое место — оператор может посадить врага кликом
    if (onToggleSeat) {
      return (
        <button onClick={onToggleSeat} title="Посадить врага" className="w-20 text-center group">
          <div className="w-10 h-10 mx-auto rounded-full bg-gray-700/40 border border-dashed border-gray-600 flex items-center justify-center text-gray-500 group-hover:border-green-400 group-hover:text-green-400 group-hover:bg-green-900/30 transition">
            <span className="text-base font-bold">+</span>
          </div>
          <div className="text-[9px] text-gray-600 group-hover:text-green-400 transition">{displayLabel}</div>
        </button>
      )
    }
    return (
      <div className="w-20 text-center">
        <div className="w-10 h-10 mx-auto rounded-full bg-gray-700/50 border border-gray-600 flex items-center justify-center text-gray-500 text-[10px]">
          {displayLabel}
        </div>
      </div>
    )
  }

  const isOur = seat.type === 'our'
  const isFolded = seat.folded
  const isPending = !!seat.pending
  const player = seat.player || {}
  const cards = player.cards || []
  const equity = player.equity_share
  const ev = player.ev
  const delta = player.equity_delta

  const name = isOur
    ? player.name || `Д${player.number}`
    : `В${player.number}`

  // Оператор может убрать врага со стула прямо со стола
  const canRemove = !!onToggleSeat && !isOur

  return (
    <motion.div
      animate={isActive ? { scale: 1.05 } : { scale: 1 }}
      className={`w-20 text-center relative ${isFolded || isPending ? 'opacity-40' : ''}`}
    >
      {/* Avatar */}
      <div
        className={`w-10 h-10 mx-auto rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all relative ${
          isActive
            ? 'border-yellow-400 bg-yellow-900/50 ring-2 ring-yellow-400/50'
            : isOur
            ? 'border-green-500 bg-green-900/50'
            : 'border-red-500 bg-red-900/50'
        }`}
      >
        <span className="text-[10px]">{displayLabel}</span>
        {canRemove && (
          <button
            onClick={onToggleSeat}
            title="Убрать врага со стула"
            className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-red-700 hover:bg-red-500 text-white text-[9px] font-bold flex items-center justify-center border border-red-300 shadow z-30"
          >
            ✕
          </button>
        )}
      </div>

      {/* Name */}
      <div className="text-[10px] font-semibold mt-0.5 truncate">{name}</div>
      {isPending && <div className="text-[8px] text-indigo-300">ждёт</div>}

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
