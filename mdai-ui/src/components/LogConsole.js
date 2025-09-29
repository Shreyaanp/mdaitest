import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef } from 'react';
export default function LogConsole({ entries }) {
    const endRef = useRef(null);
    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [entries]);
    return (_jsxs("div", { className: "log-console", children: [entries.length === 0 ? (_jsx("div", { className: "log-placeholder", children: "Awaiting events\u2026" })) : (entries.map((entry) => (_jsxs("div", { className: `log-entry ${entry.level}`, children: [_jsx("span", { className: "time", children: new Date(entry.ts).toLocaleTimeString() }), _jsx("span", { className: "message", children: entry.message })] }, entry.id)))), _jsx("div", { ref: endRef })] }));
}
