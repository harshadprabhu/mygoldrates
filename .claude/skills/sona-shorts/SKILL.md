---
name: sona-shorts
description: Make short vertical cartoon Reels/Shorts for MyGoldRates starring Chiku & Piku (our own cartoon couple) with Hindi voice dialogue, where Sona answers a real question on a phone. Use when asked for a cartoon, comic, romantic, "Bubu Dudu style" or character video, an Instagram Reel/YouTube Short with characters, or a new episode.
---

# Sona Shorts

Cute, funny, 20-35 second vertical videos (1080x1920, 30 fps): a couple has a
gold-buying problem, Sona solves it on a phone, and the punchline lands on
romance. The phone runs the real site, so every number is today's.

## The cast (original designs - ours to use anywhere)

- **Chiku** - chubby golden puppy, orange kurta. Lovable, a bit broke, easily
  shocked, dramatic fainter. Cute high boy's voice.
- **Piku** - white kitten, pink saree, bow, bindi. Sweet, knows what she wants,
  teases Chiku. Cute high girl's voice.
- **Sona** - our assistant (her avatar from assistant.js). Only appears in the
  phone and the outro; warm, clear voice; states facts, never jokes about money.

Never put another studio's characters (Bubu Dudu, Doraemon...) or someone
else's voice in a video, even on request - offer Chiku & Piku and our own
voices instead.

## Voices

Chiku and Piku speak in the owner's own recorded voices: a ~10 s clip each in
`~/.cache/sona-shorts/voices/` (`chiku.wav` + `chiku.txt` with exactly what
is said, same for `piku`), cloned line by line with IndicF5 (MIT). Only ever
use recordings of people who agreed to it, and never commit them - the repo
is public. Without a recording, a character falls back to an Indic Parler-TTS
speaker (Apache-2.0); Sona always uses that (Divya). Cloning takes 2-3 min a
line on a CPU; every line is cached by its text. Check new lines are
intelligible by transcribing them (faster-whisper "medium", language "hi").

## Making an episode

1. Copy `episodes/ring.html` and write the story: hook in 2 s, problem, ask
   Sona, real answer, romantic/comic payoff, outro. 20-35 s.
2. Dialogue in `LINES`: Hindi in Devanagari for the voice (`hi`), a short
   Hinglish subtitle (`sub`) with one emoji. Write numbers as words with
   `voice.hindi_number` (render.py passes `D.gapHi`, `D.mk.<Jewel>.hi`).
3. Lay out time with `K.timeline(window.VO, beat, firstBeat)`: `tl.say(id)`
   for each line, `tl.cut()` for scene changes (they land on the beat).
4. The Sona scene sets `EP.chat = {q, typeAt, sendAt, answerAt}` - the
   question must be one she really answers well; check it first with
   `tests/sona_harness.js`.
5. Check stills, then render:

```
python3 render.py episodes/<name>.html stills 1.5,6,12 --out <dir>
python3 render.py episodes/<name>.html video --out <dir>
```

First run downloads the voice models (Indic Parler-TTS 3.7 GB, IndicF5
1.4 GB; both checked against the official AI4Bharat files) into
`~/.cache/sona-shorts`. Needs
`pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu`,
`pip install git+https://github.com/huggingface/parler-tts.git "transformers==4.46.1" "datasets<3.2"`,
`pip install --no-deps git+https://github.com/ai4bharat/IndicF5.git vocos` and
`pip install accelerate ema_pytorch torchdiffeq x_transformers pydub cached_path jieba pypinyin tomli einops encodec wandb hydra-core matplotlib soundfile imageio-ffmpeg playwright`.

## Rules

- Real numbers only, from `render.py`'s `today()` (the knowledge file) or
  Sona's own answer. A shop's quote in a story stays unnamed and without a
  figure (the bill says "😱😱😱", not "30%").
- No jeweller is mocked; a brand name appears only inside Sona's real answer.
- Never "scraping"; never "guaranteed", "best" or "India's first".
- Text stays readable on a phone: bubbles 31 px+, captions 38 px+ at 540 px.
- Credit the music in the post: "Music: Sascha Ende, ende.app (CC BY 4.0)".
  Sound effects are Kenney's (CC0). See `assets/LICENSES.md`.
