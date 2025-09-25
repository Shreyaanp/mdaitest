import { useMemo } from 'react';
import { QRCodeSVG } from 'qrcode.react';
export default function QRCodeStage({ token, qrPayload, expiresIn }) {
    const qrValue = useMemo(() => (qrPayload ? JSON.stringify(qrPayload) : token ?? 'waiting_token'), [qrPayload, token]);
    return (<div className="overlay">
      <div className="overlay-card">
        <h1>Scan to pair</h1>
        <p>Use the mobile app to scan the QR code and continue.</p>
        <div className="qr-wrapper">
          <QRCodeSVG value={qrValue} size={240} includeMargin fgColor="#111" bgColor="#fff"/>
        </div>
        {token ? <p className="token-hint">Token: {token}</p> : null}
        {qrPayload && typeof qrPayload.server_host === 'string' ? (<p className="token-hint">Bridge: {String(qrPayload.server_host)}</p>) : null}
        {typeof expiresIn === 'number' ? (<p className="expires">Expires in {Math.round(expiresIn)} seconds</p>) : null}
      </div>
    </div>);
}
