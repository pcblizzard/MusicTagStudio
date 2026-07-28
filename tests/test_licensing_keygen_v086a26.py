from __future__ import annotations

from datetime import datetime, timedelta

from musictagstudio.licensing_keygen import (
    CachedState,
    KeygenResult,
    check_license,
    evaluate_cache,
    make_cache_state,
)


class _FakeTransport:
    """Liefert vorab bestückte Antworten und protokolliert die Aufrufe."""

    def __init__(self, responses: list[tuple[int, dict]]):
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url))
        return self._responses.pop(0)


def _valid(code="VALID", license_id="lic_1", expiry=""):
    return (
        200,
        {
            "data": {"id": license_id, "attributes": {"expiry": expiry}},
            "meta": {"valid": True, "code": code},
        },
    )


def _invalid(code, license_id="lic_1"):
    return (
        200,
        {
            "data": {"id": license_id, "attributes": {}},
            "meta": {"valid": False, "code": code},
        },
    )


def test_valid_key_passes_without_activation():
    transport = _FakeTransport([_valid()])
    result = check_license("KEY", "fp", account_id="acct", transport=transport)
    assert result.valid
    assert len(transport.calls) == 1  # nur validate, keine Aktivierung


def test_no_machine_triggers_activation_then_revalidates():
    transport = _FakeTransport(
        [_invalid("NO_MACHINE"), (201, {"data": {"id": "mach_1"}}), _valid()]
    )
    result = check_license("KEY", "fp", account_id="acct", transport=transport)
    assert result.valid
    # validate -> POST /machines -> validate
    assert [m for m, _ in transport.calls] == ["POST", "POST", "POST"]
    assert transport.calls[1][1].endswith("/machines")


def test_expired_key_is_invalid_and_not_activated():
    transport = _FakeTransport([_invalid("EXPIRED")])
    result = check_license("KEY", "fp", account_id="acct", transport=transport)
    assert not result.valid and result.code == "EXPIRED"
    assert len(transport.calls) == 1  # keine Aktivierung versucht


def test_evaluate_cache_within_grace():
    now = datetime(2026, 7, 27, 12, 0, 0)
    result = KeygenResult(valid=True, code="VALID")
    cache = make_cache_state("KEY", result, now - timedelta(days=3))
    assert evaluate_cache(cache, "KEY", now, grace_days=14) is True


def test_evaluate_cache_beyond_grace():
    now = datetime(2026, 7, 27, 12, 0, 0)
    cache = make_cache_state("KEY", KeygenResult(True, "VALID"), now - timedelta(days=30))
    assert evaluate_cache(cache, "KEY", now, grace_days=14) is False


def test_evaluate_cache_rejects_key_change():
    now = datetime(2026, 7, 27, 12, 0, 0)
    cache = make_cache_state("OLD-KEY", KeygenResult(True, "VALID"), now)
    assert evaluate_cache(cache, "NEW-KEY", now, grace_days=14) is False


def test_evaluate_cache_respects_expiry():
    now = datetime(2026, 7, 27, 12, 0, 0)
    result = KeygenResult(valid=True, code="VALID", expiry="2026-07-01T00:00:00Z")
    cache = make_cache_state("KEY", result, now - timedelta(days=1))
    # Innerhalb Kulanz, aber Lizenz ist abgelaufen -> nicht mehr aktiv.
    assert evaluate_cache(cache, "KEY", now, grace_days=14) is False


def test_evaluate_cache_none_is_false():
    assert evaluate_cache(None, "KEY", datetime(2026, 7, 27)) is False


def test_missing_cache_state_from_dataclass():
    cache = CachedState(key_id="x", last_valid="not-a-date")
    assert evaluate_cache(cache, "KEY", datetime(2026, 7, 27)) is False
