---
name: qc
description: Visual QC rubric for AI-generated microstock images (illustrations and photos) - hard defects, review triggers, and required crops. Used by the visual-qc agent.
---
# Visual QC rubric

Adobe rejects most often for soft focus / over-processing and AI artifacts. Be strict.

## Hard defects → TOLAK
- Any text, letters, pseudo-text, logo, watermark, signature, UI element.
- Anatomy: wrong finger count, fused/extra limbs, melted faces, impossible joints.
- Object geometry: warped symmetric objects (cups, wheels, keyboards, cutlery),
  impossible intersections, floating parts, duplicated handles.
- Soft focus on the main subject at 100%, smeared textures, plastic "AI sheen",
  heavy halos, banding, JPEG blocking.
- Illustration background not clean (grey cast, texture, stray marks touching edges).
- Recognisable brand shapes, characters, real people, landmarks.
- Composition crops the main subject awkwardly or leaves no usable copy space when the
  prompt asked for it.

## REVIEW (Nathan decides)
- Tech flag `near_duplicate` (compare with the referenced file).
- Minor flecks/spatter in watercolor that may be intentional.
- Prompt mismatch reported by the downloader (`prompt_match: differs`).

## Required crops (100%)
Illustration: subject outline, every fine detail cluster, all four corners, any stray mark.
Photo: main subject focus point, hands/faces if any, every object edge with geometry,
background bokeh, four corners.

## Note format
One sentence, what you saw, e.g. "clean; seeds sharp at 100%; white bg neutral".
