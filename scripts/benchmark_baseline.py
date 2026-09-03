"""Baseline performance benchmark harness for SmartClipboard (Python implementation).

Measures:
1. DB open and table verify latency
2. History listing latency
3. FTS5 search latency (median and p95 over 10 iterations)
4. Memory RSS (idle)
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

# Ensure root repository is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from smartclipboard_core.database import ClipboardDB

FIXTURES_DIR = REPO_ROOT / "tests" / "native_parity" / "fixtures"
DB_PATH = FIXTURES_DIR / "synthetic_test_v6.db"
OUTPUT_JSON = REPO_ROOT / "docs" / "benchmarks_baseline_python.json"


def get_current_rss_mb() -> float:
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0


def benchmark_db_operations() -> dict[str, float | list[float]]:
    assert DB_PATH.exists(), f"Synthetic DB fixture missing at: {DB_PATH}"

    # 1. DB open latency
    t0 = time.perf_counter()
    db = ClipboardDB(db_file=str(DB_PATH), app_dir=str(FIXTURES_DIR))
    db_open_sec = time.perf_counter() - t0

    # 2. History listing latency (10 runs)
    list_times: list[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        items = db.get_items()
        list_times.append((time.perf_counter() - t0) * 1000.0)  # ms

    # 3. FTS search latency (10 runs for English and Korean)
    fts_en_times: list[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        _results = db.search_items("Quick brown", limit=50)
        fts_en_times.append((time.perf_counter() - t0) * 1000.0)

    fts_kr_times: list[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        _results = db.search_items("스마트클립보드", limit=50)
        fts_kr_times.append((time.perf_counter() - t0) * 1000.0)

    db.conn.close()

    return {
        "db_open_ms": round(db_open_sec * 1000.0, 3),
        "history_list_ms_median": round(statistics.median(list_times), 3),
        "history_list_ms_p95": round(statistics.quantiles(list_times, n=20)[-1] if len(list_times) >= 20 else max(list_times), 3),
        "fts_en_ms_median": round(statistics.median(fts_en_times), 3),
        "fts_en_ms_p95": round(max(fts_en_times), 3),
        "fts_kr_ms_median": round(statistics.median(fts_kr_times), 3),
        "fts_kr_ms_p95": round(max(fts_kr_times), 3),
        "rss_mb": round(get_current_rss_mb(), 2),
    }


def main():
    print("=== SmartClipboard Python Baseline Benchmark ===")
    results = benchmark_db_operations()
    for k, v in results.items():
        print(f"  {k}: {v}")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Baseline results saved to: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
