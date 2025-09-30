import { useEffect, useRef } from 'react'

interface UploadingScreenProps {
  durationMs?: number
  onComplete?: () => void
  headlineLines?: string[]
}

const DEFAULT_DURATION = 3000
const DEFAULT_LINES = ['uploading encrypted', 'embeddings']

export default function UploadingScreen({
  durationMs = DEFAULT_DURATION,
  onComplete,
  headlineLines = DEFAULT_LINES
}: UploadingScreenProps) {
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
    <main className="uploading-screen" data-uploading-screen>
      <div className="uploading-screen__stack">
        <div className="uploading-screen__ring" aria-hidden="true" />
        <p>
          {headlineLines.map((line) => (
            <span key={line}>{line}</span>
          ))}
        </p>
      </div>
    </main>
  )
}
