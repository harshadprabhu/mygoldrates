"""The payload `collect.py` writes must match the columns `rates` actually has.

This file exists because of a five-day outage that nothing else could have
caught. A blanket find-and-replace of the word "scraped" across the source
renamed the payload key `scraped_at` to `collected_at`. The Postgres column
kept its name, every insert failed with PGRST204, the workflow stayed green,
and the site went on re-stamping five-day-old rates with today's date.

A grep of the repository could never have found it: the broken name lived in
the database, not in the code. So the column set is pinned here as an explicit
contract, and the row builder is checked against it.
"""
import ast
import pathlib

import pytest

import collect


SRC = pathlib.Path(__file__).resolve().parent.parent / "collect.py"


def _dict_literal_keys(src, must_contain):
    """Every string key of each dict literal in the file that contains
    `must_contain` as a key. Parsed rather than imported: building a real row
    needs a live brand, a network fetch and a Supabase client."""
    out = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Dict):
            continue
        keys = [k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        if must_contain in keys:
            out.append(set(keys))
    return out


def test_every_rate_payload_uses_only_real_columns():
    payloads = _dict_literal_keys(SRC.read_text(), "canonical_24k_pre_gst")
    assert payloads, "no rate row literal found - has the builder moved?"
    known = collect.RATES_COLUMNS | collect.RATES_OPTIONAL_COLUMNS
    for keys in payloads:
        unknown = keys - known
        assert not unknown, (
            f"{sorted(unknown)} is not a column on `rates`. If the database "
            f"really has it, add it to RATES_COLUMNS; otherwise this is the "
            f"rename bug again and every insert will fail with PGRST204.")


def test_the_timestamp_column_is_still_called_scraped_at():
    """Pinned by name. It is the one that broke, and it is the one most
    likely to be swept up by a future pass over the word 'scraped'."""
    assert "scraped_at" in collect.RATES_COLUMNS
    assert "collected_at" not in collect.RATES_COLUMNS
    payloads = _dict_literal_keys(SRC.read_text(), "canonical_24k_pre_gst")
    for keys in payloads:
        assert "scraped_at" in keys


def test_the_contract_lists_the_columns_the_database_has():
    """Guards the other direction: if someone trims RATES_COLUMNS to make a
    failing test pass, the payload check above stops being worth anything."""
    for col in ("brand_id", "rate_date", "canonical_24k_pre_gst", "status",
                "scraped_at", "method", "basis_confirmed"):
        assert col in collect.RATES_COLUMNS


def test_derived_rates_is_optional_not_required():
    """It is genuinely absent from the live table, and upsert_rate retries
    without it. Treating it as required would fail every run."""
    assert "derived_rates" in collect.RATES_OPTIONAL_COLUMNS
    assert "derived_rates" not in collect.RATES_COLUMNS


def test_no_vendor_name_or_secret_was_renamed_by_the_word_sweep():
    """The same blanket pass also renamed a vendor's domain to one that does
    not exist and a GitHub secret to a name that resolves to empty. Both are
    external contracts that a repo-wide grep for our own wording cannot see."""
    src = SRC.read_text()
    assert "api.scraperapi.com" in src
    assert "SCRAPERAPI_KEY" in src
    assert "collectorapi" not in src
    assert "COLLECTRAPI_KEY" not in src


def test_a_run_that_saves_nothing_does_not_exit_quietly():
    """The outage stayed invisible because this branch printed a calm line and
    returned 0, letting the build step republish stale rates under today's
    date. It must raise instead."""
    src = SRC.read_text()
    i = src.index("no live rates at all")
    assert "raise SystemExit(1)" in src[i:i + 600]
