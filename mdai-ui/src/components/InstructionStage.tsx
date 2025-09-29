import { useEffect, useMemo, useRef, useState } from 'react'

interface InstructionStageProps {
  title: string
  subtitle?: string
  time?: number
  randomState?: boolean
  rotatingMessages?: string[],
  className?: string
}


const PREPARING_TEXTS: string[] =  [
  "Quantum Spaghetti-fying…",
  "Banana Protocol-ing…",
  "Cosmic Zoodle Crunching…",
  "Infinite Waffle Syncing…",
  "Turbo Goose-frying…",
  "Elastic Pickle-fying…",
  "Lunar Noodle Juggling…",
  "Chaotic Jelly Uploading…",
  "Oblivion Cupcake-ing…",
  "Galactic Toaster-fying…"]

const ROTATE_INTERVAL_MS = 2000
const TRANSITION_MS = 180

function pickNextRandom(messages: string[], exclude?: string): string {
  if (messages.length === 0) return ''
  if (messages.length === 1) return messages[0]
  let next = messages[Math.floor(Math.random() * messages.length)]
  if (exclude && messages.length > 1) {
    let guard = 0
    while (next === exclude && guard++ < 6) {
      next = messages[Math.floor(Math.random() * messages.length)]
    }
  }
  return next
}

export default function InstructionStage({ title, subtitle, time, randomState, rotatingMessages, className }: InstructionStageProps) {
  const isRandom = randomState === true
  const messages = useMemo(() => (rotatingMessages && rotatingMessages.length > 0 ? rotatingMessages : PREPARING_TEXTS), [rotatingMessages])
  const [displayText, setDisplayText] = useState<string>(() => (isRandom ? pickNextRandom(messages) : title))
  const [hidden, setHidden] = useState<boolean>(false)
  const intervalRef = useRef<number | null>(null)
  const fadeRef = useRef<number | null>(null)

  useEffect(() => {
    if (!isRandom) {
      setDisplayText(title)
      return
    }

    const startRotation = () => {
      intervalRef.current = window.setInterval(() => {
        setHidden(true)
        fadeRef.current = window.setTimeout(() => {
          setDisplayText((prev) => pickNextRandom(messages, prev))
          setHidden(false)
        }, TRANSITION_MS)
      }, ROTATE_INTERVAL_MS)
    }

    startRotation()

    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current)
      if (fadeRef.current) window.clearTimeout(fadeRef.current)
      intervalRef.current = null
      fadeRef.current = null
    }
  }, [isRandom, title, messages])

  return (
    <div className="overlay overlay--center">
      <div className={`overlay-card ${className ?? ''}`}>
        <h1>
          <span className={`rotating-text${hidden ? ' hidden' : ''}`}>{displayText}</span>
        </h1>
      </div>
    </div>
  )
}
