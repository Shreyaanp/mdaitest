import { jsx as _jsx } from "react/jsx-runtime";
import { useMemo } from 'react';
import { QRCodeSVG } from 'qrcode.react';
export default function QRCodeStage({ token, qrPayload, expiresIn, status }) {
    const qrValue = useMemo(() => JSON.stringify(qrPayload), [qrPayload]);
    const heading = status ?? 'Scan to pair';
    const subtitle = status
        ? 'Scan the QR code to continue on mobile; waiting for activation.'
        : 'Use the mobile app to scan the QR code and continue.';
    const wsApp = typeof qrPayload?.ws_app_url === 'string' ? qrPayload.ws_app_url : undefined;
    const wsHardware = typeof qrPayload?.ws_hardware_url === 'string' ? qrPayload.ws_hardware_url : undefined;
    const serverHost = typeof qrPayload?.server_host === 'string' ? qrPayload.server_host : undefined;
    return (_jsx("div", { className: "overlay", children: _jsx("div", { className: "overlay-card", children: _jsx("div", { className: "qr-wrapper", children: _jsx(QRCodeSVG, { value: qrValue, size: 350, fgColor: "#111", bgColor: "#fff" }) }) }) }));
}
