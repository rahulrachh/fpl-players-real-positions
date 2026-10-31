# 19 — Selling-price spike

**Status:** todo (starts after task 18)
**Depends on:** 04. Doc-only; no app code.

## Goal
Confirm that a team's real selling prices, and so the Planner budget, can be computed from public FPL data before tasks 20 and 22 rely on it. Design: "Budget: real selling prices" in `docs/planner-design.md`.

## Scope
- Small script under `spikes/selling-prices/` that, for a team ID, fetches `entry/{id}/`, `entry/{id}/transfers/`, the latest picks and `element-summary/{id}/` for each squad player, then prints each player's purchase price, current price and selling price, plus bank + total selling value.
- Purchase price rules: latest `element_in_cost` for transferred-in players; price in the team's `started_event` for players held since the first squad.
- Check against the FPL site's transfers page for the owner's team (2020649) and at least two other teams, one of which has played a **Free Hit** and one a **Wildcard**.
- Answer:
  - Do Free Hit transfers appear in `transfers/`? After the Free Hit, which purchase prices apply?
  - Are Wildcard transfers listed like normal ones?
  - Is `element-summary` `history[].value` the price at that gameweek's deadline (the one FPL uses as purchase price)?
  - Cost: time and number of calls per team load; is there a cheaper source of the start-gameweek price than 15 `element-summary` calls?
- Findings go in `docs/fpl-api.md` (new "Selling prices" section); update `docs/planner-design.md` if a rule changes.

## Done when
- [ ] Computed selling value matches the FPL site for the owner's team and two others (numbers recorded in Notes).
- [ ] Free Hit and Wildcard behaviour answered, with the team IDs used.
- [ ] Decision recorded: exact budget for all teams, or the "≈" fallback for teams that played a Free Hit.
- [ ] Call cost recorded, with the caching plan for task 20.

## Wrap-up (required: last step of every task)
- [ ] Update this task's **Status** and the table in `tasks/README.md`.
- [ ] Update `tasks/PROGRESS.md`: add this task under **Tasks completed** with a short summary of the work done, and set **Next task** to the next task and its file path.

## Notes
