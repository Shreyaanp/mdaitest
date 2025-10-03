import { useEffect } from 'react'

const DEFAULT_TITLE = 'Camera Preview'

interface PreviewSurfaceProps {
  visible: boolean
  previewUrl: string
  title?: string
}

export default function PreviewSurface({
  visible,
  previewUrl,
  title = DEFAULT_TITLE
}: PreviewSurfaceProps) {
  console.log('📹 [PREVIEW SURFACE] Rendered | visible:', visible, '| previewUrl:', previewUrl)

  // Placeholder surface; stream disabled in favor of a static GIF
  useEffect(() => {
    console.log('📹 [PREVIEW EFFECT] Placeholder active | visible:', visible)
  }, [visible])

  const classNames = [
    'preview-surface',
    visible ? 'visible' : 'hidden'
  ]

  return (
    <div className={classNames.join(' ')} data-preview-surface>
      <div className="preview-surface__status" aria-live="polite">Scanning…</div>
      <img
        className="preview-surface__img preview-surface__media"
        src="/hero/scan.gif"
        alt={title || 'Scanning placeholder'}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
          backgroundColor: '#000'
        }}
      />
    </div>
  )
}
