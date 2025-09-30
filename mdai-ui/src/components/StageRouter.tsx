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
  console.log('🎬 [STAGE ROUTER] Phase:', currentPhase)

  // Error state
  if (state.matches('error')) {
    return <ErrorOverlay message={state.context.error ?? 'Unknown error'} />
  }

  // Idle state
  if (state.matches('idle')) {
    return <IdleScreen mode="idle" showBars={true} />
  }

  // Pairing/requesting token
  if (state.matches('pairing_request')) {
    return <InstructionStage title="Preparing session" subtitle="Contacting server" />
  }

  // QR code display
  if (state.matches('qr_display') || state.matches('waiting_activation')) {
    const payload = qrPayload ?? (state.context.qrPayload as Record<string, unknown> | undefined)
    const status = state.matches('waiting_activation') ? 'Waiting for activation' : undefined

    if (!payload) {
      return <InstructionStage title="Preparing session" subtitle="Loading QR code" />
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

  // Camera/preview phases - render nothing so preview is visible
  // Backend controls timing via phase durations
  if (state.matches('human_detect') || 
      state.matches('stabilizing') || 
      state.matches('uploading') || 
      state.matches('waiting_ack')) {
    console.log('🎬 [STAGE ROUTER] Camera phase - preview visible')
    return null
  }

  // Complete state
  if (state.matches('complete')) {
    return <InstructionStage title="Complete" subtitle="Thank you!" className="instruction-stage--tall" />
  }

  // Fallback
  console.log('🎬 [STAGE ROUTER] Unknown phase, showing idle')
  return <IdleScreen mode="idle" showBars={false} />
}