import React, { useEffect, useState } from 'react'
import { useGame } from '../context/GameContext'
import useGameSocket from '../hooks/useGameSocket'
import SetupPanel from './SetupPanel'
import PokerTable from './PokerTable'
import ActionPanel from './ActionPanel'
import OppActionPanel from './OppActionPanel'
import BoardPicker from './BoardPicker'
import RecommendationBox from './RecommendationBox'
import TeamStats from './TeamStats'
import HistoryLog from './HistoryLog'
import PlayerCardInput from './PlayerCardInput'
import BlindsModal from './BlindsModal'

export default function GameRoom({ sessionId, userId, userName, role }) {
  const { state, dispatch } = useGame()
  const { send, connected } = useGameSocket(sessionId, userId, dispatch)
  const [joined, setJoined] = useState(false)

  useEffect(() => {
    if (connected && !joined) {
      send({ action: 'join', name: userName, role })
      setJoined(true)
    }
  }, [connected, joined, send, userName, role])

  const gs = state.state
  const isSetup = !gs || gs === 'SETUP_RESPONSIBLE' || gs === 'SETUP_TABLE' || gs === 'SEAT_PICKING' || gs === 'SETUP_BLINDS'
  const isPlaying = gs === 'DEALING' || gs === 'PREFLOP' || gs === 'FLOP' || gs === 'TURN' || gs === 'RIVER' || gs === 'SHOWDOWN'
  const isOperator = state.is_responsible

  const members = state.members || {}
  const memberCount = Object.keys(members).length

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2 bg-gray-800/80 border-b border-gray-700 shrink-0 z-50">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold">Гойбот 2.0</h1>
          <span className="text-xs text-gray-500">ID: {sessionId}</span>
          <span className="text-xs text-gray-600">{memberCount} чел.</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-400">{userName}</span>
          {isOperator && <span className="text-xs bg-yellow-600 px-2 py-0.5 rounded">Оператор</span>}
        </div>
      </header>

      {state.error && (
        <div className="bg-red-900/50 text-red-300 px-4 py-2 text-sm text-center cursor-pointer shrink-0"
             onClick={() => dispatch({ type: 'CLEAR_ERROR' })}>
          {state.error}
        </div>
      )}

      {isSetup && <SetupPanel send={send} userId={userId} />}

      {isPlaying && (
        <div className="flex-1 flex flex-col lg:flex-row gap-2 p-2 overflow-auto">
          {/* Левая колонка: стол + панели */}
          <div className="flex-1 flex flex-col gap-2 min-w-0">
            {/* Стол — ограничен по размеру */}
            <div className="lg:max-w-[600px] w-full mx-auto">
              <PokerTable />
            </div>

            {/* ===== ОПЕРАТОР: управление ===== */}
            {isOperator && (
              <>
                {/* Раздача карт (оператор не раздаёт сам — игроки вводят, но оператор видит статус) */}
                {gs === 'DEALING' && <DealingStatus />}

                {/* Статистика + рекомендация */}
                <div className="flex gap-2 flex-wrap">
                  <TeamStats />
                  <RecommendationBox />
                </div>

                {/* Борд + действия оппонентов */}
                {gs !== 'DEALING' && (
                  <div className="flex gap-2 flex-wrap">
                    <BoardPicker send={send} />
                    <OppActionPanel send={send} />
                  </div>
                )}

                {/* Действия НАШИХ игроков (оператор отмечает) */}
                {gs !== 'DEALING' && gs !== 'SHOWDOWN' && (
                  <OperatorPlayerActions send={send} />
                )}

                {/* Кнопки управления */}
                <div className="flex gap-2 flex-wrap">
                  {gs === 'SHOWDOWN' && (
                    <button
                      onClick={() => send({ action: 'next_round' })}
                      className="flex-1 bg-yellow-600 hover:bg-yellow-700 text-white font-semibold py-2.5 rounded-lg transition text-sm"
                    >
                      Следующий раунд
                    </button>
                  )}
                  <BlindsModal send={send} currentSb={state.sb} currentBb={state.bb} />
                  <button
                    onClick={() => { if (confirm('Реконфигурация — сбросить размер стола и рассадку?')) send({ action: 'reconfigure' }) }}
                    className="bg-gray-600 hover:bg-gray-500 text-white px-4 py-2.5 rounded-lg transition text-sm"
                  >
                    Реконфиг
                  </button>
                  <button
                    onClick={() => { if (confirm('Новая игра — сбросить ВСЕ настройки?')) send({ action: 'new_game' }) }}
                    className="bg-red-700 hover:bg-red-600 text-white px-4 py-2.5 rounded-lg transition text-sm"
                  >
                    Новая игра
                  </button>
                </div>
              </>
            )}

            {/* ===== ИГРОК: свои карты + рекомендации ===== */}
            {!isOperator && (
              <>
                {/* Ввод своих карт */}
                {gs === 'DEALING' && <PlayerCardInput send={send} userId={userId} />}

                {/* Показать свои карты если уже введены */}
                {gs !== 'DEALING' && <PlayerCardInput send={send} userId={userId} />}

                {/* Рекомендации для игрока */}
                <div className="flex gap-2 flex-wrap">
                  <TeamStats />
                  <RecommendationBox />
                </div>
              </>
            )}
          </div>

          {/* Правая колонка: история */}
          <HistoryLog />
        </div>
      )}
    </div>
  )
}

/* Статус раздачи для оператора — кто уже ввёл карты */
function DealingStatus() {
  const { state } = useGame()
  const playerPositions = state.player_positions || []

  return (
    <div className="bg-gray-800 rounded-xl p-3 mx-2">
      <h3 className="text-sm font-bold mb-2">Ожидание карт игроков</h3>
      <div className="flex gap-2 flex-wrap">
        {playerPositions.map((pos) => {
          const seat = state.seats?.[pos]
          const name = seat?.player?.name || pos
          const cards = seat?.player?.cards || []
          const hasCards = cards.length === 2 && !cards.includes('??')
          return (
            <div key={pos} className={`px-3 py-2 rounded-lg text-xs font-semibold ${
              hasCards ? 'bg-green-800 text-green-200' : 'bg-gray-700 text-gray-400'
            }`}>
              {name} ({pos}) — {hasCards ? 'готов' : 'ждём...'}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* Оператор отмечает действия наших игроков */
function OperatorPlayerActions({ send }) {
  const { state } = useGame()
  const [raiseAmounts, setRaiseAmounts] = useState({})

  const playerPositions = (state.player_positions || []).filter((pos) => {
    const seat = state.seats?.[pos]
    return seat && !seat.folded
  })

  if (playerPositions.length === 0) return null

  const act = (pos, action, extra = {}) => {
    send({ action: 'player_action', position: pos, act: action, ...extra })
    setRaiseAmounts((prev) => ({ ...prev, [pos]: '' }))
  }

  return (
    <div className="bg-gray-800 rounded-xl p-3">
      <span className="text-sm font-semibold text-green-400 block mb-2">Действия наших игроков</span>
      {playerPositions.map((pos) => {
        const seat = state.seats[pos]
        const name = seat?.player?.name || pos
        const isCurrentTurn = state.current_turn === pos
        const ra = raiseAmounts[pos] || ''
        return (
          <div key={pos} className={`flex items-center gap-2 mb-2 ${isCurrentTurn ? 'bg-gray-700/50 rounded-lg p-1' : ''}`}>
            <span className={`text-xs font-bold w-20 ${isCurrentTurn ? 'text-yellow-400' : 'text-green-400'}`}>
              {name} ({pos})
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
              <div className="flex gap-0.5">
                <input
                  type="number"
                  value={ra}
                  onChange={(e) => setRaiseAmounts((prev) => ({ ...prev, [pos]: e.target.value }))}
                  placeholder="Сумма"
                  className="w-16 bg-gray-700 rounded px-1 py-1 text-white text-xs focus:outline-none"
                />
                <button onClick={() => act(pos, 'raise', { amount: parseInt(ra) || 0 })}
                  className="bg-green-700 hover:bg-green-600 text-white text-xs px-2 py-1 rounded transition">
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
