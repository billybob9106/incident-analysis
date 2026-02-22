"""
Unit tests for src/helpers.py

Coverage targets:
  - severity_weight()
  - extract_themes()
  - compute_team_risk()
  - save_processed()
  - load_data()  (via a temporary directory with fixture CSVs)

Run with:  pytest tests/test_helpers.py -v
"""

import os
import sys
import tempfile

import pandas as pd
import pytest

# Allow imports from project root (src/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.helpers import (
    DEFAULT_STOPWORDS,
    RISK_WEIGHTS,
    compute_team_risk,
    extract_themes,
    load_data,
    save_processed,
    severity_weight,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_incidents():
    """Two-team incidents DataFrame with known severity values."""
    return pd.DataFrame(
        {
            "incident_id": ["INC-001", "INC-002", "INC-003"],
            "title": ["Alpha outage", "Beta failure", "Alpha patch"],
            "description": ["desc1", "desc2", "desc3"],
            "severity": ["P1", "P2", "P3"],
            "status": ["Open", "Resolved", "Closed"],
            "team": ["TeamA", "TeamB", "TeamA"],
        }
    )


@pytest.fixture
def minimal_ris():
    """RIs linked to the minimal_incidents fixture."""
    return pd.DataFrame(
        {
            "ri_id": ["RI-001", "RI-002", "RI-003", "RI-004"],
            "incident_id": ["INC-001", "INC-001", "INC-002", "INC-003"],
            "title": ["Fix A", "Patch A", "Fix B", "Patch C"],
            "status": ["Open", "Closed", "Open", "Closed"],
        }
    )


@pytest.fixture
def minimal_mappings():
    """Only RI-001 and RI-003 have control mappings; RI-002 and RI-004 are gaps."""
    return pd.DataFrame(
        {
            "control_id": ["CTL-001", "CTL-002"],
            "ri_id": ["RI-001", "RI-003"],
        }
    )


@pytest.fixture
def raw_csv_dir(tmp_path):
    """
    Temporary directory containing the four raw CSVs expected by load_data().
    Uses minimal but structurally valid data.
    """
    incidents = pd.DataFrame(
        {
            "incident_id": ["INC-001", "INC-002"],
            "title": ["Outage", "Breach"],
            "description": ["Server down", "Data leak"],
            "category": ["Hardware", "Security"],
            "severity": ["P1", "P2"],
            "status": ["Open", "Closed"],
            "date_raised": ["2024-01-01", "2024-01-15"],
            "date_closed": ["", "2024-01-20"],
            "team": ["Infra", "Security"],
            "affected_system": ["SysA", "SysB"],
        }
    )
    ris = pd.DataFrame(
        {
            "ri_id": ["RI-001"],
            "incident_id": ["INC-001"],
            "title": ["Replace server"],
            "description": ["Order new hardware"],
            "status": ["Open"],
            "priority": ["High"],
            "owner_team": ["Infra"],
            "due_date": ["2024-02-01"],
        }
    )
    controls = pd.DataFrame(
        {
            "control_id": ["CTL-001"],
            "control_name": ["Patch Management"],
            "control_description": ["Apply patches monthly"],
            "control_domain": ["Patch Management"],
        }
    )
    mappings = pd.DataFrame({"control_id": ["CTL-001"], "ri_id": ["RI-001"]})

    incidents.to_csv(tmp_path / "incidents.csv", index=False)
    ris.to_csv(tmp_path / "ris.csv", index=False)
    controls.to_csv(tmp_path / "controls.csv", index=False)
    mappings.to_csv(tmp_path / "mappings.csv", index=False)

    return str(tmp_path)


# ---------------------------------------------------------------------------
# severity_weight
# ---------------------------------------------------------------------------


class TestSeverityWeight:
    def test_p1_returns_4(self):
        assert severity_weight("P1") == 4

    def test_p2_returns_3(self):
        assert severity_weight("P2") == 3

    def test_p3_returns_2(self):
        assert severity_weight("P3") == 2

    def test_p4_returns_1(self):
        assert severity_weight("P4") == 1

    def test_lowercase_accepted(self):
        assert severity_weight("p1") == 4
        assert severity_weight("p4") == 1

    def test_mixed_case_accepted(self):
        assert severity_weight("P2") == 3
        assert severity_weight("p3") == 2

    def test_whitespace_stripped(self):
        assert severity_weight("  P1  ") == 4
        assert severity_weight("\tP3\n") == 2

    def test_unknown_value_returns_zero(self):
        assert severity_weight("P5") == 0

    def test_empty_string_returns_zero(self):
        assert severity_weight("") == 0

    def test_arbitrary_string_returns_zero(self):
        assert severity_weight("critical") == 0
        assert severity_weight("HIGH") == 0

    def test_none_coerced_to_string_returns_zero(self):
        # The function calls str(severity), so None becomes "None"
        assert severity_weight(None) == 0

    def test_numeric_string_returns_zero(self):
        assert severity_weight("1") == 0
        assert severity_weight("4") == 0


# ---------------------------------------------------------------------------
# extract_themes
# ---------------------------------------------------------------------------


class TestExtractThemes:
    def test_returns_dataframe_with_correct_columns(self):
        texts = pd.Series(["alpha beta gamma delta"])
        result = extract_themes(texts)
        assert list(result.columns) == ["word", "count"]

    def test_returns_correct_word_counts(self):
        texts = pd.Series(["alpha alpha alpha beta beta"])
        result = extract_themes(texts)
        word_counts = dict(zip(result["word"], result["count"]))
        assert word_counts["alpha"] == 3
        assert word_counts["beta"] == 2

    def test_sorted_descending_by_count(self):
        texts = pd.Series(["beta alpha alpha alpha beta gamma"])
        result = extract_themes(texts)
        assert list(result["count"]) == sorted(result["count"], reverse=True)

    def test_words_shorter_than_4_chars_excluded(self):
        texts = pd.Series(["the an or is it to a be"])
        result = extract_themes(texts)
        assert result.empty or all(len(w) >= 4 for w in result["word"])

    def test_default_stopwords_removed(self):
        # Pick a stopword that is ≥4 chars: "this", "that", "with", "from"
        texts = pd.Series(["this that with from network network"])
        result = extract_themes(texts)
        words = list(result["word"])
        assert "this" not in words
        assert "that" not in words
        assert "with" not in words
        assert "from" not in words
        assert "network" in words

    def test_custom_stopwords_override(self):
        texts = pd.Series(["alpha alpha beta"])
        result = extract_themes(texts, stopwords={"alpha"})
        words = list(result["word"])
        assert "alpha" not in words
        assert "beta" in words

    def test_empty_custom_stopwords_includes_default_stopwords_words(self):
        # With an empty stopword set, default stopwords are NOT applied
        texts = pd.Series(["this this alpha"])
        result = extract_themes(texts, stopwords=set())
        words = list(result["word"])
        assert "this" in words

    def test_top_n_limits_results(self):
        texts = pd.Series(["aaaa bbbb cccc dddd eeee ffff gggg hhhh iiii jjjj"])
        result = extract_themes(texts, top_n=3)
        assert len(result) <= 3

    def test_empty_series_returns_empty_dataframe(self):
        result = extract_themes(pd.Series([], dtype=str))
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["word", "count"]
        assert result.empty

    def test_nan_values_are_skipped(self):
        texts = pd.Series([None, float("nan"), "valid text here"])
        result = extract_themes(texts)
        assert isinstance(result, pd.DataFrame)
        assert not result.empty

    def test_all_nan_series_returns_empty_dataframe(self):
        texts = pd.Series([None, None, None])
        result = extract_themes(texts)
        assert result.empty

    def test_case_insensitive_counting(self):
        texts = pd.Series(["Alpha ALPHA alpha"])
        result = extract_themes(texts)
        word_counts = dict(zip(result["word"], result["count"]))
        assert word_counts.get("alpha", 0) == 3

    def test_default_top_n_is_20(self):
        # Build 25 distinct words and confirm the default cap is 20
        words = [f"word{str(i).zfill(2)}" for i in range(25)]
        texts = pd.Series([" ".join(words)])
        result = extract_themes(texts)
        assert len(result) <= 20

    def test_numbers_and_punctuation_not_counted(self):
        texts = pd.Series(["abc123 !!!! ??? 999"])
        result = extract_themes(texts)
        assert result.empty


# ---------------------------------------------------------------------------
# compute_team_risk
# ---------------------------------------------------------------------------


class TestComputeTeamRisk:
    def test_returns_dataframe(self, minimal_incidents, minimal_ris, minimal_mappings):
        result = compute_team_risk(minimal_incidents, minimal_ris, minimal_mappings)
        assert isinstance(result, pd.DataFrame)

    def test_contains_expected_columns(
        self, minimal_incidents, minimal_ris, minimal_mappings
    ):
        result = compute_team_risk(minimal_incidents, minimal_ris, minimal_mappings)
        expected = {
            "incident_count",
            "severity_score",
            "open_ri_count",
            "control_gap_exposure",
            "total_risk_score",
        }
        assert expected.issubset(set(result.columns))

    def test_sorted_descending_by_total_risk_score(
        self, minimal_incidents, minimal_ris, minimal_mappings
    ):
        result = compute_team_risk(minimal_incidents, minimal_ris, minimal_mappings)
        scores = list(result["total_risk_score"])
        assert scores == sorted(scores, reverse=True)

    def test_incident_count_per_team(
        self, minimal_incidents, minimal_ris, minimal_mappings
    ):
        result = compute_team_risk(minimal_incidents, minimal_ris, minimal_mappings)
        # TeamA has INC-001 and INC-003 → 2 incidents
        assert result.loc["TeamA", "incident_count"] == 2
        # TeamB has INC-002 → 1 incident
        assert result.loc["TeamB", "incident_count"] == 1

    def test_severity_score_per_team(
        self, minimal_incidents, minimal_ris, minimal_mappings
    ):
        result = compute_team_risk(minimal_incidents, minimal_ris, minimal_mappings)
        # TeamA: INC-001(P1=4) + INC-003(P3=2) → 6
        assert result.loc["TeamA", "severity_score"] == 6
        # TeamB: INC-002(P2=3) → 3
        assert result.loc["TeamB", "severity_score"] == 3

    def test_open_ri_count_excludes_closed(
        self, minimal_incidents, minimal_ris, minimal_mappings
    ):
        result = compute_team_risk(minimal_incidents, minimal_ris, minimal_mappings)
        # TeamA RIs: RI-001(Open), RI-002(Closed), RI-004(Closed) → 1 open
        assert result.loc["TeamA", "open_ri_count"] == 1
        # TeamB RIs: RI-003(Open) → 1 open
        assert result.loc["TeamB", "open_ri_count"] == 1

    def test_control_gap_exposure_unmapped_ris(
        self, minimal_incidents, minimal_ris, minimal_mappings
    ):
        result = compute_team_risk(minimal_incidents, minimal_ris, minimal_mappings)
        # Mapped: RI-001, RI-003. Unmapped: RI-002, RI-004
        # TeamA: RI-002 unmapped → 1 gap; RI-004 also unmapped but Closed still counts
        # RI-002 is linked to INC-001 (TeamA), RI-004 is linked to INC-003 (TeamA)
        assert result.loc["TeamA", "control_gap_exposure"] == 2
        # TeamB: RI-003 has a mapping, so 0 gaps
        assert result.loc["TeamB", "control_gap_exposure"] == 0

    def test_total_risk_score_formula(
        self, minimal_incidents, minimal_ris, minimal_mappings
    ):
        result = compute_team_risk(minimal_incidents, minimal_ris, minimal_mappings)
        for team in result.index:
            row = result.loc[team]
            expected = (
                row["incident_count"] * RISK_WEIGHTS["incident_count"]
                + row["severity_score"] * RISK_WEIGHTS["severity_score"]
                + row["open_ri_count"] * RISK_WEIGHTS["open_ri_count"]
                + row["control_gap_exposure"] * RISK_WEIGHTS["control_gap_exposure"]
            )
            assert row["total_risk_score"] == expected

    def test_no_zero_fill_for_missing_teams(self):
        """A team with incidents but no RIs should still appear with 0 for RI metrics."""
        incidents = pd.DataFrame(
            {
                "incident_id": ["INC-001"],
                "severity": ["P1"],
                "team": ["Lonely"],
            }
        )
        ris = pd.DataFrame(columns=["ri_id", "incident_id", "status"])
        mappings = pd.DataFrame(columns=["control_id", "ri_id"])
        result = compute_team_risk(incidents, ris, mappings)
        assert "Lonely" in result.index
        assert result.loc["Lonely", "open_ri_count"] == 0
        assert result.loc["Lonely", "control_gap_exposure"] == 0

    def test_all_ris_closed_open_count_is_zero(self):
        incidents = pd.DataFrame(
            {"incident_id": ["INC-001"], "severity": ["P2"], "team": ["Alpha"]}
        )
        ris = pd.DataFrame(
            {
                "ri_id": ["RI-001", "RI-002"],
                "incident_id": ["INC-001", "INC-001"],
                "status": ["Closed", "Closed"],
            }
        )
        mappings = pd.DataFrame(columns=["control_id", "ri_id"])
        result = compute_team_risk(incidents, ris, mappings)
        assert result.loc["Alpha", "open_ri_count"] == 0

    def test_all_ris_mapped_gap_is_zero(self):
        incidents = pd.DataFrame(
            {"incident_id": ["INC-001"], "severity": ["P3"], "team": ["Beta"]}
        )
        ris = pd.DataFrame(
            {
                "ri_id": ["RI-001"],
                "incident_id": ["INC-001"],
                "status": ["Open"],
            }
        )
        mappings = pd.DataFrame({"control_id": ["CTL-001"], "ri_id": ["RI-001"]})
        result = compute_team_risk(incidents, ris, mappings)
        assert result.loc["Beta", "control_gap_exposure"] == 0

    def test_multiple_teams_ranked_correctly(self):
        """Team with higher weighted metrics should appear first."""
        incidents = pd.DataFrame(
            {
                "incident_id": ["INC-001", "INC-002"],
                "severity": ["P1", "P4"],
                "team": ["High", "Low"],
            }
        )
        ris = pd.DataFrame(
            {
                "ri_id": ["RI-001", "RI-002"],
                "incident_id": ["INC-001", "INC-002"],
                "status": ["Open", "Closed"],
            }
        )
        mappings = pd.DataFrame(columns=["control_id", "ri_id"])
        result = compute_team_risk(incidents, ris, mappings)
        assert result.index[0] == "High"


# ---------------------------------------------------------------------------
# save_processed
# ---------------------------------------------------------------------------


class TestSaveProcessed:
    def test_returns_correct_path(self, tmp_path):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        returned = save_processed(df, "output.csv", processed_dir=str(tmp_path))
        expected = os.path.join(str(tmp_path), "output.csv")
        assert returned == expected

    def test_file_is_created(self, tmp_path):
        df = pd.DataFrame({"x": [10]})
        path = save_processed(df, "test.csv", processed_dir=str(tmp_path))
        assert os.path.isfile(path)

    def test_creates_directory_if_missing(self, tmp_path):
        new_dir = str(tmp_path / "nested" / "output")
        df = pd.DataFrame({"v": [1]})
        path = save_processed(df, "data.csv", processed_dir=new_dir)
        assert os.path.isfile(path)

    def test_saved_csv_is_readable(self, tmp_path):
        df = pd.DataFrame({"col": [42, 99]})
        path = save_processed(df, "readable.csv", processed_dir=str(tmp_path))
        loaded = pd.read_csv(path, index_col=0)
        assert list(loaded["col"]) == [42, 99]

    def test_index_is_written(self, tmp_path):
        df = pd.DataFrame({"v": [1]}, index=["row0"])
        path = save_processed(df, "idx.csv", processed_dir=str(tmp_path))
        loaded = pd.read_csv(path, index_col=0)
        assert loaded.index[0] == "row0"

    def test_overwrites_existing_file(self, tmp_path):
        df1 = pd.DataFrame({"a": [1]})
        df2 = pd.DataFrame({"a": [99]})
        path = save_processed(df1, "overwrite.csv", processed_dir=str(tmp_path))
        save_processed(df2, "overwrite.csv", processed_dir=str(tmp_path))
        loaded = pd.read_csv(path, index_col=0)
        assert loaded["a"].iloc[0] == 99


# ---------------------------------------------------------------------------
# load_data
# ---------------------------------------------------------------------------


class TestLoadData:
    def test_returns_dict_with_four_keys(self, raw_csv_dir):
        data = load_data(raw_csv_dir)
        assert set(data.keys()) == {"incidents", "ris", "controls", "mappings"}

    def test_each_value_is_dataframe(self, raw_csv_dir):
        data = load_data(raw_csv_dir)
        for key, df in data.items():
            assert isinstance(df, pd.DataFrame), f"{key} is not a DataFrame"

    def test_incident_date_columns_are_datetime(self, raw_csv_dir):
        data = load_data(raw_csv_dir)
        df = data["incidents"]
        assert pd.api.types.is_datetime64_any_dtype(df["date_raised"])
        assert pd.api.types.is_datetime64_any_dtype(df["date_closed"])

    def test_ri_date_column_is_datetime(self, raw_csv_dir):
        data = load_data(raw_csv_dir)
        df = data["ris"]
        assert pd.api.types.is_datetime64_any_dtype(df["due_date"])

    def test_empty_date_becomes_nat(self, raw_csv_dir):
        data = load_data(raw_csv_dir)
        df = data["incidents"]
        # Row 0 has date_closed = "" → should be NaT
        assert pd.isna(df["date_closed"].iloc[0])

    def test_id_columns_loaded_as_strings(self, raw_csv_dir):
        # pandas ≥2.0 may return StringDtype rather than plain object for dtype=str,
        # so check that values are str instances rather than comparing dtype directly.
        data = load_data(raw_csv_dir)
        for col_df, col_name in [
            (data["incidents"], "incident_id"),
            (data["ris"], "ri_id"),
            (data["controls"], "control_id"),
            (data["mappings"], "ri_id"),
        ]:
            assert isinstance(col_df[col_name].iloc[0], str), (
                f"{col_name} values should be str, got {type(col_df[col_name].iloc[0])}"
            )

    def test_missing_file_raises_error(self, tmp_path):
        # Only create incidents.csv; others are missing
        pd.DataFrame({"incident_id": ["X"]}).to_csv(
            tmp_path / "incidents.csv", index=False
        )
        with pytest.raises(FileNotFoundError):
            load_data(str(tmp_path))

    def test_correct_row_counts(self, raw_csv_dir):
        data = load_data(raw_csv_dir)
        assert len(data["incidents"]) == 2
        assert len(data["ris"]) == 1
        assert len(data["controls"]) == 1
        assert len(data["mappings"]) == 1
