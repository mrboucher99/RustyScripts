#!/usr/bin/env python3
####################################
# gui - Version 1.35               #
####################################
# Curses-based interface for automail
####################################

from __future__ import annotations

import argparse
import curses
import subprocess

from core import (
    HEADER,
    CURRENT_USER,
    ARGUMENTS_TEXT,
    TEMPLIST_PATH,
    DEFAULT_TEMPLATE_PATH,
    select_list_file,
    select_template_file,
    ensure_default_signature,
    load_template,
    show_managed_by,
)


def run_gui(args: argparse.Namespace) -> None:
    """Curses-based interface with menu options for all CLI arguments."""

    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)

    def prompt(text: str) -> str:
        curses.echo()
        h, w = stdscr.getmaxyx()
        stdscr.addstr(h - 1, 0, text)
        stdscr.clrtoeol()
        value = stdscr.getstr(h - 1, len(text)).decode().strip()
        curses.noecho()
        return value

    def enter_names() -> None:
        nonlocal names
        names = []
        while True:
            name = prompt("Name (blank to finish): ")
            if not name:
                break
            names.append(name)
        output.append(f"Collected {len(names)} names")

    def edit_list() -> None:
        nonlocal names
        if TEMPLIST_PATH.exists():
            TEMPLIST_PATH.unlink()
        subprocess.run(["vi", str(TEMPLIST_PATH)])
        if not TEMPLIST_PATH.exists():
            TEMPLIST_PATH.touch()
        with TEMPLIST_PATH.open() as f:
            names = [line.strip() for line in f if line.strip()]
        output.append(
            f"Processing file: {TEMPLIST_PATH.name} ({len(names)} lines)"
        )

    def reuse_last() -> None:
        nonlocal names
        if not TEMPLIST_PATH.exists():
            subprocess.run(["vi", str(TEMPLIST_PATH)])
            if not TEMPLIST_PATH.exists():
                TEMPLIST_PATH.touch()
        with TEMPLIST_PATH.open() as f:
            names = [line.strip() for line in f if line.strip()]
        output.append(
            f"Processing file: {TEMPLIST_PATH.name} ({len(names)} lines)"
        )

    def load_from_dir() -> None:
        nonlocal names
        path = select_list_file()
        if path is None:
            output.append("No file selected")
            return
        with path.open() as f:
            names = [line.strip() for line in f if line.strip()]
        output.append(f"Processing file: {path.name} ({len(names)} lines)")

    def manage_templates() -> None:
        path = select_template_file()
        if path is None:
            output.append("No template selected")
        else:
            output.append(f"Selected template: {path.name}")

    def select_cc_gui() -> str:
        output.append("Select CC email:")
        output.append("1. operations@oit.gatech.edu")
        output.append("2. Enter address manually")
        output.append("0. No CC")
        choice = prompt("Choice: ")
        if choice == "1":
            return "operations@oit.gatech.edu"
        if choice == "2":
            return prompt("Enter CC email: ").strip()
        return ""

    def set_cc() -> None:
        nonlocal cc
        cc = select_cc_gui()
        if cc:
            output.append(f"CC set to: {cc}")
        else:
            output.append("CC cleared")

    def show_now() -> None:
        if names:
            show_managed_by(names)
            output.append(f"Checked {len(names)} servers")
        else:
            output.append("No server names to check")

    def quit_gui() -> str:
        return "quit"

    signature = ensure_default_signature(quiet=True)
    template = load_template(DEFAULT_TEMPLATE_PATH)
    cc = template.get("cc") or ""
    names: list[str] = args.names or []
    output: list[str] = ["Signature:"] + signature.splitlines()
    if args.cc:
        cc = select_cc_gui()
        if cc:
            output.append(f"CC set to: {cc}")
        else:
            output.append("CC cleared")
    elif cc:
        output.append(f"CC: {cc}")
    handlers = [
        enter_names,
        edit_list,
        reuse_last,
        load_from_dir,
        manage_templates,
        set_cc,
        show_now,
        quit_gui,
    ]

    try:
        current = 0
        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            stdscr.addstr(0, 0, HEADER)
            stdscr.addstr(HEADER.count("\n") + 1, 0, f"Current user: {CURRENT_USER}")
            arg_lines = ARGUMENTS_TEXT.splitlines()
            arg_start = HEADER.count("\n") + 3
            for i, line in enumerate(arg_lines):
                stdscr.addstr(arg_start + i, 0, line)
            menu_start = arg_start + len(arg_lines) + 1
            labels = [
                "Enter server names",
                "Edit server list in vi",
                "Reuse last server list",
                "Load list from directory",
                "Manage templates",
                "Set CC email",
                "Show managed_by info",
                "Quit",
            ]
            for idx, label in enumerate(labels):
                num = idx + 1 if idx < len(labels) - 1 else 0
                line = f"{num}. {label}"
                if idx == current:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(menu_start + idx, 0, line.ljust(w))
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(menu_start + idx, 0, line.ljust(w))
            out_start = h // 2
            stdscr.hline(out_start - 1, 0, ord('-'), w)
            for i, line in enumerate(output[-(h - out_start - 1):]):
                stdscr.addstr(out_start + i, 0, line[: w - 1])
            stdscr.refresh()
            key = stdscr.getch()
            if key == 27:  # ESC
                break
            elif key in (curses.KEY_UP, ord('k')):
                current = (current - 1) % len(labels)
            elif key in (curses.KEY_DOWN, ord('j')):
                current = (current + 1) % len(labels)
            elif key in (curses.KEY_ENTER, 10, 13):
                result = handlers[current]()
                if result == "quit":
                    break
            elif key == ord('0'):
                if handlers[-1]() == "quit":
                    break
            elif ord('1') <= key <= ord(str(len(labels) - 1)):
                idx = key - ord('1')
                result = handlers[idx]()
                if result == "quit":
                    break
    finally:
        stdscr.keypad(False)
        curses.echo()
        curses.nocbreak()
        curses.endwin()

####################################
# End of gui - Version 1.35        #
####################################
