#!/usr/bin/env python3
"""MyGoldRates video ads with Pinky & Gappu (owner, 12 Nov 2026).

Uses Google's Gemini API (key: GEMINI_API_KEY, a GitHub secret):
- images: gemini-nano-banana-2.1 makes the character reference sheets
  (brand/mascots/*.png), once, so every ad has the same two characters;
- video: gemini-omni-1.2-flash (Veo's replacement since 22 Oct 2026) makes
  each scene with sound and dialogue, up to 3 reference images per
  character; later scenes extend the first (one continuous shot), or, if
  extension fails, start from the previous scene's last frame.
Then ffmpeg puts together the real site screenshot (never drawn by the AI),
our logo in the corner and the black-and-gold end card, whose voice-over is
the audio of a short Omni clip made from the end card itself.

    python ad_maker.py sheet                     # reference images (once)
    python ad_maker.py clips    brand/ads/goldrate-confusion.json
    python ad_maker.py assemble brand/ads/goldrate-confusion.json
    python ad_maker.py all      brand/ads/goldrate-confusion.json

Output: out/<ad name>/ (scene-*.mp4, ad.mp4). The key is never printed.
"""
import base64
import glob
import json
import os
import shutil
import subprocess
import sys
import time

import requests

API = "https://generativelanguage.googleapis.com/v1beta/interactions"
IMAGE_MODEL = os.environ.get("AD_IMAGE_MODEL", "gemini-nano-banana-2.1")
VIDEO_MODEL = os.environ.get("AD_VIDEO_MODEL", "gemini-omni-1.2-flash")
MASCOTS = "brand/mascots"
W, H = 720, 1280

PINKY = ("Pinky: a short, round-faced Indian woman, big expressive dark eyes, warm brown skin, glossy black "
         "hair in a side braid with a small gold hair clip, pink-and-gold salwar kurta, small gold jhumka "
         "earrings, a thin gold bangle; calm, clever, playful half-smile")
GAPPU = ("Gappu: a chubby Indian man with round cheeks, curly black hair, a thin moustache, warm brown skin, "
         "mustard-yellow kurta with a navy-blue Nehru jacket, brown sandals; excitable, dramatic, lovable")
LOOK = ("Cute, chunky 3D animated character, soft rounded shapes, family-film style, warm soft lighting, "
        "plain light background, no text, no logos")


# ------------------------------------------------------------------ API
def _key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        sys.exit("GEMINI_API_KEY is not set (GitHub secret)")
    return k


def call(body, label, wait=900):
    """POST an interaction; wait until it is done; return its JSON."""
    h = {"x-goog-api-key": _key(), "Content-Type": "application/json"}
    r = requests.post(API, headers=h, json=body, timeout=600)
    if not r.ok:
        raise RuntimeError(f"{label}: HTTP {r.status_code} {r.text[:600]}")
    d = r.json()
    t0 = time.time()
    while d.get("status") not in (None, "completed", "succeeded", "done"):
        if d.get("status") in ("failed", "cancelled", "error"):
            raise RuntimeError(f"{label}: {d.get('status')} {json.dumps(d)[:600]}")
        if time.time() - t0 > wait:
            raise RuntimeError(f"{label}: still {d.get('status')} after {wait}s")
        time.sleep(10)
        g = requests.get(f"{API}/{d['id']}", headers=h, timeout=120)
        if g.ok:
            d = g.json()
    return d


def outputs(d, kind):
    """[(bytes, mime)] of the outputs of one kind ('image' or 'video')."""
    out = []
    for st in d.get("steps") or []:
        if st.get("type") != "model_output":
            continue
        for c in st.get("content") or []:
            if c.get("type") != kind:
                continue
            if c.get("data"):
                out.append((base64.b64decode(c["data"]), c.get("mime_type", "")))
            elif c.get("uri"):
                u = c["uri"]
                g = requests.get(u, headers={"x-goog-api-key": _key()}, timeout=600)
                if g.ok:
                    out.append((g.content, c.get("mime_type", "")))
    if not out:
        raise RuntimeError(f"no {kind} in the response: {json.dumps(d)[:800]}")
    return out


def img_item(path):
    mime = "image/png" if path.endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        return {"type": "image", "mime_type": mime, "data": base64.b64encode(f.read()).decode()}


# --------------------------------------------------------- reference sheet
def sheet():
    """Three reference images per character: full body front, side, face."""
    os.makedirs(MASCOTS, exist_ok=True)
    for name, desc in (("pinky", PINKY), ("gappu", GAPPU)):
        shots = [("front", "Full body, standing, facing the camera, arms relaxed."),
                 ("side", "Full body, three-quarter side view, walking."),
                 ("face", "Head and shoulders close-up, big smile.")]
        first = None
        for i, (tag, pose) in enumerate(shots, 1):
            text = f"{LOOK}. Character reference sheet image of {desc}. {pose}"
            inp = [{"type": "text", "text": text}]
            if first:                                   # same character as image 1
                inp = [img_item(first), {"type": "text", "text": "The same character exactly as in this image "
                                         "(same face, hair, outfit, colours). " + text}]
            d = call({"model": IMAGE_MODEL, "input": inp,
                      "response_format": {"type": "image", "aspect_ratio": "3:4", "image_size": "2K"}},
                     f"{name} {tag}")
            data, mime = outputs(d, "image")[0]
            path = f"{MASCOTS}/{name}-{i}-{tag}.{'jpg' if 'jpeg' in mime else 'png'}"
            with open(path, "wb") as f:
                f.write(data)
            first = first or path
            print("wrote", path)
    # the two together, for a quick look
    d = call({"model": IMAGE_MODEL, "input": [img_item(p) for p in refs()] + [{"type": "text", "text":
             f"{LOOK}. The two characters from these images standing side by side, smiling: the woman is "
             "Pinky, the man is Gappu. Keep their faces, hair and outfits exactly."}],
             "response_format": {"type": "image", "aspect_ratio": "16:9", "image_size": "2K"}}, "couple")
    data, mime = outputs(d, "image")[0]
    with open(f"{MASCOTS}/pinky-gappu.png", "wb") as f:
        f.write(data)
    print("wrote", f"{MASCOTS}/pinky-gappu.png")


def refs():
    """Up to 3 reference images per character (Omni's limit)."""
    out = []
    for name in ("pinky", "gappu"):
        out += sorted(glob.glob(f"{MASCOTS}/{name}-[0-9]-*.*"))[:3]
    return out


# ------------------------------------------------------------------ clips
def ffprobe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def last_frame(video, png):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.2", "-i", video, "-frames:v", "1", png],
                   check=True)


def clips(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    name = os.path.splitext(os.path.basename(spec_path))[0]
    od = f"out/{name}"
    os.makedirs(od, exist_ok=True)
    r = refs()
    if not r:
        sys.exit("no reference images in brand/mascots - run: python ad_maker.py sheet")
    fmt = lambda dur: {"type": "video", "aspect_ratio": spec.get("aspect_ratio", "9:16"),
                       "resolution": spec.get("resolution", "720p"), "duration": dur}
    man = {"scenes": [], "cumulative": False}
    prev_id, prev_file = None, None
    for i, sc in enumerate(spec["scenes"], 1):
        text = spec["style"] + " " + sc["prompt"]
        d = None
        if prev_id:                                   # continue the same shot
            try:
                d = call({"model": VIDEO_MODEL, "previous_interaction_id": prev_id,
                          "input": [{"type": "text", "text": text}], "response_format": fmt(sc["duration"])},
                         f"scene {i} (extend)")
            except RuntimeError as e:
                print(f"scene {i}: extension failed ({str(e)[:200]}); starting from the last frame instead")
                lf = f"{od}/scene-{i - 1}-last.png"
                last_frame(prev_file, lf)
                d = None
                text = "Start exactly from this first frame. " + text
                inp = [img_item(lf)] + [img_item(p) for p in r[:4]] + [{"type": "text", "text": text}]
        if d is None and not prev_id:
            inp = [img_item(p) for p in r] + [{"type": "text", "text": text}]
        if d is None:
            d = call({"model": VIDEO_MODEL, "input": inp, "response_format": fmt(sc["duration"])}, f"scene {i}")
        data, _ = outputs(d, "video")[0]
        f = f"{od}/scene-{i}.mp4"
        with open(f, "wb") as fh:
            fh.write(data)
        dur = ffprobe_dur(f)
        print(f"scene {i}: {f} ({dur:.1f}s)")
        man["scenes"].append({"file": f, "seconds": dur})
        prev_id, prev_file = d.get("id"), f
    # an extension may return the whole video so far rather than the new part
    s = man["scenes"]
    if len(s) > 1 and s[1]["seconds"] >= s[0]["seconds"] + 2.5:
        man["cumulative"] = True
    # the end card's voice: the audio of a short clip made from the card itself
    ec = spec.get("end_card") or {}
    if ec.get("voiceover") and os.path.exists(ec["image"]):
        try:
            d = call({"model": VIDEO_MODEL, "input": [img_item(ec["image"]), {"type": "text", "text":
                      "Keep this image completely still, no camera movement, no changes. A warm, friendly, "
                      f"confident Indian woman's voice says in clear Hindi: \"{ec['voiceover']}\" "
                      "Soft, premium background chime. No music over the voice."}],
                      "response_format": fmt(f"{max(3, int(ec.get('seconds', 3)) + 1)}s")}, "end card voice")
            data, _ = outputs(d, "video")[0]
            with open(f"{od}/endcard-voice.mp4", "wb") as fh:
                fh.write(data)
            man["voice"] = f"{od}/endcard-voice.mp4"
        except RuntimeError as e:
            print("end card voice: skipped -", str(e)[:200])
    json.dump(man, open(f"{od}/manifest.json", "w"), indent=1)


# --------------------------------------------------------------- assemble
def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def norm(src, dst):
    """720x1280, 30 fps, AAC stereo (silent track added if there is none)."""
    has_audio = bool(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                     "stream=index", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip())
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
          "fps=30,format=yuv420p")
    if has_audio:
        ff("-i", src, "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-ar", "44100", "-ac", "2", dst)
    else:
        ff("-i", src, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest", "-vf", vf,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", dst)


def screenshot(path):
    """The live homepage on a phone, pop-ups and banners removed."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(**p.devices["Pixel 7"])
        pg = c.new_page()
        pg.route("**/alerts-pop.js*", lambda r: r.abort())
        pg.goto("https://mygoldrates.com/", wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(3000)
        pg.evaluate("""() => {
          document.querySelectorAll('.sn-fab').forEach(e => e.remove());
          const bars = [...document.querySelectorAll('body *')].filter(e => /talk to Sona/i.test(e.innerText || '')
              && e.offsetHeight > 40 && e.offsetHeight < 200);
          if (bars.length) bars.sort((a, z) => z.offsetHeight - a.offsetHeight)[0].remove();
          document.querySelectorAll('body *').forEach(e => { const s = getComputedStyle(e);
            if ((s.position === 'fixed' || s.position === 'sticky') && /FREE DAILY GOLD ALERT/i.test(e.innerText || '')) e.remove(); });
        }""")
        pg.screenshot(path=path)
        b.close()


def assemble(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    name = os.path.splitext(os.path.basename(spec_path))[0]
    od = f"out/{name}"
    man = json.load(open(f"{od}/manifest.json"))
    tmp = f"{od}/tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    scenes = [s["file"] for s in man["scenes"]]
    if man.get("cumulative"):
        scenes = scenes[-1:]                       # the last extension holds the whole shot
    parts = []
    for i, s in enumerate(scenes):
        parts.append(f"{tmp}/n{i}.mp4")
        norm(s, parts[-1])
    with open(f"{tmp}/list.txt", "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    ff("-f", "concat", "-safe", "0", "-i", f"{tmp}/list.txt", "-c", "copy", f"{tmp}/story.mp4")
    # phone insert (the real site, fresh today) and the logo in the corner
    pi = spec.get("phone_insert") or {}
    phone = f"{tmp}/phone.png"
    try:
        screenshot(phone)
    except Exception as e:                          # fall back to the saved one
        print("screenshot: using the saved one -", type(e).__name__)
        shutil.copy(pi.get("image", "brand/assets/phone-screen.png"), phone)
    secs = [s["seconds"] for s in man["scenes"]]
    after = int(pi.get("after_scene", 1))
    # where the insert goes: after the scenes before it (their real lengths;
    # the planned ones when an extension returned the whole shot)
    before = spec_secs(spec)[:after] if man.get("cumulative") else secs[:after]
    t1 = sum(before) + float(str(pi.get("at", "4s")).rstrip("s"))
    t2 = t1 + float(pi.get("seconds", 2.5))
    logo = spec.get("logo", "docs/icon-192.png")
    ff("-i", f"{tmp}/story.mp4", "-loop", "1", "-i", phone, "-i", logo, "-filter_complex",
       f"[1]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black[ph];"
       f"[2]scale=88:88[lg];[0][ph]overlay=0:0:enable='between(t,{t1:.2f},{t2:.2f})':shortest=1[v1];"
       f"[v1][lg]overlay=W-w-24:24,format=yuv420p[v]",
       "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy",
       f"{tmp}/story2.mp4")
    # end card with its voice
    ec = spec.get("end_card") or {}
    n = float(ec.get("seconds", 3))
    if man.get("voice") and os.path.exists(man["voice"]):
        ff("-loop", "1", "-i", ec["image"], "-i", man["voice"], "-map", "0:v", "-map", "1:a", "-t", f"{n + 1}",
           "-vf", f"scale={W}:{H},fps=30,format=yuv420p,fade=t=in:st=0:d=0.4", "-af", "apad",
           "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-ar", "44100", "-ac", "2", f"{tmp}/end.mp4")
    else:
        ff("-loop", "1", "-i", ec["image"], "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{n}",
           "-vf", f"scale={W}:{H},fps=30,format=yuv420p,fade=t=in:st=0:d=0.4", "-c:v", "libx264",
           "-preset", "veryfast", "-c:a", "aac", f"{tmp}/end.mp4")
    with open(f"{tmp}/list2.txt", "w") as f:
        f.write(f"file '{os.path.abspath(tmp + '/story2.mp4')}'\nfile '{os.path.abspath(tmp + '/end.mp4')}'\n")
    ff("-f", "concat", "-safe", "0", "-i", f"{tmp}/list2.txt", "-c:v", "libx264", "-preset", "veryfast",
       "-crf", "20", "-c:a", "aac", "-movflags", "+faststart", f"{od}/ad.mp4")
    print(f"wrote {od}/ad.mp4 ({ffprobe_dur(od + '/ad.mp4'):.1f}s)")


def spec_secs(spec):
    return [float(s["duration"].rstrip("s")) for s in spec["scenes"]]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    spec = sys.argv[2] if len(sys.argv) > 2 else "brand/ads/goldrate-confusion.json"
    if cmd == "sheet":
        sheet()
    elif cmd == "clips":
        clips(spec)
    elif cmd == "assemble":
        assemble(spec)
    elif cmd == "all":
        if not refs():
            sheet()
        clips(spec)
        assemble(spec)
    else:
        sys.exit(__doc__)
