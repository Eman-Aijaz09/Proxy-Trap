
from collections import Counter
from threading import Lock
from time import perf_counter

import requests
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

TARGET_URL = "http://target-service:5000"

metrics_lock = Lock()

metrics = {
    "total_requests": 0,
    "forwarded_requests": 0,
    "failed_requests": 0,
    "total_response_time_ms": 0.0,
    "status_codes": Counter(),
}


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


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def forward_request(path):
    start_time = perf_counter()

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
            metrics["status_codes"][str(target_response.status_code)] += 1

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
        with metrics_lock:
            metrics["total_requests"] += 1
            metrics["failed_requests"] += 1

        return jsonify({
            "error": "target_unavailable",
            "message": "The proxy could not reach the target service."
        }), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)
