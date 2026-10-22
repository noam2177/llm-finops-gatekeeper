# Portfolio publish checklist (5 minutes)

Repo: **https://github.com/noam2177/llm-finops-gatekeeper**

## GitHub profile pin (manual — no API in `gh`)

1. Open https://github.com/noam2177
2. **Customize your pins** → select **llm-finops-gatekeeper**
3. Save

## Topics (already set via CLI when possible)

`python`, `llm`, `pydantic`, `finops`, `ollama`, `job-search`, `ai-engineering`

## Resume bullet (English, sanitized)

- Built a **tiered LLM pipeline** that filters Senior job scrapes on CPU, extracts `tech_stack` and requirements with **local-first routing**, and escalates to cloud only on **Pydantic** validation failure; dry-run benchmark cut cloud calls **65%** (~**$96 / 10k** postings) with **zero** accepted hallucinations on fixtures.

## One-liner for interviews

> CPU gate drops Senior roles before any tokens; local model extracts structured fields; cloud is the exception; abstain beats guessing.

## LinkedIn project blurb

**AI Job Posting Filter** — Open-source Python pipeline for scraped job posts: regex senior gate, Ollama + cloud LLM tiers, strict JSON schema, FinOps ROI dashboard. `pytest` + dry-run demo, no API keys required for reviewers.

## Enable CI (if push of `.github/workflows` was blocked)

```bash
gh auth refresh -h github.com -s workflow
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions test and dry-run benchmark"
git push
```

Copy from `docs/ci-workflow.example.yml` if the workflow file is missing locally.

## Demo commands (screen record ~90s)

```bash
python -m gatekeeper benchmark --dry-run
python -m gatekeeper extract --file data/fixtures/sample_escalation.txt --dry-run --explain
```
