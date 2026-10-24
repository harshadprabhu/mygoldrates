"""Render a Sona Shorts episode to a vertical video (1080x1920, 30 fps).

    python3 render.py episodes/ring.html stills 1.5,5,9.8      # check frames
    python3 render.py episodes/ring.html video                 # the finished mp4
    options: --out DIR (default ./shorts-out/<episode>)  --docs DIR (the built site)

The episode page draws every frame as a pure function of time. The phone in
it runs the real site (docs/) - Sona answers from today's knowledge file -
so the numbers in the video are the live ones. The page lists its Hindi
dialogue (EP.lines); voice.py speaks each line, and the page is reloaded
with every line's length (window.VO) so the scenes are timed to the voices. Nothing leaves the machine
except font downloads; analytics and database calls are stubbed out.
"""
import argparse, functools, http.server, json, os, shutil, subprocess, sys, threading, time

import voice

SKILL = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(SKILL, "..", "..", ".."))
FPS = 30
HIDE = ("#liveChip,.live-chip,.sn-fab,#sonaFab,#sonaBanner,.sn-ban,#subPop,.adsbygoogle,ins.adsbygoogle{display:none!important}"
        "html{scroll-behavior:auto!important}.sn-typing span{animation:none!important}"
        ".sn-b{font-size:16.5px!important;line-height:1.45!important}.sn-row{font-size:15px!important}"
        ".sn-hd b{font-size:17px!important}.sn-chip{font-size:14px!important}.sn-in input{font-size:16px!important}"
        ".sn-fb{display:none!important}")
FRAME_INIT = """if (window.top !== window) {
  try { localStorage.setItem('gr_sub','1'); localStorage.setItem('sona_ban2','1'); localStorage.setItem('sona_ban','1'); } catch (e) {}
  if (!window.webkitSpeechRecognition && !window.SpeechRecognition) { window.webkitSpeechRecognition = function () {}; }
}"""


def inr(v):
    n = str(round(v)); h, t = n[:-3], n[-3:]
    g = []
    while len(h) > 2:
        g.insert(0, h[-2:]); h = h[:-2]
    if h:
        g.insert(0, h)
    return "₹" + (",".join(g) + "," if g else "") + t


def today(docs):
    """Figures an episode may quote, from the same file Sona answers from."""
    kb = json.load(open(os.path.join(docs, "assistant.json"), encoding="utf-8"))
    nat = [b for b in kb["brands"] if b.get("nat")]
    lo, hi = min(nat, key=lambda b: b["r24"]), max(nat, key=lambda b: b["r24"])
    r22 = lambda b: b["r24"] * 22 / 24
    mk = {}                                   # lowest measured making charge per jewel: {Earrings: {b, p, hi}}
    for b in kb["brands"]:
        for c, v in (b.get("mk") or {}).items():
            if c not in mk or v < mk[c]["v"]:
                mk[c] = {"b": b["n"], "v": v, "p": f"{round(v, 1):g}%", "hi": voice.hindi_number(round(v, 1))}
    gap = round((r22(hi) - r22(lo)) * 10)
    return {"gap": inr(gap), "gapHi": voice.hindi_number(gap), "lo": lo["n"], "loP": inr(r22(lo)), "mk": mk, "date": kb.get("date", "")}


class Handler(http.server.SimpleHTTPRequestHandler):
    """/shorts/... from this skill, everything else from the built site."""
    def translate_path(self, path):
        p = path.split("?", 1)[0].split("#", 1)[0]
        if p.startswith("/shorts/"):
            return os.path.join(SKILL, p[len("/shorts/"):])
        return super().translate_path(path)

    def log_message(self, *a):
        pass


def serve(docs, port):
    h = functools.partial(Handler, directory=docs)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def relay(r):
    u = r.request.url
    try:
        if u.startswith("http://127.0.0.1"):
            return r.continue_()
        if any(k in u for k in ("supabase", "googletagmanager", "google-analytics", "googlesyndication",
                                 "doubleclick", "accounts.google.com", "cloudflareinsights")):
            return r.fulfill(status=200, content_type="application/json", body="null")
        if "fonts.googleapis.com" in u or "fonts.gstatic.com" in u:
            return r.fulfill(response=r.fetch(timeout=30000))
        return r.abort()
    except Exception:
        try:
            r.abort()
        except Exception:
            pass


def launch(p):
    try:
        return p.chromium.launch()
    except Exception:                       # use a pre-installed Chromium when Playwright's own is missing
        import glob
        exe = sorted(glob.glob("/opt/pw-browsers/chromium*/chrome-linux*/chrome"))
        if not exe:
            raise
        return p.chromium.launch(executable_path=exe[-1])


def lines_of(p, url, data):
    """The episode's dialogue, as written for today's figures."""
    b = launch(p)
    pg = b.new_page()
    pg.route("**/*", relay)
    pg.add_init_script("window.D = " + json.dumps(data, ensure_ascii=False) + ";")
    pg.goto(url, wait_until="load")
    lines = pg.evaluate("window.EP.lines || []")
    b.close()
    return lines


def open_stage(p, url, data, vo):
    b = launch(p)
    ctx = b.new_context(viewport={"width": 540, "height": 960}, device_scale_factor=2)
    ctx.route("**/*", relay)
    ctx.add_init_script("if (window.top === window) { window.D = " + json.dumps(data, ensure_ascii=False) +
                        "; window.VO = " + json.dumps(vo) + "; }")
    ctx.add_init_script(FRAME_INIT)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    pg.goto(url, wait_until="load")
    pg.evaluate("document.fonts.ready")
    ep = pg.evaluate("({chat: window.EP.chat || null, dur: window.EP.dur})")
    if ep["chat"]:                                            # a real question to the real Sona
        pg.evaluate("() => new Promise(res => { const f = document.getElementById('chat'); f.onload = () => res(); f.src = '/?c=1'; })")
        pg.wait_for_timeout(1500)
        f = [fr for fr in pg.frames if fr.url.endswith("/?c=1")][0]
        f.evaluate("css => { const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s); }", HIDE)
        f.evaluate("window.GR_ASK()")
        pg.wait_for_timeout(700)
        f.evaluate("q => window.GR_ASK(q)", ep["chat"]["q"])
        f.wait_for_function("document.querySelectorAll('#sonaPanel .sn-body > .sn-m').length >= 3 && !document.querySelector('.sn-body .sn-typing')", timeout=15000)
        f.evaluate("document.fonts.ready")
    return b, pg, errs, ep


def shot(pg, t, path, jpeg=False):
    pg.evaluate(f"render({t})")
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.locator("#stage").screenshot(path=path, type="jpeg" if jpeg else "png", **({"quality": 92} if jpeg else {}))


def mix(out, ep_audio, dur):
    """Music (dipping under the dialogue), sound effects and voices -> video.mp4."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    A = os.path.join(SKILL, "assets")
    m = ep_audio["music"]
    clips = [(os.path.join(A, "sfx", f), at, g, False) for f, at, g in ep_audio["sfx"]]
    clips += [(os.path.join(out, "work", "vo", i + ".wav"), at, g, True) for i, at, g in ep_audio["voice"]]
    ins = ["-ss", str(m.get("start", 0)), "-i", os.path.join(A, m["file"])]
    for f, _, _, _ in clips:
        ins += ["-i", f]
    fl = [f"[0:a]atrim=0:{dur:.3f},afade=t=out:st={dur - 1.4:.3f}:d=1.4,volume={m.get('gain', -2)}dB,aformat=sample_rates=48000:channel_layouts=stereo[m]"]
    fx, vo = "", ""
    for i, (_, at, g, is_vo) in enumerate(clips, 1):
        ms = int(at * 1000)
        fl.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={g}dB,adelay={ms}|{ms}[c{i}]")
        if is_vo:
            vo += f"[c{i}]"
        else:
            fx += f"[c{i}]"
    n_vo = vo.count("[")
    if n_vo:
        fl.append(f"{vo}amix=inputs={n_vo}:normalize=0[vb]")
        fl.append("[vb]asplit=2[vk][vv]")
        fl.append("[m][vk]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=350[md]")
        fl.append(f"[md][vv]{fx}amix=inputs={2 + fx.count('[')}:normalize=0,alimiter=limit=0.89[a]")
    else:
        fl.append(f"[m]{fx}amix=inputs={1 + fx.count('[')}:normalize=0,alimiter=limit=0.89[a]")
    aud = os.path.join(out, "work", "soundtrack.m4a")
    subprocess.run([ff, "-y", *ins, "-filter_complex", ";".join(fl), "-map", "[a]", "-t", f"{dur:.3f}",
                    "-c:a", "aac", "-b:a", "192k", aud], check=True, capture_output=True)
    mp4 = os.path.join(out, "video.mp4")
    subprocess.run([ff, "-y", "-framerate", str(FPS), "-i", os.path.join(out, "work", "frames", "f_%05d.jpg"), "-i", aud,
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-profile:v", "high",
                    "-movflags", "+faststart", "-c:a", "copy", "-shortest", mp4], check=True, capture_output=True)
    return mp4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode"); ap.add_argument("mode", choices=["stills", "video"]); ap.add_argument("times", nargs="?")
    ap.add_argument("--out"); ap.add_argument("--docs", default=os.path.join(REPO, "docs")); ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    name = os.path.splitext(os.path.basename(a.episode))[0]
    out = os.path.abspath(a.out or os.path.join("shorts-out", name))
    os.makedirs(os.path.join(out, "work"), exist_ok=True)
    srv = serve(os.path.abspath(a.docs), a.port)
    data = today(a.docs)
    url = f"http://127.0.0.1:{a.port}/shorts/episodes/{os.path.basename(a.episode)}"
    with sync_playwright() as p:
        lines = lines_of(p, url, data)
        vo = voice.synth(lines, os.path.join(out, "work", "vo")) if lines else {}
        b, pg, errs, ep = open_stage(p, url, data, vo)
        if a.mode == "stills":
            for t in [float(x) for x in (a.times or "0").split(",")]:
                shot(pg, t, os.path.join(out, "work", f"still_{t:05.2f}.png"))
            print("dialogue:", json.dumps(pg.evaluate("window.EP.voice")), "dur:", ep["dur"])
        else:
            fr = os.path.join(out, "work", "frames")
            shutil.rmtree(fr, ignore_errors=True); os.makedirs(fr)
            n, t0 = int(round(ep["dur"] * FPS)), time.time()
            for i in range(n):
                shot(pg, i / FPS, os.path.join(fr, f"f_{i:05d}.jpg"), jpeg=True)
                if i % 150 == 0:
                    print(f"frame {i}/{n}  {time.time() - t0:.0f}s", flush=True)
            poster = pg.evaluate("window.EP.poster || 0")
            shot(pg, poster, os.path.join(out, "poster.jpg"), jpeg=True)
            shutil.copy(os.path.join(out, "poster.jpg"), os.path.join(fr, "f_00000.jpg"))   # every feed's thumbnail
            audio = pg.evaluate("({music: window.EP.music, sfx: window.EP.sfx || [], voice: window.EP.voice || []})")
            print("wrote", mix(out, audio, ep["dur"]))
        b.close()
    srv.shutdown()
    print("today:", data, "errors:", errs[:5])


if __name__ == "__main__":
    sys.exit(main())
