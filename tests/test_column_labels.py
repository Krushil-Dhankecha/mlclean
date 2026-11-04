"""Frames whose column labels are awkward: not strings, or not unique.

Both shapes come out of ordinary pandas use — pd.read_csv(header=None) gives
integer labels, an un-suffixed join or an Excel export with repeated headers
gives duplicates — and both used to take most of the audit down quietly.
"""

import numpy as np
import pandas as pd
import pytest

from mlclean import audit


def issues_for(report, check):
    return [i for i in report.issues if i.check == check]


def check_errors(report):
    return [i.message for i in report.issues if i.check == "check_error"]


# ------------------------------------------------------------ integer labels
def test_integer_column_labels_do_not_break_any_check():
    df = pd.DataFrame(np.random.default_rng(0).normal(size=(60, 3)))
    assert check_errors(audit(df)) == []


def test_identifier_is_found_under_an_integer_label():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({0: np.arange(100), 1: rng.normal(size=100)})
    found = issues_for(audit(df), "id_column")
    assert found and found[0].columns == [0]


def test_label_named_zero_behaves_like_the_string():
    rng = np.random.default_rng(2)
    as_int = pd.DataFrame({0: np.arange(100), 1: rng.normal(size=100)})
    as_text = as_int.rename(columns={0: "0", 1: "1"})
    assert len(issues_for(audit(as_int), "id_column")) == len(
        issues_for(audit(as_text), "id_column")
    )


# ---------------------------------------------------------- duplicate labels
def test_duplicate_labels_do_not_break_any_check():
    df = pd.DataFrame(np.arange(200).reshape(100, 2), columns=["a", "a"])
    assert check_errors(audit(df)) == []


def test_duplicate_labels_are_reported_with_their_positions():
    df = pd.DataFrame(np.arange(300).reshape(100, 3), columns=["a", "b", "a"])
    found = issues_for(audit(df), "duplicate_column_names")
    assert found and found[0].columns == ["a"]
    assert found[0].details["positions"] == {"a": [0, 2]}


def test_unique_labels_produce_no_finding():
    df = pd.DataFrame({"a": range(100), "b": range(100)})
    assert issues_for(audit(df), "duplicate_column_names") == []


def test_both_copies_of_a_label_are_checked():
    # same name, different problems: one constant, one entirely missing
    df = pd.DataFrame({"x": range(100)})
    df["c"] = "k"
    df["n"] = None
    df.columns = ["x", "dup", "dup"]
    report = audit(df)
    assert len(issues_for(report, "constant_column")) == 2  # all-null counts too
    assert [i.columns for i in issues_for(report, "missing_values")] == [["dup"]]


def test_duplicated_target_is_refused_with_a_clear_message():
    df = pd.DataFrame(np.arange(300).reshape(100, 3), columns=["a", "y", "y"])
    with pytest.raises(ValueError, match="appears 2 times"):
        audit(df, target="y")


def test_labels_check_is_selectable_by_name():
    df = pd.DataFrame(np.arange(200).reshape(100, 2), columns=["a", "a"])
    report = audit(df, checks=["labels"])
    assert {i.check for i in report.issues} == {"duplicate_column_names"}
