---
name: stock-metadata
description: Write Adobe Stock and Vecteezy metadata (title, description, keywords, category) for approved images, in the JSON format `msp metadata` validates, following verified platform limits.
---
# Stage 5 — metadata

Write metadata only for assets in `qc_passed`. Look at the actual image (Read it);
describe what is visible, not what the prompt hoped for.

## Output file `$MSP_WORKSPACE/md_C{N}.json`
```json
{"1": {"title": "...", "vz_title": "...", "description": "...", "keywords": ["...", "..."], "category": 7}}
```

## Verified limits (Adobe help "CSV requirements", Vecteezy keywording tips, Oct 2026)
- Adobe title ≤ 70 characters, plain text, **no commas**. Filename ≤ 30 chars.
- Adobe keywords ≤ 50 (we use ≤ 49), ordered by importance — the first 10 matter most.
- Vecteezy: 5–50 keywords, 20–30 recommended (CSV takes the first 30). Titles must be
  unique across your portfolio.
- Adobe categories 1–21 (see config). Illustrations of isolated objects: use the
  subject's category (Food, Plants…), 8 Graphic Resources only for patterns/elements.
- Never: artist names, brands, real people, characters, "AI generated", model/tool names,
  resolution words (4k, 8k, HD), keyword stuffing, words for things not in the image.

- Vecteezy title (`vz_title`): **3-8 words**, max 200 chars, only letters, digits, `. , - '`, unique across the
  portfolio. Write it separately from the Adobe title (the Adobe title is usually 8-13 words). Missing
  `vz_title` is a warning and the CSV falls back to the Adobe title, which Vecteezy may reject.
- Vecteezy CSV columns: `Filename,Title,Description,Keywords,License` (License `pro` from config). Extensions in
  `Filename` are optional for web Add Data, must be omitted for FTP/SFTP. AI-Generated is ticked in Add Data, not in the CSV.

## Style
- Title: subject + key attribute + style/setting, 40–70 chars, natural English.
- Description: one factual sentence (Vecteezy uses it; IPTC caption).
- Keywords: lowercase, singular unless the plural is the search term, no duplicates,
  concrete first (subject, objects, colours, setting), concepts after.

Then run `msp metadata --file`, fix all errors, `msp embed`, `msp csv`.
IPTC/XMP written: ObjectName(≤64)/Headline/dc:title = title; Caption/dc:description =
description; Keywords/dc:subject = keywords. Which field Adobe shows as "Title" is
verified on the portal during `prepare` (title_seen) — report any mismatch.

## Vecteezy CSV import (verified on C183–C188)
- Vecteezy drops underscores from uploaded file names (`C189_01.jpg` → `C18901.jpg`); `msp csv` writes the Filename
  column that way (`vecteezy.csv_filename_remove_chars`). A CSV with `C189_01` matched no row and the embedded IPTC
  title/keywords were used instead. Re-check on the first import after this change.
- Keywords must be ASCII (no ü, é…): the validator now rejects them.
- Illustrations are not uploaded to Vecteezy (photos and real vectors only).
