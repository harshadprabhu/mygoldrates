"""Stores near me from the visitor's network (owner, 9 Nov 2026): the
Worker's /geo returns Cloudflare's city and state for the request, and the
homepage uses it when the device's location is not given."""
import json
import subprocess

APP = open("pulse_app.html", encoding="utf-8").read()


def _geo(origin, cf):
    js = """
import('./cf-worker-jd/worker.js').then(async m => {
  const r = new Request('https://x/geo', {headers: {Origin: %s}});
  Object.defineProperty(r, 'cf', {value: %s});
  const res = await m.default.fetch(r, {});
  console.log(JSON.stringify({s: res.status, o: res.headers.get('access-control-allow-origin'),
    c: res.headers.get('cache-control'), b: await res.json()}));
});""" % (json.dumps(origin), json.dumps(cf))
    out = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_geo_returns_the_place_not_the_address():
    r = _geo("https://mygoldrates.com", {"country": "IN", "region": "Maharashtra", "city": "Pune",
                                         "latitude": "18.52", "longitude": "73.85", "clientTcpRtt": 9})
    assert r["s"] == 200 and r["c"] == "no-store"
    assert r["b"] == {"country": "IN", "region": "Maharashtra", "city": "Pune", "lat": 18.52, "lon": 73.85}
    assert r["o"] == "https://mygoldrates.com"


def test_geo_is_readable_only_by_the_site():
    assert _geo("https://elsewhere.example", {"country": "IN"})["o"] is None


def test_geo_without_cloudflare_data_is_empty_not_an_error():
    r = _geo("https://mygoldrates.com", {})
    assert r["s"] == 200 and r["b"]["lat"] is None


def test_homepage_falls_back_to_the_network_and_names_the_real_error():
    assert "alert('Location permission denied')" not in APP
    assert "Location Services may be off" in APP              # code 2 is not a refusal
    assert "timeout:15000,maximumAge:600000" in APP
    assert "useIp(GEO_ERR[err&&err.code]" in APP
    assert "(approx.)" in APP


def test_network_location_switches_itself_on_only_on_the_homepage():
    i = APP.index("if(!nearOff()&&")
    assert "location.pathname" in APP[i:i + 120]
    assert "setNearOff(true)" in APP                          # hiding it is remembered
