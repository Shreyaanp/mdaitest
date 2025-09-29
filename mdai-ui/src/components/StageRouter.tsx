import { useEffect, useRef, useState, type MutableRefObject } from 'react'
import type { StateFrom } from 'xstate'
import { sessionMachine, type SessionPhase } from '../app-state/sessionMachine'
import ErrorOverlay from './ErrorOverlay'
import HandjetMessage from './HandjetMessage'
import IdleScreen, { IDLE_EXIT_DURATION_MS } from './IdleScreen'
import InstructionStage from './InstructionStage'
import ProcessingScreen from './ProcessingScreen'
import QRCodeStage from './QRCodeStage'
import UploadingScreen from './UploadingScreen'

interface StageRouterProps {
  state: StateFrom<typeof sessionMachine>
  qrPayload?: Record<string, unknown> | null
  processingReady?: boolean
}

const HERO_HOLD_DURATION_MS = 3000
const SCAN_PROMPT_DURATION_MS = 3000
const PROCESSING_DURATION_MS = 3000
const EMBEDDING_MESSAGE_DURATION_MS = 3000
const UPLOADING_DURATION_MS = 3000
const SCAN_COMPLETE_DURATION_MS = 3000

type ViewState =
  | 'idle'
  | 'idleExit'
  | 'heroHold'
  | 'scanPrompt'
  | 'processing'
  | 'embeddingMessage'
  | 'uploading'
  | 'scanComplete'
  | 'default'

export default function StageRouter({ state, qrPayload, processingReady = false }: StageRouterProps) {
  const [idleMode, setIdleMode] = useState<'idle' | 'exit'>(state.matches('idle') ? 'idle' : 'exit')
  const [showIdleBars, setShowIdleBars] = useState<boolean>(true)
  const [viewState, setViewState] = useState<ViewState>(state.matches('idle') ? 'idle' : 'default')

  const previousPhaseRef = useRef<SessionPhase>(state.value as SessionPhase)
  const idleTimersRef = useRef<number[]>([])
  const overlayTimersRef = useRef<number[]>([])
  const hasRunScanSequenceRef = useRef<boolean>(false)
  const hasRunProcessingSequenceRef = useRef<boolean>(false)
  const hasRunUploadingSequenceRef = useRef<boolean>(false)

  const clearTimers = (ref: MutableRefObject<number[]>) => {
    ref.current.forEach((id) => window.clearTimeout(id))
    ref.current = []
  }

  const scheduleTimer = (
    ref: MutableRefObject<number[]>,
    delay: number,
    callback: () => void
  ) => {
    const id = window.setTimeout(() => {
      ref.current = ref.current.filter((stored) => stored !== id)
      callback()
    }, delay)
    ref.current.push(id)
  }

  const resetToIdle = () => {
    clearTimers(idleTimersRef)
    clearTimers(overlayTimersRef)
    hasRunScanSequenceRef.current = false
    hasRunProcessingSequenceRef.current = false
    hasRunUploadingSequenceRef.current = false
    setViewState('idle')
    setIdleMode('idle')
    setShowIdleBars(true)
  }

  const startIdleExitSequence = () => {
    if (hasRunScanSequenceRef.current) {
      return
    }

    hasRunScanSequenceRef.current = true
    clearTimers(idleTimersRef)
    setIdleMode('exit')
    setShowIdleBars(true)
    setViewState('idleExit')

    scheduleTimer(idleTimersRef, IDLE_EXIT_DURATION_MS, () => {
      setShowIdleBars(false)
      setIdleMode('idle')
      setViewState('heroHold')

      scheduleTimer(idleTimersRef, HERO_HOLD_DURATION_MS, () => {
        setViewState('scanPrompt')
      })
    })
  }

  const startProcessingSequence = () => {
    if (hasRunProcessingSequenceRef.current) {
      return
    }

    hasRunProcessingSequenceRef.current = true
    clearTimers(overlayTimersRef)
    setViewState('processing')
  }

  const startUploadingSequence = () => {
    if (hasRunUploadingSequenceRef.current) {
      return
    }

    hasRunUploadingSequenceRef.current = true
    clearTimers(overlayTimersRef)
    setViewState('uploading')
  }

  useEffect(() => {
    const currentPhase = state.value as SessionPhase
    const previousPhase = previousPhaseRef.current

    if (currentPhase === 'idle') {
      resetToIdle()
    } else if (previousPhase === 'idle') {
      startIdleExitSequence()
    }

    if (currentPhase === 'error') {
      clearTimers(idleTimersRef)
      clearTimers(overlayTimersRef)
      setViewState('default')
    }

    if ((currentPhase === 'human_detect' || currentPhase === 'stabilizing') && processingReady) {
      startProcessingSequence()
    }

    if (currentPhase === 'uploading' || currentPhase === 'waiting_ack') {
      startUploadingSequence()
    }

    previousPhaseRef.current = currentPhase
  }, [state.value, processingReady])

  useEffect(() => {
    return () => {
      clearTimers(idleTimersRef)
      clearTimers(overlayTimersRef)
    }
  }, [])

  if (viewState === 'idle' || viewState === 'idleExit' || viewState === 'heroHold') {
    return <IdleScreen mode={idleMode} showBars={showIdleBars} />
  }

  if (viewState === 'scanPrompt') {
    return (
      <HandjetMessage
        lines={['scan this', 'to get started']}
        durationMs={SCAN_PROMPT_DURATION_MS}
        onComplete={() => setViewState('default')}
      />
    )
  }

  if (viewState === 'processing') {
    return (
      <ProcessingScreen
        durationMs={PROCESSING_DURATION_MS}
        onComplete={() => setViewState('embeddingMessage')}
      />
    )
  }

  if (viewState === 'embeddingMessage') {
    return (
      <HandjetMessage
        lines={['starting face', 'embedding generation']}
        durationMs={EMBEDDING_MESSAGE_DURATION_MS}
        onComplete={() => setViewState('default')}
      />
    )
  }

  if (viewState === 'uploading') {
    return (
      <UploadingScreen
        durationMs={UPLOADING_DURATION_MS}
        onComplete={() => setViewState('scanComplete')}
      />
    )
  }

  if (viewState === 'scanComplete') {
    return (
      <HandjetMessage
        lines={['scan completed']}
        durationMs={SCAN_COMPLETE_DURATION_MS}
        onComplete={() => setViewState('default')}
      />
    )
  }

  if (state.matches('error')) {
    return <ErrorOverlay message={state.context.error ?? 'Unknown error'} />
  }

  if (state.matches('qr_display') || state.matches('waiting_activation')) {
    const payload = qrPayload ?? (state.context.qrPayload as Record<string, unknown> | undefined)
    const status = state.matches('waiting_activation') ? 'Waiting for activation' : undefined

    if (!payload) {
      return <InstructionStage title="preparing session" randomState />
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

  if (state.matches('human_detect')) {
    return (
      <InstructionStage
        title="Center your face"
        subtitle="Move closer until your face fills the frame"
        className="instruction-stage--tall"
      />
    )
  }

  if (state.matches('stabilizing')) {
    return (
      <InstructionStage
        title="Hold steady"
        subtitle="Stay still for four seconds"
        className="instruction-stage--tall"
      />
    )
  }

  if (state.matches('uploading')) {
    return (
      <InstructionStage
        title="Uploading"
        subtitle="Please hold still"
        className="instruction-stage--tall"
      />
    )
  }

  if (state.matches('waiting_ack')) {
    return (
      <InstructionStage
        title="Processing"
        subtitle="This will take a moment"
        className="instruction-stage--tall"
      />
    )
  }

  if (state.matches('complete')) {
    return (
      <InstructionStage
        title="Completed"
        subtitle="You may step away"
        className="instruction-stage--tall"
      />
    )
  }

  return <IdleScreen mode="idle" />
}
