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


def telco_shaped_df():
    # TotalCharges as pandas reads it: money kept as text, a handful of the
    # values blank rather than NaN
    n = 200
    charges = [f"{20.5 * (i + 1):.2f}" for i in range(n - 4)] + [" "] * 4
    return pd.DataFrame(
        {
            "total_charges": charges,
            "tenure": list(range(n)),
            "churn": [i % 2 for i in range(n)],
        }
    )


def test_balanced_clean_converts_numeric_text_and_fills_the_blanks():
    df = telco_shaped_df()
    report = audit(df, target="churn")
    clean_df, pipeline = report.clean(strategy="balanced")

    assert pd.api.types.is_numeric_dtype(clean_df["total_charges"])
    assert not clean_df["total_charges"].isna().any()
    # the 4 blanks became NaN, were flagged, then filled with the fit median
    assert clean_df["total_charges_missing"].sum() == 4
    impute = next(s for s in pipeline.steps if s.step == "impute")
    assert impute.params["values"]["total_charges"] == df["total_charges"][
        : len(df) - 4
    ].astype(float).median()
    # conversion is recorded, and runs before the fill
    names = [s.step for s in pipeline.steps]
    assert names.index("to_numeric") < names.index("impute")


def test_safe_clean_converts_only_fully_parseable_text():
    lossless = pd.DataFrame({"amount": [str(i) for i in range(100)]})
    _, pipeline = audit(lossless).clean(strategy="safe")
    assert [s.step for s in pipeline.steps] == ["to_numeric"]

    # with values that don't parse, conversion would introduce NaN, so safe
    # leaves the column alone
    _, pipeline = audit(telco_shaped_df(), target="churn").clean(strategy="safe")
    assert "to_numeric" not in {s.step for s in pipeline.steps}


def test_pipeline_loads_from_json_text():
    df = telco_shaped_df()
    clean_df, pipeline = audit(df, target="churn").clean(strategy="balanced")
    replayed = CleaningPipeline.from_json(pipeline.to_json()).apply(df)
    pd.testing.assert_frame_equal(replayed, clean_df)


def test_audit_only_changes_nothing():
    df = make_df()
    report = audit(df, target="churn")
    clean_df, pipeline = report.clean(strategy="audit_only")

    pd.testing.assert_frame_equal(clean_df, df)
    assert pipeline.steps == []
