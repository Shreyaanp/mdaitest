import HelloHumanHero from './HelloHumanHero'
import TVBars, {
  TV_BARS_FALL_DURATION_MS,
  TV_BARS_MARQUEE_DURATION_MS,
  type TVBarsMode
} from './TVBars'

export const IDLE_EXIT_DURATION_MS = TV_BARS_FALL_DURATION_MS

interface IdleScreenProps {
  mode: TVBarsMode
  showBars?: boolean
}

export default function IdleScreen({ mode, showBars = true }: IdleScreenProps) {
  return (
    <div className="idle-screen" data-mode={mode}>
      <HelloHumanHero />
      {showBars ? (
        <div className="idle-screen__bars" aria-hidden="true">
          <TVBars
            mode={mode}
            fallMs={TV_BARS_FALL_DURATION_MS}
            marqueeMs={TV_BARS_MARQUEE_DURATION_MS}
          />
        </div>
      ) : null}
    </div>
  )
}
