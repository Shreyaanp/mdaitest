import { useEffect, useRef } from 'react'

interface ProcessingScreenProps {
  imageSrc?: string
  imageAlt?: string
  durationMs?: number
  onComplete?: () => void
  statusLines?: string[]
  guidanceLines?: string[]
}

const DEFAULT_IMAGE_SRC = '/hero/test1.gif'
const DEFAULT_STATUS = ['processing scan', "hold steady"]
const DEFAULT_GUIDANCE = ['align your face with the frame', 'remove hats or glasses', 'keep your gaze forward']
const DEFAULT_DURATION = 3000

export default function ProcessingScreen({
  imageSrc = DEFAULT_IMAGE_SRC,
  imageAlt = 'Processing animation',
  durationMs = DEFAULT_DURATION,
  onComplete,
  statusLines = DEFAULT_STATUS,
  guidanceLines = DEFAULT_GUIDANCE
}: ProcessingScreenProps) {
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
    <main className="processing-screen" data-processing-screen>
    
      <div className="processing-screen__status">
        {statusLines.map((line) => (
          <span key={line}>{line}</span>
        ))}
      </div>
      <img className="processing-screen__hero" src={imageSrc} alt={imageAlt} />
    </main>
  )
}
