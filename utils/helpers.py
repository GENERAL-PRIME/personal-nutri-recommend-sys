"""
utils/helpers.py
Shared utility functions for the Food Filtering System.
"""

import os
import json
import pandas as pd
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)


# ── Colour helpers ────────────────────────────────────────────────────────────
def green(text):   return f"{Fore.GREEN}{text}{Style.RESET_ALL}"
def red(text):     return f"{Fore.RED}{text}{Style.RESET_ALL}"
def yellow(text):  return f"{Fore.YELLOW}{text}{Style.RESET_ALL}"
def cyan(text):    return f"{Fore.CYAN}{text}{Style.RESET_ALL}"
def bold(text):    return f"{Style.BRIGHT}{text}{Style.RESET_ALL}"
def magenta(text): return f"{Fore.MAGENTA}{text}{Style.RESET_ALL}"


def print_header(title: str):
    width = 64
    print("\n" + cyan("═" * width))
    print(cyan("  ") + bold(title))
    print(cyan("═" * width))


def print_section(title: str):
    print("\n" + yellow(f"  ▶  {title}"))
    print(yellow("  " + "─" * 54))


def print_success(msg: str):
    print(green(f"  ✔  {msg}"))


def print_warning(msg: str):
    print(yellow(f"  ⚠  {msg}"))


def print_error(msg: str):
    print(red(f"  ✘  {msg}"))


def print_info(msg: str):
    print(cyan(f"  ℹ  {msg}"))


# ── Path helpers ──────────────────────────────────────────────────────────────
def get_project_root() -> str:
    """Return the root directory of the project (parent of utils/)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dataset_path(filename: str) -> str:
    return os.path.join(get_project_root(), "datasets", filename)


def output_path(filename: str) -> str:
    out_dir = os.path.join(get_project_root(), "outputs")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, filename)


# ── Export helpers ────────────────────────────────────────────────────────────
def export_json(data: dict, filepath: str):
    """Serialise pipeline output to JSON (handles DataFrames)."""
    def _serialise(obj):
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient="records")
        if isinstance(obj, pd.Series):
            return obj.to_dict()
        raise TypeError(f"Not serialisable: {type(obj)}")

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=_serialise)


def export_csv(df: pd.DataFrame, filepath: str):
    df.to_csv(filepath, index=False)


def timestamp_str() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ── Input parsing helpers ─────────────────────────────────────────────────────
def parse_multiline_input(prompt: str) -> list[str]:
    """
    Ask the user to enter items one per line (or comma-separated on one line).
    Pressing Enter on an empty line finishes input.
    Returns a deduplicated list of stripped strings.
    """
    print(cyan(f"\n  {prompt}"))
    print(cyan("  (Enter one per line OR comma-separated. Empty line to finish)\n"))
    items = []
    while True:
        line = input("    > ").strip()
        if not line:
            break
        # Support comma-separated on one line
        for part in line.split(","):
            part = part.strip()
            if part:
                items.append(part)
    # Deduplicate, preserve order
    seen = set()
    result = []
    for item in items:
        if item.lower() not in seen:
            seen.add(item.lower())
            result.append(item)
    return result


def confirm(prompt: str) -> bool:
    """Yes/No confirmation prompt."""
    while True:
        ans = input(cyan(f"\n  {prompt} [y/n]: ")).strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print_warning("Please enter y or n.")
