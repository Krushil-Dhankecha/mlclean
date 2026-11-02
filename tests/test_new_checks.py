import numpy as np
import pandas as pd
import pytest

from mlclean import audit


def issues_for(report, check):
    return [i for i in report.issues if i.check == check]


# ---------------------------------------------------------- disguised_missing
def test_numeric_sentinel_detected():
    rng = np.random.default_rng(0)
    age = rng.normal(40, 8, 500).round()
    age[:25] = -999  # classic "missing" code, 5% of rows
    report = audit(pd.DataFrame({"age": age}))
    found = issues_for(report, "disguised_missing")
    assert found and found[0].columns == ["age"]
    assert "-999" in found[0].details["values"]


def test_plausible_extreme_is_not_a_sentinel():
    rng = np.random.default_rng(1)
    age = rng.integers(18, 95, 500).astype(float)  # 94-year-olds are real
    report = audit(pd.DataFrame({"age": age}))
    assert issues_for(report, "disguised_missing") == []


def test_small_code_sets_are_ignored():
    df = pd.DataFrame({"flag": [-1, 0, 1] * 100})
    report = audit(df)
    assert issues_for(report, "disguised_missing") == []


def test_text_sentinels_detected():
    city = ["surat", "mumbai", "unknown", "n/a"] * 50
    report = audit(pd.DataFrame({"city": city}))
    found = issues_for(report, "disguised_missing")
    assert found
    assert set(found[0].details["tokens"]) == {"unknown", "n/a"}


# --------------------------------------------------- informative_missingness
def test_missingness_that_tracks_the_target():
    rng = np.random.default_rng(2)
    n = 1000
    churn = rng.integers(0, 2, n)
    income = rng.normal(50_000, 10_000, n)
    income[(churn == 1) & (rng.random(n) < 0.6)] = np.nan  # churners hide income
    df = pd.DataFrame({"income": income, "churn": churn})
    report = audit(df, target="churn")
    found = issues_for(report, "informative_missingness")
    assert found and found[0].columns == ["income"]
    assert found[0].details["tvd"] >= 0.2


def test_random_missingness_is_not_flagged():
    rng = np.random.default_rng(3)
    n = 1000
    income = rng.normal(50_000, 10_000, n)
    income[rng.random(n) < 0.3] = np.nan
    df = pd.DataFrame({"income": income, "churn": rng.integers(0, 2, n)})
    report = audit(df, target="churn")
    assert issues_for(report, "informative_missingness") == []


def test_regression_target_mean_shift():
    rng = np.random.default_rng(4)
    n = 600
    price = rng.normal(100, 20, n)
    sqft = rng.normal(900, 100, n)
    sqft[price > 115] = np.nan  # expensive homes miss the measurement
    df = pd.DataFrame({"sqft": sqft, "price": price})
    report = audit(df, target="price")
    found = issues_for(report, "informative_missingness")
    assert found and "standardized_mean_difference" in found[0].details


# ------------------------------------------------------------ check selection
def test_skip_removes_a_check():
    df = pd.DataFrame({"x": [1.0] * 100})
    assert issues_for(audit(df), "constant_column")
    assert issues_for(audit(df, skip=["constant"]), "constant_column") == []


def test_checks_runs_only_the_named_ones():
    df = pd.DataFrame({"x": [1.0] * 100, "padded": [" yes", "no"] * 50})
    report = audit(df, checks=["text"])
    assert {i.check for i in report.issues} <= {"whitespace_padding", "case_inconsistency"}


def test_unknown_check_name_raises():
    with pytest.raises(ValueError, match="unknown check name"):
        audit(pd.DataFrame({"x": [1]}), skip=["nope"])


# -------------------------------------------------------------- crash guard
def test_failing_check_becomes_a_finding(monkeypatch):
    import importlib

    audit_module = importlib.import_module("mlclean.audit")

    def boom(df, ctx):
        raise RuntimeError("synthetic failure")

    patched = dict(audit_module.CHECKS)
    patched["missing"] = boom
    monkeypatch.setattr(audit_module, "CHECKS", patched)

    df = pd.DataFrame({"x": [1.0] * 100, "const": 1})
    report = audit_module.audit(df)
    errors = issues_for(report, "check_error")
    assert errors and errors[0].details["check"] == "missing"
    assert "synthetic failure" in errors[0].message
    # the other checks still ran
    assert issues_for(report, "constant_column")
