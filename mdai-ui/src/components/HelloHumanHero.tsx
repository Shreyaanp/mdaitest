interface HelloHumanHeroProps {
  logoSrc?: string
  helixSrc?: string
}

const DEFAULT_LOGO_SRC = '/hero/logo.svg'
const DEFAULT_HELIX_SRC = '/hero/test.gif'

export default function HelloHumanHero({ logoSrc, helixSrc }: HelloHumanHeroProps) {
  return (
    <main className="hero" data-hello-hero>
      <div className="hero__helix" aria-hidden="true">
        <img src={helixSrc ?? DEFAULT_HELIX_SRC} alt="DNA helix animation" />
      </div>
      <div className="hero__content">
        <img className="hero__logo" src={logoSrc ?? DEFAULT_LOGO_SRC} alt="Mercle logo" />
        <h1 className="hero__headline">
          <span>hello</span>
          <span>human</span>
        </h1>
      </div>
    </main>
  )
}
