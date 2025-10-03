import { ReactNode } from 'react'

interface CRTWrapperEffectProps {
  children: ReactNode
  enabled?: boolean
  curvature?: number
  vignette?: number
  scanline?: number
  bloom?: number
  chromAberr?: number
}

export default function CRTWrapperEffect({
  children,
  enabled = true,
  curvature = 0.05,
  vignette = 0.3,
  scanline = 0.8,
  bloom = 0.2,
  chromAberr = 1.5
}: CRTWrapperEffectProps) {
  if (!enabled) {
    return <>{children}</>
  }

  return (
    <main className="crt-scanlines">
      <div className="crt-screen">
        {children}
        <div className="crt-overlay">
          <style>{`
            /* CRT Container */
            .crt-scanlines {
              position: relative;
              width: 100vw;
              height: 100vh;
              overflow: hidden;
              background: #1b2838;
            }

            /* Screen with curvature */
            .crt-screen {
              position: relative;
              width: 100%;
              height: 100%;
              ${curvature > 0 ? `
                transform: perspective(${400 - curvature * 2000}px)
                          rotateX(${curvature * 10}deg)
                          rotateY(${curvature * 5}deg)
                          scale(${1 + curvature * 0.3});
                transform-origin: center center;
                border-radius: ${curvature * 50}px;
              ` : ''}
            }

            /* Main CRT overlay effects */
            .crt-overlay {
              position: absolute;
              top: 0;
              left: 0;
              width: 100%;
              height: 100%;
              pointer-events: none;
              z-index: 9999;
            }

            /* Scanlines effect */
            .crt-overlay::before {
              content: "";
              position: absolute;
              top: 0;
              left: 0;
              width: 100%;
              height: 100%;
              background: linear-gradient(
                transparent 50%,
                rgba(0, 0, 0, ${scanline * 0.4}) 50%
              ),
              linear-gradient(
                90deg,
                rgba(255, 0, 0, ${chromAberr * 0.01}),
                rgba(0, 255, 0, ${chromAberr * 0.005}),
                rgba(0, 0, 255, ${chromAberr * 0.01})
              );
              background-size: 100% 2px, 3px 100%;
              z-index: 2;
              opacity: ${scanline};
            }

            /* CRT screen texture and vignette */
            .crt-overlay::after {
              content: "";
              position: absolute;
              top: 0;
              left: 0;
              width: 100%;
              height: 100%;
              background:
                radial-gradient(
                  ellipse at center,
                  transparent 30%,
                  rgba(0, 0, 0, ${vignette * 0.4}) 70%,
                  rgba(0, 0, 0, ${vignette * 0.8}) 100%
                ),
                repeating-linear-gradient(
                  0deg,
                  transparent,
                  transparent 2px,
                  rgba(0, 0, 0, 0.1) 2px,
                  rgba(0, 0, 0, 0.1) 4px
                );
              z-index: 1;
            }

            /* Bloom effect */
            ${bloom > 0 ? `
              .crt-screen {
                filter: brightness(${1 + bloom * 0.3})
                        contrast(${1 + bloom * 0.5})
                        saturate(${1 + bloom * 0.8});
              }
              .crt-screen::before {
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: radial-gradient(
                  circle at center,
                  rgba(255, 255, 255, ${bloom * 0.1}) 0%,
                  transparent 50%
                );
                mix-blend-mode: screen;
                z-index: -1;
              }
            ` : ''}

            /* Chromatic aberration text shadow effect */
            ${chromAberr > 0 ? `
              .crt-screen * {
                text-shadow:
                  ${chromAberr * 0.5}px 0 rgba(255, 0, 0, 0.5),
                  -${chromAberr * 0.5}px 0 rgba(0, 255, 255, 0.5) !important;
              }
            ` : ''}

            /* Flickering animation */
            @keyframes crt-flicker {
              0% { opacity: 1; }
              98% { opacity: 1; }
              99% { opacity: 0.98; }
              100% { opacity: 1; }
            }

            /* Jitter animation */
            @keyframes crt-jitter {
              0% { transform: translateX(0); }
              1% { transform: translateX(-1px); }
              2% { transform: translateX(1px); }
              3% { transform: translateX(0); }
              100% { transform: translateX(0); }
            }

            .crt-overlay {
              animation: crt-flicker 0.15s infinite linear;
            }

            ${scanline > 0.5 ? `
              .crt-screen {
                animation: crt-jitter 0.1s infinite;
              }
            ` : ''}
          `}</style>
        </div>
      </div>
    </main>
  )
}


