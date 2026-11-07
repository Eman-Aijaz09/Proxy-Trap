
# ProxyTrap
## Detection and Mitigation of Proxy-Abuse-Based IDDoS in Kubernetes

### Overview
ProxyTrap is a research project focused on detecting and mitigating proxy-abuse-based IDDoS attacks in a controlled Kubernetes environment.

The system consists of a target service, a proxy service, and a traffic generator. It is designed to study suspicious request-forwarding behaviour and evaluate detection and mitigation techniques.

### Architecture

- **Target Service:** Flask application that receives requests and records request metrics.
- **Proxy Service:** Flask-based HTTP proxy that forwards incoming requests to the target service.
- **Traffic Generator:** Component for generating controlled HTTP traffic.
- **Kubernetes:** Manages deployment and communication between services.

### Technology Stack

- Python
- Flask
- Docker
- Kubernetes
- kind
- PowerShell

### Project Structure

```text
proxytrap/
├── k8s/
├── proxy/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── target/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── traffic-generator/
└── README.md
```

### Current Progress

- [x] Target service implementation
- [x] Target Docker image
- [x] Target Kubernetes deployment
- [x] Proxy service implementation
- [x] Proxy Docker image
- [x] Proxy Kubernetes deployment
- [x] End-to-end request forwarding
- [x] Basic request and response-time metrics
- [ ] Detection mechanism
- [ ] Mitigation mechanism
- [ ] Traffic generator
- [ ] Experimental evaluation

### Project Status

Currently implementing the baseline proxy-target architecture before integrating detection and mitigation mechanisms.
