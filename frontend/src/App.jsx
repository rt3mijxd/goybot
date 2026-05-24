import React, { useState, useCallback } from 'react'
import { GameProvider } from './context/GameContext'
import LoginPage from './components/LoginPage'
import GameRoom from './components/GameRoom'

export default function App() {
  const [session, setSession] = useState(null)

  const handleJoin = useCallback((sessionId, userId, name, role) => {
    setSession({ sessionId, userId, name, role })
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
        role={session.role}
      />
    </GameProvider>
  )
}
