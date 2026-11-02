import numpy as np
import pandas as pd
import pytest

from mlclean import audit


@pytest.fixture
def churn_df():
    rng = np.random.default_rng(0)
    n = 400
    churn = rng.integers(0, 2, n)
    df = pd.DataFrame(
        {
            "customer_id": [f"C{i:05d}" for i in range(n)],
            "age": rng.integers(18, 80, n).astype(float),
            "plan": rng.choice(["basic", "pro", "Basic ", "enterprise"], n),
            "spend": rng.gamma(2.0, 50.0, n),
            "constant": 1,
            "cancellation_flag": churn,  # perfect leak
            "churn": churn,
        }
    )
    df.loc[rng.choice(n, 30, replace=False), "age"] = np.nan
    return pd.concat([df, df.iloc[:5]], ignore_index=True)  # 5 duplicate rows


def checks_found(report):
    return {issue.check for issue in report.issues}


def test_audit_finds_the_planted_issues(churn_df):
    report = audit(churn_df, target="churn")

    found = checks_found(report)
    assert "missing_values" in found
    assert "duplicate_rows" in found
    assert "constant_column" in found
    assert "id_column" in found
    assert "target_leakage" in found
    assert "whitespace_padding" in found

    leak = next(i for i in report.issues if i.check == "target_leakage")
    assert leak.columns == ["cancellation_flag"]
    assert leak.severity == "critical"


def test_task_is_inferred_as_classification(churn_df):
    report = audit(churn_df, target="churn")
    assert report.context.task == "classification"


def test_unknown_target_raises(churn_df):
    with pytest.raises(ValueError, match="not in the DataFrame"):
        audit(churn_df, target="nope")


def test_clean_audit_has_no_issues():
    rng = np.random.default_rng(5)
    df = pd.DataFrame(
        {
            "a": rng.normal(size=100),
            "b": list("abcd") * 25,
            "y": rng.integers(0, 2, 100),
        }
    )
    report = audit(df, target="y")
    assert report.issues == []


def test_report_renders_every_format(churn_df, tmp_path):
    report = audit(churn_df, target="churn")

    text = report.to_text()
    assert "mlclean audit report" in text
    assert "CRITICAL" in text

    md = report.to_markdown(tmp_path / "report.md")
    assert "| Severity |" in md
    assert (tmp_path / "report.md").exists()

    report.to_json(tmp_path / "report.json")
    assert (tmp_path / "report.json").exists()


def test_imbalance_flagged_for_rare_positive_class():
    df = pd.DataFrame(
        {
            "x": np.random.default_rng(1).normal(size=300),
            "y": [1] * 12 + [0] * 288,
        }
    )
    report = audit(df, target="y")
    assert "class_imbalance" in checks_found(report)
