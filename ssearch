#!/usr/bin/env python3
"""
Version: 4.93
----------------------------------------------------------------------------
Script Name   : ssearch
Author        : Matthew Boucher
Created       : 2025-05-31
Last Update   : 2025-07-10
Location      : /nethome/{current_user}/scriptdata/thevault
Base Path     : /nethome/{current_user}/scriptdata
Files Read    : see "FILES LIST" block below
Files Write   : see "FILES LIST" block below
Log Path      : /nethome/{current_user}/scriptdata/thevault/logs/ssearch.txt

Script Arguments:
  -s, --s <term>         Required unless --fields. Search term (one "*" wildcard allowed).
  --all                  Optional. Search all lines for the term.
  --start <PREFIX>       Optional. Only hostnames starting with PREFIX.
  -n, --normalize        Optional. Search using prefix before first dot without digits.
  --dryrun               Optional. Print commands only.
  --dryrun-only          Exit immediately after parsing.
  --refresh              Optional. Perform background refresh of stale files.
  --force                Optional. Force values into one or more fields.
  --category VALUE       Optional. Force 'category' field to VALUE.
  --fields               Optional. List fields and exit.

Fields searched (submenu?):
  category - none
  classification - none
  dns_domain - none
  environment - none
  managed_by - none
  managed_by_group - none
  manufacturer - none
  monitor - none
  os - submenu
  owned_by - none
  supported_by - none
  sys_id - none
  sys_class_name - none
  os_version - none
  u_departmen - none
  u_dr_tier - none
  u_grouping - none
  u_gt_inventory - none
  host_name - none
  u_ip_address - none
  u_oit_managed - submenu
  u_owned_by - none
  u_os_version - none
  u_patch_group - submenu
  u_patch_indentifier - none
  u_sla_type - submenu
  u_support_group - none
  u_tier_level - none
  u_internal_support_hours - submenu

Steps:
 1) Domain discovery
    Purpose : Derive FQDN & DNS domain.
    Behavior: Prints warning if unable to derive domain.

 2) Argument parsing
    Purpose : Parse & validate all flags.
    Behavior: Exits with usage or error on invalid combos.

 3) Flag validation
    Purpose : Ensure dryrun-only logic & sseta availability.
    Behavior: Exits on unmet requirements.

 4) Echo active arguments
    Purpose : Show which flags are active.
    Behavior: Prints "Active arguments: …" summary.

 5) Wildcard compilation
    Purpose : Convert single "*" wildcard to regex.
    Behavior: Error+exit if more than one wildcard.

 6) Vault discovery
    Purpose : List all ".txt" files in SEARCH_DIR.
    Behavior: Error+exit if vault missing or empty.

 7) Counter initialization
    Purpose : Prepare data structures for stats & fixes.
    Behavior: Sets up match_count, field_counts, etc.

 8) Per-file processing
    a) (--refresh only) Background refresh of stale files.
    b) Read file contents.
    c) Verify hostname present.
    d) Match logic (all/start/pattern).
    e) Metadata extraction & display.
    f) High-confidence fix detection.
    g) Patch-group fix detection.

 9) Summary & high-confidence fixes
    Purpose : Show stats, most common values, and offer fixes.

 10) Patch-group corrections
     Purpose : Auto-fix u_patch_indentifier when criteria met.

 11) Final summary & scanskip update
     Purpose : Log applied changes and append term to scanskip.txt.
----------------------------------------------------------------------------
"""
import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import getpass

CURRENT_USER = getpass.getuser()
BASE_PATH    = f"/nethome/{CURRENT_USER}/scriptdata"
VAULT_DIR    = os.path.join(BASE_PATH, "thevault")
SEARCH_DIR   = os.path.join(VAULT_DIR, "slistdata")
MLIST_DIR    = os.path.join(VAULT_DIR, "mlistdata")
CMDB_DIR     = os.path.join(BASE_PATH, "cmdbdownload")

FIELDS = [
    "category",
    "classification",
    "dns_domain",
    "environment",
    "managed_by",
    "managed_by_group",
    "manufacturer",
    "monitor",
    "os",
    "owned_by",
    "supported_by",
    "sys_id",
    "sys_class_name",
    "os_version",
    "u_departmen",
    "u_dr_tier",
    "u_grouping",
    "u_gt_inventory",
    "host_name",
    "u_ip_address",
    "u_oit_managed",
    "u_owned_by",
    "u_os_version",
    "u_patch_group",
    "u_patch_indentifier",
    "u_sla_type",
    "u_support_group",
    "u_tier_level",
    "u_internal_support_hours",
]

# Acceptable prefix variants for certain fields
HOST_NAME_ALIASES = ["host_name", "u_host_name", "host name", "hostname"]

# Fields that have predefined menus when forcing updates
SUBMENU_FIELDS = {
    "u_oit_managed",
    "u_sla_type",
    "u_patch_group",
    "os",
    "u_internal_support_hours",
}

EXCLUDED_KEYS = ["serial_number:", "sn_vul_qualys_host_id:"]

def print_banner_and_args() -> None:
    os.system("cls" if os.name == "nt" else "clear")
    banner_lines = [
        "#" * 70,
        "# ssearch  (version 4.93)",
        "#" * 70,
        "",
    ]
    print("\n".join(banner_lines))

    arg_cheatsheet = [
        "Arguments supported:",
        "  -s <term>           (required unless --fields)",
        "  --all               (optional – search all lines)",
        "  --start <PREFIX>    (optional – hostname prefix match)",
        "  -n, --normalize     (optional; search using prefix before first dot without digits)",
        "  --dryrun            (optional; print but do not execute fixes)",
        "  --dryrun-only       (optional; exit immediately)",
        "  --refresh           (optional; perform background refresh)",
        "  --force             (optional; force values via menu)",
        "  --category VALUE or -category VALUE",
        "                       (optional; force 'category' field to VALUE)",
        "  --fields            (optional; list available fields and exit)",
        "  --<FIELD> VALUE     (optional; force FIELD to VALUE)",
        "  --auto              (optional; run without prompts)",
    ]
    for line in arg_cheatsheet:
        print(line)
    print("-" * 70)
    print("Fields that may be updated:")
    for fld in FIELDS:
        suffix = " (submenu)" if fld in SUBMENU_FIELDS else ""
        print(f"  {fld}{suffix}")
    print("-" * 70 + "\n")

def is_blank(val: Optional[str]) -> bool:
    if val is None:
        return True
    stripped = val.strip()
    if ":" in stripped:
        return True
    if stripped.lower() in ("", "none", "n/a"):
        return True
    field_names = {f.lower() for f in FIELDS}
    field_names.update(alias.lower() for alias in HOST_NAME_ALIASES)
    return stripped.lower() in field_names

def extract_fields(lines: List[str]) -> Dict[str, str]:
    """Return metadata values for each field from slistdata files."""
    data = {field: "N/A" for field in FIELDS}
    for line in lines:
        stripped = line.lstrip()
        lower = stripped.lower()
        for field in FIELDS:
            if field == "host_name":
                for alias in HOST_NAME_ALIASES:
                    pre = f"{alias}:"
                    if lower.startswith(pre):
                        raw = stripped[len(pre):].strip()
                        data[field] = "N/A" if is_blank(raw) else raw
                        break
                else:
                    continue
                break
            prefix = f"{field}:"
            if lower.startswith(prefix):
                raw = stripped[len(prefix):].strip()
                data[field] = "N/A" if is_blank(raw) else raw
                break
    return data

def extract_mlist_fields(lines: List[str]) -> Dict[str, str]:
    """Parse mlistdata files using base field names without the 'u_' prefix."""
    base_map = {(f[2:] if f.startswith("u_") else f): f for f in FIELDS}
    data = {field: "N/A" for field in FIELDS}
    for line in lines:
        stripped = line.lstrip()
        lower = stripped.lower()
        for base, field in base_map.items():
            if field == "host_name":
                for alias in HOST_NAME_ALIASES:
                    pre = f"{alias}:"
                    if lower.startswith(pre):
                        raw = stripped[len(pre):].strip()
                        data[field] = "N/A" if is_blank(raw) else raw
                        break
                else:
                    continue
                break
            prefix = f"{base}:"
            if lower.startswith(prefix):
                raw = stripped[len(prefix):].strip()
                data[field] = "N/A" if is_blank(raw) else raw
                break
    return data

def update_local_txt(hostname: str, field: str, new_val: str) -> None:
    txt_path = os.path.join(SEARCH_DIR, f"{hostname}.txt")
    try:
        with open(txt_path, "r", errors="ignore") as fh:
            lines = fh.readlines()
        found = False
        with open(txt_path, "w") as fh:
            for L in lines:
                stripped = L.lstrip()
                prefixes = [f"{field}:"]
                if field == "host_name":
                    prefixes = [f"{alias}:" for alias in HOST_NAME_ALIASES]
                if any(stripped.lower().startswith(p) for p in prefixes):
                    leading_ws = L[: len(L) - len(stripped)]
                    fh.write(f"{leading_ws}{field}: {new_val}\n")
                    found = True
                else:
                    fh.write(L)
            if not found:
                fh.write(f"{field}: {new_val}\n")
        print(f"Alert: updated local file {hostname}.txt → {field}: {new_val}")
    except OSError as err:
        print(f"Warning: could not update {txt_path}: {err}", file=sys.stderr)

def log_correction(host: str, field: str, value: str) -> None:
    corr_dir = os.path.join(CMDB_DIR, "corrections")
    try:
        os.makedirs(corr_dir, exist_ok=True)
        path = os.path.join(corr_dir, f"{host}.txt")
        entry_prefix = f"{host},{field},{value}"
        lines = [ln.strip() for ln in open(path)] if os.path.isfile(path) else []
        if not any(ln.startswith(entry_prefix) for ln in lines):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(path, "a") as fh:
                fh.write(f"{entry_prefix},{ts}\n")
    except Exception:
        pass

def sanitize_owned_by(field: str, value: str) -> str:
    """Return sanitized value for owned_by fields."""
    target = "Anthony Guevara (OIT-Architecture & Infrastruct)"
    if field in ("owned_by", "u_owned_by") and value == target:
        return ""
    return value


def run_sseta(host: str, field: str, value: str) -> str:
    """Run sseta and log the change."""
    value = sanitize_owned_by(field, value)
    option = f"--{field}"
    cmd = ["sseta", "--fqdn", host, option, value]
    subprocess.run(cmd, check=True)
    log_correction(host, field, value)
    return value

def verify_update(host: str, field: str, expected: str) -> bool:
    """Return True if the slist output shows the expected value."""
    try:
        out = subprocess.run(
            ["slist", host], capture_output=True, text=True, check=True, timeout=10
        )
        lines = [ln.strip() for ln in out.stdout.splitlines()]
        if field == "host_name":
            targets = [f"{alias}: {expected}" for alias in HOST_NAME_ALIASES]
        else:
            targets = [f"{field}: {expected}"]
        found = any(t in lines for t in targets)
        text = next(
            (ln for ln in lines if any(t == ln for t in targets)),
            lines[0] if lines else "[not found]",
        )
        print(f"Check {host} {field}: {'PASS' if found else 'FAIL'} - {text}")
        return found
    except subprocess.TimeoutExpired:
        print(f"Verification timeout for {host} {field}", file=sys.stderr)
    except Exception as err:
        print(f"Verification error for {host} {field}: {err}", file=sys.stderr)
    return False

def derive_tier_level(hostname: str) -> str:
    hn = hostname.lower()
    if "prd" in hn or "prod" in hn:
        return "tier1"
    if "test" in hn:
        return "tier3"
    if "dev" in hn:
        return "tier4"
    return "tier2"

def derive_patch_identifier(pg: str) -> Optional[str]:
    """Return the patch identifier letter from a patch group string."""
    if not pg:
        return None
    group = pg.split("=", 1)[0].strip().upper()
    valid = {"A", "B", "C", "D", "CUSTOM"}
    return group if group in valid else None

def strip_digit_in_first_six(value: str) -> str:
    """If the 6th character of value is a digit, remove it."""
    if len(value) >= 6 and value[5].isdigit():
        return value[:5] + value[6:]
    return value

def main() -> None:
    print_banner_and_args()

    fqdn = socket.getfqdn()
    domain = fqdn.split(".", 1)[1] if "." in fqdn else ""
    if not domain:
        print(f"Warning: could not derive domain from fqdn='{fqdn}'.", file=sys.stderr)

    parser = argparse.ArgumentParser(
        prog="ssearch",
        description=(
            "Search .txt files by server name (or all fields) with wildcard/prefix "
            "support, and always apply high-confidence fixes."
        ),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="Search all lines")
    group.add_argument(
        "--start",
        metavar="PREFIX",
        help="Server names that start with PREFIX (mutually exclusive with --all)",
    )
    parser.add_argument("-n", "--normalize", action="store_true", help="Search using prefix before first dot without digits")
    parser.add_argument(
        "-s",
        "--s",
        dest="search_term",
        help='String to search for (one "*" wildcard allowed)',
    )
    parser.add_argument(
        "--dryrun", action="store_true", help="Print but do not execute fixes"
    )
    parser.add_argument(
        "--dryrun-only",
        action="store_true",
        help="Exit immediately after parsing",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Perform background refresh of stale vault files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force values into specified fields",
    )
    parser.add_argument(
        "--category",
        "-category",
        dest="category",
        metavar="VALUE",
        help="Force 'category' field to VALUE",
    )
    parser.add_argument(
        "--fields",
        action="store_true",
        help="List fields and exit"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run without prompts"
    )
    # add per-field arguments so each metadata key can be forced via CLI
    for fld in FIELDS:
        if fld == "category":
            continue  # handled separately above
        parser.add_argument(
            f"--{fld}",
            dest=f"field_{fld}",
            metavar="VALUE",
            help=f"Force {fld} to VALUE",
        )
    args = parser.parse_args()

    if args.fields:
        print("Available fields:")
        for fld in FIELDS:
            print(f"  {fld}")
        return

    if not args.search_term:
        parser.error("-s is required unless --fields is used")

    if args.dryrun_only:
        print("Dryrun-only flag set. Exiting.")
        sys.exit(0)

    search_term  = args.search_term
    search_all   = args.all
    start_prefix = args.start
    normalize    = args.normalize
    apply_fixes  = True
    dryrun       = args.dryrun
    auto_mode    = args.auto
    if normalize:
        base = search_term.split(".", 1)[0]
        base = re.sub(r"\d+", "", base)
        search_term = base

    active = []
    if normalize:
        active.append("--normalize")
    if search_all:
        active.append("--all")
    if start_prefix:
        active.append(f"--start {start_prefix}")
    if dryrun:
        active.append("--dryrun")
    if args.dryrun_only:
        active.append("--dryrun-only")
    if args.refresh:
        active.append("--refresh")
    if args.force:
        active.append("--force")
    if args.category:
        active.append(f"--category {args.category}")
    if auto_mode:
        active.append("--auto")
    # indicate that fixes are always applied
    active.append("--fix")
    active.append(f"--s {search_term}")
    if active:
        print("Active arguments:", " ".join(active), "\n")

    force_values: Dict[str, str] = {
        fld: getattr(args, f"field_{fld}", None)
        for fld in FIELDS
        if getattr(args, f"field_{fld}", None) is not None
    }
    if args.force:
        if auto_mode:
            print("Warning: --force ignored in --auto mode (requires interaction)")
        else:
            while True:
                for i, fld in enumerate(FIELDS, 1):
                    print(f"{i}) {fld}")
                choice = input("Select field number to force (Enter to finish): ").strip()
                if not choice:
                    break
                if choice.isdigit() and 1 <= int(choice) <= len(FIELDS):
                    fld = FIELDS[int(choice) - 1]
                    if fld == "u_patch_group":
                        pg_opts = {
                            "A": "A = 1st Thursday after Patch Tuesday",
                            "B": "B = 2nd Thursday after Patch Tuesday",
                            "C": "C = 3rd Thursday after Patch Tuesday",
                            "D": "D = 4th Thursday after Patch Tuesday",
                            "0": "CUSTOM",
                        }
                        print("u_patch_group options:")
                        for key, desc in pg_opts.items():
                            print(f"{key}) {desc}")
                        while True:
                            sel = input("Select option [A-D/0]: ").strip().upper()
                            if sel in pg_opts:
                                val = "CUSTOM" if sel == "0" else sel
                                break
                            print("Invalid selection.")
                    elif fld == "u_sla_type":
                        sla_opts = {
                            "vm-managed": "vm-managed",
                            "vm-non-managed": "vm-non-managed",
                            "physical-managed": "physical-managed",
                            "physical-non-managed": "physical-non-managed",
                        }
                        print("u_sla_type options:")
                        for k, desc in sla_opts.items():
                            print(f"{k}) {desc}")
                        while True:
                            sel = input(
                                "Select option (vm-managed/vm-non-managed/physical-managed/physical-non-managed): "
                            ).strip()
                            if sel in sla_opts:
                                val = sla_opts[sel]
                                break
                            print("Invalid selection.")
                    elif fld == "u_oit_managed":
                        while True:
                            print("u_oit_managed options:")
                            print("1) true")
                            print("2) false")
                            sel = input("Select option (1/2, Enter to skip): ").strip()
                            if not sel:
                                break
                            if sel == "1":
                                val = "true"
                                break
                            elif sel == "2":
                                val = "false"
                                break
                            else:
                                print("Invalid selection.")
                        if not sel:
                            continue
                    elif fld == "u_internal_support_hours":
                        ish_opts = {
                            "24x7": "24x7",
                            "8x5": "8x5",
                        }
                        print("u_internal_support_hours options:")
                        for k, desc in ish_opts.items():
                            print(f"{k}) {desc}")
                        while True:
                            sel = input("Select option (24x7/8x5): ").strip()
                            if sel in ish_opts:
                                val = ish_opts[sel]
                                break
                            print("Invalid selection.")
                    elif fld == "os":
                        os_opts = {
                            "1": "Linux Red Hat",
                            "2": "Linux Ubuntu",
                            "3": "Windows Server",
                        }
                        print("OS options:")
                        for num, desc in os_opts.items():
                            print(f"{num}) {desc}")
                        while True:
                            sel = input("Select option (1/2/3): ").strip()
                            if sel in os_opts:
                                val = os_opts[sel]
                                break
                            print("Invalid selection.")
                    else:
                        val = input(f"Enter value for {fld}: ").strip()
                    force_values[fld] = val
                else:
                    print("Invalid selection.")

    if args.category:
        force_values["category"] = args.category

    pattern = None
    if "*" in search_term:
        if search_term.count("*") > 1:
            print("Error: only one '*' wildcard allowed.", file=sys.stderr)
            sys.exit(1)
        prefix, suffix = map(re.escape, search_term.split("*", 1))
        pattern = re.compile(prefix + ".*" + suffix)

    if not os.path.isdir(SEARCH_DIR):
        print(f"Error: vault not found → {SEARCH_DIR}", file=sys.stderr)
        sys.exit(1)

    txt_files = [f for f in os.listdir(SEARCH_DIR) if f.endswith(".txt")]
    if not txt_files:
        print("No .txt files in vault.", file=sys.stderr)
        sys.exit(0)

    total_files = len(txt_files)
    slistdata_count = sum(
        1
        for f in txt_files
        if (
            (pattern and pattern.search(f[:-4]))
            or (not pattern and search_term in f)
        )
    )

    mlist_files = (
        [f for f in os.listdir(MLIST_DIR) if f.endswith(".txt")] if os.path.isdir(MLIST_DIR) else []
    )
    mlistdata_count = sum(
        1
        for f in mlist_files
        if (
            (pattern and pattern.search(f[:-4]))
            or (not pattern and search_term in f)
        )
    )

    print(f"\nFiles checked: {total_files}\n")
    print(f"slistdata check:{slistdata_count}")
    print(f"mlistdata check:{mlistdata_count}")
    print(
        f"Searching for: '{search_term}' (search_all={search_all}, start_prefix={start_prefix})\n"
    )

    print("--- Starting slistdata scan ---")

    match_count = 0
    matched_hosts: List[str] = []
    matches_by_host: Dict[str, List[str]] = {}
    field_occurrences: Dict[str, List[str]] = {}
    field_file_counts: Dict[str, int]      = {}
    field_blank_counts: Dict[str, int]     = {}
    field_source_tracker: Dict[str, Dict[str, Counter]] = {
        fld: {"slist": Counter(), "mlist": Counter()} for fld in FIELDS
    }
    high_confidence: Dict[str, Dict]       = {}
    updated_counts: Dict[str, int]         = {fld: 0 for fld in FIELDS}
    patch_group_fixes: List[Tuple[str, str, str]] = []
    manufacturer_fixes: List[Tuple[str, str, str]] = []
    network_device_fixes: List[Tuple[str, str, str]] = []
    host_name_fixes: List[Tuple[str, str]] = []
    ip_lookup_fixes: List[Tuple[str, str]] = []
    blank_targets_by_field: Dict[str, List[Tuple[str, str]]] = {}
    changes_made = False
    metadata_by_host: Dict[str, Dict[str, str]] = {}
    metadata_source_by_host: Dict[str, Dict[str, str]] = {}

    today_tm  = time.localtime()
    today_key = (today_tm.tm_year, today_tm.tm_yday)

    for filename in txt_files:
        hostname  = filename[:-4]
        full_path = os.path.join(SEARCH_DIR, filename)

        # 8-a) background refresh if stale (only when --refresh)
        if args.refresh:
            file_ctime = time.localtime(os.path.getctime(full_path))
            if (file_ctime.tm_year, file_ctime.tm_yday) != today_key:
                print(f"Starting background refresh for {hostname}")
                try:
                    with open(full_path, "w") as fh:
                        subprocess.run(["slist", hostname], stdout=fh, timeout=10)
                except subprocess.TimeoutExpired:
                    print(f"Refresh timeout for {hostname}", file=sys.stderr)

        matched = False
        matches:     List[str] = []
        all_lines:   List[str] = []

        try:
            with open(full_path, "r", errors="ignore") as fh:
                all_lines = [ln.rstrip("\n") for ln in fh]
        except OSError as err:
            print(f"Warning: could not read {filename}: {err}", file=sys.stderr)
            continue

        if not any(hostname in L for L in all_lines):
            print(f"Warning: hostname '{hostname}' missing inside {filename}")

        if search_all:
            for stripped in all_lines:
                if any(excl in stripped for excl in EXCLUDED_KEYS):
                    continue
                if (pattern and pattern.search(stripped)) or (not pattern and search_term in stripped):
                    matches.append(stripped)
            matched = bool(matches)
        elif start_prefix:
            matched = hostname.startswith(start_prefix)
        else:
            matched = (pattern and pattern.search(hostname)) or (not pattern and search_term in hostname)

        if matched:
            match_count += 1
            matched_hosts.append(hostname)
            matches_by_host[hostname] = matches
            metadata = extract_fields(all_lines)
            metadata_by_host[hostname] = metadata
            metadata_source_by_host[hostname] = {
                fld: ("slist" if not is_blank(metadata[fld]) else "") for fld in FIELDS
            }
            # per-host output deferred until sources known

    print(f"Total matching files: {match_count}")

    # Determine which fields remain blank after the slistdata scan
    missing_by_field: Dict[str, List[str]] = {fld: [] for fld in FIELDS}
    for host, meta in metadata_by_host.items():
        for fld in FIELDS:
            if is_blank(meta[fld]):
                missing_by_field[fld].append(host)

    remaining_fields = [f for f, hosts in missing_by_field.items() if hosts]
    if remaining_fields:
        print("Fields still missing after slistdata: " + ", ".join(remaining_fields))

    print("--- Starting mlistdata scan ---")

    mlist_match_count = 0
    # Second pass: look for missing data in mlistdata directory using base keys
    for host, meta in metadata_by_host.items():
        host_missing = [fld for fld in FIELDS if host in missing_by_field[fld]]
        if not host_missing:
            continue
        mpath = os.path.join(MLIST_DIR, f"{host}.txt")
        if not os.path.isfile(mpath):
            continue
        mlist_match_count += 1
        try:
            with open(mpath, "r", errors="ignore") as fh:
                m_lines = [ln.rstrip("\n") for ln in fh]
            mdata = extract_mlist_fields(m_lines)
        except OSError as err:
            print(f"Warning: could not read {mpath}: {err}", file=sys.stderr)
            continue
        replaced = []
        for fld in host_missing:
            val = mdata.get(fld)
            if val and not is_blank(val):
                meta[fld] = val
                metadata_source_by_host.setdefault(host, {})[fld] = "mlist"
                replaced.append(fld)
                missing_by_field[fld].remove(host)
        if replaced:
            print(f"[mlistdata] {host} filled fields: {', '.join(replaced)}")


    print(f"mlistdata matches: {mlist_match_count}")

    # Display per-host metadata with source information
    for host in matched_hosts:
        sources = {src for src in metadata_source_by_host.get(host, {}).values() if src}
        src_label = "+".join(sorted(sources)) if sources else "slist"
        print(f"=== {host} ({src_label}) ===")
        for line in matches_by_host.get(host, []):
            print(line)
        print("\n-- Metadata Fields --")
        meta = metadata_by_host[host]
        for field in FIELDS:
            print(f"{field}: {meta[field]}")
        print()

    # Recompute field statistics using updated metadata
    field_occurrences = {fld: [] for fld in FIELDS}
    field_file_counts = {fld: 0 for fld in FIELDS}
    field_blank_counts = {fld: 0 for fld in FIELDS}
    # skip u_ip_address from consensus calculations since IPs vary per host
    high_confidence = {fld: {"hosts": []} for fld in FIELDS if fld not in ("sys_id", "u_ip_address", "host_name")}
    patch_group_fixes = []
    manufacturer_fixes = []
    network_device_fixes = []

    for host, metadata in metadata_by_host.items():
        source_map = metadata_source_by_host.get(host, {})
        for field in FIELDS:
            val = metadata[field]
            if val != "N/A":
                src = source_map.get(field, "slist")
                if field == "u_gt_inventory":
                    cat = "VM" if val.lower().startswith("vm-") else "Other"
                else:
                    cat = val
                field_occurrences[field].append(cat)
                field_source_tracker[field][src][cat] += 1
                field_file_counts[field] += 1
            else:
                field_blank_counts[field] += 1

        for key in (fld for fld in FIELDS if fld not in ("sys_id", "u_ip_address", "host_name")):
            entry = {
                "hostname": host,
                "sys_id": metadata["sys_id"],
                "current_value": metadata[key],
            }
            if key == "manufacturer":
                entry["u_gt_inventory"] = metadata["u_gt_inventory"]
            high_confidence[key]["hosts"].append(entry)

        pg = metadata["u_patch_group"]
        pident = metadata["u_patch_indentifier"]
        if pg and "=" in pg and pident == "N/A":
            patch_group_fixes.append((host, metadata["sys_id"], pg.split("=", 1)[0].replace(" ", "")))
        elif pg == "CUSTOM" and pident == "N/A":
            patch_group_fixes.append((host, metadata["sys_id"], "CUSTOM"))

        if is_blank(metadata["manufacturer"]):
            inv = metadata["u_gt_inventory"]
            if host.lower().endswith(".ad.gatech.edu"):
                manufacturer_fixes.append((host, "Microsoft", "ad"))
            elif "vm-" in inv.lower():
                manufacturer_fixes.append((host, "VMware, Inc.", inv))
            else:
                manufacturer_fixes.append((host, "Hardware Unknown", inv))

        if is_blank(metadata.get("host_name")):
            derived_hn = host.split(".", 1)[0]
            host_name_fixes.append((host, derived_hn))

        if is_blank(metadata.get("u_ip_address")):
            try:
                out = subprocess.run(["host", host], capture_output=True, text=True, timeout=5)
                ip_info = out.stdout.strip().split()[-1] if out.returncode == 0 and out.stdout else "[lookup failed]"
            except Exception as err:
                ip_info = f"[lookup error: {err}]"
            ip_lookup_fixes.append((host, ip_info))

        if ".sw.gatech.edu" in host.lower() and "vm-" in metadata["u_gt_inventory"].lower():
            network_device_fixes.append((host, "Network Device", metadata["u_gt_inventory"]))


    proceed_all = False
    if (args.force or args.category) and force_values:
        pg_cycle = 0
        for host in matched_hosts:
            for field, intended in force_values.items():
                actual_val = intended
                if field == "u_patch_group" and intended == "C":
                    pg_cycle += 1
                    if pg_cycle % 3 == 0:
                        actual_val = "D"
                cmd = f'sseta --fqdn {host} --{field} "{actual_val}"'
                if dryrun:
                    print(f"[Dry-run] {cmd}")
                else:
                    print(f"Executing: {cmd}")
                    try:
                        actual_val = run_sseta(host, field, actual_val)
                        updated_counts[field] += 1
                        update_local_txt(host, field, actual_val)
                        success = verify_update(host, field, actual_val)
                        status = "updated" if success else "NOT updated"
                        print(f"Alert: {host} {field} {status}")
                        if field == "u_patch_group":
                            pid_val = derive_patch_identifier(actual_val)
                            if pid_val:
                                run_sseta(host, "u_patch_indentifier", pid_val)
                                updated_counts["u_patch_indentifier"] += 1
                                update_local_txt(host, "u_patch_indentifier", pid_val)
                                success2 = verify_update(host, "u_patch_indentifier", pid_val)
                                stat2 = "updated" if success2 else "NOT updated"
                                print(f"Alert: {host} u_patch_indentifier {stat2}")
                        changes_made = True
                    except subprocess.CalledProcessError as err:
                        print(f"Error: {err}", file=sys.stderr)
                    time.sleep(1)

    if match_count > 1:
        print("\n+------------------------------------------------------------+")
        print("| Most Common Field Values with Occurrence and Percentage    |")
        print("+------------------------------------------------------------+")
        for field in FIELDS:
            total  = field_file_counts[field]
            blanks = field_blank_counts[field]
            if total:
                most_common, count = Counter(field_occurrences[field]).most_common(1)[0]
                percent            = int(count / total * 100)
                display_val        = most_common if most_common != "N/A" else "[empty]"
                slc = field_source_tracker[field]["slist"].get(most_common, 0)
                mlc = field_source_tracker[field]["mlist"].get(most_common, 0)
                if slc > mlc:
                    src_label = "slist"
                elif mlc > slc:
                    src_label = "mlist"
                else:
                    src_label = "mixed"
                print(f"{field}: \"{display_val}\" ({src_label}) (appeared {count}/{total}, {percent}% ) [{blanks} blank]")
                if field in high_confidence and percent >= 50:
                    high_confidence[field].update({
                        "value": display_val,
                        "count": count,
                        "total": total,
                        "percent": percent,
                        "blanks": blanks,
                    })
            else:
                print(f"{field}: N/A [{blanks} blank]")
    proceed_all = False
    if any("value" in d for d in high_confidence.values()) or manufacturer_fixes or network_device_fixes or host_name_fixes or ip_lookup_fixes:
        print("\n+----------------------------+")
        print("| High Confidence Indicators |")
        print("+----------------------------+")
        blank_targets_by_field.clear()
        for field, data in high_confidence.items():
            blanks = [(h["hostname"], h["sys_id"]) for h in data["hosts"] if is_blank(h["current_value"])]
            if not blanks:
                continue
            consensus = data.get("value")
            if field == "manufacturer":
                print(f"{field}: derived from hostname or u_gt_inventory")
                for host, sid in blanks:
                    inv = next((h.get("u_gt_inventory", "") for h in data["hosts"] if h["hostname"] == host), "")
                    if host.lower().endswith(".ad.gatech.edu"):
                        intended = "Microsoft"
                        reason = "hostname contains .ad.gatech.edu"
                    else:
                        intended = "VMware, Inc." if "vm-" in inv.lower() else "Hardware Unknown"
                        reason = f"u_gt_inventory: {inv}"
                    print(f"  {host} → {intended} [{reason}]")
                continue
            if field == "dns_domain" and consensus is None:
                print(f"{field}: derive from hostname")
                for host, _ in blanks:
                    intended = host.split(".", 1)[1] if "." in host else ""
                    print(f"  {host} → {intended}")
                blank_targets_by_field[field] = blanks
                continue
            if consensus is None:
                continue
            print(f"{field}: \"{consensus}\" (consensus)")
            for host, sid in blanks:
                if field == "u_gt_inventory":
                    base_fqdn = host[:-11] if host.endswith(".gatech.edu") else host
                    base_fqdn = strip_digit_in_first_six(base_fqdn)
                    intended = f"vm-{base_fqdn}"
                elif field == "dns_domain":
                    intended = host.split(".", 1)[1] if "." in host else consensus
                elif field == "u_tier_level":
                    intended = derive_tier_level(host)
                else:
                    intended = consensus
                print(f"  {host} → {intended}")
            blank_targets_by_field[field] = blanks

        if network_device_fixes:
            print("u_gt_inventory: \"Network Device\" (precheck)")
            for host, _, inv in network_device_fixes:
                print(f"  {host} → Network Device [current: {inv}]")

            proceed_all = False
        if host_name_fixes:
            print("host_name: derived from hostname")
            for host, val in host_name_fixes:
                cmd_preview = f'sseta --fqdn {host} --host_name "{val}"'
                print(f"  {host} → {val}")
                print(f"    Command: {cmd_preview}")

            proceed_all = False
        if ip_lookup_fixes:
            print("u_ip_address: host lookup")
            for host, ip in ip_lookup_fixes:
                print(f"  {host} → {ip}")

        needs_updates = bool(blank_targets_by_field or patch_group_fixes or network_device_fixes or manufacturer_fixes or host_name_fixes)
        if apply_fixes and needs_updates:
            if auto_mode:
                proceed_all = True
            else:
                if blank_targets_by_field:
                    prompt = "\nCorrect missing fields? (y/n): "
                else:
                    prompt = "\nApply detected updates? (y/n): "
                resp = input(prompt).strip().lower()
                if resp == "y":
                    proceed_all = True
                else:
                    print("No updates applied.")
                    return

        if proceed_all and blank_targets_by_field:
            for field, host_list in list(blank_targets_by_field.items()):
                for host, sid in host_list:
                    if field == "u_gt_inventory":
                        base_fqdn = host[:-11] if host.endswith(".gatech.edu") else host
                        base_fqdn = strip_digit_in_first_six(base_fqdn)
                        intended = f"vm-{base_fqdn}"
                    elif field == "dns_domain":
                        intended = host.split(".", 1)[1] if "." in host else high_confidence[field]["value"]
                    elif field == "u_tier_level":
                        intended = derive_tier_level(host)
                    else:
                        intended = high_confidence[field]["value"]
                    cmd = f'sseta --fqdn {host} --{field} "{intended}"'
                    if dryrun:
                        print(f"[Dry-run] {cmd}")
                    else:
                        print(f"Executing: {cmd}")
                        try:
                            intended = run_sseta(host, field, intended)
                            updated_counts[field] += 1
                            update_local_txt(host, field, intended)
                            verify_update(host, field, intended)
                            if field == "u_patch_group":
                                pid_val = derive_patch_identifier(intended)
                                if pid_val:
                                    run_sseta(host, "u_patch_indentifier", pid_val)
                                    updated_counts["u_patch_indentifier"] += 1
                                    update_local_txt(host, "u_patch_indentifier", pid_val)
                                    verify_update(host, "u_patch_indentifier", pid_val)
                            changes_made = True
                        except subprocess.CalledProcessError as err:
                            print(f"Error: {err}", file=sys.stderr)
                        time.sleep(1)
            blank_targets_by_field.clear()


    if apply_fixes and patch_group_fixes and proceed_all:
        for host, sid, new_val in patch_group_fixes:
            cmd = f'sseta --fqdn {host} --u_patch_indentifier "{new_val}"'
            if dryrun:
                print(f"[Dry-run] {cmd}")
            else:
                print(f"Executing: {cmd}")
                try:
                    run_sseta(host, "u_patch_indentifier", new_val)
                    updated_counts["u_patch_indentifier"] += 1
                    update_local_txt(host, "u_patch_indentifier", new_val)
                    verify_update(host, "u_patch_indentifier", new_val)
                    changes_made = True
                except subprocess.CalledProcessError as err:
                    print(f"Error: {err}", file=sys.stderr)
                time.sleep(1)

    if apply_fixes and network_device_fixes and proceed_all:
        for host, new_val, _ in network_device_fixes:
            cmd = f'sseta --fqdn {host} --u_gt_inventory "{new_val}"'
            if dryrun:
                print(f"[Dry-run] {cmd}")
            else:
                print(f"Executing: {cmd}")
                try:
                    run_sseta(host, "u_gt_inventory", new_val)
                    updated_counts["u_gt_inventory"] += 1
                    update_local_txt(host, "u_gt_inventory", new_val)
                    verify_update(host, "u_gt_inventory", new_val)
                    changes_made = True
                except subprocess.CalledProcessError as err:
                    print(f"Error: {err}", file=sys.stderr)
                time.sleep(1)

    if apply_fixes and manufacturer_fixes and proceed_all:
        for host, new_val, _ in manufacturer_fixes:
            cmd = f'sseta --fqdn {host} --manufacturer "{new_val}"'
            if dryrun:
                print(f"[Dry-run] {cmd}")
            else:
                print(f"Executing: {cmd}")
                try:
                    run_sseta(host, "manufacturer", new_val)
                    updated_counts["manufacturer"] += 1
                    update_local_txt(host, "manufacturer", new_val)
                    verify_update(host, "manufacturer", new_val)
                    changes_made = True
                except subprocess.CalledProcessError as err:
                    print(f"Error: {err}", file=sys.stderr)
                time.sleep(1)

    if apply_fixes and host_name_fixes and proceed_all:
        for host, new_val in host_name_fixes:
            cmd = f'sseta --fqdn {host} --host_name "{new_val}"'
            if dryrun:
                print(f"[Dry-run] {cmd}")
            else:
                print(f"Executing: {cmd}")
                try:
                    run_sseta(host, "host_name", new_val)
                    updated_counts["host_name"] += 1
                    update_local_txt(host, "host_name", new_val)
                    success = verify_update(host, "host_name", new_val)
                    status = "updated" if success else "NOT updated"
                    print(f"Alert: {host} host_name {status}")
                    changes_made = True
                except subprocess.CalledProcessError as err:
                    print(f"Error: {err}", file=sys.stderr)
                time.sleep(1)

    if blank_targets_by_field:
        if auto_mode:
            return
        missing = ", ".join(blank_targets_by_field.keys())
        print(f"Missing fields: {missing}")

    print(f"\nSearch term used: '{search_term}'")
    if apply_fixes and not dryrun and any(updated_counts.values()):
        print("\nSummary of changes:")
        for fld, cnt in updated_counts.items():
            if cnt:
                print(f"  {fld}: {cnt}")

    if changes_made:
        wrapped = f"+{search_term}+"
        os.makedirs(CMDB_DIR, exist_ok=True)
        skip_file = os.path.join(CMDB_DIR, "scanskip.txt")
        existing  = {line.strip() for line in open(skip_file)} if os.path.isfile(skip_file) else set()
        if wrapped not in existing:
            with open(skip_file, "a") as sf:
                sf.write(wrapped + "\n")
            print(f"Alert: added '{wrapped}' to {skip_file}")
            print()

if __name__ == "__main__":
    main()

# ##############################################################################
# SCRIPT FOOTER - ssearch v4.93
# ##############################################################################
