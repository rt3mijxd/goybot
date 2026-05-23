import React, { useState } from 'react'
import { useGame } from '../context/GameContext'

export default function SetupPanel({ send, userId }) {
  const { state } = useGame()
  const gs = state.state

  if (gs === 'SETUP_RESPONSIBLE' || !gs) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400 text-lg">Ожидание подключения ведущего...</p>
      </div>
    )
  }

  if (gs === 'SETUP_TABLE' && state.is_responsible) {
    return <TableSizeSelector send={send} />
  }

  if (gs === 'SETUP_TABLE' && !state.is_responsible) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400">Ведущий настраивает стол...</p>
      </div>
    )
  }

  if (gs === 'SEAT_PICKING') {
    return <SeatPicker send={send} userId={userId} />
  }

  if (gs === 'SETUP_BLINDS') {
    if (state.is_responsible) return <BlindsInput send={send} />
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400">Ведущий устанавливает блайнды...</p>
      </div>
    )
  }

  return null
}

function TableSizeSelector({ send }) {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="bg-gray-800 rounded-2xl p-8 max-w-md w-full">
        <h2 className="text-xl font-bold mb-6 text-center">Количество мест за столом</h2>
        <div className="grid grid-cols-5 gap-3">
          {[2, 3, 4, 5, 6].map((n) => (
            <button
              key={n}
              onClick={() => send({ action: 'set_table', size: n })}
              className="bg-gray-700 hover:bg-green-600 text-white text-2xl font-bold py-4 rounded-xl transition"
            >
              {n}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function SeatPicker({ send, userId }) {
  const { state } = useGame()
  const positions = state.positions || []

  const claimed = {}
  for (const pos of positions) {
    const seat = state.seats?.[pos]
    if (seat?.type === 'our' && seat.player) {
      claimed[pos] = seat.player.name || seat.player.user_id
    }
  }

  const myPos = Object.entries(state.seats || {}).find(
    ([, s]) => s?.player?.user_id === userId
  )?.[0]

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="bg-gray-800 rounded-2xl p-8 max-w-lg w-full">
        <h2 className="text-xl font-bold mb-2 text-center">Выберите место</h2>
        <p className="text-gray-400 text-sm text-center mb-6">Остальные места станут оппонентами</p>
        <div className="grid grid-cols-3 gap-3 mb-6">
          {positions.map((pos) => {
            const isMine = pos === myPos
            const owner = claimed[pos]
            return (
              <button
                key={pos}
                onClick={() => send({ action: 'claim_seat', position: pos })}
                className={`py-4 rounded-xl text-center transition font-semibold ${
                  isMine
                    ? 'bg-green-600 text-white ring-2 ring-green-400'
                    : owner
                    ? 'bg-blue-700 text-white'
                    : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                }`}
              >
                <div className="text-lg">{pos}</div>
                {owner && <div className="text-xs mt-1 opacity-80">{owner}</div>}
              </button>
            )
          })}
        </div>
        {state.is_responsible && (
          <button
            onClick={() => send({ action: 'ready_for_blinds' })}
            disabled={!myPos}
            className="w-full bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white font-semibold py-3 rounded-lg transition"
          >
            Далее — блайнды
          </button>
        )}
      </div>
    </div>
  )
}

function BlindsInput({ send }) {
  const [sb, setSb] = useState('25')
  const [bb, setBb] = useState('50')

  const submit = () => {
    const sbVal = parseInt(sb) || 0
    const bbVal = parseInt(bb) || 0
    if (bbVal <= 0) return
    send({ action: 'set_blinds', sb: sbVal, bb: bbVal })
  }

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="bg-gray-800 rounded-2xl p-8 max-w-md w-full">
        <h2 className="text-xl font-bold mb-6 text-center">Установите блайнды</h2>
        <div className="flex gap-4 mb-6">
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-1">SB</label>
            <input
              type="number"
              value={sb}
              onChange={(e) => setSb(e.target.value)}
              className="w-full bg-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm text-gray-400 mb-1">BB</label>
            <input
              type="number"
              value={bb}
              onChange={(e) => setBb(e.target.value)}
              className="w-full bg-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
        </div>
        <div className="flex gap-2 mb-4">
          {[
            [10, 20], [25, 50], [50, 100], [100, 200]
          ].map(([s, b]) => (
            <button
              key={b}
              onClick={() => { setSb(String(s)); setBb(String(b)) }}
              className="flex-1 bg-gray-700 hover:bg-gray-600 text-sm py-2 rounded-lg transition"
            >
              {s}/{b}
            </button>
          ))}
        </div>
        <button
          onClick={submit}
          className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-lg transition"
        >
          Начать игру
        </button>
      </div>
    </div>
  )
}
