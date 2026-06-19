import { useEffect, useRef, useCallback, useState } from 'react'

export default function useGameSocket(sessionId, userId, dispatch) {
  const wsRef = useRef(null)
  const [connected, setConnected] = useState(false)
  const reconnectTimer = useRef(null)
  const stoppedRef = useRef(false)        // сессия мертва — не переподключаемся
  const attemptsRef = useRef(0)           // для экспоненциального бэкоффа

  const connect = useCallback(() => {
    if (!sessionId || !userId || stoppedRef.current) return

    const apiBase = import.meta.env.VITE_API_URL || ''
    let url
    if (apiBase) {
      const wsBase = apiBase.replace(/^http/, 'ws')
      url = `${wsBase}/ws/${sessionId}/${userId}`
    } else {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      url = `${proto}://${window.location.host}/ws/${sessionId}/${userId}`
    }

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      attemptsRef.current = 0
      clearTimeout(reconnectTimer.current)
    }

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'state') {
          dispatch({ type: 'SET_STATE', payload: msg.data })
        } else if (msg.type === 'error') {
          dispatch({ type: 'SET_ERROR', payload: msg.message })
        } else if (msg.type === 'session_gone') {
          // Сессия не найдена/истекла (напр. сервер перезапущен) — прекращаем
          // переподключения и просим создать новую.
          stoppedRef.current = true
          dispatch({ type: 'SET_ERROR', payload: 'Сессия не найдена или истекла. Создайте новую сессию или переподключитесь по ссылке.' })
        } else if (msg.type === 'ping') {
          ws.send(JSON.stringify({ action: 'pong' }))
        }
      } catch {}
    }

    ws.onclose = () => {
      setConnected(false)
      if (stoppedRef.current) return
      // Экспоненциальный бэкофф: 1s, 2s, 4s ... до 15s максимум
      attemptsRef.current += 1
      const delay = Math.min(1000 * 2 ** (attemptsRef.current - 1), 15000)
      reconnectTimer.current = setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [sessionId, userId, dispatch])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [connect])

  const send = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  return { send, connected }
}
