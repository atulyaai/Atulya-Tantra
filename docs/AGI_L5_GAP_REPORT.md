# AGI Level 5 Capability Gap Audit

This document tracks current gaps vs. AGI Level 5 goals across Jarvis and Skynet and provides a prioritized remediation plan.

## Scope Areas

- Autonomy: long-horizon planning, self-initiated goals, event triggers
- Multi-agent orchestration: roles, negotiation, shared memory, task passing
- Learning: continual learning, feedback loops, skill acquisition
- Safety/guardrails: policy, rate limiting, privilege separation, sandboxing
- Monitoring/auto-heal: observability, SLOs, remediation playbooks
- Tool-use/action: verification, rollback, dry-run
- Evaluation: offline harness, benchmarks, regression suites

## Findings (High Level)

- Autonomy: Partial event handling; lacks explicit goal graph, long-horizon planner, and review loops.
- Orchestration: Agents exist; need standardized task spec, handoff protocol, and shared memory contracts.
- Learning: No persistent skill acquisition; add reward modeling hooks and user feedback integration.
- Safety: Basic middleware; missing capability policies, RBAC for tools, and sandboxed execution.
- Monitoring: Good coverage; add SLOs, anomaly alerts, and automated rollback playbooks.
- Tool-use: Lacks verification and post-action checks; add reversible actions and dry-run.
- Evaluation: Tests present; add competency benchmarks and periodic regression runs.

## Prioritized Backlog (P1-P3)

- P1: Task spec + handoff protocol; category policy for tools; dry-run + verification.
- P1: Long-horizon planner skeleton with goal graph and review loop.
- P2: Shared memory API; evaluation harness with core benchmarks.
- P2: SLOs + alert rules + remediation playbooks.
- P3: Skill acquisition hooks; reward modeling.

## Owners and Milestones

- To be assigned per module leads; propose 2-week P1 sprint, 4-week P2, 6-week P3.


