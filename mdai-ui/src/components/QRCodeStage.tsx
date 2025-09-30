import { useMemo } from 'react'
import { QRCodeSVG } from 'qrcode.react'

interface QRCodeStageProps {
  token?: string
  qrPayload?: Record<string, unknown>
  expiresIn?: number
}

/**
 * QRCodeStage - Displays QR code for mobile app pairing
 * 
 * Clean display of just the QR code.
 * The "Scan this to get started" message is shown in SCAN_PROMPT phase (before this).
 */
export default function QRCodeStage({ token, qrPayload, expiresIn }: QRCodeStageProps) {
  const qrValue = useMemo(() => JSON.stringify(qrPayload), [qrPayload])

  return (
    <div className="overlay">
      <div className="overlay-card">
        <div className="qr-wrapper">
          <QRCodeSVG value={qrValue} size={350} fgColor="#111" bgColor="#fff" />
        </div>
      </div>
    </div>
  )
}
