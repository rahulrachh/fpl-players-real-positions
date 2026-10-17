// Draws the gameweek card as a PNG in the browser from the card's DOM
// (html-to-image), so fonts and colors are the ones on screen, then shares it
// through the device's share sheet or saves it. Elements marked
// data-export-ignore (the gameweek arrows, the share button) are hidden but
// keep their space, so the card is laid out as on screen.
//
// html-to-image copies each HTML element's computed style into the image, but
// not the shapes inside the pitch SVG, which are colored by the stylesheet's
// classes. So the page's style rules go into the card, in a <style> element,
// while it is drawn. The fonts are embedded here too rather than by
// html-to-image, whose font lookup fails in Firefox.

import { toBlob } from 'html-to-image'

// The self-hosted Archivo font with its files inlined, built once and reused.
let fontCss: Promise<string> | null = null

function readRules() {
  const rules: { rule: CSSRule; base: string }[] = []
  for (const sheet of Array.from(document.styleSheets)) {
    try {
      for (const rule of Array.from(sheet.cssRules)) rules.push({ rule, base: sheet.href ?? document.baseURI })
    } catch {
      // A stylesheet from another origin can't be read; ours are all local.
    }
  }
  return rules
}

function dataUrl(blob: Blob) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

// Every @font-face rule with its font files fetched and written in as data
// URLs (relative URLs would not load inside the image).
async function buildFontCss() {
  const faces = readRules().filter(({ rule }) => rule instanceof CSSFontFaceRule)
  const css = await Promise.all(
    faces.map(async ({ rule, base }) => {
      let text = rule.cssText
      for (const [, quoted, plain] of text.matchAll(/url\(\s*(?:["']([^"']+)["']|([^)"']+))\s*\)/g)) {
        const url = quoted ?? plain
        if (url.startsWith('data:')) continue
        const response = await fetch(new URL(url, base))
        if (!response.ok) throw new Error(`Font ${url}: ${response.status}`)
        text = text.replace(url, await dataUrl(await response.blob()))
      }
      return text
    }),
  )
  return css.join('\n')
}

// Every style rule on the page except @font-face (embedded separately).
function pageCss() {
  const rules = readRules()
    .filter(({ rule }) => !(rule instanceof CSSFontFaceRule))
    .map(({ rule }) => rule.cssText)
  // !important: html-to-image writes each element's on-screen style inline.
  rules.push('[data-export-ignore] { visibility: hidden !important; }')
  return rules.join('\n')
}

export function exportFilename(teamId: number, gw: number) {
  return `realshape-${teamId}-gw${gw}.png`
}

export async function renderPng(card: HTMLElement): Promise<Blob> {
  await document.fonts.ready
  fontCss ??= buildFontCss().catch((err: unknown) => {
    fontCss = null
    throw err
  })
  const options = {
    fontEmbedCSS: await fontCss,
    // Twice the on-screen size, so the image stays sharp when shared.
    pixelRatio: 2,
    // Fills the card's rounded corners with the page color instead of
    // transparency (which some apps show as black).
    backgroundColor: getComputedStyle(document.body).backgroundColor,
  }
  const style = document.createElement('style')
  style.textContent = pageCss()
  card.prepend(style)
  try {
    // Safari can draw the first image before the embedded font has loaded;
    // the second one is complete.
    if (/^((?!chrome|android).)*safari/i.test(navigator.userAgent)) await toBlob(card, options)
    const blob = await toBlob(card, options)
    if (!blob) throw new Error('The card could not be drawn.')
    return blob
  } finally {
    style.remove()
  }
}

export function savePng(png: Blob, filename: string) {
  const url = URL.createObjectURL(png)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  // Firefox only follows a download link that is in the document.
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

function pngFile(png: Blob, filename: string) {
  return new File([png], filename, { type: 'image/png' })
}

// Whether this browser can hand an image to the device's share sheet (most
// phones; few desktop browsers).
export function canSharePng() {
  try {
    const probe = pngFile(new Blob([], { type: 'image/png' }), 'probe.png')
    return typeof navigator.canShare === 'function' && navigator.canShare({ files: [probe] })
  } catch {
    return false
  }
}

// Resolves false when the person closes the share sheet without sharing.
export async function sharePng(png: Blob, filename: string, title: string) {
  try {
    await navigator.share({ files: [pngFile(png, filename)], title })
    return true
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return false
    throw err
  }
}
