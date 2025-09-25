import { useMemo } from 'react'
import { QRCodeSVG } from 'qrcode.react'

interface QRCodeStageProps {
  token?: string
  qrPayload?: Record<string, unknown>
  expiresIn?: number
  status?: string
}

export default function QRCodeStage({ token, qrPayload, expiresIn, status }: QRCodeStageProps) {
  const qrValue = useMemo(() => JSON.stringify(qrPayload), [qrPayload])

  const heading = status ?? 'Scan to pair'
  const subtitle = status
    ? 'Scan the QR code to continue on mobile; waiting for activation.'
    : 'Use the mobile app to scan the QR code and continue.'

  const wsApp = typeof qrPayload?.ws_app_url === 'string' ? qrPayload.ws_app_url : undefined
  const wsHardware =
    typeof qrPayload?.ws_hardware_url === 'string' ? qrPayload.ws_hardware_url : undefined
  const serverHost = typeof qrPayload?.server_host === 'string' ? qrPayload.server_host : undefined

  return (
    <div className="overlay">
      <div className="overlay-card">
        <h1>{heading}</h1>
        <p>{subtitle}</p>
        <div className="qr-wrapper">
          <QRCodeSVG value={qrValue} size={240} includeMargin fgColor="#111" bgColor="#fff" />
        </div>
        {token ? <p className="token-hint">Token: {token}</p> : null}
        {serverHost ? <p className="token-hint">Bridge host: {serverHost}</p> : null}
        <div className="qr-metadata">
          {wsApp ? (
            <p className="qr-endpoint">
              <span>App WS:</span>
              <code>{wsApp}</code>
            </p>
          ) : null}
          {wsHardware ? (
            <p className="qr-endpoint">
              <span>Hardware WS:</span>
              <code>{wsHardware}</code>
            </p>
          ) : null}
        </div>
        {typeof expiresIn === 'number' ? (
          <p className="expires">Expires in {Math.round(expiresIn)} seconds</p>
        ) : null}
      </div>
    </div>
  )
}
