import { assign, createMachine } from 'xstate'

export type SessionPhase =
  | 'idle'
  | 'pairing_request'
  | 'qr_display'
  | 'waiting_activation'
  | 'human_detect'
  | 'stabilizing'
  | 'uploading'
  | 'waiting_ack'
  | 'complete'
  | 'error'

export interface SessionContext {
  token?: string
  qrPayload?: Record<string, unknown>
  expiresIn?: number
  error?: string
  lastHeartbeatTs?: number
}

export type SessionEvent =
  | {
      type: 'CONTROLLER_STATE'
      phase: SessionPhase
      data?: Record<string, unknown>
      error?: string
    }
  | { type: 'HEARTBEAT' }
  | { type: 'RESET' }

const isControllerState = (
  event: SessionEvent
): event is Extract<SessionEvent, { type: 'CONTROLLER_STATE' }> => event.type === 'CONTROLLER_STATE'

const assignSessionDetails = assign({
  token: (_ctx: SessionContext, event: SessionEvent) =>
    isControllerState(event) && typeof event.data?.token === 'string' ? (event.data.token as string) : undefined,
  qrPayload: (_ctx: SessionContext, event: SessionEvent) =>
    isControllerState(event) ? (event.data?.qr_payload as Record<string, unknown> | undefined) : undefined,
  expiresIn: (_ctx: SessionContext, event: SessionEvent) =>
    isControllerState(event) && typeof event.data?.expires_in === 'number' ? (event.data.expires_in as number) : undefined,
  error: (_ctx: SessionContext, event: SessionEvent) => (isControllerState(event) ? event.error : undefined)
})

const assignError = assign({
  error: (_ctx: SessionContext, event: SessionEvent) => (isControllerState(event) ? event.error : undefined)
})

const resetContext = assign({
  token: () => undefined,
  qrPayload: () => undefined,
  expiresIn: () => undefined,
  error: (_ctx: SessionContext, event: SessionEvent) => (isControllerState(event) ? event.error : undefined)
})

const phaseGuard = (phase: SessionPhase) => {
  return (_ctx: SessionContext, event: SessionEvent) =>
    event.type === 'CONTROLLER_STATE' && event.phase === phase
}

export const sessionMachine = createMachine<SessionContext, SessionEvent>(
  {
    id: 'session',
    predictableActionArguments: true,
    initial: 'idle',
    context: {},
    on: {
      CONTROLLER_STATE: [
        { cond: phaseGuard('idle'), target: '.idle', actions: resetContext },
        { cond: phaseGuard('pairing_request'), target: '.pairing_request' },
        { cond: phaseGuard('qr_display'), target: '.qr_display', actions: assignSessionDetails },
        { cond: phaseGuard('waiting_activation'), target: '.waiting_activation' },
        { cond: phaseGuard('human_detect'), target: '.human_detect' },
        { cond: phaseGuard('stabilizing'), target: '.stabilizing' },
        { cond: phaseGuard('uploading'), target: '.uploading' },
        { cond: phaseGuard('waiting_ack'), target: '.waiting_ack' },
        { cond: phaseGuard('complete'), target: '.complete' },
        { cond: phaseGuard('error'), target: '.error', actions: assignError }
      ],
      HEARTBEAT: {
        actions: assign({ lastHeartbeatTs: () => Date.now() })
      },
      RESET: {
        target: '.idle',
        actions: assign({ token: undefined, qrPayload: undefined, expiresIn: undefined, error: undefined })
      }
    },
    states: {
      idle: {},
      pairing_request: {},
      qr_display: {},
      waiting_activation: {},
      human_detect: {},
      stabilizing: {},
      uploading: {},
      waiting_ack: {},
      complete: {},
      error: {}
    }
  }
)
