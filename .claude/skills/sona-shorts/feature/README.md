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
