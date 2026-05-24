import React from 'react'
import { useGame } from '../context/GameContext'

export default function HistoryLog() {
  const { state } = useGame()
  const history = state.history || []

  if (history.length === 0) return null

  return (
    <div className="lg:w-64 bg-gray-800 rounded-xl p-3 max-h-[400px] overflow-y-auto">
      <div className="text-xs font-semibold text-gray-400 mb-2">История</div>
      {history.map((entry, i) => (
        <div key={i} className="text-xs text-gray-300 py-0.5 border-b border-gray-700/50">
          {entry}
        </div>
      ))}
    </div>
  )
}
