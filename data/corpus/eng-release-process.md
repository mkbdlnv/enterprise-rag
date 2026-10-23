---
title: Software Release and Deployment Process
department: Engineering
updated: 2026-07-20
---
# Software Release and Deployment Process

## Code review
Every change is merged through a pull request reviewed by at least one other engineer. Changes to authentication, payments or infrastructure require two approvals, one from a senior engineer.

## Continuous integration
The CI pipeline runs linting and unit tests on every commit and builds a Docker image. A pull request cannot be merged while the pipeline is red. Test coverage of new code should be at least 80 percent.

## Deployment
Images are deployed to the staging environment automatically after merge to the main branch. Production deployments happen on Tuesdays and Thursdays and need approval from the release manager. During the December code freeze only critical fixes are deployed.

## Rollback
Every deployment must be reversible. If health checks fail after deployment, the previous image is restored automatically. An incident review is written for every production rollback.
