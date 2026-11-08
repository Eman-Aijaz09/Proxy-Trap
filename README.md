# ProxyTrap

## Project Overview

ProxyTrap is a controlled simulation of an **HTTP-based Indirect Distributed Denial-of-Service (IDDoS)** scenario.

The project models multiple simulated clients sending HTTP requests through a proxy, which forwards those requests to a target service. It also monitors traffic at the proxy and target levels.

The current implementation uses logical client IDs to simulate multiple sources. These IDs are sent using the `X-Test-Client-ID` HTTP header. They are identifiers for the experiment, not proof of separate physical devices or network origins.

## Architecture

```text
Simulated Clients
       |
       | HTTP requests
       v
     Proxy
       |
       | HTTP forwarding
       v
  Target Service
```

- **Traffic Generator:** Produces controlled HTTP traffic using configurable rates, durations, and logical client counts.
- **Proxy:** Receives and forwards HTTP requests, tracks request statistics, and monitors aggregate and per-client traffic.
- **Target:** Receives forwarded requests and exposes health and metrics endpoints.
- **Kubernetes:** Runs the proxy and target services in a local kind cluster.

## Technology Stack

- Python
- Flask
- Requests
- Docker
- Kubernetes
- kind
- PowerShell

## Project Structure

```text
proxytrap/
├── k8s/
│   ├── target.yaml
│   └── proxy.yaml
├── proxy/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── target/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── traffic-generator/
│   ├── app.py
│   └── requirements.txt
├── .gitignore
└── README.md
```

## Requirements

Install the following on the computer running the project:

- Git
- Docker Desktop with the Linux container engine enabled
- kubectl
- kind
- Python 3.12

## Setup on a New Computer

### 1. Clone the repository

```powershell
git clone YOUR_GITHUB_REPOSITORY_URL
cd proxytrap
```

### 2. Create the Kubernetes cluster

```powershell
kind create cluster --name proxytrap --image kindest/node:v1.37.0
kubectl cluster-info --context kind-proxytrap
kubectl get nodes
```

Wait until the node status is `Ready`.

### 3. Build the target Docker image

```powershell
docker build -t proxytrap-target:1.0 .\target
kind load docker-image proxytrap-target:1.0 --name proxytrap
```

### 4. Build the proxy Docker image

```powershell
docker build -t proxytrap-proxy:4.0 .\proxy
kind load docker-image proxytrap-proxy:4.0 --name proxytrap
```

### 5. Deploy the target and proxy

```powershell
kubectl apply -f .\k8s\target.yaml
kubectl apply -f .\k8s\proxy.yaml
```

Check the deployments and pods:

```powershell
kubectl get deployments
kubectl get pods
kubectl get services
```

Wait for both the target and proxy pods to become ready.

### 6. Set up the traffic generator environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
cd traffic-generator
pip install -r requirements.txt
```

### 7. Start port forwarding

Open a separate PowerShell terminal, navigate to the project folder, and run:

```powershell
kubectl port-forward service/proxy-service 8000:8000
```

Keep this terminal open while generating traffic.

### 8. Verify the services

In another terminal:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/traffic-metrics
```

The proxy forwards requests to the target through the Kubernetes service address:

```text
http://target-service:5000
```

## Running the Traffic Generator

From the `traffic-generator` directory, with the virtual environment activated:

Example: 3 logical clients sending an aggregate 3 requests per second for 30 seconds:

```powershell
python app.py --mode normal --duration 30 --normal-rate 3 --clients 3 --client-id client
```

Example: 3 logical clients sending an aggregate 10 requests per second for 30 seconds:

```powershell
python app.py --mode normal --duration 30 --normal-rate 10 --clients 3 --client-id client
```

The configured request rate is the **aggregate rate across all logical clients**, not the rate per client.

## Monitoring Endpoints

Proxy:

- `GET /health`
- `GET /metrics`
- `GET /client-metrics`
- `GET /traffic-metrics`

Target:

- `GET /health`
- `GET /metrics`
- `GET /`
- `GET /api/resource`

The proxy's `/traffic-metrics` endpoint provides aggregate recent request counts, aggregate requests per second, active logical clients, and per-client recent and cumulative counts.

The monitoring window is currently 10 seconds.

**Important:** Metrics are stored in application memory. Restarting a proxy or target pod resets that service's in-memory metrics.

## Current Development Status

- Target service implemented and deployed.
- HTTP forwarding proxy implemented and deployed.
- Traffic generator implemented with configurable duration, rate, and logical client count.
- Per-client traffic monitoring implemented.
- Aggregate traffic monitoring implemented.
- Combined `/traffic-metrics` monitoring endpoint implemented.
- Baseline experiments completed at 3, 6, and 10 aggregate requests per second, each for 30 seconds.
- The recorded generator runs completed successfully, with no failed requests.

## Next Experiment

The next planned experiment is a controlled 30-second run at an aggregate rate of 20 requests per second, using 3 logical clients.

Expected request count:

```text
20 requests/second × 30 seconds = 600 requests
```

This is a higher-load experiment, not automatically classified as an attack. Further experiments will compare normal and flooding traffic and evaluate mitigation.

## Important Notes

- The current project uses HTTP, not HTTPS.
- The simulation models indirect flooding through a forwarding proxy.
- Logical client IDs are experiment labels, not independent network identities.
- Docker images built locally are not stored in GitHub. A new computer must build and load them into its own kind cluster.
- Keep the Kubernetes cluster if you want to resume locally without recreating it.
