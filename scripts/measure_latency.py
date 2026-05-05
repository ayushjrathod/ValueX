"""Benchmark p95 first-message and end-to-end latency for the /chat SSE endpoint."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx


def percentile(values: list[float], pct: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)

    ordered = sorted(values)
    rank = (len(ordered) - 1) * (pct / 100)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    weight = rank - lower
    return lower_value + (upper_value - lower_value) * weight


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Send repeated /chat requests, measure client-observed time to the first "
            "message event, and aggregate server metrics from the SSE metrics event."
        )
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--query",
        default="How is my portfolio doing?",
        help="Query sent in each benchmark request.",
    )
    parser.add_argument(
        "--user-id",
        default="usr_001",
        help="Optional user_id for the benchmark payload.",
    )
    parser.add_argument(
        "--session-prefix",
        default=None,
        help="Optional prefix for unique session_ids. If omitted, no session_id is sent.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write per-request JSONL results.",
    )
    return parser.parse_args()


def build_payload(args: argparse.Namespace, index: int) -> dict[str, Any]:
    payload: dict[str, Any] = {"query": args.query}
    if args.user_id:
        payload["user_id"] = args.user_id
    if args.session_prefix:
        payload["session_id"] = f"{args.session_prefix}-{index}"
    return payload


def parse_sse_stream(response: httpx.Response, started_at: float) -> dict[str, Any]:
    current_event: str | None = None
    current_data: str | None = None
    first_message_ms: int | None = None
    done_payload: dict[str, Any] | None = None
    metrics_payload: dict[str, Any] | None = None
    events_seen: list[str] = []

    for raw_line in response.iter_lines():
        if raw_line is None:
            continue
        line = raw_line.strip()

        if line.startswith("event:"):
            if current_event and current_data is not None:
                payload = json.loads(current_data) if current_data else {}
                events_seen.append(current_event)
                if current_event == "message" and first_message_ms is None:
                    first_message_ms = round((time.perf_counter() - started_at) * 1000)
                if current_event == "metrics":
                    metrics_payload = payload
                if current_event == "done":
                    done_payload = payload
            current_event = line[len("event:"):].strip()
            current_data = None
            continue

        if line.startswith("data:"):
            current_data = line[len("data:"):].strip()
            continue

        if line == "":
            if current_event and current_data is not None:
                payload = json.loads(current_data) if current_data else {}
                events_seen.append(current_event)
                if current_event == "message" and first_message_ms is None:
                    first_message_ms = round((time.perf_counter() - started_at) * 1000)
                if current_event == "metrics":
                    metrics_payload = payload
                if current_event == "done":
                    done_payload = payload
                current_event = None
                current_data = None

    if current_event and current_data is not None:
        payload = json.loads(current_data) if current_data else {}
        events_seen.append(current_event)
        if current_event == "message" and first_message_ms is None:
            first_message_ms = round((time.perf_counter() - started_at) * 1000)
        if current_event == "metrics":
            metrics_payload = payload
        if current_event == "done":
            done_payload = payload

    client_e2e_ms = round((time.perf_counter() - started_at) * 1000)
    return {
        "events_seen": events_seen,
        "client_first_message_ms": first_message_ms,
        "client_e2e_ms": client_e2e_ms,
        "metrics": metrics_payload,
        "done": done_payload,
    }


def run_request(
    client: httpx.Client,
    url: str,
    payload: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    with client.stream("POST", url, json=payload) as response:
        response.raise_for_status()
        parsed = parse_sse_stream(response, started_at)

    metrics = parsed["metrics"] or {}
    done_payload = parsed["done"] or {}
    return {
        "request_index": index,
        "payload": payload,
        "events_seen": parsed["events_seen"],
        "status": done_payload.get("status", "unknown"),
        "client_first_message_ms": parsed["client_first_message_ms"],
        "client_e2e_ms": parsed["client_e2e_ms"],
        "server_first_message_ms": metrics.get("first_message_ms"),
        "server_e2e_ms": metrics.get("e2e_ms"),
        "estimated_cost_usd": metrics.get("estimated_cost_usd"),
        "model": metrics.get("model"),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [result for result in results if result["status"] == "ok"]
    first_message_values = [
        float(result["client_first_message_ms"])
        for result in successful
        if result["client_first_message_ms"] is not None
    ]
    client_e2e_values = [
        float(result["client_e2e_ms"])
        for result in successful
        if result["client_e2e_ms"] is not None
    ]
    server_e2e_values = [
        float(result["server_e2e_ms"])
        for result in successful
        if result["server_e2e_ms"] is not None
    ]
    cost_values = [
        float(result["estimated_cost_usd"])
        for result in successful
        if result["estimated_cost_usd"] is not None
    ]

    return {
        "requests_total": len(results),
        "requests_ok": len(successful),
        "requests_failed": len(results) - len(successful),
        "client_first_message_ms": build_metric_summary(first_message_values),
        "client_e2e_ms": build_metric_summary(client_e2e_values),
        "server_e2e_ms": build_metric_summary(server_e2e_values),
        "estimated_cost_usd": build_metric_summary(cost_values),
    }


def build_metric_summary(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "min": round(min(values), 3),
        "p50": round(percentile(values, 50), 3),
        "p95": round(percentile(values, 95), 3),
        "max": round(max(values), 3),
        "mean": round(statistics.fmean(values), 3),
    }


def write_results(path: Path, results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps({"type": "request", **result}) + "\n")
        handle.write(json.dumps({"type": "summary", **summary}) + "\n")


def main() -> int:
    args = parse_args()
    benchmark_url = f"{args.base_url.rstrip('/')}/chat"

    if args.requests <= 0:
        print("--requests must be greater than zero", file=sys.stderr)
        return 2
    if args.warmup < 0:
        print("--warmup cannot be negative", file=sys.stderr)
        return 2

    with httpx.Client(timeout=args.timeout) as client:
        for warmup_index in range(args.warmup):
            payload = build_payload(args, warmup_index)
            run_request(client, benchmark_url, payload, warmup_index)

        results: list[dict[str, Any]] = []
        for request_index in range(args.requests):
            payload = build_payload(args, args.warmup + request_index)
            result = run_request(client, benchmark_url, payload, request_index)
            results.append(result)
            print(
                json.dumps(
                    {
                        "request_index": request_index,
                        "status": result["status"],
                        "client_first_message_ms": result["client_first_message_ms"],
                        "server_e2e_ms": result["server_e2e_ms"],
                        "estimated_cost_usd": result["estimated_cost_usd"],
                    }
                )
            )

    summary = summarize(results)
    print(json.dumps({"type": "summary", **summary}, indent=2))

    if args.output is not None:
        write_results(args.output, results, summary)

    return 0 if summary["requests_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
