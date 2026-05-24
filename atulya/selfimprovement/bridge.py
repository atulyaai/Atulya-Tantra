#!/usr/bin/env python
"""
Self-Improvement Bridge: reads agent cron outputs → logs insights into selfimprovement.json
Closes the loop between autonomous agents and the native improvement tracker.
"""
import json, re, time
from datetime import datetime, timezone
from pathlib import Path

CRON_OUTPUT = Path("D:/Hermes/cron/output")
SELFIMPROVE = Path("F:/Atulya Tantra/atulya/selfimprovement/data")


AGENT_CHAKRA_MAP = {
    "code-self-improve":   "code_quality",
    "dataset-health":      "data_wisdom",
    "agent-orchestrator":  "orchestration",
    "npdna-unified-service": "system_operation",
    "model-test-eval":     "evaluation",
    "research-roadmap":    "research",
    "data-pipeline":       "data_wisdom",
    "training-lifecycle":  "training",
    "System Cleanup":      "system_operation",
}

AGENT_SKILL_MAP = {
    "code-self-improve":   ("code review", "automated_fixes"),
    "dataset-health":      ("data quality", "anomaly detection"),
    "agent-orchestrator":  ("orchestration", "scheduling"),
    "npdna-unified-service": ("service management", "monitoring"),
    "model-test-eval":     ("testing", "evaluation"),
    "research-roadmap":    ("research", "gap analysis"),
    "data-pipeline":       ("data ingestion", "preprocessing"),
    "training-lifecycle":  ("training ops", "automated training"),
    "System Cleanup":      ("system maintenance", "cleanup"),
}

SEVERITY_SCORE = {"critical": 10, "high": 5, "medium": 3, "low": 1, "info": 0.5}


def init_state():
    """Ensure selfimprovement.json exists with all chakras + skills."""
    from atulya.selfimprovement.unified import UnifiedSelfImprovement
    imp = UnifiedSelfImprovement(SELFIMPROVE)
    for chakra_name in set(AGENT_CHAKRA_MAP.values()):
        imp.add_chakra(chakra_name)
    for agent, skills in AGENT_SKILL_MAP.items():
        for sk in skills:
            imp.add_skill(sk, category="agent_automation")
    return imp


def scan_agent_outputs():
    """Find all markdown output files from agent cron runs."""
    if not CRON_OUTPUT.exists():
        return []
    files = []
    for job_dir in sorted(CRON_OUTPUT.iterdir()):
        if job_dir.is_dir():
            for f in sorted(job_dir.glob("*.md")):
                files.append((job_dir.name, f))
    return files


def infer_agent_name(job_id: str) -> str:
    """Map job_id back to agent name by reading output header."""
    job_dir = CRON_OUTPUT / job_id
    md_files = sorted(job_dir.glob("*.md"))
    if not md_files:
        return "unknown"
    header = md_files[-1].read_text(encoding="utf-8", errors="replace")
    m = re.search(r"Job ID: [0-9a-f]+\s+Run Time: (\S+)", header)
    if m:
        # Try to find agent name from first line
        for line in header.split("\n"):
            line = line.strip("# ").strip()
            if line.startswith("Cron Job:"):
                return line.replace("Cron Job:", "").strip()
    # Fallback: try prompt line
    for line in header.split("\n"):
        if "you are" in line.lower() and "agent" in line.lower():
            m2 = re.search(r"([A-Z][A-Za-z -]+[Aa]gent)", line)
            if m2:
                return m2.group(1).strip()
    return "unknown"


def parse_findings(text: str) -> list[dict]:
    """Extract finding entries from agent markdown output."""
    findings = []
    # Table rows: File|Issue|Severity|Fix Applied
    lines = text.split("\n")
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("---") and "|" in stripped:
            in_table = True
            continue
        if in_table and "|" in stripped and stripped.count("|") >= 3:
            cols = [c.strip() for c in stripped.split("|")]
            if len(cols) >= 4 and cols[0] and cols[1]:
                findings.append({
                    "file": cols[0],
                    "issue": cols[1],
                    "severity": cols[2].lower() if len(cols) > 2 else "info",
                    "fix": cols[3] if len(cols) > 3 else "",
                })
            continue
        # Non-table findings (bullets with severity)
        sev_match = re.search(r"(critical|high|medium|low|info)", stripped.lower())
        if sev_match and ("file" in stripped.lower() or "issue" in stripped.lower()):
            findings.append({
                "file": stripped[:60],
                "issue": stripped,
                "severity": sev_match.group(1),
                "fix": "reported",
            })
    return findings


def get_severity_score(severity: str) -> float:
    return SEVERITY_SCORE.get(severity.lower(), 1)


def process_all():
    imp = init_state()
    start_time = time.time()

    # 1) Scan all agent output files newer than last run
    last_state = SELFIMPROVE / "last_bridge_run.txt"
    last_run = 0.0
    if last_state.exists():
        try:
            last_run = float(last_state.read_text().strip())
        except:
            pass

    total_new_entries = 0
    total_findings = 0
    for job_id, fpath in scan_agent_outputs():
        mtime = fpath.stat().st_mtime
        if mtime <= last_run:
            continue  # already processed

        text = fpath.read_text(encoding="utf-8", errors="replace")
        agent_name = infer_agent_name(job_id)

        # Log as learning entry
        imp.log_learning(
            topic=f"agent:{agent_name}",
            insight=f"Agent {agent_name} ran at {datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()}"
        )
        total_new_entries += 1

        # Parse findings
        findings = parse_findings(text)
        total_findings += len(findings)

        # Gain experience
        chakra = AGENT_CHAKRA_MAP.get(agent_name, "general")
        exp_gain = 5 + len(findings) * 2 + sum(get_severity_score(f["severity"]) for f in findings)
        imp.gain_experience(chakra, exp_gain)

        # Practice skills
        skills = AGENT_SKILL_MAP.get(agent_name, [])
        for sk in skills:
            imp.practice_skill(sk, duration=1 + len(findings) * 0.5)

        # Doctor-ize findings
        if findings:
            imp.doctor_reports.append({
                "timestamp": mtime,
                "agent": agent_name,
                "job_id": job_id,
                "findings": findings,
                "file": str(fpath),
            })

    # 2) Run doctor
    doctor = imp.run_doctor()

    # 3) Check for achievement unlocks
    chakra_count = len(imp.chakras)
    total_skill_level = sum(s.level for s in imp.skills.values())

    if chakra_count >= 5:
        imp.unlock_achievement(
            "Multi-Chakra Awakening",
            f"Activated {chakra_count} chakras across the agent system",
            category="system",
        )
    if total_skill_level >= 10:
        imp.unlock_achievement(
            "Skill Apprentice",
            f"Aggregate skill level {total_skill_level:.1f} across all agent skills",
            category="system",
        )
    if len(imp.achievements) >= 3:
        imp.unlock_achievement(
            "Achievement Collector",
            f"Unlocked {len(imp.achievements)} achievements",
            category="meta",
        )

    # Save last run time
    last_state.write_text(str(time.time()))

    stats = imp.get_stats()
    return {
        "new_log_entries": total_new_entries,
        "new_findings": total_findings,
        "chakras": stats["chakras"],
        "skills": stats["skills"],
        "achievements": stats["achievements"],
        "doctor_reports": stats["doctor_reports"],
        "recommendations": doctor.get("recommendations", []),
    }


def main():
    result = process_all()
    # JSON output for cron consumption
    print(json.dumps(result, indent=2))

    # Also print human-readable summary
    print(f"\n{'='*40}")
    print(f"SELF-IMPROVEMENT BRIDGE — {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*40}")
    print(f"  New log entries:  {result['new_log_entries']}")
    print(f"  New findings:     {result['new_findings']}")
    print(f"  Chakras tracked:  {result['chakras']}")
    print(f"  Skills tracked:   {result['skills']}")
    print(f"  Achievements:     {result['achievements']}")
    print(f"  Doctor reports:   {result['doctor_reports']}")
    if result["recommendations"]:
        print(f"\n  Recommendations:")
        for r in result["recommendations"]:
            print(f"    💡 {r}")
    if not result["new_log_entries"]:
        print("  (no new agent outputs since last bridge run)")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
