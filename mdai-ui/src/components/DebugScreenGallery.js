import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Debug Screen Gallery
 *
 * AUTOMATICALLY SYNCED with actual flow.
 * Screens are derived from sessionMachine states.
 * Change the flow once → debug gallery updates automatically.
 */
import { useState, useEffect, useMemo } from 'react';
import { useMachine } from '@xstate/react';
import { sessionMachine } from '../app-state/sessionMachine';
import StageRouter from './StageRouter';
import PreviewSurface from './PreviewSurface';
import { IDLE_EXIT_DURATION_MS } from './IdleScreen';
// Both entry and exit animations use same duration (1.2s)
const IDLE_ENTRY_DURATION_MS = IDLE_EXIT_DURATION_MS;
// ============================================================
// AUTO-GENERATE SCREENS FROM STATE MACHINE
// This is the ONLY place you need to add metadata for new phases
// ============================================================
const PHASE_SEQUENCE = [
    'idle',
    'pairing_request',
    'hello_human',
    'scan_prompt',
    'qr_display',
    'human_detect',
    'processing',
    'complete',
    'error'
];
const PHASE_METADATA = {
    idle: { label: 'IDLE', description: 'TV bars static' },
    pairing_request: { label: 'PAIRING', description: 'Exit animation + token fetch' },
    hello_human: { label: 'HELLO', description: 'Welcome hero (2s)' },
    scan_prompt: { label: 'SCAN', description: 'Scan prompt (3s)' },
    qr_display: { label: 'QR CODE', description: 'QR + wait for app' },
    human_detect: { label: 'VALIDATE', description: 'Camera validation (3.5s)' },
    processing: { label: 'PROCESS', description: 'Upload + backend (3-15s)' },
    complete: { label: 'SUCCESS', description: 'Complete (3s)' },
    error: { label: 'ERROR', description: 'Error (3s)' }
};
// Mock data for specific phases
const MOCK_DATA = {
    qr_display: {
        token: 'DEBUG_TOKEN_ABC123XYZ789',
        qr_payload: {
            token: 'DEBUG_TOKEN_ABC123XYZ789',
            ws_app_url: 'ws://localhost:3001/ws/app',
            ws_hardware_url: 'ws://localhost:5000/ws/hardware',
            server_host: 'localhost:3000'
        },
        expires_in: 300
    },
    error: {
        error: 'Please try again'
    }
};
export default function DebugScreenGallery() {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [autoAdvance, setAutoAdvance] = useState(false);
    const [showCameraPreview, setShowCameraPreview] = useState(true);
    const [showAnimations, setShowAnimations] = useState(true);
    const [state, send] = useMachine(sessionMachine);
    const [isTransitioning, setIsTransitioning] = useState(false);
    // AUTO-GENERATE screens from state machine states
    const screens = useMemo(() => {
        const machineStates = new Set(Object.keys(sessionMachine.states));
        const validPhases = PHASE_SEQUENCE.filter((phase) => machineStates.has(phase));
        return validPhases.map((phase) => ({
            phase,
            label: PHASE_METADATA[phase]?.label || phase.toUpperCase(),
            description: PHASE_METADATA[phase]?.description || '',
            mockData: MOCK_DATA[phase]
        }));
    }, []);
    const currentScreen = screens[currentIndex];
    const canGoPrevious = currentIndex > 0;
    const canGoNext = currentIndex < screens.length - 1;
    const mockQrPayload = useMemo(() => ({
        token: 'DEBUG_TOKEN_ABC123XYZ789',
        ws_app_url: 'ws://localhost:3001/ws/app',
        ws_hardware_url: 'ws://localhost:5000/ws/hardware',
        server_host: 'localhost:3000'
    }), []);
    const mockPreviewUrl = 'http://localhost:5000/preview';
    // Initialize
    useEffect(() => {
        const screen = screens[0];
        send({
            type: 'CONTROLLER_STATE',
            phase: screen.phase,
            data: screen.mockData ?? {},
            error: screen.mockData?.error
        });
    }, [send, screens]);
    // Navigate when index changes
    useEffect(() => {
        const screen = screens[currentIndex];
        const prevScreen = currentIndex > 0 ? screens[currentIndex - 1] : null;
        if (currentIndex === 0 && !prevScreen && !isTransitioning)
            return;
        // Handle animations
        if (showAnimations && prevScreen) {
            if (prevScreen.phase === 'idle' && screen.phase !== 'idle') {
                setIsTransitioning(true);
                setTimeout(() => {
                    send({
                        type: 'CONTROLLER_STATE',
                        phase: screen.phase,
                        data: screen.mockData ?? {},
                        error: screen.mockData?.error
                    });
                    setIsTransitioning(false);
                }, IDLE_EXIT_DURATION_MS);
                return;
            }
            if (prevScreen.phase !== 'idle' && screen.phase === 'idle') {
                setIsTransitioning(true);
                send({
                    type: 'CONTROLLER_STATE',
                    phase: screen.phase,
                    data: screen.mockData ?? {},
                    error: screen.mockData?.error
                });
                setTimeout(() => setIsTransitioning(false), IDLE_ENTRY_DURATION_MS);
                return;
            }
        }
        send({
            type: 'CONTROLLER_STATE',
            phase: screen.phase,
            data: screen.mockData ?? {},
            error: screen.mockData?.error
        });
    }, [currentIndex, send, showAnimations, screens]);
    // Auto-advance
    useEffect(() => {
        if (!autoAdvance || isTransitioning)
            return;
        const timer = setTimeout(() => {
            if (canGoNext)
                setCurrentIndex(prev => prev + 1);
            else
                setAutoAdvance(false);
        }, 5000);
        return () => clearTimeout(timer);
    }, [autoAdvance, canGoNext, currentIndex, isTransitioning]);
    // Keyboard
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (isTransitioning)
                return;
            if (e.key === 'ArrowLeft' && canGoPrevious) {
                setCurrentIndex(prev => prev - 1);
                setAutoAdvance(false);
            }
            else if (e.key === 'ArrowRight' && canGoNext) {
                setCurrentIndex(prev => prev + 1);
                setAutoAdvance(false);
            }
            else if (e.key === ' ') {
                e.preventDefault();
                setAutoAdvance(prev => !prev);
            }
            else if (e.key === 'Escape') {
                setCurrentIndex(0);
                setAutoAdvance(false);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [canGoPrevious, canGoNext, isTransitioning]);
    const showPreview = currentScreen.phase === 'human_detect';
    return (_jsxs("div", { className: "app-shell", children: [_jsxs("div", { className: "visual-area", children: [_jsx(StageRouter, { state: state, qrPayload: mockQrPayload }), showPreview && (_jsx(PreviewSurface, { visible: showCameraPreview, previewUrl: mockPreviewUrl, title: "Mock Camera" })), showPreview && showCameraPreview && (_jsx("div", { style: {
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            width: '100%',
                            height: '100%',
                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#fff',
                            fontSize: '32px',
                            fontWeight: 'bold',
                            zIndex: 100
                        }, children: "\uD83D\uDCF9 Mock Camera" }))] }), _jsxs("div", { style: {
                    position: 'fixed',
                    top: '10px',
                    left: '10px',
                    background: 'rgba(0, 0, 0, 0.75)',
                    backdropFilter: 'blur(10px)',
                    padding: '12px',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    color: '#fff',
                    fontSize: '11px',
                    zIndex: 9999,
                    width: '200px',
                    maxHeight: 'calc(100vh - 20px)',
                    overflowY: 'auto'
                }, children: [_jsxs("div", { style: { marginBottom: '10px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '8px' }, children: [_jsxs("div", { style: { fontSize: '14px', fontWeight: 'bold', color: '#4f4' }, children: ["\uD83D\uDD27 ", currentScreen.label] }), _jsxs("div", { style: { fontSize: '9px', opacity: 0.5, marginTop: '2px' }, children: [currentIndex + 1, "/", screens.length] })] }), _jsxs("div", { style: { display: 'flex', gap: '6px', marginBottom: '10px' }, children: [_jsx("button", { onClick: () => canGoPrevious && !isTransitioning && setCurrentIndex(prev => prev - 1), disabled: !canGoPrevious || isTransitioning, style: {
                                    flex: 1,
                                    padding: '8px',
                                    background: (canGoPrevious && !isTransitioning) ? '#4f4' : 'rgba(51, 51, 51, 0.5)',
                                    color: (canGoPrevious && !isTransitioning) ? '#000' : '#555',
                                    border: 'none',
                                    borderRadius: '4px',
                                    cursor: (canGoPrevious && !isTransitioning) ? 'pointer' : 'not-allowed',
                                    fontWeight: 'bold',
                                    fontSize: '16px'
                                }, children: "\u2190" }), _jsx("button", { onClick: () => canGoNext && !isTransitioning && setCurrentIndex(prev => prev + 1), disabled: !canGoNext || isTransitioning, style: {
                                    flex: 1,
                                    padding: '8px',
                                    background: (canGoNext && !isTransitioning) ? '#4f4' : 'rgba(51, 51, 51, 0.5)',
                                    color: (canGoNext && !isTransitioning) ? '#000' : '#555',
                                    border: 'none',
                                    borderRadius: '4px',
                                    cursor: (canGoNext && !isTransitioning) ? 'pointer' : 'not-allowed',
                                    fontWeight: 'bold',
                                    fontSize: '16px'
                                }, children: "\u2192" })] }), _jsx("div", { style: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px', marginBottom: '10px' }, children: screens.map((screen, index) => (_jsx("button", { onClick: () => !isTransitioning && setCurrentIndex(index), disabled: isTransitioning, title: `${index + 1}. ${screen.label}`, style: {
                                padding: '6px',
                                background: index === currentIndex ? '#4af' : 'rgba(0, 0, 0, 0.6)',
                                color: index === currentIndex ? '#000' : '#fff',
                                border: '1px solid rgba(255, 255, 255, 0.15)',
                                borderRadius: '3px',
                                cursor: isTransitioning ? 'not-allowed' : 'pointer',
                                fontWeight: index === currentIndex ? 'bold' : 'normal',
                                fontSize: '10px'
                            }, children: index + 1 }, screen.phase))) }), _jsxs("div", { style: { fontSize: '10px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '8px' }, children: [_jsxs("label", { style: { display: 'flex', alignItems: 'center', marginBottom: '6px', cursor: 'pointer' }, children: [_jsx("input", { type: "checkbox", checked: showAnimations, onChange: (e) => setShowAnimations(e.target.checked), style: { marginRight: '6px', transform: 'scale(0.85)' } }), _jsx("span", { children: "Animations" })] }), _jsxs("label", { style: { display: 'flex', alignItems: 'center', marginBottom: '6px', cursor: 'pointer' }, children: [_jsx("input", { type: "checkbox", checked: autoAdvance, onChange: (e) => setAutoAdvance(e.target.checked), style: { marginRight: '6px', transform: 'scale(0.85)' }, disabled: isTransitioning }), _jsx("span", { children: "Auto (5s)" })] }), _jsxs("label", { style: { display: 'flex', alignItems: 'center', cursor: 'pointer' }, children: [_jsx("input", { type: "checkbox", checked: showCameraPreview, onChange: (e) => setShowCameraPreview(e.target.checked), style: { marginRight: '6px', transform: 'scale(0.85)' } }), _jsx("span", { children: "Camera" })] })] }), isTransitioning && (_jsx("div", { style: {
                            marginTop: '8px',
                            padding: '6px',
                            background: 'rgba(255, 170, 0, 0.2)',
                            borderRadius: '3px',
                            fontSize: '9px',
                            color: '#fa0',
                            textAlign: 'center'
                        }, children: "\u23F3 Animating..." })), _jsx("div", { style: {
                            fontSize: '8px',
                            opacity: 0.4,
                            textAlign: 'center',
                            marginTop: '8px',
                            borderTop: '1px solid rgba(255,255,255,0.1)',
                            paddingTop: '6px'
                        }, children: "\u2190 \u2192 \u2022 Space \u2022 Esc" })] })] }));
}
