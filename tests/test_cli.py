import numpy as np
import pandas as pd
import pytest

from mlclean.cli import main


@pytest.fixture
def csv_with_leak(tmp_path):
    rng = np.random.default_rng(7)
    n = 200
    churn = rng.integers(0, 2, n)
    df = pd.DataFrame(
        {
            "age": rng.integers(18, 80, n),
            "leak": churn,
            "churn": churn,
        }
    )
    path = tmp_path / "data.csv"
    df.to_csv(path, index=False)
    return path


def test_audit_prints_report(csv_with_leak, capsys):
    code = main(["audit", str(csv_with_leak), "--target", "churn"])
    out = capsys.readouterr().out
    assert code == 0
    assert "mlclean audit report" in out
    assert "leak" in out


def test_fail_on_gates_the_exit_code(csv_with_leak):
    assert main(["audit", str(csv_with_leak), "--target", "churn", "--fail-on", "high"]) == 1
    # nothing at critical/high in a clean file
    clean = csv_with_leak.parent / "clean.csv"
    pd.DataFrame(
        {"a": np.random.default_rng(0).normal(size=100), "y": [0, 1] * 50}
    ).to_csv(clean, index=False)
    assert main(["audit", str(clean), "--target", "y", "--fail-on", "high"]) == 0


def test_report_files_are_written(csv_with_leak, tmp_path):
    json_path = tmp_path / "r.json"
    md_path = tmp_path / "r.md"
    main(
        [
            "audit",
            str(csv_with_leak),
            "--target",
            "churn",
            "--json",
            str(json_path),
            "--markdown",
            str(md_path),
        ]
    )
    assert json_path.exists() and md_path.exists()


def test_version_flag():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
