"""Retrieval eval harness.

Runs a small golden-set of (query -> [relevant_doc_ids]) pairs against the running search endpoint 
and reports Recall@K, MRR@10, and nDCG@10. Use this to catch regressions when tuning the hybrid retrieval pipeline.

Usage
-------
    
    #1. Start the backend + seed a workspace with fixture docs whose IDs
        match--fixturés (see scripts/seed_data.py or seed manually).

#2. Run:
#       python -m backend.scripts.eval_retrieval \\
            --base-url http://localhost:8000 \\
            --email test@example.com--password testpassword123 \\
            -workspace-id <UUID> \\
            --fixtures backend/scripts/eval_retrieval_fixtures.json

Output
--------
            
            query                           R@10 MRR nDCG
            login button broken             1.00 1.00 1.00
            passwordless auth competitor    0.50 0.50 8.63

            ...
            -----
            mean                            0.75 0.68 0.72

Exit code is e when every metric mean is > the thresholds in --min-, 
otherwise 1 so this drops straight into CI once you have >= 20 fixtures.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import httpx

def _dcg(relevances: list[int]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate (relevances))

def _ndcg_at_k(hits: list[str], relevant: set[str], k: int) -> float:
    gains = [1 if h in relevant else 0 for h in hits[:k]]
    ideal = sorted(gains, reverse=True)
    idcg = _dcg(ideal)
    return _dcg(gains) / idcg if idcg else 0.0

def _mrr(hits: list[str], relevant: set[str], k: int = 10) -> float:
    for i, h in enumerate (hits[:k], start=1):
        if h in relevant:
            return 1.0/i
    return 0.0

def _recall_at_k(hits: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(hits[:k]) & relevant) / len (relevant)

def _login(client: httpx.Client, base_url: str, email: str, password: str) -> str:
    resp = client.post(
        f"{base_url}/api/v1/auth/login", json={"email": email, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access token"]

def _search(
    client: httpx.Client,
    base_url: str,
    token: str,
    workspace_id: str,
    query: str,
    top_k: int,
)-> list[dict[str, Any]]:
    resp = client.get(
        f"{base_url}/api/v1/search",
        params={"workspace_id": workspace_id, "q": query, "top_k": top_k},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--workspace-id", required=True)
    p.add_argument("--fixtures", type=Path, required=True) 
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--min-recall", type=float, default=0.0)
    p.add_argument("--min-mrr", type=float, default=0.0)
    p.add_argument("--min-ndcg", type=float, default=0.0)
    args = p.parse_args()

    fixtures = json.loads(args.fixtures.read_text(encoding="utf-8"))
    if not isinstance(fixtures, list):
        print("fixtures must be a JSON list of {query, relevant_ids)", file=sys.stderr)
        return 2

    with httpx.Client() as client:
        token = _login(client, args.base_url, args.email, args.password)
        
        rows: list[tuple [str, float, float, float]]=[]
        for fx in fixtures:
            query = fx["query"]
            relevant = set(fx["relevant_ids"])
            hits_json = _search(
                client, args.base_url, token, args.workspace_id, query, args.top_k
            )
            hit_ids = [h["id"] for h in hits_json]
            rows.append((
                query,
                _recall_at_k(hit_ids, relevant, args.top_k), 
                _mrr(hit_ids, relevant, k=10), 
                _ndcg_at_k(hit_ids, relevant, k=10),
            ))

    if not rows:
        print("no fixtures evaluated", file=sys.stderr)
        return 2

    header = f"{'query':<48} {'R@' + str(args.top_k):>6} {'MRR':>6} {'nDCG'>6}"
    print(header)
    print("-" * len(header))
    for q, r, m, n in rows:
        label = q if len(q) <= 46 else q[:43] + "..."
        print(f"{label:<48} {r:6.2f} {m:6.2f} {n:6.2f}")

    mean_r = sum(r for _, r, _, _ in rows) / len(rows)
    mean_m = sum(m for _, _, m, _ in rows) / len(rows)
    mean_n = sum(n for _, _, _, n in rows) / len(rows)

    print("-" * len(header))
    print(f"{'mean': <48} {mean_r:6.2f} {mean_m:6.2f} {mean_n:6.2f}")

    failed = []

    if mean_r < args.min_recall:
        failed.append(f"recall {mean_r:.2f} < {args.min_recall:.2f}")
    if mean_m < args.min_mrr:
        failed.append(f"mrr {mean_m:.2f} < {args.min_mrr:.2f}")
    if mean_n < args.min_ndcg:
        failed.append(f"ndcg {mean_n:.2f} < {args.min_ndcg:.2f}")
    if failed:
        print("\nFAIL: "+"; ".join(failed), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())