import numpy as np
import pandas as pd

from mlclean import CleaningPipeline, audit


def make_df():
    rng = np.random.default_rng(3)
    n = 200
    churn = rng.integers(0, 2, n)
    df = pd.DataFrame(
        {
            "customer_id": [f"C{i}" for i in range(n)],
            "age": rng.integers(18, 80, n).astype(float),
            "plan": rng.choice(["basic", " pro", "pro"], n),
            "constant": "x",
            "leak": churn,
            "churn": churn,
        }
    )
    df.loc[:9, "age"] = np.nan
    return pd.concat([df, df.iloc[:3]], ignore_index=True)


def test_safe_clean_is_conservative():
    df = make_df()
    report = audit(df, target="churn")
    clean_df, pipeline = report.clean(strategy="safe")

    # duplicates removed, constant dropped, whitespace stripped
    assert not clean_df.duplicated().any()
    assert "constant" not in clean_df.columns
    assert not clean_df["plan"].str.startswith(" ").any()
    # safe mode never drops ids, leaks, or imputes
    assert "customer_id" in clean_df.columns
    assert "leak" in clean_df.columns
    assert clean_df["age"].isna().any()
    # original frame untouched
    assert df.duplicated().any()

    steps = {s.step for s in pipeline.steps}
    assert steps == {"remove_duplicates", "drop_columns", "strip_whitespace"}


def test_balanced_clean_drops_ids_and_leaks_and_imputes():
    df = make_df()
    report = audit(df, target="churn")
    clean_df, _pipeline = report.clean(strategy="balanced")

    assert "customer_id" not in clean_df.columns
    assert "leak" not in clean_df.columns
    assert not clean_df["age"].isna().any()
    assert "age_missing" in clean_df.columns
    assert clean_df["age_missing"].sum() > 0


def test_pipeline_round_trips_through_json(tmp_path):
    df = make_df()
    report = audit(df, target="churn")
    clean_df, pipeline = report.clean(strategy="balanced")

    path = tmp_path / "steps.json"
    pipeline.to_json(path)
    replayed = CleaningPipeline.from_json(path).apply(df)

    pd.testing.assert_frame_equal(replayed, clean_df)


def test_audit_only_changes_nothing():
    df = make_df()
    report = audit(df, target="churn")
    clean_df, pipeline = report.clean(strategy="audit_only")

    pd.testing.assert_frame_equal(clean_df, df)
    assert pipeline.steps == []
