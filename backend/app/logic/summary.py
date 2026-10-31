"""The team's gameweek in numbers, beside the pitch: score against the
average and highest, ranks (with the share of all FPL teams above them),
the most captained player and the gameweek's top scorer, transfers, money,
bench points, and the points of every gameweek of the season (the season
strip). Part of the plot response (`summary`, documented in `docs/api.md`).

Built from FPL's `entry/{id}/history/` and `bootstrap-static/`. The history is
fetched fresh (short TTL) rather than kept with the long-cached team gameweek,
so the season strip includes gameweeks played since.
"""

from pydantic import BaseModel, ConfigDict

from app.fpl.schemas import BootstrapStatic, EntryHistory


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class SeasonGameweek(_Model):
    gw: int
    # False for a gameweek the team has not played (before it joined, or not
    # reached yet): points 0.
    played: bool
    # Before hits, as on the card.
    points: int
    chip: str | None


class NamedPlayer(_Model):
    id: int
    web_name: str
    # The gameweek's top scorer only: his points (before any captaincy).
    points: int | None = None


class GameweekSummary(_Model):
    # Of all FPL teams this gameweek; None until FPL has them.
    average_score: int | None
    highest_score: int | None
    gw_rank: int | None
    overall_rank: int | None
    # Rank as a share of all FPL teams, in percent ("top 7%"); None when
    # unranked or the number of teams is unknown.
    gw_rank_pct: float | None
    overall_rank_pct: float | None
    # Overall rank after the team's previous gameweek (None in its first):
    # the movement arrow.
    previous_overall_rank: int | None
    # Of all FPL teams this gameweek; None until FPL has them.
    most_captained: NamedPlayer | None
    top_player: NamedPlayer | None
    total_points: int
    transfers: int
    transfers_cost: int
    # Tenths of £m; `squad_value` includes the bank.
    bank: int
    squad_value: int
    points_on_bench: int
    # Every gameweek of the season, in order (unplayed ones with 0 points).
    season: list[SeasonGameweek]


def _pct(rank: int | None, total: int | None) -> float | None:
    if rank is None or not total:
        return None
    return round(100 * rank / total, 2)


def build_summary(
    gw: int, history: EntryHistory, bootstrap: BootstrapStatic
) -> GameweekSummary | None:
    """None if the history has no row for the gameweek (FPL not updated yet)."""
    rows = {r.event: r for r in history.current}
    row = rows.get(gw)
    event = next((e for e in bootstrap.events if e.id == gw), None)
    if row is None or event is None:
        return None
    previous = [rows[g] for g in sorted(rows) if g < gw]
    chips = {c.event: c.name for c in history.chips}
    names = {e.id: e.web_name for e in bootstrap.elements}
    total = bootstrap.total_players

    def named(fpl_id: int | None, points: int | None = None) -> NamedPlayer | None:
        if fpl_id is None or fpl_id not in names:
            return None
        return NamedPlayer(id=fpl_id, web_name=names[fpl_id], points=points)

    top = event.top_element_info
    return GameweekSummary(
        average_score=event.average_entry_score or None,
        highest_score=event.highest_score or None,
        gw_rank=row.rank,
        overall_rank=row.overall_rank,
        gw_rank_pct=_pct(row.rank, total),
        overall_rank_pct=_pct(row.overall_rank, total),
        previous_overall_rank=previous[-1].overall_rank if previous else None,
        most_captained=named(event.most_captained),
        top_player=named(top.id, top.points) if top else None,
        total_points=row.total_points,
        transfers=row.event_transfers,
        transfers_cost=row.event_transfers_cost,
        bank=row.bank,
        squad_value=row.value,
        points_on_bench=row.points_on_bench,
        season=[
            SeasonGameweek(
                gw=e.id,
                played=e.id in rows,
                points=rows[e.id].points if e.id in rows else 0,
                chip=chips.get(e.id) if e.id in rows else None,
            )
            for e in sorted(bootstrap.events, key=lambda e: e.id)
        ],
    )
