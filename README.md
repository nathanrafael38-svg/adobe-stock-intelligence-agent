# Adobe Stock Intelligence Agent

An automated research and analytics workflow for an Adobe Stock contributor business.

## Objectives

- Research commercial stock-content opportunities using public sources.
- Analyze contributor sales data from authorized data sources.
- Track portfolio performance and category-level evidence.
- Generate detailed English image-generation prompts.
- Produce daily Indonesian intelligence reports.
- Maintain historical records and execution logs.

## Data and privacy

- Source code and documentation are maintained in this private repository.
- Contributor earnings records and other private business data must be stored separately in an authorized private data store.
- Never commit credentials, access tokens, cookies, or private sales records.
- Never delete or modify published stock assets automatically.

## Current status

Daily production pipeline (C-Day N batches) rebuilt in `msp/` with agents and skills in
`.claude/`. See `docs/ARCHITECTURE.md` and `docs/RUNBOOK.md`. Unit/E2E tests pass on
synthetic data and one real image; live Flow/portal/scheduler runs still to be verified.

## Operating principles

- Distinguish verified facts from hypotheses.
- Do not fabricate sales or market-demand metrics.
- Track data freshness and source URLs.
- Test integrations before enabling scheduled production runs.
- Keep all automated operations within authorized access and usage limits.
