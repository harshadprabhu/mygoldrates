# Pinky & Gappu — MyGoldRates mascots

Our recurring ad couple (owner, 12 Nov 2026). Original characters, ours to
use anywhere. Every ad uses the reference images in `brand/mascots/` so they
look the same every time; regenerate them only if the owner wants a redesign.

## Pinky (the wife) — the smart one
- Short, round-faced, big expressive dark eyes, warm brown skin.
- Glossy black hair in a side braid with a small gold hair clip.
- Pink-and-gold salwar kurta, small gold jhumka earrings, thin gold bangle.
- Calm, clever, playful; a knowing half-smile; teases Gappu kindly.
- Always the one who knows the trick: compare rates and making charges on
  MyGoldRates before buying.

## Gappu (the husband) — the lovable over-reactor
- Chubby, round cheeks, curly black hair, thin moustache, warm brown skin.
- Mustard-yellow kurta with a navy-blue Nehru jacket, brown sandals.
- Over-excited and dramatic: eyes pop, jaw drops, nearly falls over; then
  acts like a genius once he gets it.
- Says "अरे!" a lot. Never mean, always funny.

## Look
- Cute, chunky 3D animated characters, soft rounded shapes, family-film
  style, warm lighting. Vertical 9:16 for Reels/Shorts.
- Settings: Indian jewellery showrooms, homes, festivals (Dhanteras,
  Akshaya Tritiya, weddings).

## Rules
- Pinky and Gappu, never anyone else's characters.
- The AI never draws our website, logo, prices or text: phone screens stay
  plain and dark; the real screenshot, logo and end card are added in
  editing (`ad_maker.py assemble`).
- Hindi dialogue, short and natural. Ads end on the black-and-gold end card:
  "सोना खरीदने से पहले, रेट compare करें MyGoldRates.com पर!"
- Mark posts as AI-generated where platforms ask.

## Making an ad
1. `brand/ads/<name>.json` — the scenes (see `goldrate-confusion.json`).
2. GitHub → Actions → **ad-maker** → Run: `sheet` (only once, to make the
   reference images), then `clips`, then `assemble` (or `all`).
3. The finished MP4 is in the run's artifacts.
