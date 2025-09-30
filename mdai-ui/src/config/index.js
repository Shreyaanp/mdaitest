const env = import.meta.env;
const DEFAULT_CONTROLLER_HTTP_URL = 'http://127.0.0.1:5000';
const DEFAULT_BACKEND_URL = 'https://mdai.mercle.ai';
const DEFAULT_DEVICE_ID = 'alpha';
const normalizeBaseUrl = (value, fallback) => {
    if (!value)
        return fallback;
    try {
        const url = new URL(value);
        url.pathname = url.pathname.replace(/\/+$/, '');
        return url.toString().replace(/\/$/, '');
    }
    catch (error) {
        console.warn('Invalid URL provided; falling back to default', value);
        return fallback;
    }
};
const normalizedControllerHttpBase = normalizeBaseUrl(env.VITE_CONTROLLER_HTTP_URL, DEFAULT_CONTROLLER_HTTP_URL);
const backendApiBase = normalizeBaseUrl(env.VITE_BACKEND_URL ?? env.VITE_BACKEND_API_URL, DEFAULT_BACKEND_URL);
const buildPreviewUrl = () => {
    if (env.VITE_PREVIEW_URL) {
        try {
            return new URL(env.VITE_PREVIEW_URL).toString();
        }
        catch (error) {
            console.warn('Invalid preview URL supplied; using controller base', env.VITE_PREVIEW_URL);
        }
    }
    try {
        const base = new URL(normalizedControllerHttpBase);
        base.pathname = '/preview';
        return base.toString();
    }
    catch (error) {
        return 'http://127.0.0.1:5000/preview';
    }
};
const buildControllerWsUrl = () => {
    const candidate = env.VITE_CONTROLLER_WS_URL;
    if (candidate) {
        try {
            return new URL(candidate).toString();
        }
        catch (error) {
            console.warn('Invalid controller websocket URL; falling back to HTTP base', candidate);
        }
    }
    try {
        const base = new URL(normalizedControllerHttpBase);
        base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
        base.pathname = '/ws/ui';
        base.search = '';
        base.hash = '';
        return base.toString();
    }
    catch (error) {
        return 'ws://127.0.0.1:5000/ws/ui';
    }
};
export const backendConfig = {
    controllerHttpBase: normalizedControllerHttpBase,
    controllerWsUrl: buildControllerWsUrl(),
    previewUrl: buildPreviewUrl(),
    backendApiBase,
    deviceId: env.VITE_DEVICE_ID ?? DEFAULT_DEVICE_ID,
    deviceAddress: env.VITE_DEVICE_ADDRESS
};
const stageMessages = {
    pairing_request: {
        title: 'Preparing session',
        subtitle: 'Contacting the server'
    },
    qr_display: {
        title: 'Scan the QR code',
        subtitle: 'Use your mobile app to continue'
    },
    waiting_activation: {
        title: 'Waiting for activation',
        subtitle: 'Complete the setup on your mobile app'
    },
    human_detect: {
        title: 'Center your face',
        subtitle: 'Move closer until your face fills the frame',
        className: 'instruction-stage--tall'
    },
    stabilizing: {
        title: 'Hold steady',
        subtitle: 'Stay still while we capture your image',
        className: 'instruction-stage--tall'
    },
    uploading: {
        title: 'Uploading',
        subtitle: 'Please hold still',
        className: 'instruction-stage--tall'
    },
    waiting_ack: {
        title: 'Processing',
        subtitle: 'This may take a moment',
        className: 'instruction-stage--tall'
    },
    complete: {
        title: 'Complete',
        subtitle: 'You may step away',
        className: 'instruction-stage--tall'
    }
};
export const frontendConfig = {
    previewVisiblePhases: new Set(['human_detect', 'stabilizing', 'uploading', 'waiting_ack']),
    stageMessages
};
