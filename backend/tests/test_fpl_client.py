"""FPL client against recorded responses (`tests/fixtures/fpl/`, trimmed real
data from 2026-10-17, GW6 finished / GW7 upcoming). No network."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.fpl.client import (
    FplClient,
    FplNotFound,
    FplSchemaError,
    FplUnavailable,
    get_fpl_client,
)

FIXTURES = Path(__file__).parent / "fixtures" / "fpl"
BASE_URL = "https://fpl.test/api"

ROUTES = {
    "/api/bootstrap-static/": "bootstrap-static.json",
    "/api/fixtures/": "fixtures-gw6.json",
    "/api/entry/1234/": "entry.json",
    "/api/entry/1234/history/": "entry-history.json",
    "/api/entry/5678/": "entry-not-started.json",
    "/api/entry/1234/event/6/picks/": "picks-gw6.json",
    "/api/event/6/live/": "live-gw6.json",
    "/api/event-status/": "event-status.json",
}


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeFpl:
    """httpx transport serving the recorded responses; counts requests."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.override: httpx.Response | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.override is not None:
            return self.override
        name = ROUTES.get(request.url.path)
        if name is None:
            # FPL's real 404 body.
            return httpx.Response(404, json={"detail": "Not found."})
        return httpx.Response(200, json=load(name))


@pytest.fixture
def fake():
    return FakeFpl()


@pytest.fixture
def client(fake):
    c = FplClient(BASE_URL, cache_ttl_seconds=60, transport=httpx.MockTransport(fake))
    yield c
    c.close()


def test_bootstrap_static(client):
    data = client.bootstrap_static()
    assert [t.short_name for t in data.teams] == ["ARS", "AVL", "BOU"]
    assert {t.id: t.singular_name_short for t in data.element_types} == {
        1: "GKP",
        2: "DEF",
        3: "MID",
        4: "FWD",
    }
    raya = next(e for e in data.elements if e.id == 1)
    assert (raya.second_name, raya.team, raya.element_type, raya.now_cost) == (
        "Raya Martín",
        1,
        1,
        61,
    )
    assert data.current_event.id == 6 and data.current_event.finished
    assert data.next_event.id == 7 and not data.next_event.finished
    assert data.next_event.deadline_time == datetime(2026, 10, 17, 10, tzinfo=UTC)


def test_fixtures_passes_event_param(client, fake):
    fixtures = client.fixtures(event=6)
    assert fake.requests[-1].url.params["event"] == "6"
    assert len(fixtures) == 3 and all(f.event == 6 and f.finished for f in fixtures)


def test_entry_and_history(client):
    entry = client.entry(1234)
    assert entry.id == 1234 and entry.current_event == 6
    assert entry.entered_events == [1, 2, 3, 4, 5, 6]
    assert (entry.last_deadline_bank, entry.last_deadline_value) == (1, 1017)

    history = client.entry_history(1234)
    gw6 = history.current[-1]
    assert (gw6.event, gw6.bank, gw6.value) == (6, 1, 1017)
    assert {c.name for c in history.chips} == {"bboost", "3xc", "wildcard", "freehit"}


def test_entry_not_started_yet(client):
    # Created for GW7 before its deadline: FPL still says current_event 6,
    # but no gameweek has public picks.
    entry = client.entry(5678)
    assert (entry.started_event, entry.current_event, entry.entered_events) == (7, 6, [])
    assert entry.last_deadline_bank is None and entry.last_deadline_value is None
    with pytest.raises(FplNotFound):
        client.entry_picks(5678, 6)


def test_picks(client):
    picks = client.entry_picks(1234, 6)
    assert len(picks.picks) == 15
    assert [p.position for p in picks.picks] == list(range(1, 16))
    assert sum(p.is_captain for p in picks.picks) == 1
    assert all(p.multiplier == 0 for p in picks.picks[11:])
    assert [(s.element_in, s.element_out) for s in picks.automatic_subs] == [(304, 368)]
    assert picks.entry_history.value == 1017
    assert picks.active_chip is None


def test_event_live_and_status(client):
    live = client.event_live(6)
    assert live.elements[0].stats.minutes == 90
    status = client.event_status()
    assert {d.event for d in status.status} == {6}
    assert all(d.points == "r" for d in status.status)


def test_upcoming_picks_are_not_found(client):
    # Before the deadline FPL answers 404 for the upcoming gameweek's picks.
    with pytest.raises(FplNotFound):
        client.entry_picks(1234, 7)


def test_unknown_entry_is_not_found(client, fake):
    fake.override = httpx.Response(404, json={"detail": "No Entry matches the given query."})
    with pytest.raises(FplNotFound):
        client.entry(999999999)


@pytest.mark.parametrize("status", [500, 503])
def test_server_errors_are_unavailable(client, fake, status):
    fake.override = httpx.Response(status, text="The game is being updated.")
    with pytest.raises(FplUnavailable):
        client.bootstrap_static()


def test_network_error_is_unavailable(fake):
    def boom(request):
        raise httpx.ConnectTimeout("timed out", request=request)

    c = FplClient(BASE_URL, 60, transport=httpx.MockTransport(boom))
    with pytest.raises(FplUnavailable):
        c.event_status()


def test_changed_shape_is_schema_error(client, fake):
    fake.override = httpx.Response(200, json={"events": "nope"})
    with pytest.raises(FplSchemaError):
        client.bootstrap_static()


def test_non_json_is_schema_error(client, fake):
    fake.override = httpx.Response(200, text="<html>maintenance</html>")
    with pytest.raises(FplSchemaError):
        client.event_status()


def test_responses_are_cached(client, fake):
    client.bootstrap_static()
    client.bootstrap_static()
    client.fixtures(event=6)
    client.fixtures(event=6)
    assert len(fake.requests) == 2


def test_cache_expires(fake):
    c = FplClient(BASE_URL, cache_ttl_seconds=0, transport=httpx.MockTransport(fake))
    c.event_status()
    c.event_status()
    assert len(fake.requests) == 2


def test_errors_are_not_cached(client, fake):
    fake.override = httpx.Response(503, text="The game is being updated.")
    with pytest.raises(FplUnavailable):
        client.event_status()
    fake.override = None
    assert client.event_status().leagues == "Updated"


def test_get_fpl_client_uses_settings(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("FPL_API_BASE_URL", BASE_URL)
    get_settings.cache_clear()
    get_fpl_client.cache_clear()
    try:
        c = get_fpl_client()
        assert c is get_fpl_client()
        assert str(c._http.base_url) == BASE_URL + "/"
    finally:
        get_settings.cache_clear()
        get_fpl_client.cache_clear()
