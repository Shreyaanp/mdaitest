import { jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useMemo, useRef, useState } from 'react';
const PREPARING_TEXTS = [
    "Quantum Spaghetti-fying…",
    "Banana Protocol-ing…",
    "Cosmic Zoodle Crunching…",
    "Infinite Waffle Syncing…",
    "Turbo Goose-frying…",
    "Elastic Pickle-fying…",
    "Lunar Noodle Juggling…",
    "Chaotic Jelly Uploading…",
    "Oblivion Cupcake-ing…",
    "Galactic Toaster-fying…"
];
const ROTATE_INTERVAL_MS = 2000;
const TRANSITION_MS = 180;
function pickNextRandom(messages, exclude) {
    if (messages.length === 0)
        return '';
    if (messages.length === 1)
        return messages[0];
    let next = messages[Math.floor(Math.random() * messages.length)];
    if (exclude && messages.length > 1) {
        let guard = 0;
        while (next === exclude && guard++ < 6) {
            next = messages[Math.floor(Math.random() * messages.length)];
        }
    }
    return next;
}
export default function InstructionStage({ title, subtitle, time, randomState, rotatingMessages, className }) {
    const isRandom = randomState === true;
    const messages = useMemo(() => (rotatingMessages && rotatingMessages.length > 0 ? rotatingMessages : PREPARING_TEXTS), [rotatingMessages]);
    const [displayText, setDisplayText] = useState(() => (isRandom ? pickNextRandom(messages) : title));
    const [hidden, setHidden] = useState(false);
    const intervalRef = useRef(null);
    const fadeRef = useRef(null);
    useEffect(() => {
        if (!isRandom) {
            setDisplayText(title);
            return;
        }
        const startRotation = () => {
            intervalRef.current = window.setInterval(() => {
                setHidden(true);
                fadeRef.current = window.setTimeout(() => {
                    setDisplayText((prev) => pickNextRandom(messages, prev));
                    setHidden(false);
                }, TRANSITION_MS);
            }, ROTATE_INTERVAL_MS);
        };
        startRotation();
        return () => {
            if (intervalRef.current)
                window.clearInterval(intervalRef.current);
            if (fadeRef.current)
                window.clearTimeout(fadeRef.current);
            intervalRef.current = null;
            fadeRef.current = null;
        };
    }, [isRandom, title, messages]);
    return (_jsx("div", { className: "overlay overlay--center", children: _jsx("div", { className: `overlay-card ${className ?? ''}`, children: _jsx("h1", { children: _jsx("span", { className: `rotating-text${hidden ? ' hidden' : ''}`, children: displayText }) }) }) }));
}
