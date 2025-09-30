import { jsx as _jsx } from "react/jsx-runtime";
import ErrorOverlay from './ErrorOverlay';
import IdleScreen from './IdleScreen';
import InstructionStage from './InstructionStage';
import QRCodeStage from './QRCodeStage';
import { frontendConfig } from '../config';
export default function StageRouter({ state, qrPayload }) {
    const currentPhase = state.value;
    if (state.matches('error')) {
        return _jsx(ErrorOverlay, { message: state.context.error ?? 'Unknown error' });
    }
    if (state.matches('idle')) {
        return _jsx(IdleScreen, { mode: "idle" });
    }
    if (state.matches('qr_display') || state.matches('waiting_activation')) {
        const payload = qrPayload ?? state.context.qrPayload;
        const status = state.matches('waiting_activation') ? 'Waiting for activation' : undefined;
        if (!payload) {
            const message = frontendConfig.stageMessages.waiting_activation ?? frontendConfig.stageMessages.qr_display;
            if (message) {
                return _jsx(InstructionStage, { ...message });
            }
            return _jsx(InstructionStage, { title: "Preparing session", subtitle: "Awaiting QR data" });
        }
        return (_jsx(QRCodeStage, { token: state.context.token, qrPayload: payload, expiresIn: state.context.expiresIn, status: status }));
    }
    const message = frontendConfig.stageMessages[currentPhase];
    if (message) {
        return _jsx(InstructionStage, { ...message });
    }
    if (state.matches('pairing_request')) {
        return _jsx(InstructionStage, { title: "Preparing session", subtitle: "Contacting the server" });
    }
    return _jsx(IdleScreen, { mode: "idle" });
}
