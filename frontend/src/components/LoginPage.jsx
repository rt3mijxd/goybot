import React, { useState } from 'react'

function generateId() {
  return Math.random().toString(36).slice(2, 10)
}

export default function LoginPage({ onJoin }) {
  const urlSession = new URLSearchParams(window.location.search).get('session') || ''
  const [name, setName] = useState('')
  const [joinId, setJoinId] = useState(urlSession)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const createSession = async () => {
    if (!name.trim()) return setError('Введите имя')
    setLoading(true)
    try {
      const apiBase = import.meta.env.VITE_API_URL || ''
      const res = await fetch(`${apiBase}/api/session/new`, { method: 'POST' })
      const data = await res.json()
      const userId = generateId()
      onJoin(data.session_id, userId, name.trim(), 'operator')
    } catch (e) {
      setError('Ошибка создания сессии')
    }
    setLoading(false)
  }

  const joinSession = () => {
    if (!name.trim()) return setError('Введите имя')
    if (!joinId.trim()) return setError('Введите ID сессии')
    const userId = generateId()
    onJoin(joinId.trim(), userId, name.trim(), 'player')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 p-4">
      <div className="bg-gray-800 rounded-2xl p-8 w-full max-w-md shadow-2xl">
        <h1 className="text-3xl font-bold text-center mb-1">Гойбот 2.0</h1>
        <p className="text-gray-400 text-center mb-8">Mogger Edition</p>

        {error && (
          <div className="bg-red-900/50 text-red-300 px-4 py-2 rounded-lg mb-4 text-sm">
            {error}
          </div>
        )}

        <div className="mb-6">
          <label className="block text-sm text-gray-400 mb-1">Ваше имя</label>
          <input
            type="text"
            value={name}
            onChange={(e) => { setName(e.target.value); setError('') }}
            placeholder="Мойша"
            className="w-full bg-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-green-500"
            onKeyDown={(e) => e.key === 'Enter' && createSession()}
          />
        </div>

        <button
          onClick={createSession}
          disabled={loading}
          className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-lg mb-2 transition disabled:opacity-50"
        >
          {loading ? 'Создаём...' : 'Создать сессию (оператор)'}
        </button>
        <p className="text-gray-500 text-xs text-center mb-6">
          Оператор управляет столом, но не участвует в игре
        </p>

        <div className="relative mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-700" />
          </div>
          <div className="relative flex justify-center">
            <span className="bg-gray-800 px-4 text-gray-500 text-sm">присоединиться как игрок</span>
          </div>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={joinId}
            onChange={(e) => { setJoinId(e.target.value); setError('') }}
            placeholder="ID сессии"
            className="flex-1 bg-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            onKeyDown={(e) => e.key === 'Enter' && joinSession()}
          />
          <button
            onClick={joinSession}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-lg transition"
          >
            Войти
          </button>
        </div>
      </div>
    </div>
  )
}
