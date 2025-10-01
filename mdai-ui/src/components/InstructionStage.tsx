import { useEffect, useState } from 'react'

interface InstructionStageProps {
  title: string
  subtitle?: string
  className?: string
  minDurationMs?: number  // Minimum display duration (for fallback screens)
}

export default function InstructionStage({ 
  title, 
  subtitle, 
  className,
  minDurationMs = 1800  // Default 1.8s minimum for fallbacks
}: InstructionStageProps) {
  const [canTransition, setCanTransition] = useState(false)
  
  // Enforce minimum display duration for fallback screens
  useEffect(() => {
    if (minDurationMs && minDurationMs > 0) {
      const timer = setTimeout(() => {
        setCanTransition(true)
      }, minDurationMs)
      
      return () => clearTimeout(timer)
    } else {
      setCanTransition(true)
    }
  }, [minDurationMs])
  
  return (
    <div className="overlay overlay--center" data-can-transition={canTransition}>
      <div className={`overlay-card ${className ?? ''}`}>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
    </div>
  )
}
