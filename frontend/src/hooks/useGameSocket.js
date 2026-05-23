import { useEffect, useRef, useCallback, useState } from 'react'

export default function useGameSocket(sessionId, userId, dispatch) {
  const wsRef = useRef(null)
  const [connected, setConnected] = useState(false)
  const reconnectTimer = useRef(null)

  const connect = useCallback(() => {
    if (!sessionId || !userId) return

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
      clearTimeout(reconnectTimer.current)
    }

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'state') {
          dispatch({ type: 'SET_STATE', payload: msg.data })
        } else if (msg.type === 'error') {
          dispatch({ type: 'SET_ERROR', payload: msg.message })
        } else if (msg.type === 'ping') {
          ws.send(JSON.stringify({ action: 'pong' }))
        }
      } catch {}
    }

    ws.onclose = () => {
      setConnected(false)
      reconnectTimer.current = setTimeout(connect, 2000)
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
