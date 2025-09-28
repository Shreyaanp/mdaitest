import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef } from 'react';
const DEFAULT_DURATION = 3000;
const DEFAULT_LINES = ['uploading encrypted', 'embeddings'];
export default function UploadingScreen({ durationMs = DEFAULT_DURATION, onComplete, headlineLines = DEFAULT_LINES }) {
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
    return (_jsx("main", { className: "uploading-screen", "data-uploading-screen": true, children: _jsxs("div", { className: "uploading-screen__stack", children: [_jsx("div", { className: "uploading-screen__ring", "aria-hidden": "true" }), _jsx("p", { children: headlineLines.map((line) => (_jsx("span", { children: line }, line))) })] }) }));
}
