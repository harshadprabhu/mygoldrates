"""Jewellers Digest website sign-in, exercised against the real Worker.

tests/js/jd_login_harness.mjs runs cf-worker-jd/worker.js under Node with an
in-memory Supabase and a fake Brevo, and reports what happened. These tests
assert on that report: the sign-in path hands out access, so each property
below is one a mistake would quietly break.
"""
import json
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def run():
    if not shutil.which("node"):
        pytest.skip("node not installed")
    out = subprocess.run(
        ["node", os.path.join(ROOT, "tests/js/jd_login_harness.mjs"),
         os.path.join(ROOT, "cf-worker-jd/worker.js")],
        capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_unknown_address_gets_the_same_answer_and_no_mail(run):
    assert run["unknown"]["status"] == 200
    assert run["unknown"]["body"] == run["known"]["body"]
    assert run["unknown"]["mails"] == 0


def test_underscore_is_not_a_wildcard_into_another_account(run):
    assert run["wildcard"]["mails"] == 0


def test_known_address_is_mailed_and_only_a_hash_is_stored(run):
    assert run["known"]["mails"] == 1
    assert run["known"]["to"] == "owner@shop.in"
    assert run["known"]["stored_plain"] is False


def test_wrong_code_is_refused_and_counted(run):
    assert run["wrong"] == {"status": 401, "attempts": 1}


def test_right_code_signs_in_once(run):
    assert run["right"]["status"] == 200 and run["right"]["has_token"]
    assert run["reuse"]["status"] == 401


def test_complimentary_access_is_access(run):
    assert run["right"]["ent"]["active"] is True
    assert run["status"]["ent"]["status"] == "complimentary"
    assert run["status"]["email"] == "owner@shop.in"


def test_session_downloads_the_report_and_listing_sends_prefix(run):
    assert run["report"]["status"] == 200 and run["report"]["has_url"]
    assert run["report"]["list_body"]["prefix"] == ""


def test_tampered_token_is_refused(run):
    assert run["forged"]["status"] == 401


def test_five_wrong_guesses_burn_the_code(run):
    assert run["burned"]["status"] == 401


def test_at_most_five_codes_an_hour(run):
    assert run["ratelimit"]["sent"] == 3     # 2 already sent this hour


def test_expired_complimentary_access_is_not_access(run):
    assert run["expired_comp"]["status"] == 402


def test_expired_code_is_refused(run):
    assert run["expired_code"]["status"] == 401


def test_download_picks_the_workbook_not_the_issue_json(run):
    assert run["report"]["signed"] == "jewellers-digest-2026-10-14.xlsx"


def test_issue_is_served_to_members_only(run):
    assert run["issue"]["status"] == 200
    assert run["issue"]["name"] == "jewellers-digest-2026-10-14.json"
    assert run["issue"]["read"] == "jewellers-digest-2026-10-14.json"
    assert run["issue"]["last"] == "2026-10-14"
    assert run["issue_anon"]["status"] == 401
