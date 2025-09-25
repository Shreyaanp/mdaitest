import { assign, createMachine } from 'xstate'
import type { GuardArgs } from 'xstate'

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
  event: SessionEvent | undefined
): event is Extract<SessionEvent, { type: 'CONTROLLER_STATE' }> =>
  event?.type === 'CONTROLLER_STATE'

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

const phaseGuard = (phase: SessionPhase) => ({ event }: GuardArgs<SessionContext, SessionEvent>) =>
  event.type === 'CONTROLLER_STATE' && event.phase === phase

export const sessionMachine = createMachine<SessionContext, SessionEvent>(
  {
    id: 'session',
    predictableActionArguments: true,
    initial: 'idle',
    context: {},
    on: {
      CONTROLLER_STATE: [
        { guard: phaseGuard('idle'), target: '.idle', actions: resetContext },
        { guard: phaseGuard('pairing_request'), target: '.pairing_request' },
        { guard: phaseGuard('qr_display'), target: '.qr_display', actions: assignSessionDetails },
        { guard: phaseGuard('waiting_activation'), target: '.waiting_activation' },
        { guard: phaseGuard('human_detect'), target: '.human_detect' },
        { guard: phaseGuard('stabilizing'), target: '.stabilizing' },
        { guard: phaseGuard('uploading'), target: '.uploading' },
        { guard: phaseGuard('waiting_ack'), target: '.waiting_ack' },
        { guard: phaseGuard('complete'), target: '.complete' },
        { guard: phaseGuard('error'), target: '.error', actions: assignError }
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
