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
/**
 * Stage messages - displayed for each phase
 * Note: Most phases use custom components (see StageRouter.tsx)
 */
const stageMessages = {
    pairing_request: {
        title: 'Preparing session',
        subtitle: 'Requesting token'
    },
    hello_human: {
        title: 'Hello Human',
        subtitle: ''
    },
    qr_display: {
        title: 'Scan this to get started',
        subtitle: 'Use your mobile device'
    },
    human_detect: {
        title: 'Center your face',
        subtitle: 'Position yourself in frame',
        className: 'instruction-stage--tall'
    },
    processing: {
        title: 'Processing',
        subtitle: 'Please wait',
        className: 'instruction-stage--tall'
    },
    complete: {
        title: 'Scan Complete',
        className: 'instruction-stage--tall'
    }
};
/**
 * Frontend configuration
 *
 * previewVisiblePhases: Phases where camera preview is shown
 * - ONLY 'human_detect' shows camera now
 * - Processing phase hides camera and shows animation
 */
export const frontendConfig = {
    previewVisiblePhases: new Set(['human_detect']),
    stageMessages
};
