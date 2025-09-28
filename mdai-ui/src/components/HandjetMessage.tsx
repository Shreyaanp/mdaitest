import { useEffect, useRef } from 'react'

interface HandjetMessageProps {
  lines: string[]
  durationMs?: number
  onComplete?: () => void
}

const DEFAULT_DURATION = 3000

export default function HandjetMessage({ lines, durationMs = DEFAULT_DURATION, onComplete }: HandjetMessageProps) {
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
          <span key={index}>{line}</span>
        ))}
      </p>
    </main>
  )
}
