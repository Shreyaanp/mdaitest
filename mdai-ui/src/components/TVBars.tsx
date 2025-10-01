import { useMemo } from 'react'
import type { CSSProperties } from 'react'

export type TVBarsMode = 'entry' | 'idle' | 'exit'

export interface TVBarsProps {
  fallMs?: number
  marqueeMs?: number
  mode?: TVBarsMode
}

export const TV_BARS_FALL_DURATION_MS = 1230  // 1.23 seconds for exit/entry animation
export const TV_BARS_MARQUEE_DURATION_MS = 6000

const STYLE_RULES = String.raw`
@keyframes fall {
  from { 
    background-size: 100% 0%;
  }
  to { 
    background-size: 100% 60%;
  }
}

@keyframes fall-exit {
  from { background-size: 100% 60%; }
  to { background-size: 100% 0%; }
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
  animation: fall var(--fall-duration) ease-in-out forwards;
}

main[data-tv-bars][data-mode="exit"] {
  animation: fall-exit var(--fall-duration) ease-in-out forwards;
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
}

main[data-tv-bars][data-mode="entry"]::before {
  /* During entry: slide in from left over 1.23s */
  animation: marquee-entry var(--fall-duration) ease-in-out forwards;
}

main[data-tv-bars][data-mode="exit"]::before {
  /* During exit: slide out to right over 1.23s */
  animation: marquee-exit var(--fall-duration) ease-in-out forwards;
}

@keyframes marquee-entry {
  from { transform: translateX(-120%); }
  to { transform: translateX(0); }
}

@keyframes marquee-exit {
  from { transform: translateX(0); }
  to { transform: translateX(120%); }
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
}

main[data-tv-bars][data-mode="entry"]::after {
  /* During entry: slide up from bottom over 1.23s */
  animation: bottom-entry var(--fall-duration) ease-in-out forwards;
}

main[data-tv-bars][data-mode="exit"]::after {
  /* During exit: slide down over 1.23s */
  animation: bottom-exit var(--fall-duration) ease-in-out forwards;
}

@keyframes bottom-entry {
  from { transform: translateY(130%); }
  to { transform: translateY(0); }
}

@keyframes bottom-exit {
  from { transform: translateY(0); }
  to { transform: translateY(130%); }
}
`

export function TVBars({
  fallMs = TV_BARS_FALL_DURATION_MS,
  marqueeMs = TV_BARS_MARQUEE_DURATION_MS,
  mode = 'idle'
}: TVBarsProps) {
  const mainStyle = useMemo(() => {
    return {
      position: 'relative',
      width: '100%',
      height: '100%',
      display: 'block',
      backgroundColor: 'transparent',
      backgroundImage:
        'linear-gradient(to right,#0038ff 0 14.285%,#ff0000 14.285% 28.57%,#ff00a8 28.57% 42.855%,#00c83b 42.855% 57.14%,#00d7e6 57.14% 71.425%,#d3c600 71.425% 85.71%,#bfbfbf 85.71% 100%)',
      backgroundRepeat: 'no-repeat',
      backgroundPosition: 'top left',
      backgroundSize: mode === 'entry' ? '100% 0%' : '100% 60%',
      overflow: 'hidden',
      // ALL THREE COMPONENTS use same --fall-duration for synchronized animation
      ['--fall-duration' as '--fall-duration']: `${fallMs}ms`,
      ['--marquee-duration' as '--marquee-duration']: `${marqueeMs}ms`
    } as CSSProperties
  }, [fallMs, marqueeMs, mode])

  return (
    <>
      <style>{STYLE_RULES}</style>
      <main
        data-tv-bars=""
        data-mode={mode}
        role="img"
        aria-label="SMPTE-style animation"
        style={mainStyle}
      />
    </>
  )
}

export default TVBars
