"""Price-drop alerts: who gets emailed, and only once."""
import send_alerts as sa


class _Q:
    def __init__(self, db, table):
        self.db, self.table, self.upd, self.f = db, table, None, {}
    def select(self, *_): return self
    def eq(self, k, v): self.f[k] = v; return self
    def update(self, row): self.upd = row; return self
    def execute(self):
        rows = [r for r in self.db[self.table]
                if all(r.get(k) == v for k, v in self.f.items())]
        if self.upd is not None:
            for r in rows: r.update(self.upd)
        return type("R", (), {"data": rows})


class _SB:
    def __init__(self, db): self.db = db
    def table(self, t): return _Q(self.db, t)


def _run(monkeypatch, alerts, subs, c24=14000.0):
    sent = []
    monkeypatch.setattr(sa.requests, "post", lambda *a, **k: (
        sent.append(k["json"]["to"][0]["email"]),
        type("R", (), {"status_code": 201, "text": ""}))[1])
    db = {"price_alerts": alerts, "inquiries": subs}
    base = [{"canonical_24k_pre_gst": c24, "brands": {"name": "PN Gadgil"}}]
    n = sa.send_price_alerts(_SB(db), "k", "G", "a@b.c", base, "24 Oct 2026")
    return n, sent, db


def test_sends_once_when_the_rate_reaches_the_target(monkeypatch):
    low22 = 14000 * 0.916                      # 12,824
    alerts = [{"id": 1, "email": "a@x.in", "karat": "22K", "target": 12900, "active": True},
              {"id": 2, "email": "b@x.in", "karat": "22K", "target": 12500, "active": True}]
    subs = [{"name": "Asha", "email": "a@x.in", "unsub_token": "t1"},
            {"name": "Ben", "email": "b@x.in", "unsub_token": "t2"}]
    n, sent, db = _run(monkeypatch, alerts, subs)
    assert low22 < 12900 and n == 1 and sent == ["a@x.in"]
    assert db["price_alerts"][0]["active"] is False
    assert db["price_alerts"][1]["active"] is True


def test_no_email_for_someone_who_unsubscribed(monkeypatch):
    alerts = [{"id": 1, "email": "gone@x.in", "karat": "22K", "target": 20000, "active": True}]
    n, sent, _ = _run(monkeypatch, alerts, [])
    assert n == 0 and sent == []


def test_rupees_are_grouped_the_indian_way():
    assert [sa.inr(x) for x in (999, 14175, 155785, 1234567)] == \
        ["₹999", "₹14,175", "₹1,55,785", "₹12,34,567"]
