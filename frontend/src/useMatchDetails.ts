// Opening and closing the match details box (MatchDetails.tsx): hover with a
// mouse, tap on touch (tap the same dot, the box or anywhere else to close,
// another dot to switch), keyboard focus. Escape or a resize closes it.

import {
  type FocusEvent,
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent,
  type RefObject,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

import type { BenchPlayer, PlotDot, Role } from './api'

export const ROLE_NAMES: Record<Role, string> = {
  GK: 'Goalkeeper',
  DEF: 'Defender',
  MID: 'Midfielder',
  FWD: 'Forward',
}

export type DetailsContent = { kind: 'dot'; dot: PlotDot } | { kind: 'bench'; player: BenchPlayer }

export type Anchor = { left: number; top: number; width: number; height: number }

export type Open = {
  id: string
  content: DetailsContent
  anchor: Anchor
  // Hover boxes let the pointer through, so the dots under them stay reachable.
  via: 'hover' | 'tap' | 'focus'
}

// Props for an element that opens the box (an SVG <g> or an HTML element).
export type TriggerProps = {
  tabIndex: number
  role: 'button'
  'aria-label': string
  'aria-expanded': boolean
  onPointerDown: (e: PointerEvent<Element>) => void
  onPointerEnter: (e: PointerEvent<Element>) => void
  onPointerLeave: (e: PointerEvent<Element>) => void
  onClick: (e: MouseEvent<Element>) => void
  onFocus: (e: FocusEvent<Element>) => void
  onBlur: () => void
  onKeyDown: (e: KeyboardEvent<Element>) => void
}

export type DetailsTrigger = (id: string, content: DetailsContent, label: string) => TriggerProps

// `frame` is the element the box is positioned in: it wraps the card exactly.
export function useMatchDetails(frame: RefObject<HTMLElement | null>) {
  const [open, setOpen] = useState<Open | null>(null)
  const pointer = useRef<string>('mouse')
  const close = useCallback(() => setOpen(null), [])

  const show = useCallback(
    (id: string, content: DetailsContent, el: Element, via: Open['via']) => {
      const box = frame.current?.getBoundingClientRect()
      if (!box) return
      const r = el.getBoundingClientRect()
      setOpen({
        id,
        content,
        via,
        anchor: { left: r.left - box.left, top: r.top - box.top, width: r.width, height: r.height },
      })
    },
    [frame],
  )

  // A tap anywhere else, Escape, or a resize closes the box.
  useEffect(() => {
    if (!open) return
    const onKey = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && close()
    document.addEventListener('click', close)
    document.addEventListener('keydown', onKey)
    window.addEventListener('resize', close)
    return () => {
      document.removeEventListener('click', close)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', close)
    }
  }, [open, close])

  const trigger: DetailsTrigger = (id, content, label) => {
    const isOpen = open?.id === id
    return {
      tabIndex: 0,
      role: 'button',
      'aria-label': label,
      'aria-expanded': isOpen,
      onPointerDown: (e) => {
        pointer.current = e.pointerType
      },
      onPointerEnter: (e) => {
        if (e.pointerType === 'mouse') show(id, content, e.currentTarget, 'hover')
      },
      onPointerLeave: (e) => {
        if (e.pointerType === 'mouse' && isOpen && open.via === 'hover') close()
      },
      onClick: (e) => {
        // Kept from the document listener, which closes the box.
        e.stopPropagation()
        if (pointer.current === 'mouse') {
          if (!isOpen) show(id, content, e.currentTarget, 'hover')
        } else if (isOpen) close()
        else show(id, content, e.currentTarget, 'tap')
      },
      onFocus: (e) => {
        // Keyboard focus only: a tap focuses too, and its click decides.
        if (!isOpen && e.currentTarget.matches(':focus-visible')) show(id, content, e.currentTarget, 'focus')
      },
      onBlur: () => {
        if (isOpen && open.via === 'focus') close()
      },
      onKeyDown: (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return
        e.preventDefault()
        if (isOpen) close()
        else show(id, content, e.currentTarget, 'focus')
      },
    }
  }

  return { open, close, trigger }
}
