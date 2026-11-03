"""Cleaning strategies and the reproducible pipeline.

Principle: never silently delete data without recording why. Every change is
a CleaningStep with a reason, and the pipeline replays on any DataFrame.

Layout: ``pipeline`` holds the step/pipeline model, ``steps`` the appliers
that execute each step, ``strategies`` the logic that turns a report into
a pipeline.
"""

from mlclean.cleaning.pipeline import ROW_STEPS, CleaningPipeline, CleaningStep
from mlclean.cleaning.strategies import STRATEGIES, build_pipeline

__all__ = [
    "ROW_STEPS",
    "STRATEGIES",
    "CleaningPipeline",
    "CleaningStep",
    "build_pipeline",
]
