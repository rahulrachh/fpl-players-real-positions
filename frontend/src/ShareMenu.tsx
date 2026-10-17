// The share button in the pitch's bottom-right corner and its menu: share the
// card as an image through the device's share sheet. Shown only where the
// browser can share files (most phones). The image is drawn as soon as the
// menu opens, because phones only let a page share straight after a tap.

import { type RefObject, useEffect, useRef, useState } from 'react'

import { canSharePng, renderPng, sharePng } from './exportImage'

type Props = {
  card: RefObject<HTMLElement | null>
  filename: string
  title: string
}

// The image drawn for one request, keyed by filename and attempt: while the key
// differs from the current one, it is still being drawn.
type Drawn = { key: string } & ({ png: Blob } | { failed: true })

export default function ShareMenu({ card, filename, title }: Props) {
  const [open, setOpen] = useState(false)
  const [drawn, setDrawn] = useState<Drawn | null>(null)
  const [shareFailed, setShareFailed] = useState(false)
  // Bumped by "Try again" to draw the image again.
  const [attempt, setAttempt] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const canShare = canSharePng()

  const key = `${filename}#${attempt}`
  const current = drawn !== null && drawn.key === key ? drawn : null
  const png = current !== null && 'png' in current ? current.png : null
  const failed = current !== null && 'failed' in current

  // Draws the image for this card each time the menu opens.
  useEffect(() => {
    if (!open || !card.current) return
    let cancelled = false
    renderPng(card.current)
      .then((png) => !cancelled && setDrawn({ key, png }))
      .catch(() => !cancelled && setDrawn({ key, failed: true }))
    return () => {
      cancelled = true
    }
  }, [open, card, key])

  // Closes on Escape or a tap outside the menu.
  useEffect(() => {
    if (!open) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    function onPointer(event: PointerEvent) {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('pointerdown', onPointer)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pointerdown', onPointer)
    }
  }, [open])

  function toggle() {
    // A fresh drawing each time the menu opens.
    if (!open) {
      setDrawn(null)
      setShareFailed(false)
    }
    setOpen(!open)
  }

  async function share() {
    if (!png) return
    try {
      if (await sharePng(png, filename, title)) setOpen(false)
    } catch {
      setShareFailed(true)
    }
  }

  const ready = png !== null
  if (!canShare) return null
  return (
    <div className="share" ref={root} data-export-ignore>
      {open && (
        <div className="share-menu" role="dialog" aria-label="Share this gameweek">
          <button type="button" onClick={share} disabled={!ready}>
            Share image
          </button>
          {!current && <p className="share-status">Preparing the image…</p>}
          {failed && (
            <p className="share-status error">
              Couldn't create the image.{' '}
              <button type="button" className="link" onClick={() => setAttempt((n) => n + 1)}>
                Try again
              </button>
            </p>
          )}
          {shareFailed && <p className="share-status error">Sharing didn't work here.</p>}
        </div>
      )}
      <button
        type="button"
        className="share-button"
        aria-label="Share as image"
        title="Share as image"
        aria-expanded={open}
        onClick={toggle}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 15V4M7.5 8.5 12 4l4.5 4.5M6 12H5v8h14v-8h-1" />
        </svg>
      </button>
    </div>
  )
}
