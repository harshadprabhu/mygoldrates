"""Subscriber email confirmation (sql/confirm_email.sql, cf-worker-jd /sub/*).

A typed-in address gets one confirmation email and nothing else until it is
confirmed; a Google sign-in is confirmed only by a Google token issued to our
own client for that address.
"""
import json
import os
import shutil
import subprocess

import pytest

import send_alerts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def run():
    if not shutil.which("node"):
        pytest.skip("node not installed")
    out = subprocess.run(
        ["node", os.path.join(ROOT, "tests/js/sub_confirm_harness.mjs"),
         os.path.join(ROOT, "cf-worker-jd/worker.js")],
        capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_new_address_gets_one_confirmation_with_its_link(run):
    assert run["fresh"]["status"] == 200 and run["fresh"]["mails"] == 1
    m = run["mail"]
    assert m["to"] == [{"email": "new@x.in"}]
    assert "https://mygoldrates.com/confirm?t=11111111-1111-1111-1111-111111111111" in m["htmlContent"]
    assert "<b>" not in m["htmlContent"]          # the name is not injected as HTML


def test_no_repeat_and_no_mail_to_confirmed_or_unknown(run):
    assert run["again"]["mails"] == 0
    assert run["confirmed"]["mails"] == 0 and run["unknown"]["mails"] == 0
    # same answer whether or not the address is on the list
    assert run["unknown"]["body"] == run["fresh"]["body"] == run["confirmed"]["body"]


def test_google_token_must_be_ours_and_verified(run):
    assert run["otherClient"]["confirmed"] is False and run["otherClient"]["mails"] == 1
    assert run["unverified"]["confirmed"] is False
    assert run["google"]["confirmed"] is True and run["google"]["body"]["confirmed"] is True
    assert run["google"]["mails"] == 0


def test_senders_skip_unconfirmed_rows():
    base = {"email": "a@x.in", "unsub_token": "t"}
    assert send_alerts.mailable({**base, "confirmed_at": "2026-11-02T00:00:00Z"})
    assert not send_alerts.mailable({**base, "confirmed_at": None})
    assert send_alerts.mailable(base)                 # before the SQL is run: as before
    assert not send_alerts.mailable({**base, "unsub_token": None, "confirmed_at": "x"})
    assert not send_alerts.mailable(None)


def test_confirm_sql_grants():
    sql = open(os.path.join(ROOT, "sql/confirm_email.sql"), encoding="utf-8").read()
    assert "grant execute on function public.confirm_request(text) to service_role;" in sql
    assert "grant execute on function public.confirm_google(text) to service_role;" in sql
    assert "from public, anon, authenticated" in sql
