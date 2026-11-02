"""A jeweller's rate stuck for days while the market moves is quarantined."""
from datetime import date

import collect

T = date(2026, 11, 2)
D1, D2 = date(2026, 11, 1), date(2026, 10, 31)


def test_stuck_rate_while_market_moved_is_flagged():
    note = collect.frozen_note(T, 14140.36, 13800, {D1: 14140.36, D2: 14140.36}, {D2: 14100})
    assert note and note.startswith("STALE") and "2026-10-31" in note


def test_flat_market_is_not_flagged():
    assert collect.frozen_note(T, 14140, 14150, {D1: 14140, D2: 14140}, {D2: 14140}) is None


def test_rate_that_changed_is_not_flagged():
    assert collect.frozen_note(T, 13820, 13800, {D1: 14140, D2: 14140}, {D2: 14100}) is None


def test_one_stuck_day_is_not_enough():
    assert collect.frozen_note(T, 14140, 13800, {D1: 14140, D2: 14300}, {D2: 14100}) is None


def test_missing_history_is_not_flagged():
    assert collect.frozen_note(T, 14140, 13800, {D1: 14140}, {D2: 14100}) is None
    assert collect.frozen_note(T, 14140, 13800, {D1: 14140, D2: 14140}, {}) is None
