# v1 Backlog — Claude roast

**Not part of the MVP.** Moved out on 2026-10-16 by the owner's decision. **Do not start** until the owner finalizes the design and moves this into the main task board.

Spec reference: "Claude roast" section of `../../Project-Description.md`.

## Owner's direction (draft, still being thought through)
- **No live Claude API calls from the website.** Calling Claude per team per gameweek online could make the API bill skyrocket as usage grows.
- **Roasts are generated offline and shipped with each deployment**, like the positions data (in the bundled database).
- **Roasts are keyed by shape "buckets", not by team.** Teams with a similar shape share a roast. Example buckets:
  - 9+ starters in the attacking half (y > 50% of the pitch) → one set of roasts.
  - More than 8 in the attacking half → another, and so on for other shape patterns (deep defence, captain playing as a defender, many ghosts...).
- Generate an appropriate number of roasts per bucket offline (several per bucket, so repeat users don't always see the same one), store them, and pick one deterministically per team + GW on the site.

## Open questions for the owner
- Which shape features define a bucket (attacking-half count, average defender depth, players far from their FPL role, ghosts, captain position)?
- How many buckets and how many roasts per bucket?
- Should a roast mention specific players/names (needs per-team text) or stay generic to the shape?
- Guardrails (from the spec): football banter only; roast picks and shape, never real players' personal lives.

## Earlier draft (pre-decision, for reference)
- Build a structured shape summary (not raw data) as Claude's input.
- Use the `claude-api` skill to pick the model ID and SDK usage at build time.
- Show the caption under the pitch and include it in the image export.
