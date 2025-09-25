import ErrorOverlay from './ErrorOverlay';
import IdleScreen from './IdleScreen';
import InstructionStage from './InstructionStage';
import QRCodeStage from './QRCodeStage';
export default function StageRouter({ state, qrPayload }) {
    if (state.matches('error')) {
        return <ErrorOverlay message={state.context.error ?? 'Unknown error'}/>;
    }
    if (state.matches('qr_display') || state.matches('waiting_activation')) {
        const payload = qrPayload ?? state.context.qrPayload;
        const status = state.matches('waiting_activation')
            ? 'Waiting for activation'
            : undefined;
        if (!payload) {
            return <InstructionStage title="Preparing session" subtitle="Awaiting QR payload from controller"/>;
        }
        return (<QRCodeStage token={state.context.token} qrPayload={payload} expiresIn={state.context.expiresIn} status={status}/>);
    }
    if (state.matches('pairing_request')) {
        return <InstructionStage title="Preparing session"/>;
    }
    if (state.matches('human_detect')) {
        return (<InstructionStage title="Center your face" subtitle="Move closer until your face fills the frame"/>);
    }
    if (state.matches('stabilizing')) {
        return <InstructionStage title="Hold steady" subtitle="Stay still for four seconds"/>;
    }
    if (state.matches('uploading')) {
        return <InstructionStage title="Uploading" subtitle="Please hold still"/>;
    }
    if (state.matches('waiting_ack')) {
        return <InstructionStage title="Processing" subtitle="This will take a moment"/>;
    }
    if (state.matches('complete')) {
        return <InstructionStage title="Completed" subtitle="You may step away"/>;
    }
    return <IdleScreen />;
}
