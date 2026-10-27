---
name: microstock-prompts
description: Generate the daily C-Day N prompt plan (8 illustrations 1:1 + 12 photos 16:9) for Adobe Stock, deduplicated against history, in the plan JSON format that `msp init` validates.
---
# Stage 1 — prompt plan

Output: a JSON list of 20 objects `{concept, type, aspect, prompt}` in this order:
8 × `illustration` `1:1`, then 12 × `photo` `16:9` (composition comes from
`config/pipeline.json`; if it changes there, follow the config).

## Inputs to read first
- `msp next-n` (with device state names) → N.
- `_state/C*.json` history concepts: `python -c "from msp import plan,config; print(plan.history_concepts(config.local_state_dir()))"`.
- **The latest research brief:** `python -m msp research-brief`. Follow its `priorities`
  (which subjects get more of the 20 slots), `avoid` and `notes_for_prompts`. Record in the
  plan log which brief you used. No brief yet → use the rules below and say so to Nathan.

## Rules
- Commercial stock subjects with a clear buyer use: food, home, work, seasonal (look
  ~6–8 weeks ahead of the calendar), wellness, design elements. No people's faces
  unless asked; hands are fine for photos when the action needs them.
- No brands, logos, trademarks, characters, artists, real people, landmarks with
  property-release risk, or text in the image.
- One concept per prompt; concepts must not repeat history (validator rejects Jaccard ≥ 0.6).
- Concrete materials, light and composition; realistic object geometry; clean backgrounds
  for illustrations; generous negative space.

## Fixed suffixes
Illustration:
`Clean illustration isolated on a plain white background, crisp edges, generous empty space around the subject, no text, no letters, no logos, no watermark, no signature.`

Photo (base):
`Photorealistic, shot on a full-frame camera with a 50mm lens, sharp focus on the main subject, natural textures, realistic proportions, no text, no letters, no logos, no brand names, no watermark.`
Add `anatomically correct hands with five fingers` **only** when hands/people are in the
subject. (The validator rejects it otherwise — it invites stray hands.)

## Finish
Save as `$MSP_WORKSPACE/plan_C{N}.json`, run `python -m msp validate-plan`, fix every
error, then `python -m msp init --n N --plan ...` and commit the three files it lists.
Send Nathan the PROMPTS sheet path and the Flow project name `C-Day N`, with the reminder to pick model **Nano Banana Pro**
in the Flow composer before generating (Flow defaults to Nano Banana 2 Lite).
