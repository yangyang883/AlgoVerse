import random
import time
from datetime import datetime, timezone
from uuid import uuid4

from app.engine.sorting.bubble import bubble_sort
from app.engine.registry import CAPABILITIES
from app.schemas.models import ExperimentConfig, ExperimentResult, ValidationResult


def run_experiment(config: ExperimentConfig) -> ExperimentResult:
    if not any(c.name == config.algorithm and c.executable for c in CAPABILITIES):
        raise ValueError("algorithm is not executable")
    source = config.input
    if source.values is not None:
        values = source.values.copy()
    elif source.distribution == "sorted":
        values = list(range(source.size))
    elif source.distribution == "reversed":
        values = list(range(source.size, 0, -1))
    else:
        rng = random.Random(source.seed)
        values = [rng.randint(-1000, 1000) for _ in range(source.size)]
    start = time.perf_counter()
    output, comparisons, swaps, trace, truncated = bubble_sort(
        values, trace_limit=5000 if config.visualization.enabled else 0
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    valid = output == sorted(values)
    return ExperimentResult(
        run_id=str(uuid4()), status="completed" if valid else "failed", config=config,
        input=values, output=output,
        metrics={"comparisons": comparisons, "swaps": swaps, "elapsed_ms": elapsed_ms},
        validation=ValidationResult(valid=valid, reason=None if valid else "output is not sorted"),
        trace=trace, trace_truncated=truncated, created_at=datetime.now(timezone.utc),
    )
