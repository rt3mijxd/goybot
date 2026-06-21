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
import Card from './Card'

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
              <PokerTable send={send} isOperator={isOperator} />
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

                {/* Борд: ввод новых карт когда улица завершена + правка борда в любой момент */}
                {gs !== 'SHOWDOWN' && (
                  <BoardPicker send={send} streetComplete={state.street_complete} />
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

  // Порядок по очередности хода (с бэкенда), иначе — физический порядок мест
  const order = (state.action_order && state.action_order.length)
    ? state.action_order
    : (state.positions || [])
  const currentTurn = state.current_turn
  const pot = state.pot || 0

  // Показываем все места в порядке хода (пустые — как задисейбленные с кнопкой посадить).
  // Скрываем только фолднувших.
  const shownPlayers = order.filter((pos) => {
    const seat = state.seats?.[pos]
    return seat && !seat.folded
  })

  if (shownPlayers.length === 0) return null

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

  // Пресеты рейза в % от банка (на кнопке — номинал, в скобках %)
  const raisePresets = [
    { pct: 33, mult: 0.33 },
    { pct: 50, mult: 0.5 },
    { pct: 75, mult: 0.75 },
    { pct: 100, mult: 1.0 },
    { pct: 150, mult: 1.5 },
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
      {shownPlayers.map((pos) => {
        const seat = state.seats[pos]
        const isOur = seat.type === 'our'
        const isEmpty = seat.type === 'empty'
        const isPending = !!seat.pending
        const isCurrentTurn = currentTurn === pos
        const num = seat?.player?.number || '?'
        const name = isOur
          ? (seat.player?.name || `Д${num}`)
          : `В${num}`
        const label = state.position_labels?.[pos] || pos
        const ra = raiseAmounts[pos] || ''
        const cards = (isOur && seat.player?.cards) ? seat.player.cards : []

        // Пустое место — задисейбленный ряд + кнопка посадить врага на эту позицию
        if (isEmpty) {
          return (
            <div key={pos} className="flex items-center gap-2 mb-1.5 rounded-lg p-1.5 bg-gray-900/40 border border-dashed border-gray-700">
              <span className="text-xs font-bold w-20 shrink-0 text-gray-500">
                {pos}
              </span>
              <span className="text-xs text-gray-600 italic">свободно</span>
              <button
                onClick={() => send({ action: 'toggle_seat_out', position: pos })}
                className="ml-auto bg-green-700 hover:bg-green-600 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition"
              >
                + Посадить врага на {pos}
              </button>
            </div>
          )
        }

        // Враг добавлен во время раунда — вступит в игру со следующего раунда
        if (isPending) {
          return (
            <div key={pos} className="flex items-center gap-2 mb-1.5 rounded-lg p-1.5 bg-indigo-900/20 border border-indigo-700/40">
              <span className="text-xs font-bold w-20 shrink-0 text-indigo-300">
                В{num} ({label})
              </span>
              <span className="text-xs text-indigo-400">войдёт со след. раунда</span>
              <button
                onClick={() => send({ action: 'toggle_seat_out', position: pos })}
                title="Убрать"
                className="ml-auto shrink-0 bg-red-900/60 hover:bg-red-700 text-red-300 hover:text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-red-700/60 transition"
              >
                ✕ Убрать
              </button>
            </div>
          )
        }

        return (
          <div
            key={pos}
            className={`flex items-center gap-2 mb-1.5 rounded-lg p-1.5 transition-all ${
              isCurrentTurn
                ? 'bg-yellow-900/30 ring-1 ring-yellow-500/50'
                : 'opacity-40'
            }`}
          >
            {/* Имя + карты под ним */}
            <div className="w-20 shrink-0 flex flex-col gap-0.5">
              <span className={`text-xs font-bold leading-tight ${
                isCurrentTurn
                  ? 'text-yellow-400'
                  : isOur ? 'text-green-400' : 'text-red-400'
              }`}>
                {name} ({label})
              </span>
              {isOur && (
                <div className="flex gap-0.5">
                  {cards.length === 2 && !cards.includes('??')
                    ? cards.map((c, i) => <Card key={i} card={c} size="xs" />)
                    : <span className="text-[10px] text-gray-500">нет карт</span>}
                </div>
              )}
            </div>
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
              {/* Кнопка «по совету» — точная сумма рейза из рекомендации + % банка */}
              {isCurrentTurn && state.rec_action && state.rec_action.pos === pos
                && state.rec_action.kind === 'raise' && state.rec_action.amount > 0 && (
                <button onClick={() => act(pos, 'raise', { amount: state.rec_action.amount })}
                  className="bg-green-600 hover:bg-green-500 text-white text-xs font-bold px-2 py-1 rounded ring-1 ring-green-300 transition">
                  ✓ Рейз {state.rec_action.amount}
                  {pot > 0 && <span className="font-normal opacity-80"> (≈{Math.round(state.rec_action.amount / pot * 100)}% банка)</span>}
                </button>
              )}
              {/* Пресеты: номинал + % от банка */}
              {isCurrentTurn && pot > 0 && (
                <div className="flex gap-0.5 flex-wrap">
                  {raisePresets.map((p) => {
                    const amt = Math.round(pot * p.mult)
                    return (
                      <button
                        key={p.pct}
                        onClick={() => setRaiseAmounts((prev) => ({ ...prev, [pos]: String(amt) }))}
                        className="bg-gray-700 hover:bg-gray-600 text-gray-300 text-[10px] px-1.5 py-0.5 rounded transition"
                      >
                        {amt} <span className="text-gray-500">({p.pct}%)</span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
            {/* Убрать врага со стула */}
            {!isOur && (
              <button
                onClick={() => send({ action: 'toggle_seat_out', position: pos })}
                title="Враг вышел из-за стола — убрать со стула"
                className="ml-auto shrink-0 bg-red-900/60 hover:bg-red-700 text-red-300 hover:text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-red-700/60 transition"
              >
                ✕ Убрать
              </button>
            )}
          </div>
        )
      })}
      {/* Расширить стол: добавить ещё одно место (до 6 игроков) */}
      {(state.positions || []).length < 6 && (
        <button
          onClick={() => send({ action: 'grow_table' })}
          className="mt-1 w-full bg-gray-700/60 hover:bg-gray-600 text-gray-300 text-xs font-semibold py-2 rounded-lg border border-dashed border-gray-600 transition"
        >
          + Добавить место за столом (до 6)
        </button>
      )}
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
    { pct: 33, mult: 0.33 },
    { pct: 50, mult: 0.5 },
    { pct: 75, mult: 0.75 },
    { pct: 100, mult: 1.0 },
    { pct: 150, mult: 1.5 },
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
        {/* Кнопка «по совету» — точная сумма рейза из рекомендации */}
        {state.rec_action && state.rec_action.pos === myPos
          && state.rec_action.kind === 'raise' && state.rec_action.amount > 0 && (
          <button onClick={() => act('raise', { amount: state.rec_action.amount })}
            className="bg-green-600 hover:bg-green-500 text-white text-sm font-bold px-3 py-2 rounded-lg ring-2 ring-green-300 transition">
            ✓ Рейз {state.rec_action.amount}
            {pot > 0 && <span className="font-normal opacity-80"> (≈{Math.round(state.rec_action.amount / pot * 100)}% банка)</span>}
          </button>
        )}
      </div>
      {pot > 0 && (
        <div className="flex gap-1 justify-center mt-2 flex-wrap">
          {raisePresets.map((p) => {
            const amt = Math.round(pot * p.mult)
            return (
              <button
                key={p.pct}
                onClick={() => setRaiseAmount(String(amt))}
                className="bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs px-2 py-1 rounded transition"
              >
                {amt} <span className="text-gray-500">({p.pct}%)</span>
              </button>
            )
          })}
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
