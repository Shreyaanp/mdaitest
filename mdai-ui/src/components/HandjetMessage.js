import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef } from 'react';
const DEFAULT_DURATION = 3000;
// Egyptian hieroglyph 𓅽 (Swallow) - rendered as inline SVG with silver color
const HieroglyphIcon = () => (_jsx("svg", { className: "handjet-message__icon", width: "160", height: "160", viewBox: "0 0 160 160", fill: "none", xmlns: "http://www.w3.org/2000/svg", children: _jsxs("g", { className: "hieroglyph-glow", children: [_jsx("ellipse", { cx: "80", cy: "85", rx: "35", ry: "45", fill: "#C0C0C0", opacity: "0.95" }), _jsx("circle", { cx: "80", cy: "45", r: "22", fill: "#C0C0C0", opacity: "0.95" }), _jsx("path", { d: "M 45 75 Q 20 65 15 85 Q 18 95 30 90 Q 40 85 45 90", fill: "#C0C0C0", opacity: "0.9" }), _jsx("path", { d: "M 115 75 Q 140 65 145 85 Q 142 95 130 90 Q 120 85 115 90", fill: "#C0C0C0", opacity: "0.9" }), _jsx("path", { d: "M 70 120 Q 65 135 68 145 M 80 125 Q 80 140 80 150 M 90 120 Q 95 135 92 145", stroke: "#C0C0C0", strokeWidth: "3", strokeLinecap: "round", opacity: "0.85" }), _jsx("circle", { cx: "75", cy: "42", r: "3", fill: "#000", opacity: "0.7" }), _jsx("path", { d: "M 90 42 L 100 45 L 90 48 Z", fill: "#C0C0C0", opacity: "0.9" })] }) }));
export default function HandjetMessage({ lines, durationMs = DEFAULT_DURATION, onComplete, showIcon = false }) {
    const callbackRef = useRef(onComplete);
    useEffect(() => {
        callbackRef.current = onComplete;
    }, [onComplete]);
    useEffect(() => {
        if (!callbackRef.current) {
            return;
        }
        const timer = window.setTimeout(() => {
            callbackRef.current?.();
        }, durationMs);
        return () => {
            window.clearTimeout(timer);
        };
    }, [durationMs]);
    return (_jsxs("main", { className: "handjet-message", "data-handjet-message": true, children: [showIcon && (_jsx("div", { className: "handjet-message__icon-container", children: _jsx(HieroglyphIcon, {}) })), _jsx("p", { children: lines.map((line, index) => (_jsx("span", { children: line }, index))) })] }));
}
