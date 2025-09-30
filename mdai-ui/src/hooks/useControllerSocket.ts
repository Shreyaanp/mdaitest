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

  useEffect(() => {
    const wsUrl = options?.wsUrl ?? DEFAULT_WS_URL
    const onEvent = options?.onEvent
    const onStatusChange = options?.onStatusChange
    let cancelled = false

    const connect = () => {
      if (cancelled) return
      onStatusChange?.('connecting')
      const socket = new WebSocket(wsUrl)
      socketRef.current = socket

      socket.onopen = () => {
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
        onStatusChange?.('closed')
      }

      socket.onerror = () => {
        socket.close()
      }
    }

    connect()

    return () => {
      cancelled = true
      socketRef.current?.close()
      socketRef.current = null
      onStatusChange?.('closed')
    }
  }, [send, options?.wsUrl, options?.onEvent, options?.onStatusChange])
}
