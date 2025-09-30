import { jsx as _jsx } from "react/jsx-runtime";
import ErrorOverlay from './ErrorOverlay';
import IdleScreen from './IdleScreen';
import InstructionStage from './InstructionStage';
import QRCodeStage from './QRCodeStage';
export default function StageRouter({ state, qrPayload }) {
    const currentPhase = state.value;
    console.log('🎬 [STAGE ROUTER] Phase:', currentPhase);
    // Error state
    if (state.matches('error')) {
        return _jsx(ErrorOverlay, { message: state.context.error ?? 'Unknown error' });
    }
    // Idle state
    if (state.matches('idle')) {
        return _jsx(IdleScreen, { mode: "idle", showBars: true });
    }
    // Pairing/requesting token
    if (state.matches('pairing_request')) {
        return _jsx(InstructionStage, { title: "Preparing session", subtitle: "Contacting server" });
    }
    // QR code display
    if (state.matches('qr_display') || state.matches('waiting_activation')) {
        const payload = qrPayload ?? state.context.qrPayload;
        const status = state.matches('waiting_activation') ? 'Waiting for activation' : undefined;
        if (!payload) {
            return _jsx(InstructionStage, { title: "Preparing session", subtitle: "Loading QR code" });
        }
        return (_jsx(QRCodeStage, { token: state.context.token, qrPayload: payload, expiresIn: state.context.expiresIn, status: status }));
    }
    // Camera/preview phases - render nothing so preview is visible
    // Backend controls timing via phase durations
    if (state.matches('human_detect') ||
        state.matches('stabilizing') ||
        state.matches('uploading') ||
        state.matches('waiting_ack')) {
        console.log('🎬 [STAGE ROUTER] Camera phase - preview visible');
        return null;
    }
    // Complete state
    if (state.matches('complete')) {
        return _jsx(InstructionStage, { title: "Complete", subtitle: "Thank you!", className: "instruction-stage--tall" });
    }
    // Fallback
    console.log('🎬 [STAGE ROUTER] Unknown phase, showing idle');
    return _jsx(IdleScreen, { mode: "idle", showBars: false });
}
