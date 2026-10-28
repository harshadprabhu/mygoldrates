# Feature reels (no characters, no voices)

A 10-15 s vertical clip of the real Sona answering, with the logo header,
captions and a "Visit now: mygoldrates.com" end card. Numbers are today's:
the phone runs the built site (docs/) and its assistant.json.

    python3 serve.py <repo>/docs &            # site + this folder on :8765
    NODE_PATH=$(npm root -g) node capture.js  # frames/ + frames/list.json (still, seconds)
    # then ffmpeg concat (frames/list.json -> concat.txt) with music from ../assets/music,
    # 1080x1920, 30 fps, H.264 + AAC, -movflags +faststart

Post: copy to docs/social/reel-<IST date>.mp4 with a caption in .txt beside it,
then run the social-post workflow with post=reel, mode=post.
Edit the questions and captions in capture.js; check Sona's answers first
with tests/sona_harness.js. Credit the music in the caption.

Voices (optional): lines.json holds each spoken line (`hi` = what is said,
`sub` = the subtitle). Voice them with ../voice.py (Indic Parler-TTS; Hindi
in Sona's voice "Divya", English in the model's English voice "Mary" - the
Hindi voice mispronounces English words like "gold"), check every line by
transcribing it (faster-whisper "medium"), speed up with atempo=1.1, and put
the lengths in vo.json: capture.js stretches each scene to fit its line and
writes frames/marks.json (where each line starts) for the audio mix.
