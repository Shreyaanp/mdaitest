import { jsx as _jsx } from "react/jsx-runtime";
import { useMemo } from 'react';
import { QRCodeSVG } from 'qrcode.react';
/**
 * QRCodeStage - Displays QR code for mobile app pairing
 *
 * Clean display of just the QR code.
 * The "Scan this to get started" message is shown in SCAN_PROMPT phase (before this).
 */
export default function QRCodeStage({ token, qrPayload, expiresIn }) {
    const qrValue = useMemo(() => JSON.stringify(qrPayload), [qrPayload]);
    return (_jsx("div", { className: "overlay", children: _jsx("div", { className: "overlay-card", children: _jsx("div", { className: "qr-wrapper", children: _jsx(QRCodeSVG, { value: qrValue, size: 350, fgColor: "#111", bgColor: "#fff" }) }) }) }));
}
