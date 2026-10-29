
"""Evaluate retrieval accuracy and latency through the live Search API."""
import csv
import json
import time
from pathlib import Path

import requests
import statistics


API_BASE_URL = "http://127.0.0.1:8000"
BENCHMARK_PATH = Path(__file__).with_name("retrieval_benchmark.json")

USERNAME = "manager@enterprise.local"
PASSWORD = "password"

SEARCH_MODES = ["keyword", "semantic", "hybrid"]
TOP_K = 5
LATENCY_RUNS = 5


def login(session):
    response = session.post(
        f"{API_BASE_URL}/api/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def evaluate_question(session, question, mode):
    start = time.perf_counter()

    response = session.post(
        f"{API_BASE_URL}/api/v1/search",
        json={
            "query": question["query"],
            "top_k": TOP_K,
            "search_mode": mode,
        },
        timeout=120,
    )

    latency_ms = (time.perf_counter() - start) * 1000
    response.raise_for_status()

    results = response.json()["results"]
    expected = set(question["expected_chunk_ids"])

    first_correct_rank = next(
        (
            rank
            for rank, result in enumerate(results, start=1)
            if result["chunk_id"] in expected
        ),
        None,
    )

    return {
        "question_id": question["id"],
        "mode": mode,
        "rank": first_correct_rank,
        "hit_at_1": int(first_correct_rank == 1),
        "hit_at_5": int(first_correct_rank is not None),
        "reciprocal_rank": (
            1.0 / first_correct_rank if first_correct_rank else 0.0
        ),
        "latency_ms": latency_ms,
    }


def main():
    with BENCHMARK_PATH.open(encoding="utf-8") as file:
        benchmark = json.load(file)

    questions = benchmark["questions"]
    raw_results = []

    if not questions:
        raise ValueError("Benchmark dataset contains no questions.")

    with requests.Session() as session:
        token = login(session)
        session.headers.update({
            "Authorization": f"Bearer {token}",
        })


        # Warm up each retrieval mode before collecting measurements.
        print("Warming up retrieval modes...")

        for mode in SEARCH_MODES:
            evaluate_question(session, questions[0], mode)

        print("Warm-up completed.\n")
        print(f"Benchmark: {benchmark['dataset_name']}")
        print(f"Questions: {len(questions)}")
        print(f"Top-K: {TOP_K}")
        print()

        for mode in SEARCH_MODES:
            print(f"===== {mode.upper()} =====")
            evaluations = []
            all_latencies = []

            
            for question in questions:
                runs = [
                    evaluate_question(session, question, mode)
                    for _ in range(LATENCY_RUNS)
                ]

                for run_number, run in enumerate(runs, start=1):
                    raw_results.append({
                        "question_id": run["question_id"],
                        "mode": mode,
                        "run": run_number,
                        "rank": run["rank"],
                        "hit_at_1": run["hit_at_1"],
                        "hit_at_5": run["hit_at_5"],
                        "reciprocal_rank": run["reciprocal_rank"],
                        "latency_ms": round(run["latency_ms"], 3),
                    })

                all_latencies.extend(run["latency_ms"] for run in runs)

                result = runs[0].copy()
                result["latency_ms"] = (
                    sum(run["latency_ms"] for run in runs)
                    / LATENCY_RUNS
                )

                evaluations.append(result)

                rank = result["rank"] or "Not found"
                print(
                    f"{result['question_id']}: "
                    f"Rank={rank} | "
                    f"Avg latency={result['latency_ms']:.1f} ms"
                )


            count = len(evaluations)

            hit_at_1 = sum(r["hit_at_1"] for r in evaluations) / count
            hit_at_5 = sum(r["hit_at_5"] for r in evaluations) / count
            mrr_at_5 = sum(r["reciprocal_rank"] for r in evaluations) / count
            mean_latency = sum(r["latency_ms"] for r in evaluations) / count
            p95_latency = statistics.quantiles(
                all_latencies,
                n=100,
                method="inclusive",
            )[94]

            print()
            print(f"Hit@1:       {hit_at_1:.3f}")
            print(f"Hit@5:       {hit_at_5:.3f}")
            print(f"MRR@5:       {mrr_at_5:.3f}")
            print(f"Mean latency: {mean_latency:.1f} ms")
            print(f"P95 latency:  {p95_latency:.1f} ms")
            print()

    output_path = Path(__file__).with_name("retrieval_results.csv")

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "question_id",
                "mode",
                "run",
                "rank",
                "hit_at_1",
                "hit_at_5",
                "reciprocal_rank",
                "latency_ms",
            ],
        )
        writer.writeheader()
        writer.writerows(raw_results)

    print(f"Raw results saved to: {output_path}")


if __name__ == "__main__":
    main()
