import { useEffect, useRef } from 'react'

interface HandjetMessageProps {
  lines: string[]
  durationMs?: number
  onComplete?: () => void
  showIcon?: boolean
}

const DEFAULT_DURATION = 3000

// Disco ball GIF icon for scan completed
const DiscoIcon = () => (
  <img
    src="/hero/disco.gif"
    alt="Scan completed"
    className="handjet-message__icon"
    style={{
      width: '240px',
      height: '240px',
      objectFit: 'cover'
    }}
  />
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
      <p>
        {lines.map((line, index) => (
          <span className="specialkey" key={index}>{line}</span>
        ))}
      </p>
      {showIcon && (
        <div className="handjet-message__icon-container">
          <DiscoIcon />
        </div>
      )}
    </main>
  )
}
