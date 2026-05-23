import React, { useState } from 'react'
import { useGame } from '../context/GameContext'

export default function ActionPanel({ send, userId }) {
  const { state } = useGame()
  const [raiseAmount, setRaiseAmount] = useState('')

  const myPos = Object.entries(state.seats || {}).find(
    ([, s]) => s?.type === 'our' && s.player?.user_id === userId && !s.folded
  )?.[0]

  if (!myPos) return null
  if (state.state === 'SHOWDOWN' || state.state === 'DEALING') return null

  const isMyTurn = state.current_turn === myPos
  const seat = state.seats[myPos]
  const bb = state.bb || 0

  const act = (action, extra = {}) => {
    send({ action: 'player_action', act: action, position: myPos, ...extra })
    setRaiseAmount('')
  }

  return (
    <div className={`bg-gray-800 rounded-xl p-3 transition ${isMyTurn ? 'ring-2 ring-yellow-400' : 'opacity-60'}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm font-semibold text-gray-300">
          {isMyTurn ? `Ваш ход (${myPos})` : `Ожидание... (${myPos})`}
        </span>
      </div>
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => act('fold')}
          disabled={!isMyTurn}
          className="bg-red-700 hover:bg-red-600 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-semibold transition"
        >
          Фолд
        </button>
        <button
          onClick={() => act('check')}
          disabled={!isMyTurn}
          className="bg-gray-600 hover:bg-gray-500 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-semibold transition"
        >
          Чек
        </button>
        <button
          onClick={() => act('call')}
          disabled={!isMyTurn}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-semibold transition"
        >
          Колл
        </button>
        <div className="flex gap-1">
          <input
            type="number"
            value={raiseAmount}
            onChange={(e) => setRaiseAmount(e.target.value)}
            placeholder={String(bb * 3)}
            className="w-20 bg-gray-700 rounded-lg px-2 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-green-500"
          />
          <button
            onClick={() => act('raise', { amount: parseInt(raiseAmount) || bb * 3 })}
            disabled={!isMyTurn}
            className="bg-green-600 hover:bg-green-500 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-semibold transition"
          >
            Рейз
          </button>
        </div>
      </div>
    </div>
  )
}
