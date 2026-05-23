import React, { useState, useCallback } from 'react'
import { GameProvider } from './context/GameContext'
import LoginPage from './components/LoginPage'
import GameRoom from './components/GameRoom'

export default function App() {
  const [session, setSession] = useState(null)

  const handleJoin = useCallback((sessionId, userId, name) => {
    setSession({ sessionId, userId, name })
  }, [])

  if (!session) {
    return <LoginPage onJoin={handleJoin} />
  }

  return (
    <GameProvider>
      <GameRoom
        sessionId={session.sessionId}
        userId={session.userId}
        userName={session.name}
      />
    </GameProvider>
  )
}
