import { useMemo } from 'react';
import LogConsole from './LogConsole';
const statusLabels = {
    connecting: 'Connecting…',
    open: 'Connected',
    closed: 'Disconnected'
};
export default function ControlPanel(props) {
    const { deviceId, deviceAddress, backendUrl, controllerUrl, connectionStatus, currentPhase, pairingToken, qrPayload, expiresInSeconds, lastHeartbeatSeconds, metrics, logs, onTrigger, triggerDisabled, isTriggering, onTofTrigger, tofTriggerDisabled, isTofTriggering } = props;
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
    return (<aside className="control-panel" aria-label="controller status and controls">
      <section>
        <h2>Device</h2>
        <dl>
          <div>
            <dt>ID</dt>
            <dd>{deviceId}</dd>
          </div>
          {deviceAddress && (<div>
              <dt>Address</dt>
              <dd className="address-value">{deviceAddress}</dd>
            </div>)}
          <div>
            <dt>Backend</dt>
            <dd><a href={backendUrl} target="_blank" rel="noreferrer">{backendUrl}</a></dd>
          </div>
          <div>
            <dt>Controller</dt>
            <dd><a href={controllerUrl} target="_blank" rel="noreferrer">{controllerUrl}</a></dd>
          </div>
          <div>
            <dt>WS status</dt>
            <dd className={`status ${connectionStatus}`}>{statusLabels[connectionStatus]}</dd>
          </div>
          <div>
            <dt>Heartbeat</dt>
            <dd>{heartbeatLabel}</dd>
          </div>
        </dl>
      </section>

      <section>
        <h2>Session</h2>
        <dl>
          <div>
            <dt>Phase</dt>
            <dd className="phase-label">{currentPhase}</dd>
          </div>
          <div>
            <dt>QR expires</dt>
            <dd>{typeof expiresInSeconds === 'number' ? `${expiresInSeconds}s` : '—'}</dd>
          </div>
        </dl>
        <div className="token-row">
          <label htmlFor="pairing-token">Pairing token</label>
          <div className="token-value">
            <input id="pairing-token" type="text" readOnly value={pairingToken ?? ''} placeholder="Waiting for token…"/>
            <button type="button" onClick={handleCopyToken} disabled={!pairingToken}>
              Copy
            </button>
          </div>
        </div>
        {qrPayloadJson && (<div className="qr-payload">
            <div className="qr-payload-header">
              <span>QR payload</span>
              <button type="button" onClick={handleCopyQrPayload}>
                Copy JSON
              </button>
            </div>
            <pre>{qrPayloadJson}</pre>
          </div>)}
        <div className="debug-controls">
          <button type="button" className="trigger-button secondary" onClick={onTofTrigger} disabled={tofTriggerDisabled}>
            {isTofTriggering ? 'ToF triggering…' : 'ToF Trigger'}
          </button>
        </div>
        <button type="button" className="trigger-button" onClick={onTrigger} disabled={triggerDisabled}>
          {isTriggering ? 'Triggering…' : 'Trigger Session'}
        </button>
        {triggerDisabled && !isTriggering && (<p className="trigger-hint">Trigger is available only while idle.</p>)}
      </section>

      <section>
        <h2>Metrics</h2>
        {metrics ? (<div className="metrics-grid">
            <MetricTile label="Stability" value={metrics.stability} suffix=""/>
            <MetricTile label="Focus" value={metrics.focus} suffix=""/>
            <MetricTile label="Composite" value={metrics.composite} suffix=""/>
          </div>) : (<div className="metrics-placeholder">No metrics yet</div>)}
      </section>

      <section className="log-section">
        <h2>Event log</h2>
        <LogConsole entries={logs}/>
      </section>
    </aside>);
}
function MetricTile({ label, value, suffix }) {
    const display = typeof value === 'number' ? value.toFixed(2) : '—';
    return (<div className="metric-tile">
      <span className="metric-label">{label}</span>
      <span className="metric-value">
        {display}
        {suffix}
      </span>
    </div>);
}
