import React, { useState, useCallback } from 'react'
import { useGame } from '../context/GameContext'

export default function SetupPanel({ send, userId, sessionId }) {
  const { state } = useGame()
  const gs = state.state

  if (gs === 'SETUP_RESPONSIBLE' || !gs) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400 text-lg">Ожидание оператора...</p>
      </div>
    )
  }

  if (gs === 'SETUP_TABLE') {
    if (state.is_responsible) return <TableSizeSelector send={send} />
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="text-center">
          <p className="text-gray-400 text-lg mb-2">Оператор настраивает стол...</p>
          <p className="text-gray-500 text-sm">Ожидайте выбора мест</p>
        </div>
      </div>
    )
  }

  if (gs === 'SEAT_PICKING') {
    return <SeatPickerTable send={send} userId={userId} sessionId={sessionId} />
  }

  if (gs === 'SETUP_BLINDS') {
    if (state.is_responsible) return <BlindsInput send={send} />
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400">Оператор устанавливает блайнды...</p>
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

/* Рассадка — визуальный стол */
const SEAT_POSITIONS_6 = {
  UTG: { x: 15, y: 75 },
  MP:  { x: 15, y: 25 },
  CO:  { x: 50, y: 5 },
  BU:  { x: 85, y: 25 },
  SB:  { x: 85, y: 75 },
  BB:  { x: 50, y: 95 },
}

function SeatPickerTable({ send, userId, sessionId }) {
  const { state } = useGame()
  const [copied, setCopied] = useState(false)
  const positions = state.positions || []
  const claimedMap = state.seat_claimed || {}
  const isOperator = state.is_responsible
  const hasClaimed = Object.keys(claimedMap).length > 0

  // Какое место занял текущий юзер
  const myPos = Object.entries(claimedMap).find(([, v]) => v.user_id === userId)?.[0]

  const copyLink = useCallback(() => {
    const url = `${window.location.origin}?session=${sessionId}`
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [sessionId])

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 gap-4">
      <h2 className="text-xl font-bold">Выберите места</h2>
      <p className="text-gray-400 text-sm">
        {isOperator && state.test_mode
          ? 'Нажмите на места, где сидят наши игроки. Остальные — враги.'
          : isOperator
          ? 'Игроки выбирают места. Нажмите «Подтвердить» когда все сядут.'
          : 'Нажмите на место за столом чтобы занять его'}
      </p>

      {/* Ссылка на сессию */}
      <button
        onClick={copyLink}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition ${
          copied
            ? 'bg-green-700 text-green-200'
            : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
        }`}
      >
        <span>{copied ? '✓ Скопировано!' : '📋 Скопировать ссылку на сессию'}</span>
      </button>

      {/* Визуальный стол для рассадки */}
      <div className="relative w-full max-w-[460px] mx-auto" style={{ paddingTop: 'min(55%, 250px)' }}>
        <div className="absolute inset-0">
          <div className="absolute inset-[10%] rounded-[50%] bg-felt shadow-[inset_0_4px_30px_rgba(0,0,0,0.5)] border-4 border-felt-dark" />

          {positions.map((pos) => {
            const coords = SEAT_POSITIONS_6[pos]
            if (!coords) return null
            const claimed = claimedMap[pos]
            const isMine = myPos === pos
            return (
              <button
                key={pos}
                onClick={() => {
                  if (!isOperator || state.test_mode) {
                    send({ action: 'claim_seat', position: pos })
                  }
                }}
                disabled={isOperator && !state.test_mode}
                className="absolute -translate-x-1/2 -translate-y-1/2 z-20"
                style={{ left: `${coords.x}%`, top: `${coords.y}%` }}
              >
                <div
                  className={`w-16 h-16 rounded-full flex flex-col items-center justify-center text-sm font-bold border-2 transition-all cursor-pointer
                    ${isMine
                      ? 'border-green-400 bg-green-600 ring-2 ring-green-400/50 text-white'
                      : claimed
                      ? 'border-blue-400 bg-blue-700 text-white'
                      : 'border-gray-500 bg-gray-700/80 text-gray-300 hover:bg-gray-600 hover:border-gray-400'
                    }
                  `}
                >
                  <span className="text-xs font-bold">{pos}</span>
                  {claimed && <span className="text-[10px] mt-0.5 truncate max-w-[50px]">{claimed.name}</span>}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Информация и кнопки */}
      <div className="text-center text-sm text-gray-400">
        {!isOperator && !myPos && <span>Нажмите на свободное место</span>}
        {!isOperator && myPos && <span>Вы заняли место {myPos}. Нажмите ещё раз чтобы убрать.</span>}
      </div>

      {isOperator && (
        <button
          onClick={() => send({ action: 'confirm_seats' })}
          disabled={!hasClaimed}
          className="bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white font-semibold py-3 px-8 rounded-lg transition"
        >
          Подтвердить рассадку
        </button>
      )}
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
        <button
          onClick={() => send({ action: 'skip_blinds' })}
          className="w-full mt-2 bg-gray-600 hover:bg-gray-500 text-gray-300 font-semibold py-2.5 rounded-lg transition text-sm"
        >
          Пропустить (ввести позже)
        </button>
      </div>
    </div>
  )
}
