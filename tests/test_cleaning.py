import importlib

import numpy as np
import pandas as pd

from mlclean import CleaningPipeline, MLCleaner, audit


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


def _nullable_bool_df():
    rng = np.random.default_rng(3)
    n = 400
    df = pd.DataFrame(
        {
            "verified": pd.array(rng.choice([True, False], n), dtype="boolean"),
            "amount": rng.random(n) * 100,
            "label": rng.choice([0, 1], n, p=[0.8, 0.2]),
        }
    )
    df.loc[df.index[:40], "verified"] = pd.NA
    return df


def test_nullable_boolean_column_imputed_with_mode_not_median():
    df = _nullable_bool_df()
    expected_mode = bool(df["verified"].mode(dropna=True).iloc[0])

    for strategy in ("balanced", "aggressive"):
        report = audit(df, target="label")
        clean_df, pipeline = report.clean(strategy=strategy)

        assert pipeline.errors == []
        assert clean_df["verified"].isna().sum() == 0
        assert clean_df["verified"].dtype == pd.BooleanDtype()
        mode_steps = [
            s for s in pipeline.steps if s.step == "impute" and "verified" in s.columns
        ]
        assert len(mode_steps) == 1
        assert mode_steps[0].params["method"] == "mode"
        assert mode_steps[0].params["values"]["verified"] is expected_mode


def test_nullable_boolean_pipeline_json_round_trip(tmp_path):
    df = _nullable_bool_df()
    report = audit(df, target="label")
    clean_df, pipeline = report.clean(strategy="balanced")

    path = tmp_path / "bool_steps.json"
    pipeline.to_json(path)
    reloaded = CleaningPipeline.from_json(path)
    replayed = reloaded.apply(df)

    pd.testing.assert_frame_equal(replayed, clean_df)
    assert replayed["verified"].dtype == pd.BooleanDtype()
    assert reloaded.errors == []


def test_mlcleaner_fit_transform_with_nullable_boolean():
    n = 100
    train = pd.DataFrame(
        {
            "verified": pd.array([False] * 70 + [True] * 20 + [pd.NA] * 10, dtype="boolean"),
            "amount": np.linspace(0.0, 99.0, n),
        }
    )
    y_train = np.array([0, 1] * (n // 2))
    test = pd.DataFrame(
        {
            "verified": pd.array([True] * 20 + [False] * 5 + [pd.NA] * 5, dtype="boolean"),
            "amount": np.linspace(1.0, 30.0, 30),
        }
    )

    cleaner = MLCleaner(strategy="balanced")
    train_clean = cleaner.fit_transform(train, y_train)
    test_clean = cleaner.transform(test)

    assert cleaner.pipeline_.errors == []
    assert train_clean["verified"].isna().sum() == 0
    assert train_clean["verified"].dtype == pd.BooleanDtype()
    assert test_clean["verified"].isna().sum() == 0
    assert test_clean["verified"].dtype == pd.BooleanDtype()
    # Train mode is False; test NAs must receive False rather than test mode True
    assert test_clean.loc[test["verified"].isna(), "verified"].eq(False).all()


def test_apply_crash_guard_records_error_and_continues(monkeypatch):
    cleaning_mod = importlib.import_module("mlclean.cleaning")
    df = make_df()
    report = audit(df, target="churn")
    _clean_df, pipeline = report.clean(strategy="safe")

    def boom(_df, _step):
        raise RuntimeError("synthetic step failure")

    patched = dict(cleaning_mod._APPLIERS)
    patched["strip_whitespace"] = boom
    monkeypatch.setattr(cleaning_mod, "_APPLIERS", patched)

    result = pipeline.apply(df)

    # Failing step is recorded and does not abort later steps
    assert len(pipeline.errors) == 1
    assert pipeline.errors[0]["step"] == "strip_whitespace"
    assert pipeline.errors[0]["error_type"] == "RuntimeError"
    assert "synthetic step failure" in pipeline.errors[0]["error"]
    assert "constant" not in result.columns
    assert not result.duplicated().any()

    # Re-applying with healthy appliers clears stale errors
    monkeypatch.undo()
    healthy = pipeline.apply(df)
    assert pipeline.errors == []
    assert not healthy["plan"].str.startswith(" ").any()
