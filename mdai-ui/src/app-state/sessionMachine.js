import { assign, createMachine } from 'xstate';
const isControllerState = (event) => event.type === 'CONTROLLER_STATE';
const assignSessionDetails = assign({
    token: (_ctx, event) => isControllerState(event) && typeof event.data?.token === 'string' ? event.data.token : undefined,
    qrPayload: (_ctx, event) => isControllerState(event) ? event.data?.qr_payload : undefined,
    expiresIn: (_ctx, event) => isControllerState(event) && typeof event.data?.expires_in === 'number' ? event.data.expires_in : undefined,
    error: (_ctx, event) => (isControllerState(event) ? event.error : undefined)
});
const assignError = assign({
    error: (_ctx, event) => (isControllerState(event) ? event.error : undefined)
});
const resetContext = assign({
    token: () => undefined,
    qrPayload: () => undefined,
    expiresIn: () => undefined,
    error: (_ctx, event) => (isControllerState(event) ? event.error : undefined)
});
const phaseGuard = (phase) => {
    return (_ctx, event) => event.type === 'CONTROLLER_STATE' && event.phase === phase;
};
export const sessionMachine = createMachine({
    id: 'session',
    predictableActionArguments: true,
    initial: 'idle',
    context: {},
    on: {
        CONTROLLER_STATE: [
            { cond: phaseGuard('idle'), target: '.idle', actions: resetContext },
            { cond: phaseGuard('pairing_request'), target: '.pairing_request' },
            { cond: phaseGuard('qr_display'), target: '.qr_display', actions: assignSessionDetails },
            { cond: phaseGuard('waiting_activation'), target: '.waiting_activation' },
            { cond: phaseGuard('human_detect'), target: '.human_detect' },
            { cond: phaseGuard('stabilizing'), target: '.stabilizing' },
            { cond: phaseGuard('uploading'), target: '.uploading' },
            { cond: phaseGuard('waiting_ack'), target: '.waiting_ack' },
            { cond: phaseGuard('complete'), target: '.complete' },
            { cond: phaseGuard('error'), target: '.error', actions: assignError }
        ],
        HEARTBEAT: {
            actions: assign({ lastHeartbeatTs: () => Date.now() })
        },
        RESET: {
            target: '.idle',
            actions: assign({ token: undefined, qrPayload: undefined, expiresIn: undefined, error: undefined })
        }
    },
    states: {
        idle: {},
        pairing_request: {},
        qr_display: {},
        waiting_activation: {},
        human_detect: {},
        stabilizing: {},
        uploading: {},
        waiting_ack: {},
        complete: {},
        error: {}
    }
});
