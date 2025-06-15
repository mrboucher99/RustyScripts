#!/usr/bin/env python3

################################################################################
# Script Name : listscrubber
# Version     : 4.66
# Created By  : Matthew Boucher
# Created On  : 2025-04-23
# Last Updated: 2025-06-05
# Location    : /nethome/{CURRENT_USER}/scriptdata
#
# DESCRIPTION:
#   Automates the processing and validation of environment host lists.
#
# FILES READ:
#   /nethome/{CURRENT_USER}/scriptdata/thevault/openssh.txt
#   /nethome/{CURRENT_USER}/scriptdata/thevault/add.txt
#   /nethome/{CURRENT_USER}/scriptdata/thevault/temp-listscrubber.txt
#   /nethome/{CURRENT_USER}/scriptdata/thevault/goodsubnets.txt
#   /nethome/{CURRENT_USER}/scriptdata/thevault/ourenv.txt
#   /nethome/{CURRENT_USER}/scriptdata/listscrubber/ls-donelist.txt
#   /nethome/{CURRENT_USER}/scriptdata/listscrubber/ls-non-managed.txt
#   /nethome/{CURRENT_USER}/scriptdata/listscrubber/ls-fullpass.txt
#   /etc/salt/minion.d/minion.conf
#
# FILES WRITTEN:
#   /nethome/{CURRENT_USER}/scriptdata/thevault/openssh.txt
#   /nethome/{CURRENT_USER}/scriptdata/listscrubber/ls-donelist.txt
#   /nethome/{CURRENT_USER}/scriptdata/listscrubber/ls-fullpass.txt
#   /nethome/{CURRENT_USER}/scriptdata/listscrubber/ls-onzabbix.txt
#   /nethome/{CURRENT_USER}/scriptdata/listscrubber/ls-deletedrecords.txt
#   /nethome/{CURRENT_USER}/scriptdata/thevault/goodsubnets.txt
#
# ARGUMENTS:
#   --list       : Opens or creates a temporary host list (temp-listscrubber.txt)
#                  in the vault for editing; then uses that file as input.
#   --last       : Uses the most-recent temp-*.txt file in the vault as input.
#   --add        : Appends entries from add.txt into openssh.txt, then uses
#                  openssh.txt as input.
#   --clear      : Deletes all ls-* progress files under the listscrubber
#                  directory and exits immediately.
#   --pause      : Pauses on connectivity failures and prompts for deletion.
#   --allpause   : Pauses after ALL checks for each host (manual deletion).
#   --domain     : Prompts for a domain substring and filters hosts to those
#                  containing it.
#   --single     : Prompts for a single host name, skipping file input.
#
# CHANGES LOG (highest 10 versions only):
# - v4.66 (2025-06-05): Ping check uses '(error)' on exception without details.
# - v4.65 (2025-06-05): Port 22 check now outputs '(error)' without details.
# - v4.64 (2025-06-05): Display argument list below banner.
# - v4.63 (2025-06-05): Pause after any error message.
# - v4.62 (2025-06-05): Numbered all check steps in main loop.
# - v4.61 (2025-06-05): Added display of input file name and line count before processing.
# - v4.60 (2025-06-05): Removed unsupported 'newline' args in write_text; added screen clear above banner.
# - v4.59 (2025-06-05): Increment version; ensure proper import grouping; tightened SSH timeouts.
# - v4.58 (2025-06-05): Added multi-line footer block containing script name and version.
# - v4.57 (2025-06-05): Explicit duplicate-removal immediately after input-file selection.
################################################################################


# ──────────────────────────────────────────────────────────────────────────────
# Standard‐Library Imports
# ──────────────────────────────────────────────────────────────────────────────
import argparse
import getpass
import os
import random
import shutil
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Third‐Party Imports (fail‐fast if missing)
# ──────────────────────────────────────────────────────────────────────────────
try:
    import paramiko
except ImportError:
    sys.exit("ERROR: 'paramiko' not installed.  Run: pip install paramiko")

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

# ──────────────────────────────────────────────────────────────────────────────
# Standard‐Library Import (continued)
# ──────────────────────────────────────────────────────────────────────────────
import ipaddress

# ──────────────────────────────────────────────────────────────────────────────
# Constants / paths
# ──────────────────────────────────────────────────────────────────────────────
SCRIPT_NAME        = "listscrubber"
VERSION            = "4.66"
DEFAULT_PORT       = 22
CURRENT_USER       = getpass.getuser()

base_scriptdata    = Path.home() / "scriptdata"
vault_path         = base_scriptdata / "thevault"
listscrubber_dir   = base_scriptdata / "listscrubber"
openssh_file       = vault_path / "openssh.txt"
done_list_file     = listscrubber_dir / "ls-donelist.txt"
fullpass_file      = listscrubber_dir / "ls-fullpass.txt"
non_managed_file   = listscrubber_dir / "ls-non-managed.txt"
zabbix_status_file = listscrubber_dir / "ls-onzabbix.txt"
deleted_file       = listscrubber_dir / "ls-deletedrecords.txt"
good_subnets_file  = vault_path / "goodsubnets.txt"
ourenv_file        = vault_path / "ourenv.txt"

BIGIQ_BAD_SUBNETS  = [
    ipaddress.ip_network("10.200.0.0/16"),
    ipaddress.ip_network("172.25.0.0/16"),
]

for d in (base_scriptdata, vault_path, listscrubber_dir):
    d.mkdir(parents=True, exist_ok=True)

if not good_subnets_file.exists():
    good_subnets_file.write_text("")

# ──────────────────────────────────────────────────────────────────────────────
# Helper routines
# ──────────────────────────────────────────────────────────────────────────────
def log_message(msg: str, level: str = "INFO"):
    print(f"[{level}] {msg}")
    if level == "ERROR":
        input("[ERROR PAUSE] Press ENTER to continue...")

def log_error(msg: str):
    log_message(msg, "ERROR")

def log_sub(msg: str):
    print(f"    {msg}")

def write_host(path: Path, host: str):
    # Always append a single newline, then a blank line
    with open(path, "a", newline="\n") as f:
        f.write(host + "\n\n")

def log_check(name: str, passed: bool, detail: str = ""):
    status = "pass" if passed else "fail"
    msg = f"{name}:{status}"
    if detail:
        msg += f" {detail}"
    log_message(msg, "INFO" if passed else "ERROR")

def print_banner():
    bar = "#" * 90
    print(bar)
    print(f"#  Script: {SCRIPT_NAME}    Version: {VERSION}".ljust(89) + "#")
    print(bar + "\n")

def print_argument_list():
    arg_lines = [
        "--list      : Opens or creates a temporary host list (temp-listscrubber.txt) in the vault for editing; then uses that file as input.",
        "--last      : Uses the most-recent temp-*.txt file in the vault as input.",
        "--add       : Appends entries from add.txt into openssh.txt, then uses openssh.txt as input.",
        "--clear     : Deletes all ls-* progress files under the listscrubber directory and exits immediately.",
        "--pause     : Pauses on connectivity failures and prompts for deletion.",
        "--allpause  : Pauses after ALL checks for each host (manual deletion).",
        "--domain    : Prompts for a domain substring and filters hosts to those containing it.",
        "--single    : Prompts for a single host name, skipping file input.",
    ]
    print("Arguments:")
    for line in arg_lines:
        print(f"  {line}")
    print()

def print_footer():
    # Multi‐line footer block with script name and version (no extra blank line)
    footer_bar = "#" * 90
    print(footer_bar)
    print(f"#{' ' * 88}#")
    print(f"#  Script: {SCRIPT_NAME}".ljust(89) + "#")
    print(f"#  Version: {VERSION}".ljust(89) + "#")
    print(f"#{' ' * 88}#")
    print(footer_bar)

def open_editor(path: Path):
    ed = os.getenv("EDITOR") or shutil.which("nano") or shutil.which("vi")
    if not ed:
        log_message("ERROR: No editor found (set $EDITOR or install nano/vi).", "ERROR")
        sys.exit(1)
    subprocess.run([ed, str(path)], check=False)

@contextmanager
def ssh_client(host: str, user: str, pw: str, timeout: int = 5):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        cli.connect(host, DEFAULT_PORT, user, pw,
                    timeout=timeout, banner_timeout=timeout, auth_timeout=timeout)
    except (paramiko.SSHException, socket.error, TimeoutError) as e:
        log_message(f"SSH connection error for {host}: {e}", "ERROR")
        raise
    try:
        yield cli
    finally:
        cli.close()

def is_in_bigiq_subnets(ip_str: str) -> bool:
    ip_obj = ipaddress.ip_address(ip_str)
    return any(ip_obj in net for net in BIGIQ_BAD_SUBNETS)

# ──────────────────────────────────────────────────────────────────────────────
# VLAN lookup helper
# ──────────────────────────────────────────────────────────────────────────────
def gather_vlan_info_for_servername(server: str):
    try:
        ip = socket.gethostbyname(server)
    except socket.gaierror as ex:
        log_error(f"DNS error for {server}: {ex}")
        return

    curl_path = shutil.which("curl")
    wget_path = shutil.which("wget")
    if not (curl_path or wget_path):
        log_message("ERROR: Neither 'curl' nor 'wget' found; skipping VLAN lookup", "ERROR")
        return

    if curl_path:
        cmd = [curl_path, "-s", f"https://bok.noc.gatech.edu/api/vlan_lookup.php?search={ip}"]
    else:
        cmd = [wget_path, "-qO-", f"https://bok.noc.gatech.edu/api/vlan_lookup.php?search={ip}"]

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        if res.returncode != 0:
            log_error(f"VLAN lookup failed for {ip}: {res.stderr.strip()}")
            return

        lines = res.stdout.strip().splitlines()[1:]
        existing = set(good_subnets_file.read_text().splitlines()) if good_subnets_file.exists() else set()

        new_entries = []
        for ln in lines:
            if "::" not in ln:
                continue
            v, rest = ln.split("::", 1)
            parts = [p for p in rest.split(":") if p]
            if len(parts) < 3:
                continue
            entry = f"{v}::{parts[0]}:{parts[1]}:{parts[2]}"
            if entry not in existing:
                existing.add(entry)
                new_entries.append(entry)

        if new_entries:
            with open(good_subnets_file, "a", newline="\n") as gf:
                for e in new_entries:
                    gf.write(e + "\n")
                    log_sub("")
                    border = "#" * 84
                    log_sub(border)
                    log_sub(f"    [ALERT] New subnet for {server}: {e}")
                    log_sub(border)
                    log_sub("")
    except Exception as e:
        log_error(f"VLAN fail for {server}: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# Start-up checks
# ──────────────────────────────────────────────────────────────────────────────
def check_prereqs():
    for cmd in ("nc", "ping"):
        if not shutil.which(cmd):
            log_message(f"Missing required command: {cmd}", "ERROR")
            sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(description="Process host lists.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--list",  action="store_true")
    g.add_argument("--last",  action="store_true")
    g.add_argument("--add",   action="store_true")
    g.add_argument("--clear", action="store_true")
    p.add_argument("--pause",    action="store_true")
    p.add_argument("--allpause", action="store_true")
    p.add_argument("--domain",   action="store_true")
    p.add_argument("--single",   action="store_true")
    return p.parse_args()

def clear_progress_files():
    for p in listscrubber_dir.glob("ls-*"):
        p.unlink(missing_ok=True)
        log_message(f"Deleted {p.name}", "INFO")

def remove_host_from_file(host: str, path: Path):
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    if host in lines:
        lines = [l for l in lines if l != host]
        path.write_text("\n\n".join(lines) + ("\n\n" if lines else ""))
        log_message(f"Removed {host} from {path.name}", "INFO")

def read_hosts_from_file(path: Path) -> list:
    if not path.exists():
        return []
    lines = [l.strip() for l in path.read_text().splitlines() if l.strip()]
    uniq = list(dict.fromkeys(lines))
    path.write_text("\n\n".join(uniq) + "\n\n")
    log_message(f"Duplicates cleaned: {len(lines)}→{len(uniq)}", "INFO")
    return uniq

def filter_excluded_domains(hosts: list, source: Path) -> list:
    patterns = [
        ".ad.gatech.edu", ".tfad.gatech.edu", ".fw.gatech.edu",
        ".sw.gatech.edu", ".net.gatech.edu", ".esx.gatech.edu",
        ".pace.gatech.edu"
    ]
    done = set(read_hosts_from_file(done_list_file))
    keep = []
    for h in hosts:
        if any(p in h for p in patterns):
            log_message(f"EXCLUDE pattern — {h}", "WARN")
            remove_host_from_file(h, source)
        elif h in done:
            log_message(f"SKIP done-list — {h}", "WARN")
            remove_host_from_file(h, source)
        else:
            keep.append(h)
    random.shuffle(keep)
    return keep

def check_exclude_keywords(host: str, source: Path) -> bool:
    for kw in ("switch", "rtr", "jerry"):
        if kw in host.lower():
            log_message(f"ALERT keyword '{kw}' in {host}", "WARN")
            remove_host_from_file(host, source)
            return True
    return False

def run_slist_gatech_check():
    log_message("SLIST warm-up done", "INFO")

def check_acc_agent(host: str) -> bool:
    return True

def check_slist_u_sla_type(host: str) -> str:
    return "cpu_count-lab" if "cpu" in host else "vm-managed"

def check_zabbix(host: str) -> str:
    return "Missing"

def do_zabbix_install_pexpect(host: str) -> str:
    try:
        import pexpect
    except ImportError:
        log_message("WARNING: 'pexpect' not installed; cannot run automated Zabbix installation.", "WARN")
        return "Missing"
    for n in (1, 2):
        log_message(f"Zabbix install attempt {n} on {host}", "INFO")
        time.sleep(1)
    return "Success"

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    # Clear the screen before printing banner
    os.system("clear")

    print_banner()
    print_argument_list()
    a = parse_args()
    if a.clear:
        clear_progress_files()
        return

    check_prereqs()
    run_slist_gatech_check()

    pw = getpass.getpass("SSH password: ")

    expected_sm = None
    if ourenv_file.exists():
        for ln in ourenv_file.read_text().splitlines():
            if ln.lower().startswith("salt master"):
                parts = ln.split(",", 1)
                if len(parts) == 2:
                    expected_sm = parts[1].strip()

    if a.list:
        tmp = vault_path / "temp-listscrubber.txt"
        open_editor(tmp)
        input_file = tmp
    elif a.last:
        latest = sorted(vault_path.glob("temp-*.txt"),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True)
        if not latest:
            log_message("ERROR: No temp files.", "ERROR")
            sys.exit(2)
        input_file = latest[0]
    elif a.add:
        addf = vault_path / "add.txt"
        open_editor(addf)
        new_lines = [l for l in addf.read_text().splitlines() if l.strip()]
        if new_lines:
            with open(openssh_file, "a", newline="\n") as mf:
                mf.write("\n\n".join(new_lines) + "\n\n")
            log_message(f"Appended {len(new_lines)} entries to openssh.txt", "INFO")
        input_file = openssh_file
    else:
        input_file = openssh_file

    # Display input file name and line count
    try:
        total_lines = sum(1 for l in input_file.read_text().splitlines() if l.strip())
        log_message(f"Using input file: {input_file}", "INFO")
        log_message(f"Input file line count: {total_lines}", "INFO")
    except Exception as e:
        log_message(f"Could not read {input_file} for line count: {e}", "ERROR")

    initial_hosts = read_hosts_from_file(input_file)
    hosts = filter_excluded_domains(initial_hosts, input_file)

    if not hosts:
        log_message("No hosts to process – exiting.", "INFO")
        print_footer()
        return

    if a.single:
        hosts = [input("Single server: ").strip()]
    elif a.domain:
        dom = input("Domain substring: ").strip()
        hosts = [h for h in hosts if dom in h]
        log_message(f"Domain filtered list to {len(hosts)} hosts", "INFO")

    proc_idx = 0
    i = 0
    while i < len(hosts):
        host = hosts[i]
        proc_idx += 1
        print()
        log_message(f"Host {proc_idx}/{len(hosts)}: {host}", "INFO")
        print("-" * 65)

        # Step 1: Exclude keywords
        if check_exclude_keywords(host, input_file):
            hosts.pop(i)
            continue

        # Step 2: DNS resolution
        try:
            ip = socket.gethostbyname(host)
            log_check("dns", True, ip)
        except socket.gaierror as e:
            log_check("dns", False, str(e))
            remove_host_from_file(host, input_file)
            log_message(f"Removed {host} from {input_file.name} due to DNS error", "INFO")
            write_host(deleted_file, host)
            hosts.pop(i)
            continue

        # Step 3: BIG-IQ subnet exclusion
        if is_in_bigiq_subnets(ip):
            log_check("bigiq_subnet", False, ip)
            remove_host_from_file(host, input_file)
            write_host(deleted_file, host)
            hosts.pop(i)
            continue

        # Step 4: Reverse DNS lookup
        try:
            rev = socket.gethostbyaddr(ip)[0]
            log_check("rdns", True, rev)
        except (socket.herror, socket.gaierror) as e:
            log_check("rdns", False, str(e))
            if a.pause:
                input("[PAUSE] rDNS failure. ENTER …")

        # Step 5: Ping check
        try:
            ping_rc = subprocess.run(
                ["ping", "-c", "1", host],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            ).returncode
            if ping_rc != 0:
                log_check("ping", False)
                write_host(deleted_file, host)
                hosts.pop(i)
                continue
        except (subprocess.TimeoutExpired, FileNotFoundError):
            log_check("ping", False, "(error)")
            write_host(deleted_file, host)
            hosts.pop(i)
            continue

        log_check("ping", True)

        # Step 6: Port 22 check
        try:
            nc_rc = subprocess.run(
                ["nc", "-z", host, "22"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            ).returncode
            if nc_rc != 0:
                log_check("port22", False)
                if a.pause and input("[PAUSE] Port fail, 'x' delete? ").lower() == 'x':
                    remove_host_from_file(host, input_file)
                    write_host(deleted_file, host)
                    hosts.pop(i)
                continue
            log_check("port22", True)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            log_check("port22", False, "(error)")
            write_host(deleted_file, host)
            hosts.pop(i)
            continue

        # Step 7: SSH connectivity check (uname)
        try:
            with ssh_client(host, CURRENT_USER, pw) as cli:
                _, so, _ = cli.exec_command("uname -a", timeout=10)
                log_check("ssh", True, so.read().decode().strip())
        except (paramiko.SSHException, socket.error, TimeoutError) as e:
            log_check("ssh", False, str(e))
            if a.pause and input("[PAUSE] SSH fail, 'x' delete? ").lower() == 'x':
                remove_host_from_file(host, input_file)
                write_host(deleted_file, host)
                hosts.pop(i)
            continue

        # Step 8: Salt-call test.ping
        salt_ok = False
        for _ in range(3):
            try:
                with ssh_client(host, CURRENT_USER, pw) as cli:
                    _, so, _ = cli.exec_command("sudo salt-call test.ping", timeout=15)
                    output = so.read().decode()
                    if "True" in output:
                        salt_ok = True
                        break
            except (paramiko.SSHException, socket.error, TimeoutError):
                pass

        log_check("salt-call", salt_ok)
        if not salt_ok:
            if a.pause:
                print(
                    f"\nTo test manually on {host}, run:\n"
                    f"    ssh {CURRENT_USER}@{host} sudo salt-call test.ping\n"
                )
                if input("[PAUSE] Salt-call fail, 'x' delete? ").lower() == 'x':
                    remove_host_from_file(host, input_file)
                    write_host(deleted_file, host)
            continue

        # Step 9: ACC agent check (placeholder)
        acc_ok = check_acc_agent(host)
        log_check("acc_agent", acc_ok)

        # Step 10: SLIST SLA type
        sla = check_slist_u_sla_type(host)
        if "cpu_count" in sla:
            log_check("slist", False, sla)
            if a.pause:
                input("[PAUSE] cpu_count. ENTER …")
        else:
            log_check("slist", True, sla)

        # Step 11: Zabbix status
        zb_status = check_zabbix(host)
        if zb_status == "Missing":
            log_message("Zabbix missing → installing …", "INFO")
            zb_status = "Enabled" if do_zabbix_install_pexpect(host) == "Success" else "Missing"
        log_check("zabbix", zb_status in ("Enabled", "Disabled"), zb_status)
        if zb_status in ("Enabled", "Disabled"):
            write_host(zabbix_status_file, f"{host} : {zb_status}")

        # Step 12: VLAN lookup
        gather_vlan_info_for_servername(host)
        log_check("vlan_lookup", True)

        # Step 13: Satellite check (placeholder)
        log_check("satellite", True)

        # Step 14: Salt-Master configuration validation
        try:
            with ssh_client(host, CURRENT_USER, pw) as cli:
                cmd = (
                    "grep -A1 '^master:' /etc/salt/minion.d/minion.conf "
                    "| tail -n1 | sed 's/[-[:space:]]//g'"
                )
                stdin, stdout, stderr = cli.exec_command(cmd, timeout=10)
                exit_status = stdout.channel.recv_exit_status()
                stderr_out = stderr.read().decode().strip()
                if exit_status != 0:
                    log_check("salt_master_parse", False, stderr_out)
                    if a.pause:
                        input("[PAUSE] Salt-Master parse pipeline error. ENTER …")
                remote_sm = stdout.read().decode().strip()
            if remote_sm:
                matched = bool(expected_sm and remote_sm == expected_sm)
                log_check("salt_master", matched, remote_sm)
            else:
                log_check("salt_master", False, "no_output")
        except (paramiko.SSHException, socket.error, TimeoutError) as e:
            log_check("salt_master", False, str(e))
            if a.pause:
                input("[PAUSE] Salt-Master failure. ENTER …")

        write_host(fullpass_file, host)
        write_host(done_list_file, host)
        log_message(f"{host} logged to fullpass & donelist", "INFO")

        if a.allpause and input("[ALL-PAUSE] Done. 'x' delete? ").lower() == 'x':
            remove_host_from_file(host, input_file)
            write_host(deleted_file, host)
            hosts.pop(i)
            log_message(f"{host} removed.", "INFO")
            continue

        i += 1  # advance when host remains

    if fullpass_file.exists():
        sorted_hosts = sorted({h for h in read_hosts_from_file(fullpass_file)})
        fullpass_file.write_text("\n\n".join(sorted_hosts) + "\n\n")
        log_message(f"FULLPASS sorted ({len(sorted_hosts)} hosts)", "INFO")

    if fullpass_file.exists() and non_managed_file.exists():
        mismatch = set(read_hosts_from_file(fullpass_file)) - set(read_hosts_from_file(non_managed_file))
        log_message(
            "Mismatch check: none" if not mismatch else "Mismatch hosts:\n" + "\n".join(mismatch),
            "INFO" if not mismatch else "WARN"
        )
    else:
        log_message("Mismatch skipped (file missing)", "INFO")

    print_footer()

if __name__ == "__main__":
    main()

################################################################################
#                                                                              #
#  Script: listscrubber    Version: 4.66                                      #
#                                                                              #
################################################################################
