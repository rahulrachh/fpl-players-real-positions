// Light / dark switch in the page header. The page follows the device's
// setting until someone picks a theme here; the choice is remembered in this
// browser and set as data-theme on <html> (index.html applies it before the
// first paint, so the page doesn't flash the other theme).

import { useEffect, useState } from 'react'

type Theme = 'light' | 'dark'

const STORED_THEME = 'realshape.theme'
const darkQuery = window.matchMedia('(prefers-color-scheme: dark)')

function chosenTheme(): Theme | null {
  const value = document.documentElement.dataset.theme
  return value === 'light' || value === 'dark' ? value : null
}

function storeTheme(theme: Theme) {
  try {
    window.localStorage.setItem(STORED_THEME, theme)
  } catch {
    // Not remembered; the switch still works for this visit.
  }
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => chosenTheme() ?? (darkQuery.matches ? 'dark' : 'light'))

  // Follows the device's setting while nothing has been picked here.
  useEffect(() => {
    function onChange(event: MediaQueryListEvent) {
      if (chosenTheme() === null) setTheme(event.matches ? 'dark' : 'light')
    }
    darkQuery.addEventListener('change', onChange)
    return () => darkQuery.removeEventListener('change', onChange)
  }, [])

  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    storeTheme(next)
    setTheme(next)
  }

  const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'
  return (
    <button type="button" className="theme-toggle" onClick={toggle} aria-label={label} title={label}>
      {theme === 'dark' ? (
        // Sun: tap for light.
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
        </svg>
      ) : (
        // Moon: tap for dark.
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
        </svg>
      )}
    </button>
  )
}
