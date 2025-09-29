import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo } from 'react';
export const TV_BARS_FALL_DURATION_MS = 4000;
export const TV_BARS_MARQUEE_DURATION_MS = 6000;
const STYLE_RULES = String.raw `
@keyframes fall {
  0% { background-size: 100% 0%; }
  60% { background-size: 100% 60%; }
  100% { background-size: 100% 60%; }
}

@keyframes fall-exit {
  0% { background-size: 100% 60%; }
  100% { background-size: 100% 0%; }
}

@keyframes marquee {
  from { background-position: 100% 0; }
  to { background-position: 0% 0; }
}

main[data-tv-bars] {
  /* Stationary by default; entry/exit modes control animations */
  --marquee-gradient: linear-gradient(
    to right,
    #bfbfbf 0 14.285%,
    #000 14.285% 28.57%,
    #00d7e6 28.57% 42.855%,
    #000 42.855% 57.14%,
    #ff00a8 57.14% 71.425%,
    #000 71.425% 85.71%,
    #0038ff 85.71% 100%
  );
}

main[data-tv-bars][data-mode="entry"] {
  animation: fall var(--fall-duration) linear forwards;
}

main[data-tv-bars][data-mode="exit"] {
  background-size: 100% 60%;
  animation: fall-exit var(--fall-duration) cubic-bezier(0.45, 0, 0.45, 1) forwards;
  --marquee-gradient: linear-gradient(
    to right,
    #bfbfbf 0 14.285%,
    #000 14.285% 28.57%,
    #00d7e6 28.57% 42.855%,
    #000 42.855% 57.14%,
    #ff00a8 57.14% 71.425%,
    #000 71.425% 85.71%,
    #000 85.71% 100%
  );
}

main[data-tv-bars]::before {
  content: "";
  position: absolute;
  left: 0;
  top: 60%;
  width: 100%;
  height: 10%;
  background-image: var(--marquee-gradient);
  background-size: 200% 100%;
  background-repeat: no-repeat;
  animation: marquee var(--marquee-duration) linear infinite;
  transform: translateX(0);
  transition: transform var(--exit-duration) cubic-bezier(0.55, 0, 0.45, 1);
}

main[data-tv-bars][data-mode="exit"]::before {
  transform: translateX(120%);
}

main[data-tv-bars]::after {
  content: "";
  position: absolute;
  left: 0;
  top: 70%;
  width: 100%;
  height: 30%;
  background: linear-gradient(
    to right,
    #000 0 16.66%,
    #bfbfbf 16.66% 33.32%,
    #000 33.32% 49.98%,
    #0a3a8a 49.98% 66.64%,
    #fff 66.64% 83.3%,
    #0a3a8a 83.3% 100%
  );
  transform: translateY(0);
  transition: transform var(--exit-duration) cubic-bezier(0.55, 0, 0.45, 1);
}

main[data-tv-bars][data-mode="exit"]::after {
  transform: translateY(130%);
}
`;
export function TVBars({ fallMs = TV_BARS_FALL_DURATION_MS, marqueeMs = TV_BARS_MARQUEE_DURATION_MS, mode = 'idle' }) {
    const exitDuration = fallMs;
    const mainStyle = useMemo(() => {
        return {
            position: 'relative',
            width: '100%',
            height: '100%',
            display: 'block',
            backgroundColor: 'transparent',
            backgroundImage: 'linear-gradient(to right,#0038ff 0 14.285%,#ff0000 14.285% 28.57%,#ff00a8 28.57% 42.855%,#00c83b 42.855% 57.14%,#00d7e6 57.14% 71.425%,#d3c600 71.425% 85.71%,#bfbfbf 85.71% 100%)',
            backgroundRepeat: 'no-repeat',
            backgroundPosition: 'top left',
            backgroundSize: mode === 'entry' ? '100% 0%' : '100% 60%',
            overflow: 'hidden',
            ['--fall-duration']: `${fallMs}ms`,
            ['--marquee-duration']: `${marqueeMs}ms`,
            ['--exit-duration']: `${exitDuration}ms`
        };
    }, [fallMs, marqueeMs, mode, exitDuration]);
    return (_jsxs(_Fragment, { children: [_jsx("style", { children: STYLE_RULES }), _jsx("main", { "data-tv-bars": "", "data-mode": mode, role: "img", "aria-label": "SMPTE-style animation", style: mainStyle })] }));
}
export default TVBars;
