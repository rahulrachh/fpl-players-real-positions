// A small "i" beside the page title: hover (or keyboard focus) shows how to read
// the graphic; on a phone, tap to open and tap again or anywhere else to close.

import { useEffect, useId, useRef, useState } from 'react'

export default function InfoTip({ text }: { text: string }) {
  const [hover, setHover] = useState(false)
  const [pinned, setPinned] = useState(false)
  const wrap = useRef<HTMLSpanElement>(null)
  const id = useId()
  const open = hover || pinned

  // A tap elsewhere or Escape closes a tapped-open tip.
  useEffect(() => {
    if (!pinned) return
    function onDown(event: PointerEvent) {
      if (!wrap.current?.contains(event.target as Node)) setPinned(false)
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setPinned(false)
    }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [pinned])

  return (
    <span
      className="info-tip"
      ref={wrap}
      onPointerEnter={(e) => e.pointerType === 'mouse' && setHover(true)}
      onPointerLeave={(e) => e.pointerType === 'mouse' && setHover(false)}
    >
      <button
        type="button"
        className="info-button"
        aria-label="How to read the graphic"
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onClick={() => setPinned((p) => !p)}
        onFocus={() => setHover(true)}
        onBlur={() => setHover(false)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="9.5" />
          <path d="M12 11v6M12 7.2v.1" />
        </svg>
      </button>
      {open && (
        <span id={id} role="tooltip" className="info-bubble">
          {text}
        </span>
      )}
    </span>
  )
}
