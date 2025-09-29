import { jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useRef, useState } from 'react';
import ErrorOverlay from './ErrorOverlay';
import HandjetMessage from './HandjetMessage';
import IdleScreen, { IDLE_EXIT_DURATION_MS } from './IdleScreen';
import InstructionStage from './InstructionStage';
import ProcessingScreen from './ProcessingScreen';
import QRCodeStage from './QRCodeStage';
import UploadingScreen from './UploadingScreen';
const HERO_HOLD_DURATION_MS = 3000;
const SCAN_PROMPT_DURATION_MS = 3000;
const PROCESSING_DURATION_MS = 3000;
const EMBEDDING_MESSAGE_DURATION_MS = 3000;
const UPLOADING_DURATION_MS = 3000;
const SCAN_COMPLETE_DURATION_MS = 3000;
export default function StageRouter({ state, qrPayload, onMockTof, processingReady = false }) {
    const [idleMode, setIdleMode] = useState(state.matches('idle') ? 'idle' : 'exit');
    const [showIdleBars, setShowIdleBars] = useState(true);
    const [viewState, setViewState] = useState(state.matches('idle') ? 'idle' : 'default');
    const previousPhaseRef = useRef(state.value);
    const idleTimersRef = useRef([]);
    const overlayTimersRef = useRef([]);
    const hasRunScanSequenceRef = useRef(false);
    const hasRunProcessingSequenceRef = useRef(false);
    const hasRunUploadingSequenceRef = useRef(false);
    const clearTimers = (ref) => {
        ref.current.forEach((id) => window.clearTimeout(id));
        ref.current = [];
    };
    const scheduleTimer = (ref, delay, callback) => {
        const id = window.setTimeout(() => {
            ref.current = ref.current.filter((stored) => stored !== id);
            callback();
        }, delay);
        ref.current.push(id);
    };
    const resetToIdle = () => {
        clearTimers(idleTimersRef);
        clearTimers(overlayTimersRef);
        hasRunScanSequenceRef.current = false;
        hasRunProcessingSequenceRef.current = false;
        hasRunUploadingSequenceRef.current = false;
        setViewState('idle');
        setIdleMode('idle');
        setShowIdleBars(true);
    };
    const startIdleExitSequence = () => {
        if (hasRunScanSequenceRef.current) {
            return;
        }
        hasRunScanSequenceRef.current = true;
        clearTimers(idleTimersRef);
        setIdleMode('exit');
        setShowIdleBars(true);
        setViewState('idleExit');
        scheduleTimer(idleTimersRef, IDLE_EXIT_DURATION_MS, () => {
            setShowIdleBars(false);
            setIdleMode('idle');
            setViewState('heroHold');
            scheduleTimer(idleTimersRef, HERO_HOLD_DURATION_MS, () => {
                setViewState('scanPrompt');
            });
        });
    };
    const startProcessingSequence = () => {
        if (hasRunProcessingSequenceRef.current) {
            return;
        }
        hasRunProcessingSequenceRef.current = true;
        clearTimers(overlayTimersRef);
        setViewState('processing');
    };
    const startUploadingSequence = () => {
        if (hasRunUploadingSequenceRef.current) {
            return;
        }
        hasRunUploadingSequenceRef.current = true;
        clearTimers(overlayTimersRef);
        setViewState('uploading');
    };
    useEffect(() => {
        const currentPhase = state.value;
        const previousPhase = previousPhaseRef.current;
        if (currentPhase === 'idle') {
            resetToIdle();
        }
        else if (previousPhase === 'idle') {
            startIdleExitSequence();
        }
        if (currentPhase === 'error') {
            clearTimers(idleTimersRef);
            clearTimers(overlayTimersRef);
            setViewState('default');
        }
        if ((currentPhase === 'human_detect' || currentPhase === 'stabilizing') && processingReady) {
            startProcessingSequence();
        }
        if (currentPhase === 'uploading' || currentPhase === 'waiting_ack') {
            startUploadingSequence();
        }
        previousPhaseRef.current = currentPhase;
    }, [state.value, processingReady]);
    useEffect(() => {
        return () => {
            clearTimers(idleTimersRef);
            clearTimers(overlayTimersRef);
        };
    }, []);
    if (viewState === 'idle' || viewState === 'idleExit' || viewState === 'heroHold') {
        return _jsx(IdleScreen, { mode: idleMode, showBars: showIdleBars, onMockTof: onMockTof });
    }
    if (viewState === 'scanPrompt') {
        return (_jsx(HandjetMessage, { lines: ['scan this', 'to get started'], durationMs: SCAN_PROMPT_DURATION_MS, onComplete: () => setViewState('default') }));
    }
    if (viewState === 'processing') {
        return (_jsx(ProcessingScreen, { durationMs: PROCESSING_DURATION_MS, onComplete: () => setViewState('embeddingMessage') }));
    }
    if (viewState === 'embeddingMessage') {
        return (_jsx(HandjetMessage, { lines: ['starting face', 'embedding generation'], durationMs: EMBEDDING_MESSAGE_DURATION_MS, onComplete: () => setViewState('default') }));
    }
    if (viewState === 'uploading') {
        return (_jsx(UploadingScreen, { durationMs: UPLOADING_DURATION_MS, onComplete: () => setViewState('scanComplete') }));
    }
    if (viewState === 'scanComplete') {
        return (_jsx(HandjetMessage, { lines: ['scan completed'], durationMs: SCAN_COMPLETE_DURATION_MS, onComplete: () => setViewState('default') }));
    }
    if (state.matches('error')) {
        return _jsx(ErrorOverlay, { message: state.context.error ?? 'Unknown error' });
    }
    if (state.matches('qr_display') || state.matches('waiting_activation')) {
        const payload = qrPayload ?? state.context.qrPayload;
        const status = state.matches('waiting_activation') ? 'Waiting for activation' : undefined;
        if (!payload) {
            return _jsx(InstructionStage, { title: "preparing session", randomState: true });
        }
        return (_jsx(QRCodeStage, { token: state.context.token, qrPayload: payload, expiresIn: state.context.expiresIn, status: status }));
    }
    if (state.matches('human_detect')) {
        return (_jsx(InstructionStage, { title: "Center your face", subtitle: "Move closer until your face fills the frame", className: "instruction-stage--tall" }));
    }
    if (state.matches('stabilizing')) {
        return (_jsx(InstructionStage, { title: "Hold steady", subtitle: "Stay still for four seconds", className: "instruction-stage--tall" }));
    }
    if (state.matches('uploading')) {
        return (_jsx(InstructionStage, { title: "Uploading", subtitle: "Please hold still", className: "instruction-stage--tall" }));
    }
    if (state.matches('waiting_ack')) {
        return (_jsx(InstructionStage, { title: "Processing", subtitle: "This will take a moment", className: "instruction-stage--tall" }));
    }
    if (state.matches('complete')) {
        return (_jsx(InstructionStage, { title: "Completed", subtitle: "You may step away", className: "instruction-stage--tall" }));
    }
    return _jsx(IdleScreen, { mode: "idle", onMockTof: onMockTof });
}
