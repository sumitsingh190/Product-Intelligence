
"""CLI runner for ProductOS AI agent evaluation suites.

Usage:
    python -m app.agents.evals.runner --suite all
    python -m app.agents.evals.runner --suite customer
    python -m app.agents.evals.runner --suite strategy --offline
    python -m app.agents.evals.runner --suite prd
    python -m app.agents.evals.runner --suite all --offline --json out.json

Exit code is e if all suites' pass_rate >= --min-pass-rate (default 0.7), 
otherwise 1. Useful as a CI gate.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys

from typing import Any

SUITES: dict[str, str] = {
    "customer": "app.agents.evals.eval_customer_intelligence", 
    "strategy": "app.agents.evals.eval_product_strategy",
    "prd": "app.agents.evals.eval_prd",
}

def _resolve(suite: str) -> list[str]:
    if suite == "all":
        return list(SUITES.keys())
    if suite not in SUITES:
        raise SystemExit(f"Unknown suite: {suite}. Valid: {','.join(SUITES)} or 'all'.")

    return [suite]

async def _run_one(suite_key: str, offline: bool) -> dict[str, Any]:
    module = importlib.import_module(SUITES[suite_key])
    return await module.run(offline=offline)

async def _run_all(suite_keys: list[str], offline: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in suite_keys:
        try:
            out[key] = await _run_one(key, offline=offline) 
        except Exception as exc: #noqa: BLE001 eval harness must keep running 
            out[key] = {
                "suite": key,
                "summary": {"count": 0, "pass_rate": 0.0, "mean_score": 0.0, "error": str(exc)}, 
                "results": [], 
                }
    return out

def _print_table(results: dict[str, Any]) -> None:
    print("\n== ProductOS AI eval summary")
    print(f"{'suite':<20}{'cases':>7}{'passed':>8}{'pass_rate':>11}{'mean_score':>12}")
    print("-" * 58)
    for key, payload in results.items():
        s = payload["summary"]
        print(
            f"{key:<20}"
            f"{s.get('count', 0):>7}"
            f"{s.get('passed', 0):>8}"
            f"{s.get('pass_rate', 0.0):>11.2f}"
            f"{s.get('mean_score', 0.0):>12.2f}"
        )
    print("-"* 58)

def main(argv: list [str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ProductOS AI agent evals")
    parser.add_argument(
        "--suite", default="all", help=f"Suite to run: 'all' or one of {list(SUITES)}",
    )
    parser.add_argument(
        "--offline", action="store_true", 
        help="Skip real LLM calls; use deterministic stubs / heuristic=only checks.",
    )
    parser.add_argument(
        "--json",
        dest="json_out", 
        default=None, 
        help="If set, write the full 350N results to this path.",
    )
    parser.add_argument(
        "--min-pass-rate", type=float, default=0.7,
        help="Per-suite minimum pass rate for exit code 0 (default 0.7).",
    )
    args = parser.parse_args(argv)

    suites = _resolve(args.suite)
    results = asyncio.run(_run_all(suites, offline=args.offline))

    _print_table(results)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf=8") as fh: 
            json.dump(results, fh, indent=2) 
            print(f"\nFull results written to {args.json_out}")

    worst = min(
        (r["summary"].get("pass_rate", 0.0) for r in results.values()),
        default=0.0,
    )
    return 0 if worst >= args.min_pass_rate else 1

if __name__ == "__main__":
    sys.exit(main())