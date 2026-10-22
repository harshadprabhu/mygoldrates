"""MCX contract selection skips expired contracts (worker and homepage).

Moneycontrol keeps serving an expired contract's last traded price, so
picking the first contract that answers froze MCX gold on the October 2026
contract (last trade 5 Oct) for weeks. Both pickers now skip any expiry
before today (IST); the homepage also drops a remembered expired contract.
"""
import json
import shutil
import subprocess

import pytest

node = pytest.mark.skipif(not shutil.which("node"), reason="node not installed")


def _run(js):
    return subprocess.run(["node", "-e", js], capture_output=True, text=True,
                          check=True).stdout.strip()


def _worker_fn():
    src = open("cf-worker-market/worker.js", encoding="utf-8").read()
    i = src.index("function mcxCandidateExpiries()")
    j = src.index("\n}\n", i) + 3
    return src[i:j]


def _page_fns():
    src = open("pulse_app.html", encoding="utf-8").read()
    i = src.index("  var MCX_MONTHS=")
    j = src.index("  function fetchMcxOne", i)
    return src[i:j]


FAKE_NOW = "Date.now = () => Date.UTC(2026, 9, 22, 6, 0);\n"   # 22 Oct 2026 11:30 IST


@node
def test_worker_never_offers_an_expired_contract():
    out = json.loads(_run(FAKE_NOW + _worker_fn() + "console.log(JSON.stringify(mcxCandidateExpiries()))"))
    assert not any(e.endswith("OCT2026") for e in out)
    assert out.index("04DEC2026") < out.index("05FEB2027") if "05FEB2027" in out else "04DEC2026" in out


@node
def test_page_never_offers_an_expired_contract_and_drops_a_remembered_one():
    js = FAKE_NOW + _page_fns() + """
var c = mcxCandidateExpiries();
console.log(JSON.stringify({c: c, oct: expiryTime('05OCT2026') >= istToday(),
                            dec: expiryTime('04DEC2026') >= istToday()}));"""
    r = json.loads(_run(js))
    assert not any(e.endswith("OCT2026") for e in r["c"])
    assert r["oct"] is False and r["dec"] is True
