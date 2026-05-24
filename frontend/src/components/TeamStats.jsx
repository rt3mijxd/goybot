import React from 'react'
import { useGame } from '../context/GameContext'

const REC_COLORS = {
  'РЕЙЗ': 'text-orange-400',
  'КОЛЛ': 'text-blue-400',
  'ЧЕК/КОЛЛ': 'text-cyan-400',
  'ФОЛД': 'text-red-400',
}

export default function TeamStats() {
  const { state } = useGame()
  const wp = state.team_win_pct || 0
  const pot = state.pot || 0
  const perPlayerRecs = state.per_player_recs || {}

  const ourSeats = Object.entries(state.seats || {}).filter(
    ([, s]) => s?.type === 'our' && !s.folded
  )

  if (ourSeats.length === 0) return null

  return (
    <div className="bg-gray-800 rounded-xl p-3 min-w-[180px] flex-1">
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

      {/* Per-player equity + recommendation */}
      {ourSeats.length > 0 && (
        <div className="mt-2 space-y-1">
          {ourSeats.map(([pos, seat]) => {
            const player = seat.player || {}
            const name = player.name || `Д${player.number}`
            const label = state.position_labels?.[pos] || pos
            const equity = player.equity_share
            const rec = perPlayerRecs[pos]

            return (
              <div key={pos} className="flex items-center gap-2 text-xs">
                <span className="text-green-400 font-semibold w-20 truncate">{name}</span>
                <span className="text-gray-500">{label}</span>
                {equity > 0 && (
                  <span className="text-green-300 font-mono">{equity.toFixed(1)}%</span>
                )}
                {rec && (
                  <span className={`font-bold ${REC_COLORS[rec] || 'text-gray-300'}`}>
                    {rec}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
