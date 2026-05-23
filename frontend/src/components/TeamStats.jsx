import React from 'react'
import { useGame } from '../context/GameContext'

export default function TeamStats() {
  const { state } = useGame()
  const wp = state.team_win_pct || 0
  const pot = state.pot || 0

  const ourSeats = Object.entries(state.seats || {}).filter(
    ([, s]) => s?.type === 'our' && !s.folded
  )

  if (ourSeats.length === 0) return null

  return (
    <div className="bg-gray-800 rounded-xl p-3 min-w-[180px]">
      <div className="text-xs text-gray-400 mb-1">Команда</div>
      <div className="flex items-baseline gap-3">
        <div>
          <span className="text-green-400 text-xl font-bold font-mono">
            {wp.toFixed(1)}%
          </span>
          <span className="text-gray-500 text-xs ml-1">equity</span>
        </div>
        <div>
          <span className="text-yellow-400 text-sm font-mono">{pot}</span>
          <span className="text-gray-500 text-xs ml-1">pot</span>
        </div>
      </div>
      <div className="mt-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-green-500 to-emerald-400 rounded-full transition-all duration-500"
          style={{ width: `${Math.min(wp, 100)}%` }}
        />
      </div>
    </div>
  )
}
