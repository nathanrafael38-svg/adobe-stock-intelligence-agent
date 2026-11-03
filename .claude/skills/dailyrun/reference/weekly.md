# Weekly research

Goal: tell next week's prompt generation **what to make more of, what to stop, and why**,
based on what Nathan's portfolio actually sells and what Adobe rejects.

## 1. Portfolio evidence (Nathan's Edge, contributor portal, read-only)
- `https://contributor.stock.adobe.com/` → **Dashboard / Insights**: last 7 and 30 days
  sales/downloads, top-selling files (title, type, category) — copy the figures shown.
- **Uploaded Files → Not accepted**: count rejections in the last 30 days and group by the
  reason Adobe shows (e.g. quality/focus, artifacts, IP, similar content). Note which of
  them are Claude batches (filenames `C{N}_kk.jpg`).
- **In review**: how many C-batch files are waiting.
- Pipeline state: stage `F:\...\1. Dari Claude\_state\C*.json` and count per batch:
  generated, QC-rejected (and the reasons in `qc_review.note`), submitted. This shows
  what fails *before* Adobe.

## 2. Market evidence (public)
- Seasonal calendar 6–10 weeks ahead (holidays, events, seasons for global buyers).
- Adobe Stock's own trend/creative-insights pages and contributor blog for current
  themes (WebSearch; cite URLs). Prefer sources from the last 12 months.
- Do not use competitor download counts or paywalled data you cannot verify.

## 3. Brief schema (JSON) — return exactly this
```json
{
  "generated_at": "2026-11-02T09:05:00+07:00",
  "period": "2026-W45",
  "sources": [{"where": "Adobe Insights, last 30 days", "url": null, "status": "ok|blocked|not available"},
              {"where": "Adobe Stock trends 2026", "url": "https://...", "status": "ok"}],
  "portfolio": {
    "sales_7d": "…or not available", "sales_30d": "…", "downloads_30d": "…",
    "top_sellers": [{"title": "…", "type": "photo|illustration", "category": "…"}],
    "rejections_30d": {"total": 0, "by_reason": {"…": 0}, "claude_batches": 0},
    "pipeline": {"generated": 0, "qc_rejected": 0, "submitted": 0, "top_qc_reasons": ["…"]}
  },
  "priorities": [{"niche": "…", "type": "photo|illustration", "share": "e.g. 4 of 20",
                  "why": "…", "evidence": "source reference", "fact_or_hypothesis": "fact|hypothesis"}],
  "avoid": [{"what": "…", "why": "…", "evidence": "…"}],
  "seasonal_window": [{"event": "…", "date": "…", "start_producing_by": "…"}],
  "notes_for_prompts": ["concrete instructions, e.g. 'no hands in mug shots: 2 rejects for fingers'"],
  "summary_for_nathan": "Indonesian, max 5 lines"
}
```
Rules: every priority has `evidence`; at most 6 priorities; composition stays 8
illustrations + 12 photos unless Nathan changes the config — priorities say *which*
subjects, not the counts. Hypotheses are allowed only when labelled.

## 4. Hand-off (orchestrator)
Save the agent's JSON to `$MSP_WORKSPACE/research.json` → `python -m msp research-save
--file …` (rejects briefs without evidence) → commit the file it prints to
`<base>\_research\` → send Nathan the `summary_for_nathan` plus the top 3 priorities.
`reference/prompts.md` reads it with `python -m msp research-brief`.

## 5. Weekly report + evaluation (orchestrator, same run)
Nathan wants one report per week with an honest evaluation and what to do next week.
Facts first, then judgement; label every judgement as fact or hypothesis.

1. Numbers: `python -m msp weekly-stats --days 7` (made, QC-rejected and why, passed,
   submitted, failed per batch) plus the brief's `portfolio` block (Adobe sales, downloads,
   accepted / not accepted, In review). Anything Adobe-side that the researcher could not
   read is written as "not available", never estimated.
2. Sections, in this order, in Indonesian:
   - **Ringkasan minggu ini**: batches, generated, passed QC, submitted, accepted/rejected by
     Adobe, sales and downloads if available.
   - **Apa yang berhasil / gagal**: QC reject rate per batch and the top reasons; which
     concepts, types (illustration vs photo) and models (Nano Banana Pro vs 2.1) correlate
     with rejects. Small samples are said to be small.
   - **Evaluasi**: what the numbers support (fact) and what is only a guess (hypothesis);
     whether the pipeline itself caused problems (stale locks, failed uploads, wrong project names).
   - **Rekomendasi minggu depan**: at most 5 concrete actions, each with the evidence it rests on
     and how we will know next week whether it worked (a number to compare).
3. Deliver: publish as a Docs artifact when the Artifact tool offers it (title
   "Laporan mingguan 2026-W45"), otherwise send it as a `.md` file with SendUserFile. Send Nathan the
   five-line summary with the link or file. Never mention numbers that are not in the sources above.
4. The recommendations feed `notes_for_prompts` of the next brief; do not change composition
   or platform limits unless Nathan says so.
