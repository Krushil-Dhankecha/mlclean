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


def partly_labelled_df():
    """60 rows whose target is missing for four scattered customers.

    Scattered, not trailing: if every dropped row sits at the end of the
    frame a fresh RangeIndex happens to line up with the survivors, which
    is how index renumbering stays invisible.
    """
    rng = np.random.default_rng(11)
    n = 60
    df = pd.DataFrame(
        {
            # distinct ages, so no row duplicates another and this fixture
            # exercises drop_unlabeled_rows on its own
            "age": (rng.random(n) * 60 + 18).round(2),
            "plan": rng.choice(["basic", "pro"], n),
            "churn": rng.integers(0, 2, n).astype(float),
        }
    )
    df.loc[[5, 17, 33, 48], "churn"] = np.nan
    assert not df.duplicated().any()
    return df


def interleaved_duplicates_df():
    """53 rows with three exact duplicates sitting next to their originals."""
    rng = np.random.default_rng(12)
    rows = []
    for i in range(50):
        rows.append(
            {
                "age": float(rng.integers(18, 80)),
                "plan": "basic" if i % 2 else "pro",
                "churn": float(i % 2),
            }
        )
        if i in (7, 19, 31):
            rows.append(dict(rows[-1]))
    return pd.DataFrame(rows)


def test_clean_preserves_surviving_index_when_rows_dropped():
    df = partly_labelled_df()
    clean_df, pipeline = audit(df, target="churn").clean(strategy="balanced")

    steps = {s.step for s in pipeline.steps}
    assert "drop_unlabeled_rows" in steps and "remove_duplicates" not in steps
    expected = df.index[df["churn"].notna()]
    pd.testing.assert_index_equal(clean_df.index, expected, exact=True)
    # the renumbered index would be 0..55, which is the bug this guards
    assert not clean_df.index.equals(pd.RangeIndex(len(clean_df)))


def test_clean_preserves_index_when_duplicates_removed():
    df = interleaved_duplicates_df()
    clean_df, pipeline = audit(df, target="churn").clean(strategy="balanced")

    steps = {s.step for s in pipeline.steps}
    assert "remove_duplicates" in steps and "drop_unlabeled_rows" not in steps
    expected = df.index[~df.duplicated()]
    pd.testing.assert_index_equal(clean_df.index, expected, exact=True)
    assert not clean_df.index.equals(pd.RangeIndex(len(clean_df)))


def test_series_held_outside_the_frame_remaps_after_clean():
    """The id column mlclean tells you to exclude is the motivating case."""
    df = partly_labelled_df()
    ids = pd.Series([f"C{i:04d}" for i in range(len(df))], index=df.index)

    clean_df, _ = audit(df, target="churn").clean(strategy="balanced")

    remapped = ids.loc[clean_df.index]
    expected = ids[df["churn"].notna()]
    pd.testing.assert_series_equal(remapped, expected)
    # and a target held aside lines up with the one inside the frame
    y = df["churn"].loc[clean_df.index]
    np.testing.assert_array_equal(y.to_numpy(), clean_df["churn"].to_numpy())


def test_apply_without_row_steps_keeps_every_row_and_the_index():
    """The transformer path: no row step runs, so the caller's index stands."""
    df = interleaved_duplicates_df()
    _, pipeline = audit(df, target="churn").clean(strategy="balanced")

    out = pipeline.apply(df, include_row_steps=False)
    pd.testing.assert_index_equal(out.index, df.index, exact=True)
    assert len(out) == len(df)
