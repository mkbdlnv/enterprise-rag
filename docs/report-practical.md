---
title: "Practical Report: CI/CD Pipeline for a Python RAG Project with Docker and Jenkins"
author: "Medet Kabdulinov"
date: "Assignment 5. DevOps and CI/CD: Automating Processes for Research Projects"
---

**Repository and Jenkinsfile:** https://github.com/mkbdlnv/enterprise-rag (Jenkinsfile in the repository root). **Deployed service:** https://rag.mkab.dev. **Jenkins:** `127.0.0.1:8090` on the same server, reached through an SSH tunnel.

# Project

The sample project is my thesis prototype: a Retrieval-Augmented Generation system for enterprise search, written in Python 3.12 with FastAPI. It indexes 12 policy documents (44 chunks) and retrieves passages with BM25. An LLM then writes an answer that cites the sources; without a model, the system answers extractively. On 30 labelled questions it scores Recall@3 = 1.0 and MRR = 0.967.

# Steps

1. **Git.** Code, data, tests, Dockerfile, Jenkinsfile and the Jenkins configuration are in one GitHub repository. Jenkins builds every commit to `main`.
2. **Dockerfile.** The Dockerfile is multi-stage. `base` holds the pinned dependencies. `test` adds pytest and Ruff and is used by CI. `runtime` contains only the code and data and runs as a non-root user with a `HEALTHCHECK`. Its content is 48 MB.
3. **Jenkins server.** Jenkins LTS 2.580.1 runs in Docker on a 1 vCPU / 2 GB VPS and is fully defined as code. The image adds the Docker CLI and the plugins. Configuration as Code creates the admin user, the LLM-key credential and the job (Job DSL). The compose file sets a 768 MB memory limit and mounts the Docker socket. One script sets the server up.
4. **CI pipeline.** It is triggered by `pollSCM` every 2 minutes. The stages are: Checkout → Build test image → Lint (Ruff) → Unit tests (30 pytest tests with a JUnit report and 96 % coverage) → Evaluate retrieval (`eval.json` archived; the build fails if Recall@3 < 0.9) → Build image (`enterprise-rag:<sha>`) → Push image. Push is optional and switched on by `PUSH_IMAGE=true` plus a registry credential.
5. **CD (bonus).** `scripts/deploy.sh` replaces the service container and waits for the health check. If the new version never becomes healthy, it restores the previous image and fails the build. The smoke test sends real requests and checks that the new revision is running. A Kubernetes manifest for Minikube/k3s is included.

The first build started by itself (*"Started by an SCM change"*) and took 69 s. The second took 39 s, because the dependency layers were cached. All stages passed.

# Difficulties

- **2 GB RAM shared with other services.** I set a JVM heap limit and a container limit for Jenkins. Builds run in the host Docker daemon, and Python tools stay in the test image, so the agent needs only git and Docker.
- **Docker socket permissions.** The `jenkins` user could not reach `/var/run/docker.sock`. I added the socket's group ID to the container (`group_add`).
- **Secrets.** Jenkins process variables are visible to every `sh` step. Configuration as Code therefore reads secrets from files. The LLM key is a masked credential, passed to the container as `-e LLM_API_KEY` without a value.
- **No webhook.** Jenkins is reachable only via SSH, so GitHub cannot call a webhook. SCM polling every 2 minutes replaces it.
- **Windows ↔ Linux.** `.gitattributes` forces LF line endings. Server commands are sent as script files, because PowerShell breaks quotes inside `ssh` arguments.
- **External LLM in tests.** The HTTP call is mocked. The tests check the prompt, the model fallback chain and the extractive fallback without network access.

# Conclusions

Every commit becomes a tested, measured and deployed version in under a minute, without manual steps. Pinned dependencies and images make the environment reproducible. The archived `eval.json` ties each quality number to a commit. For RAG research, a metric-based quality gate in CI matters as much as unit tests: it decides whether a change to chunking, tokenisation or the prompt is accepted. Next steps are hybrid retrieval, a faithfulness metric in the same gate, and pushing images to a registry.

\newpage

# Appendix: screenshots

![Jenkins job: stage view of builds #1 and #2, test result trend, archived artifacts](screenshots/01-job-stage-view.png){width=16cm}

![Build #2: triggered by an SCM change, two commits, revision, artifacts, test results](screenshots/02-build.png){width=16cm}

![JUnit test report: 30 of 30 tests passed](screenshots/03-test-results.png){width=16cm}

![Console output of build #2: image built, push skipped, deployed with health check, smoke test passed](screenshots/04-console-deploy.png){width=16cm}

![Archived retrieval evaluation (eval.json) of build #2](screenshots/05-artifacts.png){width=8cm}

![The deployed service at https://rag.mkab.dev answering with cited sources](screenshots/06-app.png){width=14cm}

![GitHub repository with the code, Dockerfile and Jenkinsfile](screenshots/07-github.png){width=16cm}
