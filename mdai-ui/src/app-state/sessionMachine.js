import { assign, createMachine } from 'xstate';
const isControllerState = (event) => (event?.type === 'CONTROLLER_STATE');
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
    return ({ event }) => event.type === 'CONTROLLER_STATE' && event.phase === phase;
};
export const sessionMachine = createMachine({
    id: 'session',
    predictableActionArguments: true,
    initial: 'idle',
    context: {},
    on: {
        CONTROLLER_STATE: [
            { guard: phaseGuard('idle'), target: '.idle', actions: resetContext },
            { guard: phaseGuard('pairing_request'), target: '.pairing_request' },
            { guard: phaseGuard('qr_display'), target: '.qr_display', actions: assignSessionDetails },
            { guard: phaseGuard('waiting_activation'), target: '.waiting_activation' },
            { guard: phaseGuard('human_detect'), target: '.human_detect' },
            { guard: phaseGuard('stabilizing'), target: '.stabilizing' },
            { guard: phaseGuard('uploading'), target: '.uploading' },
            { guard: phaseGuard('waiting_ack'), target: '.waiting_ack' },
            { guard: phaseGuard('complete'), target: '.complete' },
            { guard: phaseGuard('error'), target: '.error', actions: assignError }
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
