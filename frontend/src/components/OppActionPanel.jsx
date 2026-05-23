import React, { useState } from 'react'
import { useGame } from '../context/GameContext'

export default function OppActionPanel({ send }) {
  const { state } = useGame()
  const [raiseAmount, setRaiseAmount] = useState('')

  const oppPositions = (state.opponent_positions || []).filter((pos) => {
    const seat = state.seats?.[pos]
    return seat && !seat.folded
  })

  if (oppPositions.length === 0) return null
  if (state.state === 'SHOWDOWN') return null

  const act = (pos, action, extra = {}) => {
    send({ action: 'opp_action', position: pos, act: action, ...extra })
    setRaiseAmount('')
  }

  return (
    <div className="bg-gray-800 rounded-xl p-3 flex-1">
      <span className="text-sm font-semibold text-gray-300 block mb-2">Действия оппонентов</span>
      {oppPositions.map((pos) => {
        const seat = state.seats[pos]
        const num = seat?.player?.number || '?'
        const isCurrentTurn = state.current_turn === pos
        return (
          <div key={pos} className={`flex items-center gap-2 mb-2 ${isCurrentTurn ? 'bg-gray-700/50 rounded-lg p-1' : ''}`}>
            <span className={`text-xs font-bold w-16 ${isCurrentTurn ? 'text-yellow-400' : 'text-red-400'}`}>
              В{num} ({pos})
            </span>
            <div className="flex gap-1 flex-wrap">
              <button onClick={() => act(pos, 'fold')}
                className="bg-red-800 hover:bg-red-700 text-white text-xs px-2 py-1 rounded transition">
                Фолд
              </button>
              <button onClick={() => act(pos, 'check')}
                className="bg-gray-600 hover:bg-gray-500 text-white text-xs px-2 py-1 rounded transition">
                Чек
              </button>
              <button onClick={() => act(pos, 'call')}
                className="bg-blue-700 hover:bg-blue-600 text-white text-xs px-2 py-1 rounded transition">
                Колл
              </button>
              <button onClick={() => act(pos, 'limp')}
                className="bg-gray-600 hover:bg-gray-500 text-white text-xs px-2 py-1 rounded transition">
                Лимп
              </button>
              <div className="flex gap-0.5">
                <input
                  type="number"
                  value={raiseAmount}
                  onChange={(e) => setRaiseAmount(e.target.value)}
                  placeholder="Сумма"
                  className="w-16 bg-gray-700 rounded px-1 py-1 text-white text-xs focus:outline-none"
                />
                <button onClick={() => act(pos, 'raise', { amount: parseInt(raiseAmount) || 0 })}
                  className="bg-orange-700 hover:bg-orange-600 text-white text-xs px-2 py-1 rounded transition">
                  Рейз
                </button>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
