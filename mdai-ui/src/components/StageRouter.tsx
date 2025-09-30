import type { StateFrom } from 'xstate'
import { sessionMachine, type SessionPhase } from '../app-state/sessionMachine'
import ErrorOverlay from './ErrorOverlay'
import IdleScreen from './IdleScreen'
import InstructionStage from './InstructionStage'
import QRCodeStage from './QRCodeStage'
import { frontendConfig } from '../config'

interface StageRouterProps {
  state: StateFrom<typeof sessionMachine>
  qrPayload?: Record<string, unknown> | null
}

export default function StageRouter({ state, qrPayload }: StageRouterProps) {
  const currentPhase = state.value as SessionPhase

  if (state.matches('error')) {
    return <ErrorOverlay message={state.context.error ?? 'Unknown error'} />
  }

  if (state.matches('idle')) {
    return <IdleScreen mode="idle" />
  }

  if (state.matches('qr_display') || state.matches('waiting_activation')) {
    const payload = qrPayload ?? (state.context.qrPayload as Record<string, unknown> | undefined)
    const status = state.matches('waiting_activation') ? 'Waiting for activation' : undefined

    if (!payload) {
      const message = frontendConfig.stageMessages.waiting_activation ?? frontendConfig.stageMessages.qr_display
      if (message) {
        return <InstructionStage {...message} />
      }
      return <InstructionStage title="Preparing session" subtitle="Awaiting QR data" />
    }

    return (
      <QRCodeStage
        token={state.context.token}
        qrPayload={payload}
        expiresIn={state.context.expiresIn}
        status={status}
      />
    )
  }

  const message = frontendConfig.stageMessages[currentPhase]
  if (message) {
    return <InstructionStage {...message} />
  }

  if (state.matches('pairing_request')) {
    return <InstructionStage title="Preparing session" subtitle="Contacting the server" />
  }

  return <IdleScreen mode="idle" />
}
