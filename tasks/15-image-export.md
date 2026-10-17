# 15 — Image export

**Status:** done (2026-10-17)
**Depends on:** 14.

## Goal
Each gameweek graphic can be downloaded as a shareable image.

## Scope
- "Export as image" button producing a PNG of the pitch card (pitch + team name + GW + legend).
- Client-side export (e.g. `html-to-image` or SVG to canvas). Fonts and colors must match the screen.
- Filename like `realshape-{team}-gw{n}.png`.

## Done when
- [x] Exported PNGs for 3 different gameweeks match the on-screen graphic (saved to `docs/screenshots/exports/`).
- [x] Works in Chrome and one other browser (or noted if not tested). (Chrome, Edge and Firefox; Safari not tested, see Notes.)

## Wrap-up (required: last step of every task)
- [x] Update this task's **Status** and the table in `tasks/README.md`.
- [x] Update the root `README.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path (for a 🛑 task: "waiting for owner approval on task NN").

## Notes
- **Share instead of a plain button (owner, 2026-10-17):** most people will look at the graphic on a phone and share it, so a round share icon sits in the bottom-right corner of the pitch (on the dark border beside the touchline). It opens a small menu: **Share image** hands the PNG to the device's share sheet (`navigator.share` with a file; shown only where `navigator.canShare` accepts files, so most phones) and **Save image** downloads it. The image is drawn as soon as the menu opens, because phone browsers (Safari especially) only allow sharing straight after a tap; "Preparing the image…" shows meanwhile (about 0.2-0.4 s). Closes on Escape, a tap outside, or after sharing / saving. **Save image removed (owner, 2026-10-17, during task 16):** the menu now has only Share image, and the share icon is hidden where the browser cannot share files (most desktop browsers, e.g. Firefox), since the menu would be empty there. **One tap (owner, same day):** the menu is gone; the share icon itself opens the share sheet. The image is now drawn ahead of time, 0.4 s after the card appears and again after a theme change, so the tap can share at once (phones only allow sharing straight after a tap). A tap before it is ready draws it then; if the browser refuses the late share, a note says "Image ready. Tap again to share." The image is drawn from an off-screen copy of the card with the arrows and icon hidden, so the page never changes while drawing (the old page-wide hiding rule would have made them blink on every gameweek). Checked in Playwright on an emulated Pixel 7 with a stubbed share sheet: one tap shares within ~50 ms, the file follows the gameweek and the theme, the note and second tap work, nothing blinks, and no icon without file sharing.
- **How it draws:** `frontend/src/exportImage.ts`, client side with `html-to-image` (1.11.13, pinned). PNG at 2x the on-screen size, filename `realshape-{team}-gw{n}.png`. The gameweek arrows and the share icon are marked `data-export-ignore` and hidden in the image but keep their space, so the header is laid out exactly as on screen. The card's rounded corners are filled with the page color, not transparency.
- **Two html-to-image gaps worked around:** (1) it copies computed styles onto HTML elements but not onto the shapes inside the pitch SVG (colored by CSS classes), so the pitch came out black; the page's style rules are now put into the card in a `<style>` while it is drawn. (2) Its font lookup crashes in Firefox (`rule.style.fontFamily` is undefined on `@font-face` rules there); the Archivo `@font-face` rules are now read and their files inlined as data URLs by our own code, once per page load. Firefox also only follows a download link that is in the document, so the link is attached briefly.
- **Verified (Playwright, real team 2020649):** GW6, GW5, GW2 exported via the share menu in Chrome, Edge and Firefox; each PNG matches the on-screen card (`docs/screenshots/exports/`: `realshape-2020649-gw{6,5,2}.png` from Chrome next to `screen-gw{n}.png`, plus `firefox-realshape-2020649-gw2.png`). Phone (Pixel 7 emulation, dark theme) with a stand-in `navigator.share`: the menu shows Share / Save, sharing hands over `realshape-2020649-gw6.png` (image/png, 227 KB) titled "navratri OG, GW6: Real Shape" (`phone-share-menu.png`). **Not tested:** Safari / iOS and a real phone share sheet (no device here); Safari gets a known workaround (draws twice so the embedded font is in).
- **Colors (owner, 2026-10-17):** pink midfielders didn't suit the image. Now GK white (`#f2f2f2`, slightly grey so the white outline shows), DEF sky blue, MID yellow, FWD red-orange; the chip / Triple Captain tags and the armband edge keep the old gold as their own `--gold` token. Several palettes were tried as samples first.
- **Bench cards (owner, 2026-10-17):** bench players are small rounded cards like FPL's bench (name on top, points on a strip in the role color), at most 4.6rem wide (`sample-edge-cases-new-colors.png`).
- The exported image follows the theme on screen (dark page → dark card); the pitch is the same in both.
- **Light / dark switch (owner, after the share work, 2026-10-17):** a sun / moon button at the top right of the page header (`frontend/src/ThemeToggle.tsx`). The page follows the device's setting until a theme is picked; the choice is remembered in this browser (`localStorage` key `realshape.theme`, in try/catch) and set as `data-theme` on `<html>`, applied by a small script in `index.html` before the first paint so there's no flash. Verified on an emulated phone set to light: switch → dark, survives a reload, export comes out dark, switch back → light (`docs/screenshots/theme/`). Known nit: in the dark phone export the footnote wraps one line shorter than on screen, leaving a little space at the bottom of the card.
