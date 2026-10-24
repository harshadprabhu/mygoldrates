"""Voices for Sona Shorts: Hindi dialogue, generated offline on this machine.

A character with a recorded voice (<voices>/<who>.wav, a few seconds of the
person speaking, and <who>.txt, exactly what they say) speaks every line in
that voice, cloned with IndicF5 (AI4Bharat, MIT). Use only recordings of
people who agreed to it - the owner's own. They are never committed: the
repo is public. <voices> is $SONA_SHORTS_VOICES, else ~/.cache/sona-shorts/voices.

A character without one (Sona) uses one of Indic Parler-TTS's own Hindi
speakers (AI4Bharat, Apache-2.0), directed by a style description and lifted
a little in pitch with the formants kept.

Both models' official repos are gated behind a Hugging Face login, so they
come from public mirrors, and the weights are checked against the official
files' SHA-256 before use. IndicF5 runs AI4Bharat's own code
(pip install git+https://github.com/ai4bharat/IndicF5.git), never a mirror's.
Lines are cached by their text, so re-renders only voice what changed.
"""
import hashlib, json, os, subprocess

MIRROR = "naklitechie/indic-parler-tts"
WEIGHTS_SHA256 = "c68daecb60f80c8f1faf0a6d2e6ddd6de8e224fb19750f3e9a33bca43c552c90"   # ai4bharat/indic-parler-tts model.safetensors
F5_MIRROR = "6Morpheus6/IndicF5"
F5_SHA256 = "ba7f3671180fb7784e24bd1dafc96e729a38ce02e7f6d3877cdef32525a1865c"        # ai4bharat/IndicF5 model.safetensors
HOME = os.path.expanduser("~/.cache/sona-shorts")
VOICES = os.environ.get("SONA_SHORTS_VOICES") or os.path.join(HOME, "voices")
GIRL = ("speaks in a very high-pitched, cute, childlike and bubbly voice, very animated and expressive like a cartoon "
        "character, at a fast pace. The recording is very clear and close up, with no background noise.")
BOY = ("speaks in a high-pitched, cute, boyish and comic voice, very animated and expressive like a cartoon character, "
       "at a fast pace. The recording is very clear and close up, with no background noise.")
SONA = ("speaks in a warm, friendly and clear voice with a slightly high pitch, at a moderate pace. The recording is "
        "very clear and close up, with no background noise.")
CAST = {                      # speaker, style, pitch lift (x1.19 = +3 semitones)
    "piku": ("Rani", GIRL, 1.19),
    "chiku": ("Aman", BOY, 1.19),
    "sona": ("Divya", SONA, 1.06),
}

_ONES = ("शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस इक्कीस बाईस तेईस "
         "चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस चालीस "
         "इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास पचास इक्यावन बावन तिरेपन चौवन पचपन छप्पन "
         "सत्तावन अट्ठावन उनसठ साठ इकसठ बासठ तिरेसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर "
         "चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्यासी अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी "
         "नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे").split()


def hindi_number(x):
    """2647 -> 'दो हज़ार छह सौ सैंतालीस'; 15.7 -> 'पंद्रह दशमलव सात' (the model reads words better than digits)."""
    s = f"{x}"
    if "." in s:
        a, b = s.split(".", 1)
        return hindi_number(int(a)) + " दशमलव " + " ".join(_ONES[int(d)] for d in b)
    n, out = int(x), []
    for size, word in ((100000, "लाख"), (1000, "हज़ार"), (100, "सौ")):
        if n >= size:
            out.append(f"{_ONES[n // size]} {word}"); n %= size
    if n or not out:
        out.append(_ONES[n])
    return " ".join(out)


def _checked(w, sha, d):
    h = hashlib.sha256()
    with open(w, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    if h.hexdigest() != sha:
        raise SystemExit(f"voice model at {d} is not the official AI4Bharat release; delete it and retry")


def model_dir():
    d = os.environ.get("SONA_SHORTS_TTS") or os.path.join(HOME, "indic-parler-tts")
    w = os.path.join(d, "model.safetensors")
    if not os.path.exists(w):
        from huggingface_hub import snapshot_download
        snapshot_download(MIRROR, local_dir=d)
    _checked(w, WEIGHTS_SHA256, d)
    return d


def recorded(who):
    """(wav, transcript) of the owner's recording for a character, or None."""
    w, t = os.path.join(VOICES, who + ".wav"), os.path.join(VOICES, who + ".txt")
    if os.path.exists(w) and os.path.exists(t):
        return w, open(t, encoding="utf-8").read().strip()
    return None


class _Clone:
    """IndicF5: new lines in a recorded voice."""
    def __init__(self):
        import torch, torchaudio, soundfile as sf
        from huggingface_hub import hf_hub_download, snapshot_download
        from safetensors.torch import load_file
        from vocos import Vocos
        from f5_tts.model import DiT
        from f5_tts.infer.utils_infer import load_model, infer_process, preprocess_ref_audio_text

        def _load(path, *a, **k):            # newer torchaudio.load needs torchcodec; soundfile does the job
            y, sr = sf.read(path, dtype="float32", always_2d=True)
            return torch.from_numpy(y.T.copy()), sr
        torchaudio.load = _load
        d = os.environ.get("SONA_SHORTS_F5") or os.path.join(HOME, "indicf5")
        w = os.path.join(d, "model.safetensors")
        if not os.path.exists(w):
            for f in ("model.safetensors", "checkpoints/vocab.txt"):
                hf_hub_download(F5_MIRROR, f, local_dir=d)
        _checked(w, F5_SHA256, d)
        vd = os.path.join(HOME, "vocos")
        if not os.path.exists(os.path.join(vd, "config.yaml")):
            snapshot_download("charactr/vocos-mel-24khz", local_dir=vd)
        self.model = load_model(DiT, dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4),
                                mel_spec_type="vocos", vocab_file=os.path.join(d, "checkpoints", "vocab.txt"), device="cpu")
        sd = load_file(w)                    # one file: the speech model and its tuned vocoder
        pre = "ema_model._orig_mod."
        self.model.load_state_dict({k[len(pre):]: v for k, v in sd.items() if k.startswith(pre)}, strict=False)
        self.voc = Vocos.from_hparams(os.path.join(vd, "config.yaml"))
        pre = "vocoder._orig_mod."
        self.voc.load_state_dict({k[len(pre):]: v for k, v in sd.items() if k.startswith(pre)})
        self.model.eval(); self.voc.eval()
        self.infer, self.prep, self.sr = infer_process, preprocess_ref_audio_text, 24000

    def say(self, ref, text):
        import soundfile as sf
        ra, rt = self.prep(*ref)
        rd = sf.info(ref[0]).duration
        pace = max(1.0, len(text) / 13.0)    # ~13 characters a second, whatever the recording's pauses
        wav, sr, _ = self.infer(ra, rt, text, self.model, self.voc, mel_spec_type="vocos", nfe_step=32,
                                fix_duration=rd + pace, device="cpu")
        return wav


class _TTS:
    def __init__(self):
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer
        d = model_dir()
        self.torch = torch
        self.model = ParlerTTSForConditionalGeneration.from_pretrained(d).eval()
        self.tok = AutoTokenizer.from_pretrained(d)
        self.dtok = AutoTokenizer.from_pretrained(self.model.config.text_encoder._name_or_path)
        self.sr = self.model.config.sampling_rate

    def say(self, speaker, style, text, seed):
        self.torch.manual_seed(seed)
        d = self.dtok(f"{speaker} {style}", return_tensors="pt")
        p = self.tok(text, return_tensors="pt")
        with self.torch.no_grad():
            a = self.model.generate(input_ids=d.input_ids, attention_mask=d.attention_mask,
                                    prompt_input_ids=p.input_ids, prompt_attention_mask=p.attention_mask)
        return a.cpu().numpy().squeeze()


def synth(lines, outdir):
    """lines: [{id, who, hi}] -> {id: seconds}; writes <outdir>/<id>.wav (48 kHz mono)."""
    import imageio_ffmpeg, numpy as np, soundfile as sf
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cache = os.path.join(outdir, "cache")
    os.makedirs(cache, exist_ok=True)
    tts, clone, durs = None, None, {}
    for ln in lines:
        speaker, style, lift = CAST[ln["who"]]
        ref = recorded(ln["who"])
        if ref:
            lift, tag = 1.0, ["clone", hashlib.sha1(open(ref[0], "rb").read()).hexdigest()[:12], ref[1]]
        else:
            tag = [speaker, style, lift]
        key = hashlib.sha1(json.dumps(tag + [ln["hi"]], ensure_ascii=False).encode()).hexdigest()[:16]
        done = os.path.join(cache, key + ".wav")
        if not os.path.exists(done):
            if ref:
                clone = clone or _Clone()
                best, sr = (clone.say(ref, ln["hi"]), 0), clone.sr
            else:
                tts = tts or _TTS()
                best, sr = None, tts.sr
                for seed in (7, 21, 42):        # keep a take whose pace is plausible speech
                    a = tts.say(speaker, style, ln["hi"], seed)
                    rate = len(ln["hi"]) / max(.1, len(a) / tts.sr)
                    if best is None or abs(rate - 14) < abs(best[1] - 14):
                        best = (a, rate)
                    if 8 <= rate <= 20:
                        break
            raw = os.path.join(cache, key + ".raw.wav")
            sf.write(raw, np.asarray(best[0], dtype=np.float32), sr)
            subprocess.run([ff, "-y", "-i", raw, "-af",
                            f"rubberband=pitch={lift}:formant=preserved:pitchq=quality:transients=smooth,highpass=f=80,"
                            "silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_threshold=-45dB:stop_duration=0.25,"
                            "aresample=48000", "-ac", "1", done], check=True, capture_output=True)
            y, sr = sf.read(done)
            sf.write(done, y / max(1e-6, np.abs(y).max()) * .89, sr)
            print(f"voiced {ln['id']} ({ln['who']}, {'recorded voice' if ref else speaker})", flush=True)
        dst = os.path.join(outdir, ln["id"] + ".wav")
        if os.path.abspath(dst) != os.path.abspath(done):
            import shutil
            shutil.copy(done, dst)
        info = sf.info(dst)
        durs[ln["id"]] = round(info.frames / info.samplerate, 3)
    return durs
