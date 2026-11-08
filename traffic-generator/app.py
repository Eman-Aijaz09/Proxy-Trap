
import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

import requests


PROXY_URL = "http://localhost:8000"
TARGET_PATH = "/api/resource"

stats_lock = threading.Lock()

stats = {
    "total": 0,
    "successful": 0,
    "failed": 0,
    "total_response_time_ms": 0.0,
}


def send_request(client_id):
    """Send one HTTP request through the proxy."""

    start = perf_counter()

    try:
        response = requests.get(
            f"{PROXY_URL}{TARGET_PATH}",
            headers={"X-Test-Client-ID": client_id},
            timeout=5,
        )

        elapsed = (perf_counter() - start) * 1000

        with stats_lock:
            stats["total"] += 1
            stats["total_response_time_ms"] += elapsed

            if response.status_code == 200:
                stats["successful"] += 1
            else:
                stats["failed"] += 1

    except requests.RequestException as error:
        elapsed = (perf_counter() - start) * 1000

        with stats_lock:
            stats["total"] += 1
            stats["failed"] += 1
            stats["total_response_time_ms"] += elapsed

        print(
            f"[REQUEST ERROR] Client: {client_id} | "
            f"{type(error).__name__}: {error}"
        )


def get_rate(mode, elapsed, normal_rate, high_rate, burst_rate):
    """Choose the request rate for the current traffic scenario."""

    if mode == "normal":
        return normal_rate

    if mode == "high":
        return high_rate

    # Burst mode: high traffic for 3 seconds,
    # followed by normal traffic for 7 seconds.
    if elapsed % 10 < 3:
        return burst_rate

    return normal_rate


def run_generator(
    mode,
    duration,
    normal_rate,
    high_rate,
    burst_rate,
    workers,
    client_id,
    clients,
):
    """Generate HTTP traffic from multiple simulated clients."""

    if clients == 1:
        client_ids = [client_id]
    else:
        client_ids = [
            f"{client_id}-{i:02d}"
            for i in range(1, clients + 1)
        ]

    print("\nStarting traffic generator...")
    print(f"Mode: {mode}")
    print(f"Duration: {duration} seconds")
    print(f"Proxy: {PROXY_URL}")
    print(f"Number of simulated clients: {clients}")
    print("Simulated clients:", ", ".join(client_ids))
    print("-----------------------------------")

    start_time = perf_counter()
    next_request_time = start_time
    request_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:

        while True:
            elapsed = perf_counter() - start_time

            if elapsed >= duration:
                break

            current_rate = get_rate(
                mode,
                elapsed,
                normal_rate,
                high_rate,
                burst_rate,
            )

            interval = 1.0 / current_rate

            if perf_counter() >= next_request_time:

                # Distribute requests round-robin
                # across the simulated clients.
                selected_client = client_ids[
                    request_count % len(client_ids)
                ]

                executor.submit(send_request, selected_client)

                request_count += 1
                next_request_time += interval

            else:
                time.sleep(
                    max(0.0, min(0.01, next_request_time - perf_counter()))
                )

    total_time = perf_counter() - start_time

    with stats_lock:
        total = stats["total"]
        successful = stats["successful"]
        failed = stats["failed"]

        average = (
            stats["total_response_time_ms"] / total
            if total else 0
        )

    print("\n========== TRAFFIC REPORT ==========")
    print(f"Scenario: {mode}")
    print(f"Simulated clients: {clients}")
    print(f"Duration: {total_time:.2f} seconds")
    print(f"Total requests: {total}")
    print(f"Successful requests: {successful}")
    print(f"Failed requests: {failed}")
    print(f"Average response time: {average:.2f} ms")

    if total_time > 0:
        print(
            f"Actual request rate: "
            f"{total / total_time:.2f} requests/sec"
        )

    print("====================================")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="ProxyTrap controlled HTTP traffic generator"
    )

    parser.add_argument(
        "--mode",
        choices=["normal", "high", "burst"],
        default="normal",
    )

    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--normal-rate", type=float, default=2)
    parser.add_argument("--high-rate", type=float, default=10)
    parser.add_argument("--burst-rate", type=float, default=20)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--client-id", default="legitimate-client")
    parser.add_argument("--clients", type=int, default=1)

    args = parser.parse_args()

    if (
        args.duration <= 0
        or args.normal_rate <= 0
        or args.high_rate <= 0
        or args.burst_rate <= 0
        or args.workers <= 0
        or args.clients <= 0
    ):
        parser.error(
            "Duration, rates, workers and clients must be positive."
        )

    run_generator(
        args.mode,
        args.duration,
        args.normal_rate,
        args.high_rate,
        args.burst_rate,
        args.workers,
        args.client_id,
        args.clients,
    )
