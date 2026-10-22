# AI Job Posting Filter

> **CPU senior-role gate + tiered local/cloud LLM extraction** for scraped job postings.
> Spend cloud budget only on eligible Junior/Mid roles, with strict `JobPostingSchema` validation.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Pydantic v2](https://img.shields.io/badge/pydantic-v2-e92063)

## Problem

Job boards and scrapers dump **Senior**, **Staff**, and **Principal** listings alongside Junior/Mid
AI roles. Sending every scrape to a heavy cloud LLM wastes money and pollutes downstream filters.

This pipeline:

1. **CPU gate** — regex rules drop Senior+ titles and non-job noise (0 tokens).
2. **Tier 1 (local)** — Ollama extracts `tech_stack` + `requirements` into JSON.
3. **Tier 2 (cloud)** — OpenAI-compatible API runs only when validation fails.
4. **Abstain** — if both tiers fail schema checks, return no structured output.

## Dry-run benchmark (20 synthetic postings)

| Metric | Value |
|---|---:|
| Cloud calls saved vs naive baseline | **65%** |
| Est. savings per 10,000 postings | **$96** |
| Routing accuracy (fixtures) | **20/20** |
| Hallucinations accepted | **0** |

```bash
pip install -e ".[dev]"
python -m gatekeeper benchmark --dry-run
python -m gatekeeper extract --file data/fixtures/sample_escalation.txt --dry-run --explain
pytest
```

## `JobPostingSchema`

```json
{
  "job_title": "Junior AI Developer",
  "seniority_level": "junior",
  "tech_stack": ["Python", "LLMs", "Pydantic"],
  "requirements": ["1+ years Python", "LLM integration experience"],
  "remote_ok": true
}
```

## Scenarios (fixtures)

| Scn | Meaning | Count |
|-----|---------|------:|
| A | Senior role or scrape noise → **BLOCKED** at CPU gate | 5 |
| B | Eligible posting → **local** model + schema OK | 8 |
| C | Local validation fail → **cloud** escalation | 4 |
| D | Unrecoverable scrape → **ABSTAIN** | 3 |

Regenerate fixtures: `python scripts/generate_fixtures.py`

## Configuration

See [`.env.example`](.env.example) for Ollama, cloud API, timeouts, and FinOps pricing.

## License

MIT
