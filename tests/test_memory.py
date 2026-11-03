import json

import numpy as np
import pandas as pd
import pytest

from mlclean import audit, dtype_plan, footprint, optimize_dtypes
from mlclean.memory import PLAN_VERSION

ROWS = 200_000


@pytest.fixture
def wasteful():
    """A frame whose dtypes cost several times what its values need."""
    return pd.DataFrame(
        {
            "age": np.arange(ROWS) % 100,  # int64 holding 0-99
            "city": ["mumbai", "surat", "pune"] * (ROWS // 3) + ["surat"] * (ROWS % 3),
            "ratio": [1.5, 2.25, 3.0] * (ROWS // 3) + [1.5] * (ROWS % 3),
            "churn": [0, 1] * (ROWS // 2),
        }
    )


def test_footprint_finds_savings_without_converting(wasteful):
    before = wasteful.dtypes.to_dict()
    stats = footprint(wasteful)
    assert stats["saved_bytes"] > 0
    assert 0 < stats["savings_rate"] < 1
    assert stats["optimized_bytes"] < stats["current_bytes"]
    # measuring must not touch the caller's frame
    assert wasteful.dtypes.to_dict() == before


def test_int_downcast_keeps_every_value(wasteful):
    out = optimize_dtypes(wasteful)
    assert out["age"].dtype == np.int8
    pd.testing.assert_series_equal(
        out["age"].astype("int64"), wasteful["age"], check_dtype=False
    )


def test_text_becomes_category_and_shrinks(wasteful):
    out = optimize_dtypes(wasteful)
    assert isinstance(out["city"].dtype, pd.CategoricalDtype)
    assert out["city"].tolist() == wasteful["city"].tolist()
    assert out.memory_usage(deep=True).sum() < wasteful.memory_usage(deep=True).sum()


def test_unsigned_is_opt_in():
    df = pd.DataFrame({"n": np.full(1000, 200, dtype="int64")})
    assert optimize_dtypes(df)["n"].dtype == np.int16
    assert optimize_dtypes(df, allow_unsigned=True)["n"].dtype == np.uint8


def test_float_downcast_only_when_exact():
    exact = pd.DataFrame({"x": [1.5, 2.25, 3.0] * 100})
    assert optimize_dtypes(exact)["x"].dtype == np.float32

    lossy = pd.DataFrame({"x": [0.1, 0.2, 0.3] * 100})
    assert optimize_dtypes(lossy)["x"].dtype == np.float64
    assert optimize_dtypes(lossy, allow_lossy_float=True)["x"].dtype == np.float32


def test_plan_is_json_serializable(wasteful):
    plan = dtype_plan(wasteful)
    assert plan["version"] == PLAN_VERSION
    assert json.loads(json.dumps(plan)) == plan


def test_plan_replay_gives_identical_dtypes_on_new_data():
    """The point of the plan: a second frame must not get its own dtypes."""
    train = pd.DataFrame(
        {"n": np.arange(3000) % 1000, "city": ["mumbai", "surat", "pune"] * 1000}
    )
    later = pd.DataFrame({"n": np.arange(100) % 50, "city": ["surat", "pune"] * 50})

    plan = dtype_plan(train)
    assert plan["columns"]["n"]["dtype"] == "int16"
    # left to itself, this narrow frame would choose int8 and two categories
    fresh = dtype_plan(later)
    assert fresh["columns"]["n"]["dtype"] == "int8"
    assert fresh["columns"]["city"]["categories"] != plan["columns"]["city"]["categories"]

    replayed = optimize_dtypes(later, plan)
    trained = optimize_dtypes(train, plan)
    assert replayed.dtypes.to_dict() == trained.dtypes.to_dict()
    assert list(replayed["city"].cat.categories) == list(trained["city"].cat.categories)


def test_unseen_category_raises_by_default(wasteful):
    plan = dtype_plan(wasteful)
    later = pd.DataFrame({"city": ["mumbai", "delhi"]})
    with pytest.raises(ValueError, match="never saw"):
        optimize_dtypes(later, {"version": PLAN_VERSION, "columns": {"city": plan["columns"]["city"]}})


def test_unseen_category_can_be_accepted_as_nan(wasteful):
    plan = {"version": PLAN_VERSION, "columns": {"city": dtype_plan(wasteful)["columns"]["city"]}}
    later = pd.DataFrame({"city": ["mumbai", "delhi"]})
    out = optimize_dtypes(later, plan, on_unseen="nan")
    assert out["city"].tolist()[0] == "mumbai"
    assert pd.isna(out["city"].tolist()[1])


def test_replay_refuses_to_wrap_out_of_range_integers():
    """int64 1000 cast to int8 becomes -24 in numpy; that must never happen."""
    plan = dtype_plan(pd.DataFrame({"n": np.arange(100)}))
    assert plan["columns"]["n"]["dtype"] == "int8"
    with pytest.raises(ValueError, match="do not fit int8"):
        optimize_dtypes(pd.DataFrame({"n": [1000]}), plan)


def test_rejects_unknown_on_unseen_and_future_plan(wasteful):
    with pytest.raises(ValueError, match="on_unseen"):
        optimize_dtypes(wasteful, on_unseen="shrug")
    with pytest.raises(ValueError, match="newer mlclean"):
        optimize_dtypes(wasteful, {"version": PLAN_VERSION + 1, "columns": {}})


def test_ignore_columns_are_left_alone(wasteful):
    out = optimize_dtypes(wasteful, ignore_columns=("age",))
    assert out["age"].dtype == np.int64
    assert out["city"].dtype != object


def test_extension_dtypes_are_left_alone():
    df = pd.DataFrame({"n": pd.array([1, 2, None], dtype="Int64")})
    assert dtype_plan(df)["columns"] == {}


def test_audit_reports_the_footprint(wasteful):
    report = audit(wasteful, target="churn", checks=["memory"])
    assert [i.check for i in report.issues] == ["memory_footprint"]
    issue = report.issues[0]
    assert issue.details["saved_bytes"] > 0
    assert "optimize_dtypes" in issue.recommendation


def test_audit_stays_quiet_on_a_small_frame():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    assert audit(df, checks=["memory"]).issues == []
