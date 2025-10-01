import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMachine } from '@xstate/react'

import StageRouter from './components/StageRouter'
import PreviewSurface from './components/PreviewSurface'
import ControlPanel from './components/ControlPanel'
import { sessionMachine, type SessionPhase } from './app-state/sessionMachine'
import {
  ControllerMessage,
  SocketStatus,
  useControllerSocket
} from './hooks/useControllerSocket'
import { LogEntry, LogLevel, MetricsSnapshot } from './types/dashboard'
import { backendConfig, frontendConfig } from './config'

type ControllerData = Record<string, unknown>

function getNumberField(data: ControllerData | undefined, key: string): number | undefined {
  if (!data) return undefined
  const value = data[key]
  return typeof value === 'number' ? value : undefined
}

function getBooleanField(data: ControllerData | undefined, key: string): boolean | undefined {
  if (!data) return undefined
  const value = data[key]
  return typeof value === 'boolean' ? value : undefined
}

const nowId = () => `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`

export default function App() {
  const [state, send] = useMachine(sessionMachine)

  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [connectionStatus, setConnectionStatus] = useState<SocketStatus>('connecting')
  const [lastHeartbeatTs, setLastHeartbeatTs] = useState<number | null>(null)
  const [tokenExpiryTs, setTokenExpiryTs] = useState<number | null>(null)
  const [now, setNow] = useState(Date.now())
  const [qrPayloadOverride, setQrPayloadOverride] = useState<ControllerData | null>(null)

  const {
    controllerHttpBase,
    controllerWsUrl,
    previewUrl,
    backendApiBase,
    deviceId,
    deviceAddress
  } = backendConfig
  const previewVisiblePhases = frontendConfig.previewVisiblePhases
  const controllerUrl = controllerHttpBase

  const appendLog = useCallback((message: string, level: LogLevel = 'info') => {
    setLogs((prev) => {
      const entry: LogEntry = { id: nowId(), ts: Date.now(), message, level }
      const next = [...prev, entry]
      if (next.length > 200) {
        return next.slice(next.length - 200)
      }
      return next
    })
  }, [])

  const handleStatusChange = useCallback(
    (status: SocketStatus) => {
      setConnectionStatus(status)
      if (status === 'open') {
        appendLog('Connected to controller websocket')
      } else if (status === 'closed') {
        appendLog('Controller websocket disconnected', 'error')
      }
    },
    [appendLog, send]
  )

  const handleControllerEvent = useCallback(
    (message: ControllerMessage) => {
      const { type } = message
      if (type === 'heartbeat') {
        setLastHeartbeatTs(Date.now())
        return
      }

      if (type === 'metrics') {
        const payload = message.data as ControllerData | undefined
        const stability = getNumberField(payload, 'stability')
        const focus = getNumberField(payload, 'focus')
        const composite = getNumberField(payload, 'composite')
        const instantAlive = getBooleanField(payload, 'instant_alive')
        const stableAlive = getBooleanField(payload, 'stable_alive')

        setMetrics({
          stability,
          focus,
          composite,
          instantAlive,
          stableAlive
        })
        return
      }

      if (type === 'state') {
        const payload = message.data as ControllerData | undefined
        const phase = message.phase ?? 'unknown'
        if (message.error) {
          appendLog(`Phase → ${phase} (${message.error})`, 'error')
        } else {
          appendLog(`Phase → ${phase}`)
        }
        if (payload && typeof payload.token === 'string') {
          appendLog(`Token issued: ${payload.token.slice(0, 12)}…`)
        }
        if (phase === 'qr_display' && payload && payload.qr_payload && typeof payload.qr_payload === 'object') {
          setQrPayloadOverride(payload.qr_payload as ControllerData)
        }
        if (phase === 'idle') {
          setQrPayloadOverride(null)
        }
        const expires = getNumberField(payload, 'expires_in')
        if (typeof expires === 'number') {
          setTokenExpiryTs(Date.now() + expires * 1000)
        } else {
          setTokenExpiryTs(null)
        }
        return
      }

      if (type === 'backend') {
        const payload = message.data as ControllerData | undefined
        const eventName = payload && typeof payload.event === 'string' ? payload.event : 'event'
        appendLog(`Backend → ${eventName}`)
        if (eventName === 'backend_response') {
          const status = getNumberField(payload, 'status_code')
          appendLog(`Backend response status ${status ?? 'unknown'}`)
        }
        if (eventName === 'error') {
          appendLog(String(payload?.message ?? 'Bridge error'), 'error')
        }
        return
      }

      if (type === 'watchdog') {
        const payload = message.data as ControllerData | undefined
        const action = payload && typeof payload.action === 'string' ? (payload.action as string) : 'unknown'
        const status = payload && typeof payload.status === 'string' ? (payload.status as string) : undefined
        const elapsed = getNumberField(payload, 'elapsed')
        const extras: string[] = []
        if (status) extras.push(`status=${status}`)
        if (typeof elapsed === 'number') extras.push(`elapsed=${elapsed}s`)
        if (payload && typeof payload.reason === 'string') extras.push(`reason=${payload.reason}`)
        appendLog(`Watchdog → ${action}${extras.length ? ` (${extras.join(', ')})` : ''}`)

        if (action === 'forced_idle') {
          send({ type: 'RESET' })
        }
        return
      }

      if (type === 'error') {
        appendLog(message.error ?? 'Controller reported an error', 'error')
        return
      }

      appendLog(`Event → ${type}`)
    },
    [appendLog, send]
  )

  const socketOptions = useMemo(
    () => ({
      wsUrl: controllerWsUrl,
      onEvent: handleControllerEvent,
      onStatusChange: handleStatusChange
    }),
    [controllerWsUrl, handleControllerEvent, handleStatusChange]
  )

  useControllerSocket(send, socketOptions)

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    document.body.style.backgroundColor = '#000'
    return () => {
      document.body.style.backgroundColor = ''
    }
  }, [])

  const showPreview = useMemo(() => {
    const shouldShow = previewVisiblePhases.has(state.value as SessionPhase)
    console.log('🎥 [APP PREVIEW] Phase:', state.value, '| Should show:', shouldShow, '| Phases:', Array.from(previewVisiblePhases))
    return shouldShow
  }, [previewVisiblePhases, state.value])

  const heartbeatAgeSeconds = useMemo(() => {
    if (!lastHeartbeatTs) return undefined
    return Math.max(Math.floor((now - lastHeartbeatTs) / 1000), 0)
  }, [lastHeartbeatTs, now])

  const pairingToken = state.context.token
  const qrPayload = state.context.qrPayload as ControllerData | undefined
  const expiresInSeconds = useMemo(() => {
    if (tokenExpiryTs) {
      const remaining = Math.floor((tokenExpiryTs - now) / 1000)
      return remaining > 0 ? remaining : 0
    }
    if (typeof state.context.expiresIn === 'number') {
      return Math.max(Math.floor(state.context.expiresIn), 0)
    }
    return undefined
  }, [state.context.expiresIn, tokenExpiryTs, now])

  useEffect(() => {
    if (state.matches('qr_display')) {
      appendLog('QR code displayed – waiting for mobile activation')
    }
  }, [state, appendLog])

  return (
    <div className="app-shell">
      <div className="visual-area">
        <StageRouter
          state={state}
          qrPayload={qrPayloadOverride ?? qrPayload}
        />
        <PreviewSurface
          visible={showPreview}
          previewUrl={previewUrl}
        />
      </div>
      <ControlPanel
        deviceId={deviceId}
        deviceAddress={deviceAddress}
        backendUrl={backendApiBase}
        controllerUrl={controllerUrl}
        connectionStatus={connectionStatus}
        currentPhase={String(state.value)}
        pairingToken={pairingToken}
        qrPayload={qrPayloadOverride ?? qrPayload}
        expiresInSeconds={expiresInSeconds}
        lastHeartbeatSeconds={heartbeatAgeSeconds}
        metrics={metrics}
        logs={logs}
      />
    </div>
  )
}
