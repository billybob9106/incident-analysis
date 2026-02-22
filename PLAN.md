# Project Plan — Incident Analysis

> This file is committed to the repo so the full planning context is never lost.
> If you lose the chat session, start here.

---

## What We Are Building

A Python/Jupyter data analysis project that:
1. Generates 150 mock IT incident tickets linked to ~300 remediation items (RIs)
2. Defines 30 IT/security controls across 8 domains
3. Maps those controls to RIs — with intentional gaps for the analysis to find
4. Analyses incidents, controls, and teams across 5 notebooks
5. Produces a markdown report and Excel export

---

## Execution Order

Build in this order — each step produces artifacts the next step depends on:

```
Step 1  → Create directory structure
Step 2  → Write requirements.txt
Step 3  → Write src/__init__.py  (empty)
Step 4  → Write src/helpers.py   (shared functions)
Step 5  → Write scripts/generate_data.py
Step 6  → Run: python scripts/generate_data.py  → data/raw/*.csv
Step 7  → Write notebooks/01_explore_data.ipynb
Step 8  → Write notebooks/02_control_mapping.ipynb
Step 9  → Write notebooks/03_team_risk.ipynb
Step 10 → Write notebooks/04_themes.ipynb
Step 11 → Write notebooks/05_summary_report.ipynb
Step 12 → Write README.md
Step 13 → Write PLAN.md (this file)
Step 14 → Initial git commit
```

---

## Key Design Decisions

### 1. `helpers.py` is the single source of truth for shared logic
All functions used by more than one notebook live in `src/helpers.py`.
No notebook imports from another notebook. This prevents copy-paste drift.

### 2. `generate_data.py` uses a fixed seed (42)
All random calls use `SEED=42`. The CSVs are identical on every run.
This makes the project reproducible and means charts always look the same.

### 3. Intentional control gaps are algorithmic
The mapping generator:
- Leaves 30% of RIs unmapped (no control coverage)
- Forces 8 specific controls to have zero mappings
- Over-represents 5 controls (to create contrast in analysis)

This is by design — the analysis notebooks should find these gaps.

### 4. Risk weights are named constants, not magic numbers
`RISK_WEIGHTS` in `helpers.py` defines the coefficients for team risk scoring.
Changing them changes all scores predictably:
```python
RISK_WEIGHTS = {
    "incident_count":       1,
    "severity_score":       2,
    "open_ri_count":        3,
    "control_gap_exposure": 4,
}
```

### 5. Notebooks are independent except for data dependencies
Notebooks 01–04 each read from `data/raw/` and write to `data/processed/`.
They do NOT read each other's outputs.
Notebook 05 reads all processed outputs and must be run last.
You can safely re-run any single notebook 01–04 without re-running all of them.

### 6. No ML libraries
All analysis uses `pandas`, `matplotlib`, and `seaborn` only.
Word frequency is done with `collections.Counter` — no `nltk` or `spacy` needed.

---

## Data Schema

### incidents.csv
```
incident_id, title, description, category, severity, status,
date_raised, date_closed, team, affected_system
```
- `category`: Systems | Technology | Hardware
- `severity`: P1 | P2 | P3 | P4 (P1 = most severe)
- `date_closed`: empty string for open incidents (loads as NaT)

### ris.csv
```
ri_id, incident_id, title, description, status, priority, owner_team, due_date
```
- `owner_team`: 60% same as incident team, 40% cross-team

### controls.csv
```
control_id, control_name, control_description, control_domain
```
- 30 controls across 8 domains
- IDs: CTL-001 through CTL-030

### mappings.csv
```
control_id, ri_id
```
- Many-to-many
- 8 controls intentionally have zero rows here

---

## Risk Score Formula

```
total_risk_score =
  (incident_count       × 1) +
  (severity_score       × 2) +
  (open_ri_count        × 3) +
  (control_gap_exposure × 4)
```

**Why these weights?**
- Raw incident count (×1) matters least — a team might just be unlucky
- Severity (×2) matters more — P1/P2 incidents indicate real business impact
- Open RIs (×3) indicate unresolved work accumulating
- Control gap exposure (×4) is the most serious — RIs with no control accountability

---

## Output File Inventory

| File | Produced by | Description |
|------|-------------|-------------|
| `data/raw/incidents.csv` | generate_data.py | 150 incidents |
| `data/raw/ris.csv` | generate_data.py | ~300 RIs |
| `data/raw/controls.csv` | generate_data.py | 30 controls |
| `data/raw/mappings.csv` | generate_data.py | Control→RI mappings |
| `data/processed/summary_stats.csv` | Notebook 01 | Basic dataset counts |
| `data/processed/chart_*.png` | Notebooks 01–04 | Chart exports |
| `data/processed/control_coverage.csv` | Notebook 02 | Per-control RI counts |
| `data/processed/team_risk_scores.csv` | Notebook 03 | Per-team risk scores |
| `data/processed/theme_frequencies.csv` | Notebook 04 | Word frequency table |
| `reports/REPORT.md` | Notebook 05 | Markdown summary |
| `data/processed/incident_analysis_report.xlsx` | Notebook 05 | Excel export (7 sheets) |

---

## How to Resume This Project in a New Chat

1. Open this file (`PLAN.md`) and paste relevant sections into the new chat
2. The assistant can read the repo structure to understand current state
3. Ask: "Where are we with the plan in PLAN.md?"

---

## Known Pitfalls

| Pitfall | Fix |
|---------|-----|
| `ModuleNotFoundError: src` in notebooks | Add `sys.path.insert(0, "..")` as first code line |
| `date_closed` comparisons failing | Use `.notna()` not `!= ""` — empty strings load as NaT |
| Duplicate mappings | `generate_data.py` deduplicates before saving |
| Notebook 05 fails | Run notebooks 01–04 first; guards will tell you what's missing |
