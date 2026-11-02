# Contributing

Bug reports and check ideas are welcome — open an issue first for anything
bigger than a small fix, so we agree on the direction before you spend time
on it.

## Setup

```bash
git clone https://github.com/Krushil-Dhankecha/mlclean
cd mlclean
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
```

## Before you open a PR

```bash
ruff check .
pytest --cov=mlclean
```

Work on a branch, not on main. CI runs on every push and must be green
before merge. New checks need tests with a planted problem the check is
supposed to catch, and a negative case it must not flag.

A note on philosophy: mlclean prefers few, high-precision findings over many
noisy ones. A check that fires on healthy data is worse than no check.
