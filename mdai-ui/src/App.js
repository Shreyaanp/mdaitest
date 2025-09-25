import { useCallback, useEffect, useMemo, useState } from 'react';
import { useMachine } from '@xstate/react';
import StageRouter from './components/StageRouter';
import ControlPanel from './components/ControlPanel';
import { sessionMachine } from './app-state/sessionMachine';
import { useControllerSocket } from './hooks/useControllerSocket';
const previewVisibleStates = new Set([
    'human_detect',
    'stabilizing',
    'uploading',
    'waiting_ack'
]);
const DEFAULT_CONTROLLER_HTTP_URL = 'http://127.0.0.1:5000';
const DEFAULT_BACKEND_URL = 'https://mdai.mercle.ai';
const DEFAULT_DEVICE_ID = 'alpha';
const readEnv = (...keys) => {
    const env = import.meta.env;
    for (const key of keys) {
        const value = env[key];
        if (typeof value === 'string' && value.length > 0) {
            return value;
        }
    }
    return undefined;
};
function getNumberField(data, key) {
    if (!data)
        return undefined;
    const value = data[key];
    return typeof value === 'number' ? value : undefined;
}
function normaliseBaseUrl(url) {
    return url.endsWith('/') ? url.slice(0, -1) : url;
}
function buildControllerUrl(baseUrl, path) {
    return `${normaliseBaseUrl(baseUrl)}${path.startsWith('/') ? path : `/${path}`}`;
}
const nowId = () => `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
export default function App() {
    const [state, send] = useMachine(sessionMachine);
    const [metrics, setMetrics] = useState(null);
    const [logs, setLogs] = useState([]);
    const [connectionStatus, setConnectionStatus] = useState('connecting');
    const [lastHeartbeatTs, setLastHeartbeatTs] = useState(null);
    const [isTriggering, setIsTriggering] = useState(false);
    const [isTofTriggering, setIsTofTriggering] = useState(false);
    const [tokenExpiryTs, setTokenExpiryTs] = useState(null);
    const [now, setNow] = useState(Date.now());
    const [qrPayloadOverride, setQrPayloadOverride] = useState(null);
    const controllerHttpBase = readEnv('VITE_CONTROLLER_HTTP_URL') ?? DEFAULT_CONTROLLER_HTTP_URL;
    const previewUrl = readEnv('VITE_PREVIEW_URL') ?? `${normaliseBaseUrl(controllerHttpBase)}/preview`;
    const backendUrl = readEnv('VITE_BACKEND_URL', 'VITE_BACKEND_API_URL') ?? DEFAULT_BACKEND_URL;
    const deviceId = readEnv('VITE_DEVICE_ID') ?? DEFAULT_DEVICE_ID;
    const deviceAddress = readEnv('VITE_DEVICE_ADDRESS');
    const appendLog = useCallback((message, level = 'info') => {
        setLogs((prev) => {
            const entry = { id: nowId(), ts: Date.now(), message, level };
            const next = [...prev, entry];
            if (next.length > 200) {
                return next.slice(next.length - 200);
            }
            return next;
        });
    }, []);
    const handleStatusChange = useCallback((status) => {
        setConnectionStatus(status);
        if (status === 'open') {
            appendLog('Connected to controller websocket');
        }
        else if (status === 'closed') {
            appendLog('Controller websocket disconnected', 'error');
        }
    }, [appendLog]);
    const handleControllerEvent = useCallback((message) => {
        const { type } = message;
        if (type === 'heartbeat') {
            setLastHeartbeatTs(Date.now());
            return;
        }
        if (type === 'metrics') {
            const payload = message.data;
            setMetrics({
                stability: getNumberField(payload, 'stability'),
                focus: getNumberField(payload, 'focus'),
                composite: getNumberField(payload, 'composite')
            });
            return;
        }
        if (type === 'state') {
            const payload = message.data;
            const phase = message.phase ?? 'unknown';
            if (message.error) {
                appendLog(`Phase → ${phase} (${message.error})`, 'error');
            }
            else {
                appendLog(`Phase → ${phase}`);
            }
        if (payload && typeof payload.token === 'string') {
            appendLog(`Token issued: ${payload.token.slice(0, 12)}…`);
        }
        if (phase === 'qr_display' && payload && payload.qr_payload && typeof payload.qr_payload === 'object') {
            setQrPayloadOverride(payload.qr_payload);
        }
        if (phase === 'idle') {
            setQrPayloadOverride(null);
        }
        const expires = getNumberField(payload, 'expires_in');
        if (typeof expires === 'number') {
            setTokenExpiryTs(Date.now() + expires * 1000);
        }
        else {
                setTokenExpiryTs(null);
            }
            return;
        }
        if (type === 'backend') {
            const payload = message.data;
            const eventName = payload && typeof payload.event === 'string' ? payload.event : 'event';
            appendLog(`Backend → ${eventName}`);
            if (eventName === 'backend_response') {
                const status = getNumberField(payload, 'status_code');
                appendLog(`Backend response status ${status ?? 'unknown'}`);
            }
            if (eventName === 'error') {
                appendLog(String(payload?.message ?? 'Bridge error'), 'error');
            }
            return;
        }
        if (type === 'error') {
            appendLog(message.error ?? 'Controller reported an error', 'error');
            return;
        }
        appendLog(`Event → ${type}`);
    }, [appendLog]);
    const socketOptions = useMemo(() => ({
        onEvent: handleControllerEvent,
        onStatusChange: handleStatusChange
    }), [handleControllerEvent, handleStatusChange]);
    useControllerSocket(send, socketOptions);
    useEffect(() => {
        const id = window.setInterval(() => setNow(Date.now()), 1000);
        return () => window.clearInterval(id);
    }, []);
    useEffect(() => {
        document.body.style.backgroundColor = '#000';
        return () => {
            document.body.style.backgroundColor = '';
        };
    }, []);
    const showPreview = useMemo(() => previewVisibleStates.has(state.value), [state.value]);
    const heartbeatAgeSeconds = useMemo(() => {
        if (!lastHeartbeatTs)
            return undefined;
        return Math.max(Math.floor((now - lastHeartbeatTs) / 1000), 0);
    }, [lastHeartbeatTs, now]);
    const pairingToken = state.context.token;
    const qrPayload = state.context.qrPayload;
    const expiresInSeconds = useMemo(() => {
        if (tokenExpiryTs) {
            const remaining = Math.floor((tokenExpiryTs - now) / 1000);
            return remaining > 0 ? remaining : 0;
        }
        if (typeof state.context.expiresIn === 'number') {
            return Math.max(Math.floor(state.context.expiresIn), 0);
        }
        return undefined;
    }, [state.context.expiresIn, tokenExpiryTs, now]);
    const triggerSession = useCallback(async () => {
        setIsTriggering(true);
        try {
            const url = buildControllerUrl(controllerHttpBase, '/debug/trigger');
            const response = await fetch(url, { method: 'POST' });
            if (!response.ok) {
                const text = await response.text().catch(() => '');
                throw new Error(text || `HTTP ${response.status}`);
            }
            appendLog('Manual trigger sent to controller');
        }
        catch (error) {
            const reason = error instanceof Error ? error.message : String(error);
            appendLog(`Trigger failed: ${reason}`, 'error');
        }
        finally {
            setIsTriggering(false);
        }
    }, [appendLog, controllerHttpBase]);
    const triggerTof = useCallback(async () => {
        setIsTofTriggering(true);
        try {
            const url = buildControllerUrl(controllerHttpBase, '/debug/tof-trigger');
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ triggered: true })
            });
            if (!response.ok) {
                const text = await response.text().catch(() => '');
                throw new Error(text || `HTTP ${response.status}`);
            }
            appendLog('Simulated ToF trigger');
        }
        catch (error) {
            const reason = error instanceof Error ? error.message : String(error);
            appendLog(`ToF trigger failed: ${reason}`, 'error');
        }
        finally {
            setIsTofTriggering(false);
        }
    }, [appendLog, controllerHttpBase]);
    useEffect(() => {
        if (state.matches('qr_display')) {
            appendLog('QR code displayed – waiting for mobile activation');
        }
    }, [state, appendLog]);
    return (<div className="app-shell">
      <div className="visual-area">
        <StageRouter state={state} qrPayload={qrPayloadOverride ?? state.context.qrPayload}/>
        <iframe title="RealSense preview" className={`preview-frame ${showPreview ? 'visible' : 'hidden'}`} src={previewUrl} allow="autoplay"/>
      </div>
      <ControlPanel deviceId={deviceId} deviceAddress={deviceAddress} backendUrl={backendUrl} controllerUrl={controllerHttpBase} connectionStatus={connectionStatus} currentPhase={state.value} pairingToken={pairingToken} qrPayload={qrPayloadOverride ?? qrPayload} expiresInSeconds={expiresInSeconds} lastHeartbeatSeconds={heartbeatAgeSeconds} metrics={metrics} logs={logs} onTrigger={triggerSession} triggerDisabled={isTriggering || state.value !== 'idle'} isTriggering={isTriggering} onTofTrigger={triggerTof} tofTriggerDisabled={isTofTriggering || state.value !== 'idle'} isTofTriggering={isTofTriggering}/>
    </div>);
}
