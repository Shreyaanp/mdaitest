import { useEffect, useRef } from 'react'

interface HandjetMessageProps {
  lines: string[]
  durationMs?: number
  onComplete?: () => void
  showIcon?: boolean
}

const DEFAULT_DURATION = 3000

// Egyptian hieroglyph 𓅽 (Swallow) - rendered as inline SVG with silver color
const HieroglyphIcon = () => (
  <svg
    className="handjet-message__icon"
    width="160"
    height="160"
    viewBox="0 0 160 160"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Simplified hieroglyph inspired by 𓅽 */}
    <g className="hieroglyph-glow">
      {/* Body */}
      <ellipse cx="80" cy="85" rx="35" ry="45" fill="#C0C0C0" opacity="0.95" />
      
      {/* Head */}
      <circle cx="80" cy="45" r="22" fill="#C0C0C0" opacity="0.95" />
      
      {/* Wing left */}
      <path
        d="M 45 75 Q 20 65 15 85 Q 18 95 30 90 Q 40 85 45 90"
        fill="#C0C0C0"
        opacity="0.9"
      />
      
      {/* Wing right */}
      <path
        d="M 115 75 Q 140 65 145 85 Q 142 95 130 90 Q 120 85 115 90"
        fill="#C0C0C0"
        opacity="0.9"
      />
      
      {/* Tail feathers */}
      <path
        d="M 70 120 Q 65 135 68 145 M 80 125 Q 80 140 80 150 M 90 120 Q 95 135 92 145"
        stroke="#C0C0C0"
        strokeWidth="3"
        strokeLinecap="round"
        opacity="0.85"
      />
      
      {/* Eye */}
      <circle cx="75" cy="42" r="3" fill="#000" opacity="0.7" />
      
      {/* Beak */}
      <path
        d="M 90 42 L 100 45 L 90 48 Z"
        fill="#C0C0C0"
        opacity="0.9"
      />
    </g>
  </svg>
)

export default function HandjetMessage({ 
  lines, 
  durationMs = DEFAULT_DURATION, 
  onComplete,
  showIcon = false 
}: HandjetMessageProps) {
  const callbackRef = useRef<typeof onComplete>(onComplete)

  useEffect(() => {
    callbackRef.current = onComplete
  }, [onComplete])

  useEffect(() => {
    if (!callbackRef.current) {
      return
    }

    const timer = window.setTimeout(() => {
      callbackRef.current?.()
    }, durationMs)

    return () => {
      window.clearTimeout(timer)
    }
  }, [durationMs])

  return (
    <main className="handjet-message" data-handjet-message>
      {showIcon && (
        <div className="handjet-message__icon-container">
          <HieroglyphIcon />
        </div>
      )}
      <p>
        {lines.map((line, index) => (
          <span key={index}>{line}</span>
        ))}
      </p>
    </main>
  )
}
