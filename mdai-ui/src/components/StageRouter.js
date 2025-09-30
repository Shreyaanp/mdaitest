import { jsx as _jsx } from "react/jsx-runtime";
/**
 * StageRouter - Routes session phases to UI components
 *
 * Clean routing with proper entry/exit animations:
 * - Leaving IDLE: Show EXIT animation (bars retract)
 * - Returning to IDLE: Show ENTRY animation (bars fall)
 * - In IDLE: Show static bars
 */
import { useState, useEffect, useRef } from 'react';
import ErrorOverlay from './ErrorOverlay';
import IdleScreen, { IDLE_EXIT_DURATION_MS } from './IdleScreen';
import HelloHumanHero from './HelloHumanHero';
import HandjetMessage from './HandjetMessage';
import InstructionStage from './InstructionStage';
import QRCodeStage from './QRCodeStage';
import ProcessingScreen from './ProcessingScreen';
// Both entry and exit use same duration (1.2s)
const IDLE_ENTRY_DURATION_MS = IDLE_EXIT_DURATION_MS;
export default function StageRouter({ state, qrPayload }) {
    const currentPhase = state.value;
    const previousPhaseRef = useRef(currentPhase);
    const [animationState, setAnimationState] = useState(null);
    console.log('🎬 [STAGE ROUTER] Phase:', currentPhase, '| Animation:', animationState);
    // ============================================================
    // TV Bars Animation Controller
    // ============================================================
    useEffect(() => {
        const prev = previousPhaseRef.current;
        const curr = currentPhase;
        // LEAVING IDLE → Play EXIT animation
        if (prev === 'idle' && curr !== 'idle') {
            console.log('🎬 TV Bars: IDLE → other (EXIT animation)');
            setAnimationState('exit');
            setTimeout(() => {
                setAnimationState(null);
            }, IDLE_EXIT_DURATION_MS);
            previousPhaseRef.current = curr;
            return;
        }
        // RETURNING TO IDLE → Play ENTRY animation
        if (prev !== 'idle' && curr === 'idle') {
            console.log('🎬 TV Bars: other → IDLE (ENTRY animation)');
            setAnimationState('entry');
            setTimeout(() => {
                setAnimationState(null);
            }, IDLE_ENTRY_DURATION_MS);
            previousPhaseRef.current = curr;
            return;
        }
        previousPhaseRef.current = curr;
    }, [currentPhase]);
    // ============================================================
    // Phase Routing
    // ============================================================
    // Playing exit animation (leaving idle)
    if (animationState === 'exit') {
        return _jsx(IdleScreen, { mode: "exit", showBars: true });
    }
    // Playing entry animation (returning to idle)
    if (animationState === 'entry') {
        return _jsx(IdleScreen, { mode: "entry", showBars: true });
    }
    // Phase 1: IDLE - TV bars static at 60%
    if (state.matches('idle')) {
        return _jsx(IdleScreen, { mode: "idle", showBars: true });
    }
    // Phase 2: PAIRING_REQUEST - Handled by exit animation above
    if (state.matches('pairing_request')) {
        // This should be covered by exit animation, but show static as fallback
        return _jsx(IdleScreen, { mode: "idle", showBars: false });
    }
    // Phase 3: HELLO_HUMAN - Welcome screen (2s)
    if (state.matches('hello_human')) {
        return _jsx(HelloHumanHero, {});
    }
    // Phase 4: SCAN_PROMPT - "Scan this to get started" (3s)
    if (state.matches('scan_prompt')) {
        return (_jsx(HandjetMessage, { lines: ['scan this to', 'get started'], durationMs: 3000 }));
    }
    // Phase 4: QR_DISPLAY - Show QR code (indefinite)
    if (state.matches('qr_display')) {
        const payload = qrPayload ?? state.context.qrPayload;
        if (!payload) {
            return _jsx(InstructionStage, { title: "Loading", subtitle: "Preparing QR code" });
        }
        return (_jsx(QRCodeStage, { token: state.context.token, qrPayload: payload, expiresIn: state.context.expiresIn }));
    }
    // Phase 5: HUMAN_DETECT - Camera preview (3.5s validation)
    if (state.matches('human_detect')) {
        console.log('🎬 [STAGE ROUTER] Human detect - camera preview visible');
        return null; // PreviewSurface shows camera
    }
    // Phase 6: PROCESSING - Processing animation (3-15s)
    if (state.matches('processing')) {
        return (_jsx(ProcessingScreen, { statusLines: ['processing', 'dont move away'], durationMs: 15000 }));
    }
    // Phase 7: COMPLETE - Success screen (3s) with hieroglyph icon
    if (state.matches('complete')) {
        return (_jsx(HandjetMessage, { lines: ['scan completed'], durationMs: 3000, showIcon: true }));
    }
    // Phase 8: ERROR - Error screen (3s)
    if (state.matches('error')) {
        return _jsx(ErrorOverlay, { message: state.context.error ?? 'Please try again' });
    }
    // Fallback
    console.warn('🎬 [STAGE ROUTER] Unknown phase:', currentPhase);
    return _jsx(IdleScreen, { mode: "idle", showBars: true });
}
