import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo } from 'react';
import LogConsole from './LogConsole';
const statusLabels = {
    connecting: 'Connecting…',
    open: 'Connected',
    closed: 'Disconnected'
};
export default function ControlPanel(props) {
    const { deviceId, deviceAddress, backendUrl, controllerUrl, connectionStatus, currentPhase, pairingToken, qrPayload, expiresInSeconds, lastHeartbeatSeconds, metrics, logs, onTrigger, triggerDisabled, isTriggering } = props;
    const heartbeatLabel = useMemo(() => {
        if (typeof lastHeartbeatSeconds !== 'number') {
            return 'No heartbeat yet';
        }
        if (lastHeartbeatSeconds === 0) {
            return 'Just now';
        }
        return `${lastHeartbeatSeconds}s ago`;
    }, [lastHeartbeatSeconds]);
    const qrPayloadJson = useMemo(() => (qrPayload ? JSON.stringify(qrPayload) : undefined), [qrPayload]);
    const handleCopyToken = async () => {
        if (!pairingToken)
            return;
        try {
            await navigator.clipboard.writeText(pairingToken);
        }
        catch (error) {
            console.warn('Failed to copy pairing token', error);
        }
    };
    const handleCopyQrPayload = async () => {
        if (!qrPayloadJson)
            return;
        try {
            await navigator.clipboard.writeText(qrPayloadJson);
        }
        catch (error) {
            console.warn('Failed to copy QR payload', error);
        }
    };
    return (_jsxs("aside", { className: "control-panel", "aria-label": "controller status and controls", children: [_jsxs("section", { children: [_jsx("h2", { children: "Device" }), _jsxs("dl", { children: [_jsxs("div", { children: [_jsx("dt", { children: "ID" }), _jsx("dd", { children: deviceId })] }), deviceAddress && (_jsxs("div", { children: [_jsx("dt", { children: "Address" }), _jsx("dd", { className: "address-value", children: deviceAddress })] })), _jsxs("div", { children: [_jsx("dt", { children: "Backend" }), _jsx("dd", { children: _jsx("a", { href: backendUrl, target: "_blank", rel: "noreferrer", children: backendUrl }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "Controller" }), _jsx("dd", { children: _jsx("a", { href: controllerUrl, target: "_blank", rel: "noreferrer", children: controllerUrl }) })] }), _jsxs("div", { children: [_jsx("dt", { children: "WS status" }), _jsx("dd", { className: `status ${connectionStatus}`, children: statusLabels[connectionStatus] })] }), _jsxs("div", { children: [_jsx("dt", { children: "Heartbeat" }), _jsx("dd", { children: heartbeatLabel })] })] })] }), _jsxs("section", { children: [_jsx("h2", { children: "Session" }), _jsxs("dl", { children: [_jsxs("div", { children: [_jsx("dt", { children: "Phase" }), _jsx("dd", { className: "phase-label", children: currentPhase })] }), _jsxs("div", { children: [_jsx("dt", { children: "QR expires" }), _jsx("dd", { children: typeof expiresInSeconds === 'number' ? `${expiresInSeconds}s` : '—' })] })] }), _jsxs("div", { className: "token-row", children: [_jsx("label", { htmlFor: "pairing-token", children: "Pairing token" }), _jsxs("div", { className: "token-value", children: [_jsx("input", { id: "pairing-token", type: "text", readOnly: true, value: pairingToken ?? '', placeholder: "Waiting for token\u2026" }), _jsx("button", { type: "button", onClick: handleCopyToken, disabled: !pairingToken, children: "Copy" })] })] }), qrPayloadJson && (_jsxs("div", { className: "qr-payload", children: [_jsxs("div", { className: "qr-payload-header", children: [_jsx("span", { children: "QR payload" }), _jsx("button", { type: "button", onClick: handleCopyQrPayload, children: "Copy JSON" })] }), _jsx("pre", { children: qrPayloadJson })] })), _jsx("button", { type: "button", className: "trigger-button", onClick: onTrigger, disabled: triggerDisabled, children: isTriggering ? 'Triggering…' : 'Trigger Session' }), triggerDisabled && !isTriggering && (_jsx("p", { className: "trigger-hint", children: "Trigger is available only while idle." }))] }), _jsxs("section", { children: [_jsx("h2", { children: "Metrics" }), metrics ? (_jsxs("div", { className: "metrics-grid", children: [_jsx(MetricTile, { label: "Stability", value: metrics.stability, suffix: "" }), _jsx(MetricTile, { label: "Focus", value: metrics.focus, suffix: "" }), _jsx(MetricTile, { label: "Composite", value: metrics.composite, suffix: "" })] })) : (_jsx("div", { className: "metrics-placeholder", children: "No metrics yet" }))] }), _jsxs("section", { className: "log-section", children: [_jsx("h2", { children: "Event log" }), _jsx(LogConsole, { entries: logs })] })] }));
}
function MetricTile({ label, value, suffix }) {
    const display = typeof value === 'number' ? value.toFixed(2) : '—';
    return (_jsxs("div", { className: "metric-tile", children: [_jsx("span", { className: "metric-label", children: label }), _jsxs("span", { className: "metric-value", children: [display, suffix] })] }));
}
