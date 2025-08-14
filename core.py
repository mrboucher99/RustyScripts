#!/usr/bin/env python3
####################################
# core - Version 1.35              #
####################################
# Shared constants and functions for automail
####################################

from __future__ import annotations

import os
import getpass
import subprocess
from pathlib import Path

SCRIPT_NAME = "automail"
VERSION = "1.35"
VERSION_TAG = f"{SCRIPT_NAME} v{VERSION}"
CURRENT_USER = getpass.getuser()

LISTS_DIR = Path("/nethome/mboucher3/scriptdata/automail/lists")
if not LISTS_DIR.exists():
    LISTS_DIR = Path(__file__).with_name("lists")
TEMPLATES_DIR = Path("/nethome/mboucher3/scriptdata/automail/templates")
if not TEMPLATES_DIR.exists():
    TEMPLATES_DIR = Path(__file__).with_name("templates")
SIGNATURES_DIR = Path("/nethome/mboucher3/scriptdata/automail/signatures")
if not SIGNATURES_DIR.exists():
    SIGNATURES_DIR = Path(__file__).with_name("signatures")
DEFAULT_SIGNATURE_PATH = SIGNATURES_DIR / "defaultsignature.txt"
DEFAULT_TEMPLATE_PATH = TEMPLATES_DIR / "default_template.txt"
TEMPLIST_PATH = Path("templist.txt")
MANAGER_EMAIL_PATH = Path(__file__).with_name("managed_by-emailaddress.txt")

ARGUMENTS_INFO = [
    ("names", "Server names"),
    ("--gui", "Run in interactive CLI mode"),
    ("--list", "Edit server list in vi"),
    ("--last", "Reuse server list from last --list run"),
    ("--load", "Select or create a list file in the lists directory"),
    ("--template", "Manage template files in the templates directory"),
    ("--cc", "Choose CC email address"),
]
ARGUMENTS_TEXT = "Arguments:\n" + "\n".join(
    f"  {name:<17} {desc}" for name, desc in ARGUMENTS_INFO
)

def make_banner(text: str) -> str:
    border = "#" * (len(text) + 4)
    return f"{border}\n# {text} #\n{border}"

HEADER = make_banner(VERSION_TAG)
FOOTER = HEADER

def display_banner() -> None:
    os.system("cls" if os.name == "nt" else "clear")
    print(HEADER)
    print(f"Current user: {CURRENT_USER}")
    print()
    print(ARGUMENTS_TEXT)
    print()

def ensure_default_signature(*, quiet: bool = False) -> str:
    """Ensure default signature exists and optionally display its contents."""
    SIGNATURES_DIR.mkdir(parents=True, exist_ok=True)
    if not DEFAULT_SIGNATURE_PATH.exists():
        print("No signature found. Launching vi to create defaultsignature.txt.")
        subprocess.run(["vi", str(DEFAULT_SIGNATURE_PATH)])
        if not DEFAULT_SIGNATURE_PATH.exists():
            DEFAULT_SIGNATURE_PATH.touch()
    with DEFAULT_SIGNATURE_PATH.open() as f:
        signature = f.read().strip()
    if not quiet:
        print("Signature:\n" + signature)
    return signature

def choose_cc_address() -> str | None:
    """Prompt user to select a CC address."""
    print("Select CC email:")
    print("1. operations@oit.gatech.edu")
    print("2. Enter address manually")
    print("0. No CC")
    while True:
        choice = input("Choice: ").strip()
        if choice == "1":
            return "operations@oit.gatech.edu"
        if choice == "2":
            addr = input("Enter CC email: ").strip()
            return addr or None
        if choice in {"0", ""}:
            return None
        print("Invalid selection. Try again.")

def load_template(path: Path) -> dict[str, str | None]:
    """Load sender, subject, optional cc, and body from a template."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return {"sender": "", "subject": "", "cc": None, "body": ""}
    sender = ""
    subject = ""
    cc: str | None = None
    body_lines: list[str] = []
    with path.open() as f:
        for line in f:
            lower = line.lower()
            if lower.startswith("sender:"):
                sender = line.split(":", 1)[1].strip()
            elif lower.startswith("cc:"):
                value = line.split(":", 1)[1].strip()
                if value:
                    cc = value
            elif lower.startswith("subject:"):
                subject = line.split(":", 1)[1].strip()
            else:
                body_lines.append(line.rstrip("\n"))
    body = "\n".join(body_lines).strip()
    return {"sender": sender, "subject": subject, "cc": cc, "body": body}

def lookup_manager_email(manager: str) -> str:
    """Return email address for manager, prompting and storing if missing."""
    MANAGER_EMAIL_PATH.touch(exist_ok=True)
    mapping: dict[str, str] = {}
    with MANAGER_EMAIL_PATH.open() as f:
        for line in f:
            if "," in line:
                name, email = line.strip().split(",", 1)
                mapping[name.strip()] = email.strip()
    if manager in mapping:
        email = mapping[manager]
        print(f"Email for {manager}: {email}")
        return email
    email = input(f"Enter email address for '{manager}': ").strip()
    with MANAGER_EMAIL_PATH.open("a") as f:
        f.write(f"{manager},{email}\n")
    print(f"Email for {manager}: {email}")
    return email

def show_managed_by(names: list[str]) -> None:
    """Run slist for each server and display its managed_by field."""
    total = len(names)
    for index, server in enumerate(names, 1):
        print(f"{index}/{total} Server: {server}")
        try:
            result = subprocess.run(
                ["slist", server],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            output = result.stdout
        except FileNotFoundError:
            managed_by = "slist command not found"
        else:
            managed_by = "Unknown"
            for line in output.splitlines():
                if "managed_by" in line.lower():
                    managed_by = line.split(":", 1)[1].strip() if ":" in line else line.split()[-1]
                    break
        print(f"Managed By: {managed_by}")
        if managed_by not in {"slist command not found", "Unknown"}:
            lookup_manager_email(managed_by)
        print("-" * 40)

def count_lines(path: Path) -> int:
    """Return the number of non-empty lines in a file."""
    with path.open() as f:
        return sum(1 for line in f if line.strip())

def select_list_file() -> Path | None:
    """Display a menu of list files or create a new one."""
    LISTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in LISTS_DIR.iterdir() if p.is_file())
    print("Available server lists:")
    for idx, path in enumerate(files, 1):
        print(f"{idx}. {path.name} ({count_lines(path)} lines)")
    print("0. Create a new list file")
    print("m. Enter a file name manually")
    while True:
        choice = input("Select a file by number, 0 to create new, or m for manual: ")
        choice = choice.strip().lower()
        if choice == "0":
            name = input("Enter new list file name: ").strip()
            if not name:
                print("Name cannot be empty.")
                continue
            new_path = LISTS_DIR / name
            new_path.touch(exist_ok=True)
            subprocess.run(["vi", str(new_path)])
            return new_path
        if choice == "m":
            name = input("Enter list file name: ").strip()
            if not name:
                print("Name cannot be empty.")
                continue
            manual_path = LISTS_DIR / name
            if manual_path.exists():
                print(f"Selected file: {manual_path.name} ({count_lines(manual_path)} lines)")
                return manual_path
            print(f"File not found: {name}")
            continue
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(files):
                return files[index - 1]
        print("Invalid selection. Try again.")

def select_template_file() -> Path | None:
    """Manage template files: select, create, or delete."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        files = sorted(p for p in TEMPLATES_DIR.iterdir() if p.is_file())
        print("Available templates:")
        for idx, path in enumerate(files, 1):
            print(f"{idx}. {path.name}")
        print("0. Create a new template file")
        print("m. Enter a template file name manually")
        print("d. Delete a template file")
        print("q. Quit without selecting")
        choice = input("Select template by number or option: ").strip().lower()
        if choice == "0":
            name = input("Enter new template file name: ").strip()
            if not name:
                print("Name cannot be empty.")
                continue
            new_path = TEMPLATES_DIR / name
            new_path.touch(exist_ok=True)
            subprocess.run(["vi", str(new_path)])
            return new_path
        if choice == "m":
            name = input("Enter template file name: ").strip()
            if not name:
                print("Name cannot be empty.")
                continue
            manual_path = TEMPLATES_DIR / name
            if manual_path.exists():
                print(f"Selected template: {manual_path.name}")
                return manual_path
            print(f"File not found: {name}")
            continue
        if choice == "d":
            target = input("Enter number or name of template to delete: ").strip()
            if target.isdigit():
                idx = int(target)
                if 1 <= idx <= len(files):
                    files[idx - 1].unlink()
                    print(f"Deleted template: {files[idx - 1].name}")
                else:
                    print("Invalid selection.")
            else:
                del_path = TEMPLATES_DIR / target
                if del_path.exists():
                    del_path.unlink()
                    print(f"Deleted template: {del_path.name}")
                else:
                    print(f"Template not found: {target}")
            continue
        if choice == "q":
            return None
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(files):
                return files[idx - 1]
        print("Invalid selection. Try again.")

####################################
# End of core - Version 1.35       #
####################################
