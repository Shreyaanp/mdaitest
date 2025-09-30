/**
 * StageRouter - Routes session phases to UI components
 * 
 * Clean, easy-to-understand routing for each phase.
 * Each phase explicitly shows what the user sees.
 */

import { useState, useEffect, useRef } from 'react'
import type { StateFrom } from 'xstate'
import { sessionMachine, type SessionPhase } from '../app-state/sessionMachine'
import ErrorOverlay from './ErrorOverlay'
import IdleScreen, { IDLE_EXIT_DURATION_MS } from './IdleScreen'
import HelloHumanHero from './HelloHumanHero'
import InstructionStage from './InstructionStage'
import QRCodeStage from './QRCodeStage'
import ProcessingScreen from './ProcessingScreen'

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
  
  // ============================================================
  // Exit Animation Handler
  // Detects when leaving idle state and plays exit animation
  // ============================================================
  useEffect(() => {
    const prev = previousPhaseRef.current
    const curr = currentPhase
    
    // If leaving idle → trigger exit animation
    if (prev === 'idle' && curr !== 'idle') {
      console.log('🎬 [STAGE ROUTER] Leaving idle → exit animation')
      setIsExiting(true)
      setExitFromPhase('idle')
      
      const timer = setTimeout(() => {
        setIsExiting(false)
        setExitFromPhase(null)
      }, IDLE_EXIT_DURATION_MS)
      
      return () => clearTimeout(timer)
    }
    
    previousPhaseRef.current = curr
  }, [currentPhase])
  
  // ============================================================
  // Phase Routing - Each phase returns a specific UI component
  // ============================================================
  
  // Exit animation (TV bars retracting)
  if (isExiting && exitFromPhase === 'idle') {
    return <IdleScreen mode="exit" showBars={true} />
  }

  // Phase 1: IDLE - TV bars at 60% (static)
  if (state.matches('idle')) {
    return <IdleScreen mode="idle" showBars={true} />
  }

  // Phase 2: PAIRING_REQUEST - TV bars falling animation (1.5s)
  if (state.matches('pairing_request')) {
    return <IdleScreen mode="exit" showBars={true} />
  }

  // Phase 3: HELLO_HUMAN - Welcome screen (2s)
  if (state.matches('hello_human')) {
    return <HelloHumanHero />
  }

  // Phase 4: QR_DISPLAY - Show QR code + "Scan to get started"
  if (state.matches('qr_display')) {
    const payload = qrPayload ?? (state.context.qrPayload as Record<string, unknown> | undefined)
    
    if (!payload) {
      return <InstructionStage title="Preparing session" subtitle="Loading QR code" />
    }

    return (
      <QRCodeStage
        token={state.context.token}
        qrPayload={payload}
        expiresIn={state.context.expiresIn}
        status="Scan this to get started"
      />
    )
  }

  // Phase 5: HUMAN_DETECT - Camera preview (3.5s validation)
  if (state.matches('human_detect')) {
    console.log('🎬 [STAGE ROUTER] Human detect - camera preview visible')
    return null  // PreviewSurface component shows camera
  }

  // Phase 6: PROCESSING - Processing animation (3-15s)
  if (state.matches('processing')) {
    return (
      <ProcessingScreen
        statusLines={['processing scan', 'please wait']}
        guidanceLines={['verifying identity', 'analyzing biometric data']}
      />
    )
  }

  // Phase 7: COMPLETE - Success screen (3s)
  if (state.matches('complete')) {
    return <InstructionStage title="Complete!" subtitle="Thank you" className="instruction-stage--tall" />
  }

  // Phase 8: ERROR - Error screen (3s)
  if (state.matches('error')) {
    return <ErrorOverlay message={state.context.error ?? 'Please try again'} />
  }

  // Fallback - should never reach here
  console.warn('🎬 [STAGE ROUTER] Unknown phase:', currentPhase, '- showing idle')
  return <IdleScreen mode="idle" showBars={true} />
}