import { useEffect, useRef } from 'react'
import type { SessionEvent, SessionPhase } from '../app-state/sessionMachine'

const DEFAULT_WS_URL = 'ws://127.0.0.1:5000/ws/ui'

export interface ControllerMessage {
  type: string
  phase?: string
  data?: Record<string, unknown>
  error?: string
}

export type SocketStatus = 'connecting' | 'open' | 'closed'

interface ControllerSocketOptions {
  wsUrl?: string
  onEvent?: (message: ControllerMessage) => void
  onStatusChange?: (status: SocketStatus) => void
}

type SendEvent = (event: SessionEvent) => void

export function useControllerSocket(send: SendEvent, options?: ControllerSocketOptions) {
  const socketRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    const wsUrl = options?.wsUrl ?? DEFAULT_WS_URL
    const onEvent = options?.onEvent
    const onStatusChange = options?.onStatusChange
    let cancelled = false
    let reconnectDelay = 1000 // Start with 1 second

    const connect = () => {
      if (cancelled) return
      
      // Clear any existing socket
      if (socketRef.current) {
        socketRef.current.close()
        socketRef.current = null
      }
      
      onStatusChange?.('connecting')
      console.log('[WebSocket] Connecting to', wsUrl)
      const socket = new WebSocket(wsUrl)
      socketRef.current = socket

      socket.onopen = () => {
        console.log('[WebSocket] Connected')
        reconnectDelay = 1000 // Reset delay on successful connection
        onStatusChange?.('open')
      }

      socket.onmessage = (event) => {
        try {
          const message: ControllerMessage = JSON.parse(event.data)
          onEvent?.(message)
          if (message.type === 'heartbeat') {
            send({ type: 'HEARTBEAT' })
            return
          }
          if (message.type === 'state' && typeof message.phase === 'string') {
            send({
              type: 'CONTROLLER_STATE',
              phase: message.phase as SessionPhase,
              data: message.data,
              error: message.error
            })
          }
        } catch (err) {
          console.error('Failed to parse controller message', err)
        }
      }

      socket.onclose = () => {
        if (cancelled) return
        console.log('[WebSocket] Disconnected, reconnecting in', reconnectDelay, 'ms')
        onStatusChange?.('closed')
        
        // Attempt to reconnect with exponential backoff
        reconnectTimerRef.current = setTimeout(() => {
          if (!cancelled) {
            reconnectDelay = Math.min(reconnectDelay * 1.5, 10000) // Max 10 seconds
            connect()
          }
        }, reconnectDelay)
      }

      socket.onerror = (err) => {
        console.error('[WebSocket] Error:', err)
        socket.close()
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      socketRef.current?.close()
      socketRef.current = null
      onStatusChange?.('closed')
    }
  }, [send, options?.wsUrl, options?.onEvent, options?.onStatusChange])
}
