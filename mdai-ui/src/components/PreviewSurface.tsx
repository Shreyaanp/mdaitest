interface PreviewSurfaceProps {
  visible: boolean
  previewUrl: string
  title?: string
}

const DEFAULT_TITLE = 'Camera preview'

export default function PreviewSurface({
  visible,
  previewUrl,
  title = DEFAULT_TITLE
}: PreviewSurfaceProps) {
  const classNames = [
    'preview-surface',
    visible ? 'visible' : 'hidden'
  ]

  return (
    <div className={classNames.join(' ')} data-preview-surface>
      {visible ? (
        <iframe
          title={title}
          className="preview-surface__media preview-surface__iframe"
          src={previewUrl}
          allow="autoplay"
        />
      ) : null}
    </div>
  )
}
