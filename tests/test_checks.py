"""Unit tests for each individual check, with planted problems."""

import numpy as np
import pandas as pd

from mlclean import audit


def issues_for(report, check):
    return [i for i in report.issues if i.check == check]


def test_constant_and_quasi_constant():
    df = pd.DataFrame(
        {
            "const": 1,
            "quasi": [0] * 199 + [1],
            "ok": np.arange(200) % 7,
        }
    )
    report = audit(df)
    assert issues_for(report, "constant_column")[0].columns == ["const"]
    assert issues_for(report, "quasi_constant_column")[0].columns == ["quasi"]
    for issue in report.issues:
        assert "ok" not in issue.columns


def test_id_column_detection():
    n = 100
    df = pd.DataFrame(
        {
            "customer_id": [f"C{i}" for i in range(n)],
            "row_num": np.arange(n),
            "measurement": np.random.default_rng(0).normal(size=n),
        }
    )
    report = audit(df)
    flagged = {c for i in issues_for(report, "id_column") for c in i.columns}
    assert "customer_id" in flagged
    assert "row_num" in flagged
    # a continuous float that happens to be all-unique is not an identifier
    assert "measurement" not in flagged


def test_id_check_skips_tiny_frames():
    df = pd.DataFrame({"id": ["a", "b", "c"]})
    assert issues_for(audit(df), "id_column") == []


def test_mixed_types_and_numeric_as_text():
    df = pd.DataFrame(
        {
            "mixed": ["a", 1, "b", 2.5] * 25,
            "numbers_as_text": [str(i) for i in range(100)],
        }
    )
    report = audit(df)
    assert issues_for(report, "mixed_types")[0].columns == ["mixed"]
    as_text = issues_for(report, "numeric_stored_as_text")[0]
    assert as_text.columns == ["numbers_as_text"]
    assert as_text.details["parse_rate"] == 1.0


def test_telco_style_numeric_with_blanks():
    # TotalCharges in the Telco churn set: numeric column with a few
    # blank strings, read by pandas as object
    values = [str(round(v, 2)) for v in np.linspace(10, 900, 97)] + [" "] * 3
    df = pd.DataFrame({"TotalCharges": values})
    report = audit(df)
    found = issues_for(report, "numeric_stored_as_text")
    assert found and found[0].severity == "medium"


def test_whitespace_and_case_issues():
    df = pd.DataFrame(
        {
            "plan": ["yes", " yes", "no", "No"] * 25,
        }
    )
    report = audit(df)
    assert issues_for(report, "whitespace_padding")
    assert issues_for(report, "case_inconsistency")


def test_high_cardinality():
    cities = [f"city_{i}" for i in range(150)] * 2
    df = pd.DataFrame({"city": cities, "x": np.arange(300)})
    report = audit(df)
    assert issues_for(report, "high_cardinality")[0].columns == ["city"]


def test_outliers_and_skew():
    rng = np.random.default_rng(2)
    df = pd.DataFrame(
        {
            "normal": rng.normal(100, 5, 500),
            "skewed": rng.lognormal(0, 2, 500),
        }
    )
    df.loc[0, "normal"] = 10_000
    report = audit(df)
    out_cols = {c for i in issues_for(report, "outliers") for c in i.columns}
    assert "normal" in out_cols
    skew_cols = {c for i in issues_for(report, "skewed_feature") for c in i.columns}
    assert "skewed" in skew_cols


def test_single_class_target():
    df = pd.DataFrame({"x": np.arange(100), "y": 1})
    report = audit(df, target="y", task="classification")
    assert issues_for(report, "single_class_target")


def test_rare_classes():
    labels = ["a"] * 100 + ["b"] * 100 + ["c"] * 3
    df = pd.DataFrame({"x": np.arange(203), "y": labels})
    report = audit(df, target="y")
    rare = issues_for(report, "rare_classes")[0]
    assert rare.details["rare_classes"] == {"c": 3}


def test_missing_severity_tiers():
    n = 1000
    df = pd.DataFrame(
        {
            "barely": np.ones(n),
            "moderate": np.ones(n),
            "mostly": np.ones(n),
            "y": np.arange(n) % 2,
        }
    )
    df.loc[: n * 0.01, "barely"] = np.nan
    df.loc[: n * 0.2, "moderate"] = np.nan
    df.loc[: n * 0.8, "mostly"] = np.nan
    report = audit(df, target="y")
    by_col = {i.columns[0]: i for i in issues_for(report, "missing_values")}
    assert by_col["barely"].severity == "info"
    assert by_col["moderate"].severity == "medium"
    assert by_col["mostly"].severity == "high"


def test_missing_target_flagged_high():
    df = pd.DataFrame({"x": np.arange(100), "y": [np.nan] * 10 + list(range(90))})
    report = audit(df, target="y")
    issue = issues_for(report, "missing_target")[0]
    assert issue.severity == "high"
    assert issue.details["missing"] == 10


def test_duplicates_hiding_behind_ids():
    base = pd.DataFrame(
        {
            "id": range(50),
            "a": [1, 2, 3, 4, 5] * 10,
            "b": list("vwxyz") * 10,
        }
    )
    # same observations re-ingested under new ids
    double = pd.concat([base, base.assign(id=range(50, 100))], ignore_index=True)
    report = audit(double, id_columns=["id"])
    assert issues_for(report, "duplicate_rows_ignoring_ids")


def test_leakage_via_pearson_for_regression():
    rng = np.random.default_rng(4)
    y = rng.normal(size=300)
    df = pd.DataFrame(
        {
            "leak": y * 2 + rng.normal(scale=0.01, size=300),
            "honest": rng.normal(size=300),
            "y": y,
        }
    )
    report = audit(df, target="y")
    assert report.context.task == "regression"
    leak = issues_for(report, "target_leakage")[0]
    assert leak.columns == ["leak"]
    assert "Pearson" in leak.details["measure"]


def test_near_unique_feature_not_called_leakage():
    n = 200
    df = pd.DataFrame(
        {
            "almost_id": [f"v{i}" for i in range(n - 2)] + ["v0", "v1"],
            "y": np.arange(n) % 2,
        }
    )
    report = audit(df, target="y")
    assert issues_for(report, "target_leakage") == []


def test_empty_frame_is_handled():
    report = audit(pd.DataFrame())
    assert report.issues == []
    assert "No issues found" in report.to_text()


def test_ignore_columns_are_skipped():
    df = pd.DataFrame({"noisy": [1] * 100, "x": np.arange(100)})
    report = audit(df, ignore_columns=["noisy"])
    assert all("noisy" not in i.columns for i in report.issues)
