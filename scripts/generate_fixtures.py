"""Regenerate 20 synthetic job-posting fixtures and ``data/ground_truth.csv``."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"
GROUND_TRUTH = ROOT / "data" / "ground_truth.csv"


@dataclass(frozen=True, slots=True)
class Fixture:
    filename: str
    scenario: str
    description: str
    text: str
    expected_status: str
    expected_resolved_by: str
    job_title: str | None = None
    seniority: str | None = None
    tech_stack: str | None = None


def _posting(
    *,
    title: str,
    seniority: str,
    tech: str,
    requirements: list[str],
    remote: str = "no",
    extra: str = "",
) -> str:
    req_block = "\n".join(f"- {line}" for line in requirements)
    return f"""JOB_POSTING_SCRAPE
Title: {title}
Seniority: {seniority}
Remote: {remote}

About the role
We are hiring for this position. Apply now via our careers page.

Tech stack: {tech}

Requirements:
{req_block}
{extra}
"""


def build_fixtures() -> list[Fixture]:
    fixtures: list[Fixture] = []

    blocked = [
        (
            "sample_blocked_senior_engineer.txt",
            "Senior in title",
            _posting(
                title="Senior Software Engineer",
                seniority="Mid",
                tech="Python, AWS",
                requirements=["5+ years experience"],
            ),
        ),
        (
            "sample_blocked_principal.txt",
            "Principal level cue",
            _posting(
                title="Principal Machine Learning Engineer",
                seniority="Mid",
                tech="PyTorch, Kubernetes",
                requirements=["Lead research initiatives"],
            ),
        ),
        (
            "sample_blocked_staff.txt",
            "Staff engineer cue",
            """JOB_POSTING_SCRAPE
Title: Platform Engineer
Seniority: Mid
Remote: yes

Staff Engineer — platform reliability
We are hiring. Tech stack: Go, Terraform
Requirements:
- On-call rotation experience
""",
        ),
        (
            "sample_blocked_sr_abbrev.txt",
            "Sr. abbreviation",
            _posting(
                title="Sr. Backend Developer",
                seniority="Mid",
                tech="Java, Spring",
                requirements=["API design"],
            ),
        ),
        (
            "sample_blocked_scrape_noise.txt",
            "Not a job posting (newsletter scrape)",
            """WEEKLY TECH NEWSLETTER — Issue 412
Top stories: new GPU launch, framework updates.
Unsubscribe | Privacy | Click tracking pixel
""",
        ),
    ]
    for filename, description, text in blocked:
        fixtures.append(Fixture(filename, "A", description, text, "BLOCKED", "gate"))

    clean_specs = [
        (
            "Junior AI Developer",
            "junior",
            "Python|LLMs|Pydantic",
            ["1+ years Python", "Familiarity with LLMs"],
        ),
        (
            "Mid-level ML Engineer",
            "mid",
            "Python|scikit-learn|Docker",
            ["Ship models to production", "Write unit tests"],
        ),
        (
            "AI Automation Intern",
            "intern",
            "Python|Playwright|OpenAI API",
            ["Automate internal workflows"],
        ),
        (
            "Associate Data Scientist",
            "associate",
            "SQL|pandas|Jupyter",
            ["Analytical thinking", "Clear communication"],
        ),
        (
            "Machine Learning Developer",
            "mid",
            "TensorFlow|GCP|FastAPI",
            ["Build APIs around models"],
            "yes",
        ),
        (
            "Junior NLP Engineer",
            "junior",
            "spaCy|Hugging Face|Python",
            ["Text preprocessing pipelines"],
        ),
        (
            "AI Tools Engineer",
            "mid",
            "TypeScript|Node.js|LangChain",
            ["Integrate external AI services"],
        ),
        (
            "MLOps Associate",
            "associate",
            "Kubernetes|MLflow|Python",
            ["Monitor model drift", "CI for ML"],
        ),
    ]
    for index, (title, level, tech, reqs, *rest) in enumerate(clean_specs, start=1):
        remote = rest[0] if rest else "no"
        fixtures.append(
            Fixture(
                f"sample_clean_{index:02d}.txt",
                "B",
                "Eligible posting, local model passes JobPostingSchema",
                _posting(title=title, seniority=level, tech=tech, requirements=reqs, remote=remote),
                "SUCCESS",
                "local",
                title,
                level,
                tech.replace("|", "|"),
            )
        )

    esc = [
        (
            "sample_escalation.txt",
            "Local returns tech_stack as string",
            _posting(
                title="Junior AI Developer",
                seniority="junior",
                tech="Python|FastAPI|OpenAI API",
                requirements=["Python proficiency", "API integration experience"],
                extra="[mock:tech_string]",
            ),
            "Junior AI Developer",
            "junior",
            "Python|FastAPI|OpenAI API",
        ),
        (
            "sample_escalation_truncated.txt",
            "Local emits truncated JSON",
            _posting(
                title="Mid-level Prompt Engineer",
                seniority="mid",
                tech="Python|LangChain|vector DBs",
                requirements=["Prompt design", "Evaluation harnesses"],
                extra="[mock:truncated]",
            ),
            "Mid-level Prompt Engineer",
            "mid",
            "Python|LangChain|vector DBs",
        ),
        (
            "sample_escalation_empty_reqs.txt",
            "Local returns empty requirements list",
            _posting(
                title="AI Developer",
                seniority="mid",
                tech="Python|pytest|LLMs",
                requirements=["Write clean Python", "Test AI solutions"],
                extra="[mock:empty_requirements]",
            ),
            "AI Developer",
            "mid",
            "Python|pytest|LLMs",
        ),
        (
            "sample_escalation_tech_string_2.txt",
            "Second tech-as-string escalation path",
            _posting(
                title="Automation Engineer",
                seniority="junior",
                tech="Python|RPA|REST APIs",
                requirements=["Build internal tools", "Document automations"],
                extra="[mock:tech_string]",
            ),
            "Automation Engineer",
            "junior",
            "Python|RPA|REST APIs",
        ),
    ]
    for filename, description, text, title, level, tech in esc:
        fixtures.append(
            Fixture(filename, "C", description, text, "SUCCESS", "cloud", title, level, tech)
        )

    abstain = [
        (
            "sample_abstain_unclear.txt",
            "Cloud cannot recover missing requirements",
            """JOB_POSTING_SCRAPE
Title: Mystery AI Role
Seniority: mid
Remote: no

About the role
We are hiring but the requirements section failed to scrape.
Tech stack: Python
Requirements:
[mock:empty_requirements]
[mock:unrecoverable]
""",
        ),
        (
            "sample_abstain_corrupted.txt",
            "Both tiers return invalid JSON",
            _posting(
                title="Broken Listing",
                seniority="junior",
                tech="Python",
                requirements=["Unknown"],
                extra="[mock:truncated]\n[mock:unrecoverable]",
            ),
        ),
        (
            "sample_abstain_missing_tech.txt",
            "No technologies in scrape; cloud unrecoverable",
            """JOB_POSTING_SCRAPE
Title: Generic Analyst
Seniority: associate
Remote: hybrid

About the role
Apply now. Requirements:
- Strong communication
[mock:unrecoverable]
""",
        ),
    ]
    for filename, description, text in abstain:
        fixtures.append(Fixture(filename, "D", description, text, "ABSTAIN", "none"))

    return fixtures


def main() -> int:
    fixtures = build_fixtures()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    keep = {fixture.filename for fixture in fixtures}
    for path in FIXTURES.glob("*.txt"):
        if path.name not in keep:
            path.unlink()
    for fixture in fixtures:
        (FIXTURES / fixture.filename).write_text(fixture.text, encoding="utf-8")
    with GROUND_TRUTH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "filename",
                "scenario",
                "description",
                "expected_status",
                "expected_resolved_by",
                "expected_job_title",
                "expected_seniority",
                "expected_tech_stack",
            ]
        )
        for f in fixtures:
            writer.writerow(
                [
                    f.filename,
                    f.scenario,
                    f.description,
                    f.expected_status,
                    f.expected_resolved_by,
                    f.job_title or "",
                    f.seniority or "",
                    f.tech_stack or "",
                ]
            )
    print(f"wrote {len(fixtures)} fixtures to {FIXTURES.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
