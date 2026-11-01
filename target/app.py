
from collections import Counter
from threading import Lock
from time import perf_counter, time

from flask import Flask, jsonify, request

app = Flask(__name__)

# Thread-safe counters for controlled experiments.
metrics_lock = Lock()
started_at = time()

metrics = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "total_response_time_ms": 0.0,
    "max_response_time_ms": 0.0,
    "status_codes": Counter(),
    "paths": Counter(),
}

# Store each request's start time.
@app.before_request
def start_request_timer():
    request.start_time = perf_counter()


@app.after_request
def record_request(response):
    # Monitoring requests should not inflate experiment measurements.
    if request.path in ("/health", "/metrics"):
        return response

    elapsed_ms = (perf_counter() - request.start_time) * 1000

    with metrics_lock:
        metrics["total_requests"] += 1

        if 200 <= response.status_code < 400:
            metrics["successful_requests"] += 1
        else:
            metrics["failed_requests"] += 1

        metrics["total_response_time_ms"] += elapsed_ms
        metrics["max_response_time_ms"] = max(
            metrics["max_response_time_ms"], elapsed_ms
        )
        metrics["status_codes"][str(response.status_code)] += 1
        metrics["paths"][request.path] += 1

    response.headers["X-Target-Service"] = "proxytrap-target"
    return response


@app.get("/health")
def health():
    """Kubernetes health check; excluded from experiment counters."""
    return jsonify({"status": "healthy", "service": "target"}), 200


@app.get("/metrics")
def get_metrics():
    """Return request and latency measurements as JSON."""
    with metrics_lock:
        total = metrics["total_requests"]
        average_ms = (
            metrics["total_response_time_ms"] / total if total else 0.0
        )

        result = {
            "service": "target",
            "uptime_seconds": round(time() - started_at, 2),
            "total_requests": total,
            "successful_requests": metrics["successful_requests"],
            "failed_requests": metrics["failed_requests"],
            "average_response_time_ms": round(average_ms, 3),
            "max_response_time_ms": round(
                metrics["max_response_time_ms"], 3
            ),
            "status_codes": dict(metrics["status_codes"]),
            "paths": dict(metrics["paths"]),
        }

    return jsonify(result), 200


@app.get("/")
def home():
    return jsonify({
        "service": "proxytrap-target",
        "message": "Target service is running.",
        "available_endpoints": ["/", "/api/resource", "/health", "/metrics"],
    }), 200


@app.get("/api/resource")
def resource():
    """A simple endpoint for proxy and traffic-generator experiments."""
    return jsonify({
        "service": "proxytrap-target",
        "message": "Request reached the target service successfully.",
        "resource": "demo",
    }), 200


@app.errorhandler(404)
def not_found(_error):
    return jsonify({
        "error": "not_found",
        "message": "The requested endpoint does not exist.",
    }), 404


if __name__ == "__main__":
    # Listen on all container interfaces so Kubernetes can reach the app.
    app.run(host="0.0.0.0", port=5000, threaded=True)
