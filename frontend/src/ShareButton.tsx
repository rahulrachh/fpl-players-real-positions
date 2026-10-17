// The share button in the pitch's bottom-right corner: one tap hands the card,
// as an image, to the device's share sheet. Shown only where the browser can
// share files (most phones). Phones only let a page share straight after a
// tap, so the image is drawn ahead of time, when the card appears and again
// when the theme changes. A tap before it is ready draws it then; if the
// browser no longer counts that as straight after the tap, a note asks for a
// second tap, which shares the image just drawn.

import { type RefObject, useCallback, useEffect, useRef, useState } from 'react'

import { canSharePng, renderPng, sharePng } from './exportImage'

type Props = {
  card: RefObject<HTMLElement | null>
  filename: string
  title: string
}

// Wait after the card (or theme) changes before drawing, so the drawing never
// competes with the page settling.
const PREDRAW_DELAY_MS = 400
// How long a note stays up.
const NOTE_MS = 4000

type Note = { text: string; error?: boolean }

export default function ShareButton({ card, filename, title }: Props) {
  const canShare = canSharePng()
  // The image drawn for the card as it is now, keyed by filename and theme.
  const drawn = useRef<{ key: string; png: Promise<Blob> } | null>(null)
  const [themeVersion, setThemeVersion] = useState(0)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<Note | null>(null)
  const key = `${filename}#${themeVersion}`

  const draw = useCallback(() => {
    if (drawn.current?.key !== key && card.current) {
      const png = renderPng(card.current)
      drawn.current = { key, png }
      // A failed drawing is dropped, so the next tap tries again.
      png.catch(() => {
        if (drawn.current?.png === png) drawn.current = null
      })
    }
    return drawn.current?.key === key ? drawn.current.png : null
  }, [card, key])

  // Redraws when the theme changes: the toggle (data-theme on <html>) or the
  // device setting.
  useEffect(() => {
    if (!canShare) return
    const bump = () => setThemeVersion((n) => n + 1)
    const observer = new MutationObserver(bump)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    const dark = window.matchMedia('(prefers-color-scheme: dark)')
    dark.addEventListener('change', bump)
    return () => {
      observer.disconnect()
      dark.removeEventListener('change', bump)
    }
  }, [canShare])

  useEffect(() => {
    if (!canShare) return
    const timer = setTimeout(draw, PREDRAW_DELAY_MS)
    return () => clearTimeout(timer)
  }, [canShare, draw])

  useEffect(() => {
    if (!note) return
    const timer = setTimeout(() => setNote(null), NOTE_MS)
    return () => clearTimeout(timer)
  }, [note])

  async function share() {
    const png = draw()
    if (!png || busy) return
    setNote(null)
    setBusy(true)
    try {
      await sharePng(await png, filename, title)
    } catch (err) {
      if (err instanceof DOMException && err.name === 'NotAllowedError') {
        setNote({ text: 'Image ready. Tap again to share.' })
      } else {
        setNote({ text: "Couldn't share the image. Try again.", error: true })
      }
    } finally {
      setBusy(false)
    }
  }

  if (!canShare) return null
  return (
    <div className="share" data-export-ignore>
      {note && (
        <p className={note.error ? 'share-note error' : 'share-note'} role="status">
          {note.text}
        </p>
      )}
      <button
        type="button"
        className="share-button"
        aria-label="Share as image"
        title="Share as image"
        aria-busy={busy}
        onClick={share}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 15V4M7.5 8.5 12 4l4.5 4.5M6 12H5v8h14v-8h-1" />
        </svg>
      </button>
    </div>
  )
}
