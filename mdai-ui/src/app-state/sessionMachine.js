import { setup } from 'xstate';
const isControllerState = (event) => event?.type === 'CONTROLLER_STATE';
const sessionMachineSetup = setup({
    types: {
        context: {},
        events: {}
    }
});
const assignSessionDetails = sessionMachineSetup.assign({
    token: ({ event }) => isControllerState(event) && typeof event.data?.token === 'string' ? event.data.token : undefined,
    qrPayload: ({ event }) => isControllerState(event) ? event.data?.qr_payload : undefined,
    expiresIn: ({ event }) => isControllerState(event) && typeof event.data?.expires_in === 'number' ? event.data.expires_in : undefined,
    error: ({ event }) => (isControllerState(event) ? event.error : undefined)
});
const assignError = sessionMachineSetup.assign({
    error: ({ event }) => (isControllerState(event) ? event.error : undefined)
});
const resetContext = sessionMachineSetup.assign({
    token: () => undefined,
    qrPayload: () => undefined,
    expiresIn: () => undefined,
    error: ({ event }) => (isControllerState(event) ? event.error : undefined)
});
const phaseGuard = (phase) => ({ event }) => event.type === 'CONTROLLER_STATE' && event.phase === phase;
export const sessionMachine = sessionMachineSetup.createMachine({
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
            actions: sessionMachineSetup.assign({ lastHeartbeatTs: () => Date.now() })
        },
        RESET: {
            target: '.idle',
            actions: sessionMachineSetup.assign({
                token: undefined,
                qrPayload: undefined,
                expiresIn: undefined,
                error: undefined
            })
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
