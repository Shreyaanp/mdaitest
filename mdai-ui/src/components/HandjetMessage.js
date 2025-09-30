import { jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useRef } from 'react';
const DEFAULT_DURATION = 3000;
export default function HandjetMessage({ lines, durationMs = DEFAULT_DURATION, onComplete }) {
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
    return (_jsx("main", { className: "handjet-message", "data-handjet-message": true, children: _jsx("p", { children: lines.map((line, index) => (_jsx("span", { children: line }, index))) }) }));
}
