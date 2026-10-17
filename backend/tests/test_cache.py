from app.cache import TTLCache


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_entry_expires_after_ttl():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=10, clock=clock)
    cache.set("k", 1)
    clock.now = 9.9
    assert cache.get("k") == 1
    clock.now = 10
    assert cache.get("k") is None


def test_get_or_set_calls_factory_once_while_fresh():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=5, clock=clock)
    calls = []

    def factory():
        calls.append(1)
        return len(calls)

    assert cache.get_or_set("k", factory) == 1
    assert cache.get_or_set("k", factory) == 1
    clock.now = 5
    assert cache.get_or_set("k", factory) == 2


def test_cached_none_is_a_hit():
    cache = TTLCache(ttl_seconds=5)
    calls = []
    cache.get_or_set("k", lambda: calls.append(1))
    cache.get_or_set("k", lambda: calls.append(1))
    assert len(calls) == 1


def test_evicts_when_full():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=5, max_entries=2, clock=clock)
    cache.set("a", 1)
    clock.now = 1
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2 and cache.get("c") == 3


def test_per_entry_ttl_overrides_default():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=5, clock=clock)
    cache.set("short", 1)
    cache.set("long", 2, ttl_seconds=100)
    clock.now = 50
    assert cache.get("short") is None
    assert cache.get("long") == 2
