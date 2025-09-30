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
            { guard: phaseGuard('hello_human'), target: '.hello_human' },
            { guard: phaseGuard('scan_prompt'), target: '.scan_prompt' },
            { guard: phaseGuard('qr_display'), target: '.qr_display', actions: assignSessionDetails },
            { guard: phaseGuard('human_detect'), target: '.human_detect' },
            { guard: phaseGuard('processing'), target: '.processing' },
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
        hello_human: {},
        scan_prompt: {},
        qr_display: {},
        human_detect: {},
        processing: {},
        complete: {},
        error: {}
    }
});
