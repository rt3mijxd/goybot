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
import DealCards from './DealCards'

export default function GameRoom({ sessionId, userId, userName }) {
  const { state, dispatch } = useGame()
  const { send, connected } = useGameSocket(sessionId, userId, dispatch)
  const [joined, setJoined] = useState(false)

  useEffect(() => {
    if (connected && !joined) {
      send({ action: 'join', name: userName })
      setJoined(true)
    }
  }, [connected, joined, send, userName])

  const gs = state.state
  const isSetup = !gs || gs === 'SETUP_RESPONSIBLE' || gs === 'SETUP_TABLE' || gs === 'SEAT_PICKING' || gs === 'SETUP_BLINDS'
  const isPlaying = gs === 'DEALING' || gs === 'PREFLOP' || gs === 'FLOP' || gs === 'TURN' || gs === 'RIVER' || gs === 'SHOWDOWN'

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      <header className="flex items-center justify-between px-4 py-2 bg-gray-800/80 border-b border-gray-700">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold">Гойбот 2.0</h1>
          <span className="text-xs text-gray-500">ID: {sessionId}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-400">{userName}</span>
          {state.is_responsible && <span className="text-xs bg-yellow-600 px-2 py-0.5 rounded">Ведущий</span>}
        </div>
      </header>

      {state.error && (
        <div className="bg-red-900/50 text-red-300 px-4 py-2 text-sm text-center cursor-pointer"
             onClick={() => dispatch({ type: 'CLEAR_ERROR' })}>
          {state.error}
        </div>
      )}

      {isSetup && <SetupPanel send={send} userId={userId} />}

      {isPlaying && (
        <div className="flex-1 flex flex-col lg:flex-row gap-2 p-2">
          <div className="flex-1 flex flex-col gap-2">
            <PokerTable />
            {gs === 'DEALING' && state.is_responsible && <DealCards send={send} />}
            <div className="flex gap-2 flex-wrap">
              <TeamStats />
              <RecommendationBox />
            </div>
            {state.is_responsible && (
              <div className="flex gap-2 flex-wrap">
                <BoardPicker send={send} />
                <OppActionPanel send={send} />
              </div>
            )}
            <ActionPanel send={send} userId={userId} />
            {gs === 'SHOWDOWN' && state.is_responsible && (
              <button
                onClick={() => send({ action: 'next_round' })}
                className="bg-yellow-600 hover:bg-yellow-700 text-white font-semibold py-3 rounded-lg transition"
              >
                Следующий раунд
              </button>
            )}
          </div>
          <HistoryLog />
        </div>
      )}
    </div>
  )
}
