"""
generate_data.py — Generate all mock data for the Incident Analysis project.

Run from the project root:
    python scripts/generate_data.py

Outputs four CSVs to data/raw/:
    incidents.csv   — 150 incident tickets
    ris.csv         — ~200–350 remediation items linked to incidents
    controls.csv    — 30 IT/security controls
    mappings.csv    — control-to-RI mappings (with intentional gaps)

All randomness uses SEED=42 for full reproducibility.
"""

import os
import random
from datetime import datetime, timedelta

import pandas as pd
from faker import Faker

# ---------------------------------------------------------------------------
# Configuration constants — change these to adjust data shape
# ---------------------------------------------------------------------------

SEED = 42
N_INCIDENTS = 150
MIN_RIS_PER_INCIDENT = 1
MAX_RIS_PER_INCIDENT = 3
N_CONTROLS = 30
MAPPING_COVERAGE_RATE = 0.70   # 70% of RIs mapped; 30% intentionally unmapped
CONTROL_OVERREP_COUNT = 5      # these controls get extra mappings
ZERO_COVERAGE_CONTROLS = 8     # these controls get NO mappings (guaranteed gap)

BASE_DATE = datetime(2024, 7, 1)
END_DATE  = datetime(2026, 2, 1)

TEAMS = [
    "Infrastructure",
    "Security",
    "Networking",
    "DevOps",
    "Cloud Platform",
    "Database Administration",
    "Application Support",
    "IT Operations",
    "Middleware",
    "End User Computing",
    "Identity & Access Management",
    "Change Management",
    "Release Engineering",
    "Monitoring & Observability",
    "Backup & Recovery",
    "Vulnerability Management",
    "Compliance",
    "Service Desk",
    "Architecture",
    "Data Engineering",
]

CATEGORIES = ["Systems", "Technology", "Hardware"]

SEVERITIES        = ["P1", "P2", "P3", "P4"]
SEVERITY_WEIGHTS  = [0.10, 0.25, 0.40, 0.25]

INCIDENT_STATUSES        = ["Open", "In Progress", "Resolved", "Closed"]
INCIDENT_STATUS_WEIGHTS  = [0.05, 0.10, 0.30, 0.55]

RI_STATUSES       = ["Open", "In Progress", "Closed"]
RI_STATUS_WEIGHTS = [0.20, 0.30, 0.50]

RI_PRIORITIES        = ["High", "Medium", "Low"]
RI_PRIORITY_WEIGHTS  = [0.30, 0.45, 0.25]

AFFECTED_SYSTEMS = [
    "Active Directory", "Email Gateway", "Core Router", "Firewall Cluster",
    "CI/CD Pipeline", "Production Database", "Backup Server", "Load Balancer",
    "SIEM Platform", "Identity Provider", "API Gateway", "Container Registry",
    "DNS Server", "NTP Server", "Patch Management Server", "CMDB",
    "Monitoring Stack", "VPN Concentrator", "Storage Array", "Web Proxy",
]

INCIDENT_TITLE_TEMPLATES = {
    "Systems": [
        "{system} unavailable — service degradation reported",
        "Unexpected reboot on {system}",
        "{system} authentication failures spiking",
        "High CPU utilisation on {system}",
        "{system} disk space threshold breached",
        "Scheduled job failure on {system}",
        "{system} connection pool exhausted",
        "{system} process crash — automatic restart triggered",
        "Replication lag detected on {system}",
    ],
    "Technology": [
        "SSL certificate expiry on {system}",
        "Software version mismatch detected on {system}",
        "{system} API returning 5xx errors",
        "Dependency vulnerability identified in {system}",
        "Configuration drift detected on {system}",
        "{system} deployment pipeline broken",
        "Licensing compliance issue on {system}",
        "Deprecated library in use on {system}",
        "Security patch missing on {system}",
    ],
    "Hardware": [
        "NIC failure on {system} host",
        "RAID degraded on {system}",
        "Power supply failure — {system}",
        "Fan speed alarm on {system}",
        "Memory bank error detected on {system}",
        "Storage controller firmware mismatch on {system}",
        "KVM switch unresponsive — {system} console unavailable",
        "Hard drive pre-failure warning on {system}",
        "Temperature threshold exceeded on {system}",
    ],
}

RI_TITLE_TEMPLATES = [
    "Apply emergency patch to {system}",
    "Review and rotate credentials for {system}",
    "Update firewall rules to restrict access to {system}",
    "Conduct root cause analysis for {system} failure",
    "Implement monitoring alert for {system} threshold",
    "Restore {system} from verified backup",
    "Re-baseline configuration on {system}",
    "Document runbook for {system} incident response",
    "Schedule vulnerability scan on {system}",
    "Escalate {system} hardware replacement to vendor",
    "Review access permissions on {system}",
    "Update {system} SSL/TLS certificate",
    "Increase disk capacity on {system}",
    "Enable audit logging on {system}",
    "Conduct tabletop exercise for {system} failure scenario",
    "Update asset register entry for {system}",
    "Raise change request for {system} remediation",
    "Verify backup integrity for {system}",
]

# ---------------------------------------------------------------------------
# 30 hand-authored controls (name, description, domain)
# NOT Faker-generated — needs to sound like real IT controls
# ---------------------------------------------------------------------------

CONTROL_DEFINITIONS = [
    # Access Management (4)
    ("MFA Enforcement",
     "All privileged accounts must use multi-factor authentication.",
     "Access Management"),
    ("Least Privilege Access",
     "Users are granted minimum permissions required for their role.",
     "Access Management"),
    ("Access Review Cycle",
     "Quarterly review of all user access rights and entitlements.",
     "Access Management"),
    ("Privileged Access Workstation",
     "PAW must be used for all administrative sessions on critical systems.",
     "Access Management"),

    # Patch Management (4)
    ("Patch Cadence — Critical",
     "Critical patches must be applied within 7 days of release.",
     "Patch Management"),
    ("Patch Cadence — High",
     "High-severity patches applied within 30 days of release.",
     "Patch Management"),
    ("Patch Approval Process",
     "All patches must pass change approval before deployment to production.",
     "Patch Management"),
    ("End-of-Life System Tracking",
     "EOL systems tracked in CMDB with decommission plans maintained and reviewed quarterly.",
     "Patch Management"),

    # Logging & Monitoring (4)
    ("Centralised Log Aggregation",
     "All systems must forward logs to the central SIEM platform.",
     "Logging & Monitoring"),
    ("Alert Threshold Tuning",
     "Alert rules reviewed quarterly to reduce false positives and prevent alert fatigue.",
     "Logging & Monitoring"),
    ("Log Retention Policy",
     "Logs retained for minimum 12 months in accordance with compliance requirements.",
     "Logging & Monitoring"),
    ("Uptime Monitoring",
     "All production services monitored with maximum 5-minute health check intervals.",
     "Logging & Monitoring"),

    # Network Security (4)
    ("Firewall Rule Review",
     "Firewall rules reviewed every 6 months for necessity and least-privilege compliance.",
     "Network Security"),
    ("Network Segmentation",
     "Production, staging, and development networks must be isolated at layer 3.",
     "Network Security"),
    ("Intrusion Detection",
     "IDS signatures updated weekly and all alerts triaged within 4 hours.",
     "Network Security"),
    ("Remote Access Control",
     "VPN access restricted to approved endpoints with valid certificates.",
     "Network Security"),

    # Backup & Recovery (3)
    ("Backup Verification",
     "Backup integrity verified monthly via restore test to isolated environment.",
     "Backup & Recovery"),
    ("Offsite Backup Storage",
     "Critical backups replicated to a geographically separate site daily.",
     "Backup & Recovery"),
    ("RTO/RPO Documentation",
     "Recovery Time and Point Objectives documented and reviewed annually for all critical systems.",
     "Backup & Recovery"),

    # Configuration Management (4)
    ("Baseline Configuration",
     "Approved hardening baselines applied to all new system builds before production promotion.",
     "Configuration Management"),
    ("Configuration Drift Detection",
     "Automated scanning detects and alerts on configuration drift within 24 hours.",
     "Configuration Management"),
    ("Asset Inventory Accuracy",
     "Asset register updated within 24 hours of any hardware or software change.",
     "Configuration Management"),
    ("Secrets Management",
     "No credentials stored in source code or config files; all secrets stored in approved vault.",
     "Configuration Management"),

    # Change Control (3)
    ("Change Freeze Windows",
     "No changes permitted during business-critical periods without CAB emergency approval.",
     "Change Control"),
    ("CAB Approval Mandatory",
     "All standard changes require Change Advisory Board sign-off before implementation.",
     "Change Control"),
    ("Rollback Plan Required",
     "Every change request must include a tested rollback procedure before CAB submission.",
     "Change Control"),

    # Vulnerability Management (4)
    ("Vulnerability Scan Cadence",
     "Authenticated vulnerability scans run weekly on all in-scope assets.",
     "Vulnerability Management"),
    ("CVE Triage SLA",
     "All CVEs triaged and assigned to owning team within 48 hours of publication.",
     "Vulnerability Management"),
    ("Penetration Test Annual",
     "Annual penetration test covering all external-facing systems by approved third party.",
     "Vulnerability Management"),
    ("Risk Acceptance Process",
     "Unmitigated vulnerabilities require formal risk acceptance signed off by CISO.",
     "Vulnerability Management"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_date(start: datetime, end: datetime, rng: random.Random) -> datetime:
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def weighted_choice(choices, weights, rng: random.Random):
    return rng.choices(choices, weights=weights, k=1)[0]


def make_incident_description(fake: Faker, system: str, severity: str) -> str:
    impact = {
        "P1": "Critical business impact — all users affected and service completely unavailable.",
        "P2": "Significant impact — multiple teams affected with partial service degradation.",
        "P3": "Moderate impact — limited user base affected, workaround available.",
        "P4": "Low impact — single user or non-production environment affected.",
    }.get(severity, "Impact under assessment.")
    return (
        f"{fake.sentence()} "
        f"{impact} "
        f"Affected system: {system}. "
        f"{fake.sentence()} "
        f"Initial investigation indicates {fake.bs()}."
    )


def make_ri_description(fake: Faker, system: str) -> str:
    return (
        f"{fake.sentence()} "
        f"This remediation item relates to the affected system: {system}. "
        f"{fake.sentence()}"
    )


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def main():
    rng = random.Random(SEED)
    fake = Faker()
    fake.seed_instance(SEED)

    os.makedirs("data/raw", exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Controls
    # ------------------------------------------------------------------
    controls_rows = []
    for i, (name, desc, domain) in enumerate(CONTROL_DEFINITIONS, start=1):
        controls_rows.append({
            "control_id":          f"CTL-{i:03d}",
            "control_name":        name,
            "control_description": desc,
            "control_domain":      domain,
        })
    controls_df = pd.DataFrame(controls_rows)
    all_control_ids = list(controls_df["control_id"])

    # ------------------------------------------------------------------
    # 2. Incidents
    # ------------------------------------------------------------------
    incidents_rows = []
    for i in range(1, N_INCIDENTS + 1):
        category      = weighted_choice(CATEGORIES, [1, 1, 1], rng)
        severity      = weighted_choice(SEVERITIES, SEVERITY_WEIGHTS, rng)
        status        = weighted_choice(INCIDENT_STATUSES, INCIDENT_STATUS_WEIGHTS, rng)
        team          = rng.choice(TEAMS)
        system        = rng.choice(AFFECTED_SYSTEMS)
        title_tmpl    = rng.choice(INCIDENT_TITLE_TEMPLATES[category])
        title         = title_tmpl.format(system=system)
        description   = make_incident_description(fake, system, severity)
        date_raised   = random_date(BASE_DATE, END_DATE, rng)

        if status in ("Resolved", "Closed"):
            date_closed = date_raised + timedelta(days=rng.randint(1, 30))
            date_closed_str = date_closed.strftime("%Y-%m-%d")
        else:
            date_closed_str = ""

        incidents_rows.append({
            "incident_id":     f"INC-{i:04d}",
            "title":           title,
            "description":     description,
            "category":        category,
            "severity":        severity,
            "status":          status,
            "date_raised":     date_raised.strftime("%Y-%m-%d"),
            "date_closed":     date_closed_str,
            "team":            team,
            "affected_system": system,
        })

    incidents_df = pd.DataFrame(incidents_rows)

    # ------------------------------------------------------------------
    # 3. Remediation Items
    # ------------------------------------------------------------------
    ris_rows = []
    ri_counter = 1

    for _, inc_row in incidents_df.iterrows():
        n_ris = rng.randint(MIN_RIS_PER_INCIDENT, MAX_RIS_PER_INCIDENT)
        inc_date = datetime.strptime(inc_row["date_raised"], "%Y-%m-%d")
        system = inc_row["affected_system"]

        for _ in range(n_ris):
            title_tmpl  = rng.choice(RI_TITLE_TEMPLATES)
            title       = title_tmpl.format(system=system)
            description = make_ri_description(fake, system)
            status      = weighted_choice(RI_STATUSES, RI_STATUS_WEIGHTS, rng)
            priority    = weighted_choice(RI_PRIORITIES, RI_PRIORITY_WEIGHTS, rng)
            due_date    = inc_date + timedelta(days=rng.randint(14, 90))

            # 60% chance owner team is same as incident team
            if rng.random() < 0.60:
                owner_team = inc_row["team"]
            else:
                owner_team = rng.choice(TEAMS)

            ris_rows.append({
                "ri_id":       f"RI-{ri_counter:04d}",
                "incident_id": inc_row["incident_id"],
                "title":       title,
                "description": description,
                "status":      status,
                "priority":    priority,
                "owner_team":  owner_team,
                "due_date":    due_date.strftime("%Y-%m-%d"),
            })
            ri_counter += 1

    ris_df = pd.DataFrame(ris_rows)
    all_ri_ids = list(ris_df["ri_id"])

    # ------------------------------------------------------------------
    # 4. Mappings — with intentional gaps
    # ------------------------------------------------------------------

    # Step A: select 70% of RIs to receive at least one mapping
    covered_count = int(len(all_ri_ids) * MAPPING_COVERAGE_RATE)
    covered_ris   = rng.sample(all_ri_ids, covered_count)

    mapping_set = set()

    # Step B: assign 1–3 random controls to each covered RI
    for ri_id in covered_ris:
        n_controls = rng.randint(1, 3)
        assigned   = rng.sample(all_control_ids, n_controls)
        for ctrl_id in assigned:
            mapping_set.add((ctrl_id, ri_id))

    # Step C: over-represent 5 controls (they appear in many more mappings)
    overrep_controls = rng.sample(all_control_ids, CONTROL_OVERREP_COUNT)
    for ctrl_id in overrep_controls:
        extra_ris = rng.sample(covered_ris, min(20, len(covered_ris)))
        for ri_id in extra_ris:
            mapping_set.add((ctrl_id, ri_id))

    # Step D: force 8 controls to have zero coverage
    # Pick from controls not already in the overrep set
    eligible_for_gap = [c for c in all_control_ids if c not in overrep_controls]
    zero_coverage    = rng.sample(eligible_for_gap, ZERO_COVERAGE_CONTROLS)
    mapping_set      = {(c, r) for c, r in mapping_set if c not in zero_coverage}

    mappings_df = pd.DataFrame(list(mapping_set), columns=["control_id", "ri_id"])
    mappings_df = mappings_df.sort_values(["control_id", "ri_id"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    # 5. Save
    # ------------------------------------------------------------------
    controls_df.to_csv("data/raw/controls.csv",  index=False)
    incidents_df.to_csv("data/raw/incidents.csv", index=False)
    ris_df.to_csv("data/raw/ris.csv",             index=False)
    mappings_df.to_csv("data/raw/mappings.csv",   index=False)

    # Summary
    mapped_ri_ids = set(mappings_df["ri_id"].unique())
    coverage_rate = len(mapped_ri_ids) / len(all_ri_ids)
    zero_cov_controls = [
        c for c in all_control_ids
        if c not in mappings_df["control_id"].values
    ]

    print("=" * 50)
    print("Data generation complete.")
    print("=" * 50)
    print(f"  Incidents  : {len(incidents_df)}")
    print(f"  RIs        : {len(ris_df)}")
    print(f"  Controls   : {len(controls_df)}")
    print(f"  Mappings   : {len(mappings_df)}")
    print(f"  RI coverage: {coverage_rate:.1%}")
    print(f"  Zero-coverage controls: {len(zero_cov_controls)} → {zero_cov_controls}")
    print("=" * 50)
    print("Files written to data/raw/")


if __name__ == "__main__":
    main()
