import { setup } from 'xstate'

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

const sessionMachineSetup = setup({
  types: {
    context: {} as SessionContext,
    events: {} as SessionEvent
  }
})

const assignSessionDetails = sessionMachineSetup.assign({
  token: ({ event }) =>
    isControllerState(event) && typeof event.data?.token === 'string' ? (event.data.token as string) : undefined,
  qrPayload: ({ event }) =>
    isControllerState(event) ? (event.data?.qr_payload as Record<string, unknown> | undefined) : undefined,
  expiresIn: ({ event }) =>
    isControllerState(event) && typeof event.data?.expires_in === 'number' ? (event.data.expires_in as number) : undefined,
  error: ({ event }) => (isControllerState(event) ? event.error : undefined)
})

const assignError = sessionMachineSetup.assign({
  error: ({ event }) => (isControllerState(event) ? event.error : undefined)
})

const resetContext = sessionMachineSetup.assign({
  token: () => undefined,
  qrPayload: () => undefined,
  expiresIn: () => undefined,
  error: ({ event }) => (isControllerState(event) ? event.error : undefined)
})

type PhaseGuardArgs = { event: SessionEvent }

const phaseGuard = (phase: SessionPhase) => ({ event }: PhaseGuardArgs) =>
  event.type === 'CONTROLLER_STATE' && event.phase === phase

export const sessionMachine = sessionMachineSetup.createMachine({
  id: 'session',
  predictableActionArguments: true,
  initial: 'idle',
  context: {} as SessionContext,
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
      actions: sessionMachineSetup.assign({ lastHeartbeatTs: () => Date.now() })
    },
    RESET: {
      target: '.idle',
      actions: sessionMachineSetup.assign({
        token: undefined,
        qrPayload: undefined,
        expiresIn: undefined,
        error: undefined
      })
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
})
