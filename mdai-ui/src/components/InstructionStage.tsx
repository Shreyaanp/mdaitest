interface InstructionStageProps {
  title: string
  subtitle?: string
  className?: string
}

export default function InstructionStage({ title, subtitle, className }: InstructionStageProps) {
  return (
    <div className="overlay overlay--center">
      <div className={`overlay-card ${className ?? ''}`}>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
    </div>
  )
}
