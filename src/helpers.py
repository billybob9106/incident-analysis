"""
helpers.py — Shared utilities for the Incident Analysis project.

Imported by all notebooks. All functions are stateless (pure or close to pure).
No imports from notebooks — no circular dependencies.
"""

import os
import re
from collections import Counter

import pandas as pd

# ---------------------------------------------------------------------------
# Risk scoring coefficients
# Changing these values changes team risk scores predictably.
# ---------------------------------------------------------------------------
RISK_WEIGHTS = {
    "incident_count":       1,
    "severity_score":       2,
    "open_ri_count":        3,
    "control_gap_exposure": 4,
}

# ---------------------------------------------------------------------------
# Default stopwords for theme extraction
# ---------------------------------------------------------------------------
DEFAULT_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "was",
    "for", "on", "at", "by", "with", "from", "that", "this", "it",
    "be", "as", "are", "were", "has", "have", "had", "not", "no",
    "due", "via", "new", "old", "system", "issue", "ticket", "error",
    "unable", "failed", "failure", "during", "after", "before",
    "been", "will", "also", "into", "than", "its", "they", "their",
    "when", "all", "our", "which", "more", "some", "team", "user",
    "would", "could", "should", "about",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(data_dir: str = "../data/raw") -> dict:
    """
    Load all four raw CSVs and return them as a dict of DataFrames.

    Keys: "incidents", "ris", "controls", "mappings"

    Date columns are parsed to datetime (NaT for empty/invalid values).
    All ID columns are loaded as strings to prevent int coercion.
    """
    paths = {
        "incidents": os.path.join(data_dir, "incidents.csv"),
        "ris":       os.path.join(data_dir, "ris.csv"),
        "controls":  os.path.join(data_dir, "controls.csv"),
        "mappings":  os.path.join(data_dir, "mappings.csv"),
    }
    date_cols = {
        "incidents": ["date_raised", "date_closed"],
        "ris":       ["due_date"],
    }
    frames = {}
    for name, path in paths.items():
        df = pd.read_csv(path, dtype=str)
        for col in date_cols.get(name, []):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        frames[name] = df
    return frames


# ---------------------------------------------------------------------------
# Severity weighting
# ---------------------------------------------------------------------------

def severity_weight(severity: str) -> int:
    """
    Convert a P1–P4 severity string to a numeric weight.

    P1 = 4 (most severe), P2 = 3, P3 = 2, P4 = 1 (least severe).
    Returns 0 for unrecognised values (defensive default).
    """
    weights = {"P1": 4, "P2": 3, "P3": 2, "P4": 1}
    return weights.get(str(severity).upper().strip(), 0)


# ---------------------------------------------------------------------------
# Theme extraction
# ---------------------------------------------------------------------------

def extract_themes(
    texts: pd.Series,
    top_n: int = 20,
    stopwords: set = None,
) -> pd.DataFrame:
    """
    Word frequency analysis on a pandas Series of strings.

    Tokenises by extracting words of 4+ characters, lowercases, removes
    stopwords, and returns a DataFrame with columns {"word", "count"}
    sorted descending by count.

    Parameters
    ----------
    texts     : pd.Series of strings (titles, descriptions, etc.)
    top_n     : number of top words to return
    stopwords : set of words to exclude; defaults to DEFAULT_STOPWORDS

    Returns
    -------
    pd.DataFrame with columns ["word", "count"]
    """
    sw = stopwords if stopwords is not None else DEFAULT_STOPWORDS
    all_words = []
    for text in texts.dropna().astype(str):
        tokens = re.findall(r"[a-zA-Z]{4,}", text.lower())
        all_words.extend(t for t in tokens if t not in sw)
    counts = Counter(all_words).most_common(top_n)
    return pd.DataFrame(counts, columns=["word", "count"])


# ---------------------------------------------------------------------------
# Team risk scoring
# ---------------------------------------------------------------------------

def compute_team_risk(
    incidents: pd.DataFrame,
    ris: pd.DataFrame,
    mappings: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute a composite risk score for each team.

    Dimensions:
      incident_count        — total incidents belonging to team
      severity_score        — sum of severity_weight() for team's incidents
      open_ri_count         — RIs linked to team's incidents with status != "Closed"
      control_gap_exposure  — RIs linked to team's incidents with NO mapping entry

    Final score:
      total_risk_score = (incident_count × 1) + (severity_score × 2)
                       + (open_ri_count × 3) + (control_gap_exposure × 4)

    Returns a DataFrame indexed by team name, sorted descending by total_risk_score.
    """
    inc = incidents.copy()
    inc["sev_w"] = inc["severity"].apply(severity_weight)

    sev = inc.groupby("team")["sev_w"].sum().rename("severity_score")
    cnt = inc.groupby("team")["incident_id"].count().rename("incident_count")

    # Attach team to each RI via the incident
    ri_team = ris.merge(inc[["incident_id", "team"]], on="incident_id", how="left")

    # Open RI count per team
    open_ri = (
        ri_team[ri_team["status"] != "Closed"]
        .groupby("team")["ri_id"].count()
        .rename("open_ri_count")
    )

    # Control gap exposure: RIs with no entry in mappings
    covered_ri_ids = set(mappings["ri_id"].unique())
    ri_team["has_mapping"] = ri_team["ri_id"].isin(covered_ri_ids)
    gap = (
        ri_team[~ri_team["has_mapping"]]
        .groupby("team")["ri_id"].count()
        .rename("control_gap_exposure")
    )

    result = pd.concat([cnt, sev, open_ri, gap], axis=1).fillna(0).astype(int)
    w = RISK_WEIGHTS
    result["total_risk_score"] = (
        result["incident_count"]       * w["incident_count"] +
        result["severity_score"]       * w["severity_score"] +
        result["open_ri_count"]        * w["open_ri_count"] +
        result["control_gap_exposure"] * w["control_gap_exposure"]
    )
    return result.sort_values("total_risk_score", ascending=False)


# ---------------------------------------------------------------------------
# Plot style
# ---------------------------------------------------------------------------

def set_plot_style() -> None:
    """
    Apply a consistent seaborn/matplotlib style across all notebooks.
    Call once at the top of each notebook before any plotting.
    """
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(style="whitegrid", palette="muted")
    plt.rcParams.update({
        "figure.figsize": (10, 5),
        "axes.titlesize": 13,
        "axes.labelsize": 11,
    })


# ---------------------------------------------------------------------------
# Save processed outputs
# ---------------------------------------------------------------------------

def save_processed(
    df: pd.DataFrame,
    filename: str,
    processed_dir: str = "../data/processed",
) -> str:
    """
    Save a DataFrame to the data/processed/ directory.

    Creates the directory if it does not exist.
    Returns the full path the file was saved to.
    """
    os.makedirs(processed_dir, exist_ok=True)
    path = os.path.join(processed_dir, filename)
    df.to_csv(path, index=True)
    return path
