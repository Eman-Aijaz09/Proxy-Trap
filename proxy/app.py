
from collections import Counter, defaultdict, deque
from threading import Lock
from time import perf_counter, monotonic

import requests
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

TARGET_URL = "http://target-service:5000"

WINDOW_SECONDS = 10

metrics_lock = Lock()

# Overall proxy metrics
metrics = {
    "total_requests": 0,
    "forwarded_requests": 0,
    "failed_requests": 0,
    "total_response_time_ms": 0.0,
    "status_codes": Counter(),
}

# Per-client request tracking
client_metrics = defaultdict(lambda: {
    "total_requests": 0,
    "recent_requests": deque()
})

# Aggregate request tracking across all clients
aggregate_recent_requests = deque()


def remove_old_requests(request_queue, cutoff):
    """Remove timestamps outside the monitoring window."""

    while request_queue and request_queue[0] < cutoff:
        request_queue.popleft()


@app.get("/health")
def health():
    return jsonify({
        "service": "proxytrap-proxy",
        "status": "healthy"
    }), 200


@app.get("/metrics")
def get_metrics():

    with metrics_lock:
        total = metrics["total_requests"]

        average = (
            metrics["total_response_time_ms"] / total
            if total else 0.0
        )

        result = {
            "service": "proxytrap-proxy",
            "total_requests": total,
            "forwarded_requests": metrics["forwarded_requests"],
            "failed_requests": metrics["failed_requests"],
            "average_response_time_ms": round(average, 3),
            "status_codes": dict(metrics["status_codes"]),
        }

    return jsonify(result), 200


@app.get("/client-metrics")
def get_client_metrics():

    now = monotonic()
    cutoff = now - WINDOW_SECONDS

    result = {}

    with metrics_lock:

        for client_id, data in client_metrics.items():

            remove_old_requests(
                data["recent_requests"],
                cutoff
            )

            result[client_id] = {
                "total_requests": data["total_requests"],
                "requests_last_10_seconds": len(
                    data["recent_requests"]
                )
            }

    return jsonify(result), 200


# New aggregate traffic monitoring endpoint

@app.get("/traffic-metrics")
def get_traffic_metrics():

    now = monotonic()
    cutoff = now - WINDOW_SECONDS

    with metrics_lock:

        # Remove requests outside the monitoring window
        remove_old_requests(
            aggregate_recent_requests,
            cutoff
        )

        # Collect per-client metrics using the same timestamp
        clients = {}

        for client_id, data in client_metrics.items():

            remove_old_requests(
                data["recent_requests"],
                cutoff
            )

            recent_count = len(data["recent_requests"])

            clients[client_id] = {
                "total_requests": data["total_requests"],
                "requests_last_10_seconds": recent_count
            }

        # Calculate aggregate metrics
        aggregate_count = sum(
            client["requests_last_10_seconds"]
            for client in clients.values()
        )

        active_clients = sum(
            1
            for client in clients.values()
            if client["requests_last_10_seconds"] > 0
        )

        result = {
            "monitoring_window_seconds": WINDOW_SECONDS,
            "aggregate_requests_last_10_seconds": aggregate_count,
            "aggregate_requests_per_second": round(
                aggregate_count / WINDOW_SECONDS,
                2
            ),
            "active_clients_last_10_seconds": active_clients,
            "clients": clients
        }

    return jsonify(result), 200


@app.route(
    "/",
    defaults={"path": ""},
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
)
@app.route(
    "/<path:path>",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
)
def forward_request(path):

    start_time = perf_counter()
    current_time = monotonic()

    # Identify the incoming client
    client_id = (
        request.headers.get("X-Test-Client-ID")
        or request.remote_addr
        or "unknown"
    )

    cutoff = current_time - WINDOW_SECONDS

    # Record incoming traffic
    with metrics_lock:

        client_data = client_metrics[client_id]

        client_data["total_requests"] += 1
        client_data["recent_requests"].append(current_time)

        aggregate_recent_requests.append(current_time)

        # Keep monitoring queues within the 10-second window
        remove_old_requests(
            client_data["recent_requests"],
            cutoff
        )

        remove_old_requests(
            aggregate_recent_requests,
            cutoff
        )

    destination = f"{TARGET_URL}/{path}"

    try:

        target_response = requests.request(
            method=request.method,
            url=destination,
            params=request.args,
            data=request.get_data(),
            headers={
                key: value
                for key, value in request.headers
                if key.lower() not in (
                    "host",
                    "content-length",
                    "connection"
                )
            },
            timeout=10,
            allow_redirects=False
        )

        elapsed_ms = (perf_counter() - start_time) * 1000

        with metrics_lock:

            metrics["total_requests"] += 1
            metrics["forwarded_requests"] += 1
            metrics["total_response_time_ms"] += elapsed_ms

            metrics["status_codes"][
                str(target_response.status_code)
            ] += 1

        excluded_headers = {
            "content-encoding",
            "content-length",
            "transfer-encoding",
            "connection"
        }

        response_headers = [
            (key, value)
            for key, value in target_response.headers.items()
            if key.lower() not in excluded_headers
        ]

        return Response(
            target_response.content,
            status=target_response.status_code,
            headers=response_headers
        )

    except requests.RequestException:

        elapsed_ms = (perf_counter() - start_time) * 1000

        with metrics_lock:

            metrics["total_requests"] += 1
            metrics["failed_requests"] += 1
            metrics["total_response_time_ms"] += elapsed_ms

        return jsonify({
            "error": "target_unavailable",
            "message": "The proxy could not reach the target service."
        }), 502


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000,
        threaded=True
    )
