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


# --- #21: the column contract --------------------------------------------


def test_transform_restores_training_column_order():
    train, y, test = train_test_frames()
    cleaner = MLCleaner(strategy="balanced")
    fitted = cleaner.fit_transform(train, y)

    scrambled = test[list(reversed(test.columns))]
    out = cleaner.transform(scrambled)
    assert list(out.columns) == list(fitted.columns)


def test_transform_raises_on_missing_column():
    train, y, test = train_test_frames()
    cleaner = MLCleaner(strategy="balanced")
    cleaner.fit(train, y)

    assert "age" in cleaner.required_columns_
    with pytest.raises(ValueError, match="'age'"):
        cleaner.transform(test.drop(columns=["age"]))


def test_transform_drops_unknown_columns():
    train, y, test = train_test_frames()
    cleaner = MLCleaner(strategy="balanced")
    cleaner.fit(train, y)

    out = cleaner.transform(test.assign(leaked_score=1.0))
    assert "leaked_score" not in out.columns
    assert cleaner.unknown_columns_ == ["leaked_score"]


def test_feature_names_describe_fit_and_output():
    train, y, _ = train_test_frames()
    cleaner = MLCleaner(strategy="balanced")
    assert not hasattr(cleaner, "feature_names_in_")
    with pytest.raises(RuntimeError, match="not fitted"):
        cleaner.get_feature_names_out()

    fitted = cleaner.fit_transform(train, y)
    # sklearn's meaning: what fit was given, not what it produced
    assert cleaner.feature_names_in_ == list(train.columns)
    assert cleaner.n_features_in_ == train.shape[1]
    assert cleaner.feature_names_out_ == list(fitted.columns)
    assert list(cleaner.get_feature_names_out()) == list(fitted.columns)


def test_transform_keeps_the_index_while_reordering_columns():
    train, y, test = train_test_frames()
    cleaner = MLCleaner(strategy="balanced")
    cleaner.fit(train, y)

    odd = test.set_index(pd.RangeIndex(500, 500 + len(test)))
    out = cleaner.transform(odd[list(reversed(odd.columns))])
    assert list(out.index) == list(odd.index)
    assert len(out) == len(odd)


# --- #27: the row contract -----------------------------------------------


def leakage_frame(n=600, seed=3):
    rng = np.random.default_rng(seed)
    churn = rng.integers(0, 2, n)
    X = pd.DataFrame(
        {
            "tenure": rng.integers(1, 60, n),
            "monthly": rng.normal(70, 20, n).round(2),
            "exit_survey_sent": churn,  # only exists because the label does
        }
    )
    return X, pd.Series(churn, name="churn")


def test_fit_aligns_y_by_index():
    X, y = leakage_frame()
    shuffled = y.sample(frac=1, random_state=7)
    assert not shuffled.index.equals(X.index)  # otherwise vacuous

    in_order = MLCleaner(strategy="balanced").fit(X, y)
    reordered = MLCleaner(strategy="balanced").fit(X, shuffled)

    def leakage(cleaner):
        return [
            tuple(i.columns)
            for i in cleaner.report_.issues
            if i.check == "target_leakage"
        ]

    assert leakage(in_order), "the fixture should trip the leakage check"
    assert leakage(reordered) == leakage(in_order)
    assert [s.step for s in reordered.pipeline_.steps] == [
        s.step for s in in_order.pipeline_.steps
    ]


def test_fit_rejects_misaligned_y_index():
    X, y = leakage_frame(n=50)
    disjoint = y.set_axis(pd.RangeIndex(1000, 1000 + len(y)))
    with pytest.raises(ValueError, match="does not cover"):
        MLCleaner().fit(X, disjoint)


def test_fit_accepts_array_y():
    X, y = leakage_frame(n=50)
    fitted = MLCleaner(strategy="balanced").fit(X, y.to_numpy())
    assert hasattr(fitted, "pipeline_")
    with pytest.raises(ValueError):
        MLCleaner().fit(X, y.to_numpy()[:10])


def test_fit_rejects_y_index_that_collapses_onto_one_label():
    # every label on index 0: X's other rows have no label at all
    X, y = leakage_frame(n=20)
    dupes = y.set_axis([0] * len(y))
    with pytest.raises(ValueError, match="does not cover"):
        MLCleaner().fit(X, dupes)


def test_fit_rejects_ambiguous_duplicate_labels():
    # same index *set* as X, but a repeated label, so which row gets which
    # label is not decidable
    X, y = leakage_frame(n=3)
    ambiguous = pd.concat([y, y.iloc[[1]]]).set_axis([0, 1, 2, 1])
    with pytest.raises(ValueError, match="duplicate labels"):
        MLCleaner().fit(X, ambiguous)


def test_fit_accepts_single_column_dataframe_y():
    X, y = leakage_frame(n=80)
    one_col = MLCleaner(strategy="balanced").fit(X, y.to_frame())
    series = MLCleaner(strategy="balanced").fit(X, y)
    assert [i.check for i in one_col.report_.issues] == [
        i.check for i in series.report_.issues
    ]

    with pytest.raises(ValueError, match="2 columns"):
        MLCleaner().fit(X, y.to_frame().assign(second=1))


def test_transform_refuses_to_invent_a_missing_output_column():
    train, y, test = train_test_frames()
    cleaner = MLCleaner(strategy="balanced")
    cleaner.fit(train, y)
    # a schema the pipeline cannot produce: reindexing would fill it with
    # nulls, which is the silent failure this guard exists to prevent
    cleaner.feature_names_out_ = cleaner.feature_names_out_ + ["never_built"]
    with pytest.raises(ValueError, match="could not reproduce"):
        cleaner.transform(test)


@pytest.mark.parametrize("dtype", ["Int64", "Float64", "boolean"])
def test_fit_nullable_y_with_na(dtype):
    X, y = leakage_frame(n=120)
    nullable = y.astype(dtype).copy()
    nullable.iloc[:5] = pd.NA

    fitted = MLCleaner(strategy="balanced").fit(X, nullable)
    checks = {i.check for i in fitted.report_.issues}
    assert "missing_target" in checks
    assert fitted.report_.context.task == "classification"
