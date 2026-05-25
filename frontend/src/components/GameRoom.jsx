import React, { useEffect, useState } from 'react'
import { useGame } from '../context/GameContext'
import useGameSocket from '../hooks/useGameSocket'
import SetupPanel from './SetupPanel'
import PokerTable from './PokerTable'
import BoardPicker from './BoardPicker'
import RecommendationBox from './RecommendationBox'
import TeamStats from './TeamStats'
import HistoryLog from './HistoryLog'
import PlayerCardInput from './PlayerCardInput'
import CardPicker from './CardPicker'
import BlindsModal from './BlindsModal'

export default function GameRoom({ sessionId, userId, userName, role, testMode }) {
  const { state, dispatch } = useGame()
  const { send, connected } = useGameSocket(sessionId, userId, dispatch)
  const [joined, setJoined] = useState(false)

  useEffect(() => {
    if (connected && !joined) {
      send({ action: 'join', name: userName, role, test_mode: !!testMode })
      setJoined(true)
    }
  }, [connected, joined, send, userName, role, testMode])

  const gs = state.state
  const isSetup = !gs || gs === 'SETUP_RESPONSIBLE' || gs === 'SETUP_TABLE' || gs === 'SEAT_PICKING' || gs === 'SETUP_BLINDS'
  const isPlaying = gs === 'PREFLOP' || gs === 'FLOP' || gs === 'TURN' || gs === 'RIVER' || gs === 'SHOWDOWN'
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

      {isSetup && <SetupPanel send={send} userId={userId} sessionId={sessionId} />}

      {isPlaying && (
        <div className="flex-1 flex flex-col lg:flex-row gap-2 p-2 overflow-auto">
          {/* Левая колонка: стол + панели */}
          <div className="flex-1 flex flex-col gap-2 min-w-0">
            {/* Стол */}
            <div className="lg:max-w-[600px] w-full mx-auto">
              <PokerTable />
            </div>

            {/* ===== ОПЕРАТОР ===== */}
            {isOperator && (
              <>
                {/* Тест-режим: ввод карт за игроков */}
                {state.test_mode && gs !== 'SHOWDOWN' && (
                  <TestCardInputs send={send} />
                )}

                {/* Статистика + рекомендация */}
                <div className="flex gap-2 flex-wrap">
                  <TeamStats />
                  <RecommendationBox />
                </div>

                {/* Единая панель действий: все игроки по порядку хода */}
                {gs !== 'SHOWDOWN' && (
                  <UnifiedActionPanel send={send} />
                )}

                {/* Борд — только когда все действия на улице завершены */}
                {gs !== 'SHOWDOWN' && state.street_complete && (
                  <BoardPicker send={send} />
                )}

                {/* Кнопки управления */}
                <div className="flex gap-2 flex-wrap">
                  {(gs === 'SHOWDOWN' || gs === 'RIVER' || gs === 'TURN' || gs === 'FLOP' || gs === 'PREFLOP') && (
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

            {/* ===== ИГРОК ===== */}
            {!isOperator && (
              <>
                <PlayerCardInput send={send} userId={userId} />

                {/* Персональная рекомендация */}
                {state.my_recommendation && (
                  <div className="bg-gradient-to-r from-purple-900/80 to-indigo-900/80 rounded-xl p-3 mx-2 border border-purple-500/30">
                    <div className="text-purple-300 text-xs font-bold mb-1">Рекомендация для вас</div>
                    <div className="text-white text-sm font-semibold whitespace-pre-line">{state.my_recommendation}</div>
                  </div>
                )}

                <div className="flex gap-2 flex-wrap">
                  <TeamStats />
                </div>

                {/* Панель действий — игрок может нажать свое действие */}
                {gs !== 'SHOWDOWN' && (
                  <PlayerActionPanel send={send} userId={userId} />
                )}
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

/* Единая панель действий — все игроки по порядку хода */
function UnifiedActionPanel({ send }) {
  const { state } = useGame()
  const [raiseAmounts, setRaiseAmounts] = useState({})

  const positions = state.positions || []
  const currentTurn = state.current_turn
  const pot = state.pot || 0

  // Все активные (не фолднувшие) игроки в порядке позиций
  const activePlayers = positions.filter((pos) => {
    const seat = state.seats?.[pos]
    return seat && seat.type !== 'empty' && !seat.folded
  })

  if (activePlayers.length === 0) return null

  const act = (pos, action, extra = {}) => {
    const seat = state.seats?.[pos]
    if (!seat) return
    if (seat.type === 'our') {
      send({ action: 'player_action', position: pos, act: action, ...extra })
    } else {
      send({ action: 'opp_action', position: pos, act: action, ...extra })
    }
    setRaiseAmounts((prev) => ({ ...prev, [pos]: '' }))
  }

  // Пресеты рейза в % от банка
  const raisePresets = [
    { label: '33%', mult: 0.33 },
    { label: '50%', mult: 0.5 },
    { label: '75%', mult: 0.75 },
    { label: '100%', mult: 1.0 },
    { label: '150%', mult: 1.5 },
  ]

  return (
    <div className="bg-gray-800 rounded-xl p-3">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm font-semibold text-gray-300">Действия игроков</span>
        {currentTurn && (
          <span className="text-xs bg-yellow-600/30 text-yellow-300 px-2 py-0.5 rounded">
            Ход: {state.position_labels?.[currentTurn] || currentTurn}
          </span>
        )}
        {!currentTurn && (
          <span className="text-xs bg-green-600/30 text-green-300 px-2 py-0.5 rounded">
            Все действия завершены
          </span>
        )}
      </div>
      {activePlayers.map((pos) => {
        const seat = state.seats[pos]
        const isOur = seat.type === 'our'
        const isCurrentTurn = currentTurn === pos
        const num = seat?.player?.number || '?'
        const name = isOur
          ? (seat.player?.name || `Д${num}`)
          : `В${num}`
        const ra = raiseAmounts[pos] || ''

        return (
          <div
            key={pos}
            className={`flex items-center gap-2 mb-1.5 rounded-lg p-1.5 transition-all ${
              isCurrentTurn
                ? 'bg-yellow-900/30 ring-1 ring-yellow-500/50'
                : 'opacity-40'
            }`}
          >
            <span className={`text-xs font-bold w-24 shrink-0 ${
              isCurrentTurn
                ? 'text-yellow-400'
                : isOur ? 'text-green-400' : 'text-red-400'
            }`}>
              {name} ({state.position_labels?.[pos] || pos})
            </span>
            <div className={`flex gap-1 flex-wrap ${!isCurrentTurn ? 'pointer-events-none' : ''}`}>
              {(() => {
                const callAmt = isCurrentTurn ? (state.call_amount || 0) : 0
                const canCheck = callAmt === 0
                return (
                  <>
                    <button onClick={() => act(pos, 'fold')}
                      disabled={!isCurrentTurn}
                      className="bg-red-800 hover:bg-red-700 disabled:opacity-30 text-white text-xs px-2 py-1 rounded transition">
                      Фолд
                    </button>
                    {canCheck ? (
                      <button onClick={() => act(pos, 'check')}
                        disabled={!isCurrentTurn}
                        className="bg-gray-600 hover:bg-gray-500 disabled:opacity-30 text-white text-xs px-2 py-1 rounded transition">
                        Чек
                      </button>
                    ) : (
                      <button onClick={() => act(pos, 'call')}
                        disabled={!isCurrentTurn}
                        className="bg-blue-700 hover:bg-blue-600 disabled:opacity-30 text-white text-xs px-2 py-1 rounded transition">
                        Колл {callAmt > 0 ? callAmt : ''}
                      </button>
                    )}
                    {!isOur && canCheck && (
                      <button onClick={() => act(pos, 'limp')}
                        disabled={!isCurrentTurn}
                        className="bg-gray-600 hover:bg-gray-500 disabled:opacity-30 text-white text-xs px-2 py-1 rounded transition">
                        Лимп
                      </button>
                    )}
                  </>
                )
              })()}
              <div className="flex gap-0.5 items-center">
                <input
                  type="number"
                  value={ra}
                  onChange={(e) => setRaiseAmounts((prev) => ({ ...prev, [pos]: e.target.value }))}
                  placeholder="Сумма"
                  disabled={!isCurrentTurn}
                  className="w-16 bg-gray-700 rounded px-1 py-1 text-white text-xs focus:outline-none disabled:opacity-30"
                />
                <button onClick={() => act(pos, 'raise', { amount: parseInt(ra) || 0 })}
                  disabled={!isCurrentTurn}
                  className="bg-orange-700 hover:bg-orange-600 disabled:opacity-30 text-white text-xs px-2 py-1 rounded transition">
                  Рейз
                </button>
              </div>
              {/* Пресеты % от банка */}
              {isCurrentTurn && pot > 0 && (
                <div className="flex gap-0.5">
                  {raisePresets.map((p) => (
                    <button
                      key={p.label}
                      onClick={() => {
                        const amt = Math.round(pot * p.mult)
                        setRaiseAmounts((prev) => ({ ...prev, [pos]: String(amt) }))
                      }}
                      className="bg-gray-700 hover:bg-gray-600 text-gray-300 text-[10px] px-1.5 py-0.5 rounded transition"
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/* Панель действий для игрока — только свой ход */
function PlayerActionPanel({ send, userId }) {
  const { state } = useGame()
  const [raiseAmount, setRaiseAmount] = useState('')

  const currentTurn = state.current_turn
  const pot = state.pot || 0

  // Найти позицию текущего игрока
  const myEntry = Object.entries(state.seats || {}).find(
    ([, s]) => s?.type === 'our' && s.player?.user_id === userId
  )
  if (!myEntry) return null

  const [myPos, mySeat] = myEntry
  const isMyTurn = currentTurn === myPos
  const label = state.position_labels?.[myPos] || myPos
  const name = mySeat.player?.name || `Д${mySeat.player?.number}`

  if (!isMyTurn) {
    if (!currentTurn) return null
    const turnLabel = state.position_labels?.[currentTurn] || currentTurn
    return (
      <div className="bg-gray-800/50 rounded-xl p-3 mx-2 text-center">
        <span className="text-xs text-gray-400">Ход: <span className="text-yellow-400 font-bold">{turnLabel}</span></span>
      </div>
    )
  }

  const act = (action, extra = {}) => {
    send({ action: 'player_action', position: myPos, act: action, ...extra })
    setRaiseAmount('')
  }

  const raisePresets = [
    { label: '33%', mult: 0.33 },
    { label: '50%', mult: 0.5 },
    { label: '75%', mult: 0.75 },
    { label: '100%', mult: 1.0 },
    { label: '150%', mult: 1.5 },
  ]

  return (
    <div className="bg-yellow-900/30 border border-yellow-500/50 rounded-xl p-3 mx-2">
      <div className="text-sm font-bold text-yellow-400 mb-2 text-center">
        Ваш ход ({label})
      </div>
      <div className="flex gap-1.5 flex-wrap justify-center">
        {(() => {
          const callAmt = state.call_amount || 0
          const canCheck = callAmt === 0
          return (
            <>
              <button onClick={() => act('fold')}
                className="bg-red-800 hover:bg-red-700 text-white text-sm px-3 py-2 rounded-lg transition font-semibold">
                Фолд
              </button>
              {canCheck ? (
                <button onClick={() => act('check')}
                  className="bg-gray-600 hover:bg-gray-500 text-white text-sm px-3 py-2 rounded-lg transition font-semibold">
                  Чек
                </button>
              ) : (
                <button onClick={() => act('call')}
                  className="bg-blue-700 hover:bg-blue-600 text-white text-sm px-3 py-2 rounded-lg transition font-semibold">
                  Колл {callAmt}
                </button>
              )}
            </>
          )
        })()}
        <div className="flex gap-1 items-center">
          <input
            type="number"
            value={raiseAmount}
            onChange={(e) => setRaiseAmount(e.target.value)}
            placeholder="Сумма"
            className="w-20 bg-gray-700 rounded px-2 py-2 text-white text-sm focus:outline-none"
          />
          <button onClick={() => act('raise', { amount: parseInt(raiseAmount) || 0 })}
            className="bg-orange-700 hover:bg-orange-600 text-white text-sm px-3 py-2 rounded-lg transition font-semibold">
            Рейз
          </button>
        </div>
      </div>
      {pot > 0 && (
        <div className="flex gap-1 justify-center mt-2">
          {raisePresets.map((p) => (
            <button
              key={p.label}
              onClick={() => setRaiseAmount(String(Math.round(pot * p.mult)))}
              className="bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs px-2 py-1 rounded transition"
            >
              {p.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/* Тест-режим: оператор вводит карты за каждого нашего игрока */
function TestCardInputs({ send }) {
  const { state } = useGame()
  const [openPos, setOpenPos] = useState(null)

  const playerPositions = state.player_positions || []
  if (playerPositions.length === 0) return null

  // Собрать все занятые карты
  const usedCards = []
  for (const [, s] of Object.entries(state.seats || {})) {
    if (s?.player?.cards) {
      for (const c of s.player.cards) {
        if (c !== '??') usedCards.push(c)
      }
    }
  }
  for (const c of (state.board || [])) usedCards.push(c)

  // Проверяем, все ли уже ввели карты
  const allHaveCards = playerPositions.every((pos) => {
    const cards = state.seats?.[pos]?.player?.cards || []
    return cards.length === 2 && !cards.includes('??')
  })

  if (allHaveCards) return null

  return (
    <div className="bg-gray-800 rounded-xl p-3">
      <h3 className="text-sm font-bold mb-2">Карты игроков (тест)</h3>
      <div className="space-y-2">
        {playerPositions.map((pos) => {
          const seat = state.seats?.[pos]
          const name = seat?.player?.name || pos
          const label = state.position_labels?.[pos] || pos
          const cards = seat?.player?.cards || []
          const hasCards = cards.length === 2 && !cards.includes('??')

          if (hasCards) {
            return (
              <div key={pos} className="flex items-center gap-2 px-2 py-1 bg-green-900/30 rounded-lg">
                <span className="text-xs text-green-400 font-semibold">{name} ({label})</span>
                <span className="text-xs text-white font-bold">{cards.join(' ')}</span>
              </div>
            )
          }

          if (openPos === pos) {
            return (
              <div key={pos} className="bg-gray-700 rounded-lg p-2">
                <div className="text-xs text-gray-300 mb-1 font-semibold">{name} ({label})</div>
                <CardPicker
                  onSelect={(picked) => {
                    send({ action: 'set_test_cards', position: pos, cards: picked })
                    setOpenPos(null)
                  }}
                  selectedCards={usedCards}
                  maxCards={2}
                  title={`Карты ${name}`}
                />
              </div>
            )
          }

          return (
            <button
              key={pos}
              onClick={() => setOpenPos(pos)}
              className="w-full text-left flex items-center gap-2 px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition"
            >
              <span className="text-xs text-gray-300 font-semibold">{name} ({label})</span>
              <span className="text-xs text-gray-500">— выбрать карты</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
