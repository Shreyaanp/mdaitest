import { useState, useEffect, useRef } from 'react'
import type { StateFrom } from 'xstate'
import { sessionMachine, type SessionPhase } from '../app-state/sessionMachine'
import ErrorOverlay from './ErrorOverlay'
import IdleScreen, { IDLE_EXIT_DURATION_MS } from './IdleScreen'
import InstructionStage from './InstructionStage'
import QRCodeStage from './QRCodeStage'
import { frontendConfig } from '../config'
import type { TVBarsMode } from './TVBars'

interface StageRouterProps {
  state: StateFrom<typeof sessionMachine>
  qrPayload?: Record<string, unknown> | null
}

export default function StageRouter({ state, qrPayload }: StageRouterProps) {
  const currentPhase = state.value as SessionPhase
  const previousPhaseRef = useRef<SessionPhase>(currentPhase)
  const [isExiting, setIsExiting] = useState(false)
  const [exitFromPhase, setExitFromPhase] = useState<SessionPhase | null>(null)
  
  console.log('🎬 [STAGE ROUTER] Phase:', currentPhase, '| Exiting:', isExiting)
  
  // Detect transitions OUT of idle state and trigger exit animation
  useEffect(() => {
    const prev = previousPhaseRef.current
    const curr = currentPhase
    
    // If we're leaving idle state, trigger exit animation
    if (prev === 'idle' && curr !== 'idle') {
      console.log('🎬 [STAGE ROUTER] Leaving idle → triggering exit animation')
      setIsExiting(true)
      setExitFromPhase('idle')
      
      // Clear exit state after animation completes
      const timer = setTimeout(() => {
        setIsExiting(false)
        setExitFromPhase(null)
      }, IDLE_EXIT_DURATION_MS)
      
      return () => clearTimeout(timer)
    }
    
    previousPhaseRef.current = curr
  }, [currentPhase])
  
  // If we're in exit animation, show the exiting screen
  if (isExiting && exitFromPhase === 'idle') {
    console.log('🎬 [STAGE ROUTER] Playing exit animation from idle')
    return <IdleScreen mode="exit" showBars={true} />
  }

  // Error state
  if (state.matches('error')) {
    return <ErrorOverlay message={state.context.error ?? 'Unknown error'} />
  }

  // Idle state
  if (state.matches('idle')) {
    return <IdleScreen mode="entry" showBars={true} />
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
  return <IdleScreen mode="entry" showBars={true} />
}