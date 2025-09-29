import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useCallback, useMemo } from 'react';
import { useMachine } from '@xstate/react';
import StageRouter from './StageRouter';
import { sessionMachine } from '../app-state/sessionMachine';
const DEBUG_STATES = [
    { phase: 'idle', label: 'Idle', description: 'Default waiting state with TV bars animation' },
    { phase: 'pairing_request', label: 'Pairing Request', description: 'Preparing session' },
    { phase: 'qr_display', label: 'QR Display', description: 'Show QR code for mobile pairing' },
    { phase: 'waiting_activation', label: 'Waiting Activation', description: 'Waiting for mobile app activation' },
    { phase: 'human_detect', label: 'Human Detect', description: 'Center your face instruction' },
    { phase: 'stabilizing', label: 'Stabilizing', description: 'Hold steady instruction' },
    { phase: 'uploading', label: 'Uploading', description: 'Uploading data' },
    { phase: 'waiting_ack', label: 'Waiting Ack', description: 'Processing, waiting for acknowledgment' },
    { phase: 'complete', label: 'Complete', description: 'Process completed successfully' },
    { phase: 'error', label: 'Error', description: 'Error state with message' }
];
const SAMPLE_QR_PAYLOAD = {
    ws_app_url: 'ws://localhost:3001/ws/app',
    ws_hardware_url: 'ws://localhost:5000/ws/hardware',
    server_host: 'localhost:3000',
    session_id: 'debug-session-123',
    device_id: 'debug-device'
};
export default function DebugInterface() {
    const [state, send] = useMachine(sessionMachine);
    const [mockMetrics, setMockMetrics] = useState({
        stability: 0.85,
        focus: 0.92,
        composite: 0.88
    });
    const [errorMessage, setErrorMessage] = useState('Debug error message');
    const [showControls, setShowControls] = useState(true);
    const mockQrPayload = useMemo(() => SAMPLE_QR_PAYLOAD, []);
    const triggerState = useCallback((phase) => {
        const baseData = {};
        if (phase === 'qr_display' || phase === 'waiting_activation') {
            baseData.token = 'debug-token-' + Math.random().toString(36).substr(2, 9);
            baseData.qr_payload = mockQrPayload;
            baseData.expires_in = 300; // 5 minutes
        }
        send({
            type: 'CONTROLLER_STATE',
            phase,
            data: baseData,
            error: phase === 'error' ? errorMessage : undefined
        });
    }, [send, mockQrPayload, errorMessage]);
    const updateMetrics = useCallback(() => {
        setMockMetrics({
            stability: Math.random() * 0.4 + 0.6, // 0.6 - 1.0
            focus: Math.random() * 0.3 + 0.7, // 0.7 - 1.0
            composite: Math.random() * 0.4 + 0.6 // 0.6 - 1.0
        });
    }, []);
    // Enhanced state context for QR display states
    const enhancedState = useMemo(() => {
        if (state.matches('qr_display') || state.matches('waiting_activation')) {
            return {
                ...state,
                context: {
                    ...state.context,
                    token: state.context.token || 'debug-token-' + Math.random().toString(36).substr(2, 9),
                    qrPayload: state.context.qrPayload || mockQrPayload,
                    expiresIn: state.context.expiresIn || 300
                }
            };
        }
        return state;
    }, [state, mockQrPayload]);
    return (_jsxs("div", { className: "debug-interface", children: [_jsxs("div", { className: `debug-controls ${showControls ? 'visible' : 'hidden'}`, children: [_jsxs("div", { className: "debug-header", children: [_jsx("h1", { children: "\uD83D\uDD27 Debug Interface" }), _jsx("button", { className: "toggle-controls", onClick: () => setShowControls(!showControls), children: showControls ? 'Hide Controls' : 'Show Controls' })] }), _jsxs("div", { className: "debug-content", children: [_jsxs("div", { className: "current-state", children: [_jsx("h2", { children: "Current State" }), _jsx("div", { className: "state-display", children: _jsx("span", { className: "state-badge", children: state.value }) })] }), _jsxs("div", { className: "state-controls", children: [_jsx("h2", { children: "Trigger States" }), _jsx("div", { className: "state-buttons", children: DEBUG_STATES.map(({ phase, label, description }) => (_jsx("button", { className: `state-button ${state.matches(phase) ? 'active' : ''}`, onClick: () => triggerState(phase), title: description, children: label }, phase))) })] }), _jsxs("div", { className: "mock-controls", children: [_jsx("h2", { children: "Mock Data" }), _jsxs("div", { className: "control-group", children: [_jsx("label", { htmlFor: "error-message", children: "Error Message:" }), _jsx("input", { id: "error-message", type: "text", value: errorMessage, onChange: (e) => setErrorMessage(e.target.value), placeholder: "Enter error message" })] }), _jsxs("div", { className: "control-group", children: [_jsx("label", { children: "Metrics:" }), _jsxs("div", { className: "metrics-display", children: [_jsxs("span", { children: ["Stability: ", mockMetrics.stability?.toFixed(2)] }), _jsxs("span", { children: ["Focus: ", mockMetrics.focus?.toFixed(2)] }), _jsxs("span", { children: ["Composite: ", mockMetrics.composite?.toFixed(2)] })] }), _jsx("button", { onClick: updateMetrics, children: "Randomize Metrics" })] }), _jsxs("div", { className: "control-group", children: [_jsx("label", { children: "QR Payload:" }), _jsx("pre", { className: "json-display", children: JSON.stringify(mockQrPayload, null, 2) })] })] }), _jsxs("div", { className: "debug-info", children: [_jsx("h2", { children: "Debug Info" }), _jsxs("div", { className: "info-grid", children: [_jsxs("div", { children: [_jsx("strong", { children: "State Value:" }), " ", state.value] }), _jsxs("div", { children: [_jsx("strong", { children: "Token:" }), " ", state.context.token || 'None'] }), _jsxs("div", { children: [_jsx("strong", { children: "Expires In:" }), " ", state.context.expiresIn || 'N/A'] }), _jsxs("div", { children: [_jsx("strong", { children: "Error:" }), " ", state.context.error || 'None'] })] })] })] })] }), _jsx("div", { className: "debug-display", children: _jsx(StageRouter, { state: enhancedState, qrPayload: mockQrPayload }) }), !showControls && (_jsx("button", { className: "show-controls-fab", onClick: () => setShowControls(true), title: "Show Debug Controls", children: "\uD83D\uDD27" }))] }));
}
