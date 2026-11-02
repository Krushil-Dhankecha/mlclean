import json

import numpy as np
import pandas as pd
import pytest

from mlclean import CleaningPipeline, MLCleaner, audit


def train_test_frames():
    rng = np.random.default_rng(11)
    n = 200
    churn = rng.integers(0, 2, n)
    train = pd.DataFrame(
        {
            "customer_id": [f"C{i}" for i in range(n)],
            "age": rng.normal(40, 5, n).round(),
            "plan": rng.choice(["basic", "pro"], n),
            "leak": churn,
        }
    )
    train.loc[:19, "age"] = np.nan
    test = pd.DataFrame(
        {
            "customer_id": [f"T{i}" for i in range(50)],
            "age": rng.normal(10, 2, 50).round(),  # very different distribution
            "plan": ["basic"] * 50,
            "leak": rng.integers(0, 2, 50),
        }
    )
    test.loc[:9, "age"] = np.nan
    return train, pd.Series(churn, name="churn"), test


def test_transform_replays_training_decisions():
    train, y, test = train_test_frames()
    cleaner = MLCleaner(strategy="balanced")
    train_clean = cleaner.fit_transform(train, y)
    test_clean = cleaner.transform(test)

    # same columns dropped on both sides
    assert "customer_id" not in train_clean.columns
    assert "leak" not in train_clean.columns
    assert list(test_clean.columns) == list(train_clean.columns)


def test_imputation_uses_train_statistics_not_test():
    train, y, test = train_test_frames()
    cleaner = MLCleaner(strategy="balanced")
    cleaner.fit(train, y)
    test_clean = cleaner.transform(test)

    train_median = train["age"].median()
    test_median = test["age"].median()
    filled = test_clean.loc[test["age"].isna(), "age"]
    assert (filled == train_median).all()
    assert train_median != test_median  # the test would be vacuous otherwise


def test_transform_never_drops_rows():
    train, y, _ = train_test_frames()
    with_dupes = pd.concat([train, train.iloc[:10]], ignore_index=True)
    cleaner = MLCleaner(strategy="safe")
    cleaner.fit(train, y)
    assert len(cleaner.transform(with_dupes)) == len(with_dupes)


def test_unfitted_transform_raises():
    with pytest.raises(RuntimeError, match="not fitted"):
        MLCleaner().transform(pd.DataFrame({"a": [1]}))


def test_params_round_trip_like_sklearn_clone():
    cleaner = MLCleaner(strategy="safe", id_columns=["id"])
    clone = MLCleaner(**cleaner.get_params())
    assert clone.get_params() == cleaner.get_params()
    clone.set_params(strategy="aggressive")
    assert clone.strategy == "aggressive"
    with pytest.raises(ValueError, match="unknown parameter"):
        clone.set_params(nope=1)


def test_target_as_named_column_still_works():
    train, y, _ = train_test_frames()
    frame = train.assign(churn=y.to_numpy())
    cleaner = MLCleaner(strategy="balanced", target="churn")
    cleaned = cleaner.fit_transform(frame)
    assert "leak" not in cleaned.columns
    assert "churn" in cleaned.columns  # the target itself is never cleaned away


def test_learned_values_survive_json_round_trip(tmp_path):
    train, y, test = train_test_frames()
    cleaner = MLCleaner(strategy="balanced")
    cleaner.fit(train, y)

    path = tmp_path / "steps.json"
    cleaner.pipeline_.to_json(path)
    payload = json.loads(path.read_text())
    impute = next(s for s in payload["steps"] if s["step"] == "impute")
    assert impute["params"]["values"]["age"] == train["age"].median()

    replayed = CleaningPipeline.from_json(path).apply(test, include_row_steps=False)
    pd.testing.assert_frame_equal(replayed, cleaner.transform(test))


def test_old_pipelines_without_learned_values_still_apply():
    legacy = CleaningPipeline.from_json(
        json.dumps(
            {
                "version": "0.1.0",
                "steps": [
                    {
                        "step": "impute",
                        "reason": "missing_values",
                        "columns": ["age"],
                        "params": {"method": "median", "indicator": True},
                    }
                ],
            }
        )
    )
    df = pd.DataFrame({"age": [10.0, np.nan, 30.0]})
    out = legacy.apply(df)
    assert out["age"].tolist() == [10.0, 20.0, 30.0]
    assert out["age_missing"].tolist() == [0, 1, 0]


def test_report_clean_still_learns_from_its_own_frame():
    # the single-frame path: fill values come from the frame being cleaned
    df = pd.DataFrame(
        {
            "age": [20.0, np.nan, 40.0] * 40,
            "y": [0, 1] * 60,
        }
    )
    clean_df, pipeline = audit(df, target="y").clean(strategy="balanced")
    assert not clean_df["age"].isna().any()
    impute = next(s for s in pipeline.steps if s.step == "impute")
    assert impute.params["values"]["age"] == 30.0
