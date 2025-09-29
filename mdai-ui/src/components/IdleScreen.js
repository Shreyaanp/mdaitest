import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import HelloHumanHero from './HelloHumanHero';
import TVBars, { TV_BARS_FALL_DURATION_MS, TV_BARS_MARQUEE_DURATION_MS } from './TVBars';
export const IDLE_EXIT_DURATION_MS = TV_BARS_FALL_DURATION_MS;
export default function IdleScreen({ mode, showBars = true, onMockTof }) {
    return (_jsxs("div", { className: "idle-screen", "data-mode": mode, children: [_jsx(HelloHumanHero, {}), showBars ? (_jsx("div", { className: "idle-screen__bars", "aria-hidden": "true", children: _jsx(TVBars, { mode: mode, fallMs: TV_BARS_FALL_DURATION_MS, marqueeMs: TV_BARS_MARQUEE_DURATION_MS }) })) : null, onMockTof ? (_jsx("button", { type: "button", className: "idle-screen__mock-button", onClick: onMockTof, children: "Mock ToF" })) : null] }));
}
