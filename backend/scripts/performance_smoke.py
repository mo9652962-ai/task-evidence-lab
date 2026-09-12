"""Repeatable local smoke benchmark; this is not a production load test."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Task Evidence Lab local list/search benchmark")
    parser.add_argument("--tasks", type=int, default=500, help="number of temporary tasks to create")
    parser.add_argument("--repetitions", type=int, default=10, help="number of list/search repetitions")
    args = parser.parse_args()
    if args.tasks < 1 or args.repetitions < 1:
        raise SystemExit("--tasks and --repetitions must be positive")

    with tempfile.TemporaryDirectory(prefix="task-evidence-lab-benchmark-") as temp_dir:
        os.environ["DATABASE_PATH"] = str(Path(temp_dir) / "benchmark.db")
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            seed_started = time.perf_counter()
            for index in range(args.tasks):
                response = client.post(
                    "/api/tasks",
                    json={"title": f"Benchmark task {index}", "description": "benchmark searchable evidence"},
                )
                response.raise_for_status()
            seed_ms = (time.perf_counter() - seed_started) * 1000

            def measure(params: dict[str, object]) -> float:
                started = time.perf_counter()
                for _ in range(args.repetitions):
                    response = client.get("/api/tasks", params=params)
                    response.raise_for_status()
                return (time.perf_counter() - started) * 1000 / args.repetitions

            result = {
                "tasks_seeded": args.tasks,
                "repetitions": args.repetitions,
                "seed_total_ms": round(seed_ms, 2),
                "list_avg_ms": round(measure({"limit": 100}), 2),
                "ascii_search_avg_ms": round(measure({"q": "Benchmark", "limit": 100}), 2),
                "chinese_like_fallback_avg_ms": round(measure({"q": "可搜索", "limit": 100}), 2),
                "scope": "local TestClient smoke baseline; excludes production RUM, concurrency, multiprocess and network latency",
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
