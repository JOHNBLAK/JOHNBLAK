#!/usr/bin/env python3
"""Bunker System Inspector

Run this file directly to print a rich, terminal-friendly system report.
"""

from __future__ import annotations

import datetime as _dt
import ipaddress
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import textwrap
from pathlib import Path


APP_NAME = "bunker"
APP_VERSION = "1.0.0"
WIDTH = 100


def line(char: str = "─", width: int = WIDTH) -> str:
    return char * width


def title(text: str) -> None:
    print(f"\n┌{line('─')}┐")
    print(f"│ {text.center(WIDTH - 2)} │")
    print(f"└{line('─')}┘")


def subsection(text: str) -> None:
    print(f"\n• {text}\n  {line('·', 48)}")


def kv(items: dict[str, str | int | float | None]) -> None:
    key_width = max((len(k) for k in items), default=10) + 2
    for k, v in items.items():
        print(f"  {k:<{key_width}}: {v}")


def run_command(cmd: list[str]) -> str:
    """Run a command and return trimmed output without crashing on failures."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=4, check=False)
        text = (result.stdout or result.stderr).strip()
        return text if text else "N/A"
    except Exception as exc:  # keep output resilient across systems
        return f"N/A ({exc.__class__.__name__})"


def bytes_to_human(size: int | float | None) -> str:
    if size is None:
        return "N/A"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    n = float(size)
    for unit in units:
        if n < 1024 or unit == units[-1]:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{size} B"


def get_uptime_seconds() -> int | None:
    # Linux first
    proc = Path("/proc/uptime")
    if proc.exists():
        try:
            return int(float(proc.read_text().split()[0]))
        except Exception:
            pass

    # macOS fallback
    if sys.platform == "darwin":
        out = run_command(["sysctl", "-n", "kern.boottime"])
        # Example: { sec = 1713785488, usec = 0 } ...
        if "sec =" in out:
            try:
                sec = int(out.split("sec =", 1)[1].split(",", 1)[0].strip())
                return max(0, int(_dt.datetime.now().timestamp()) - sec)
            except Exception:
                pass

    # Windows fallback
    if os.name == "nt":
        out = run_command(["wmic", "os", "get", "lastbootuptime", "/value"])
        for chunk in out.splitlines():
            if chunk.startswith("LastBootUpTime="):
                raw = chunk.split("=", 1)[1].strip()
                try:
                    boot = _dt.datetime.strptime(raw[:14], "%Y%m%d%H%M%S")
                    return int((_dt.datetime.now() - boot).total_seconds())
                except Exception:
                    pass
    return None


def fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return "N/A"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    return f"{days}d {hours}h {mins}m {secs}s"


def read_mem_info() -> tuple[int | None, int | None]:
    """Return (total_bytes, available_bytes) for memory with multiple fallbacks."""
    if Path("/proc/meminfo").exists():
        values: dict[str, int] = {}
        for ln in Path("/proc/meminfo").read_text().splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                values[k.strip()] = int(v.strip().split()[0]) * 1024
        total = values.get("MemTotal")
        available = values.get("MemAvailable") or values.get("MemFree")
        return total, available

    if shutil.which("vm_stat") and sys.platform == "darwin":
        page_size = run_command(["sysctl", "-n", "hw.pagesize"])
        pages = run_command(["vm_stat"])
        try:
            psize = int(page_size.strip())
            vals = {}
            for ln in pages.splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    vals[k.strip()] = int(v.strip().strip(".").replace(".", ""))
            free = (vals.get("Pages free", 0) + vals.get("Pages speculative", 0)) * psize
            total = int(run_command(["sysctl", "-n", "hw.memsize"]).strip())
            return total, free
        except Exception:
            return None, None

    return None, None


def disk_report() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        out = run_command(["df", "-h"])  # best-effort
        for idx, ln in enumerate(out.splitlines()):
            if idx == 0 or not ln.strip():
                continue
            parts = ln.split()
            if len(parts) >= 6:
                rows.append(
                    {
                        "Filesystem": parts[0],
                        "Size": parts[1],
                        "Used": parts[2],
                        "Avail": parts[3],
                        "Use%": parts[4],
                        "Mount": parts[5],
                    }
                )
    elif os.name == "nt":
        out = run_command(["wmic", "logicaldisk", "get", "name,size,freespace"])
        for ln in out.splitlines()[1:]:
            parts = ln.split()
            if len(parts) == 3:
                free, name, size = parts
                try:
                    size_i, free_i = int(size), int(free)
                    used = size_i - free_i
                    pct = (used / size_i * 100) if size_i else 0
                    rows.append(
                        {
                            "Filesystem": name,
                            "Size": bytes_to_human(size_i),
                            "Used": bytes_to_human(used),
                            "Avail": bytes_to_human(free_i),
                            "Use%": f"{pct:.1f}%",
                            "Mount": name,
                        }
                    )
                except Exception:
                    continue
    return rows


def print_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("  N/A")
        return
    cols = list(rows[0].keys())
    widths = {c: max(len(c), *(len(r.get(c, "")) for r in rows)) for c in cols}
    header = "  " + " | ".join(f"{c:<{widths[c]}}" for c in cols)
    sep = "  " + "-+-".join("-" * widths[c] for c in cols)
    print(header)
    print(sep)
    for r in rows:
        print("  " + " | ".join(f"{r.get(c, ''):<{widths[c]}}" for c in cols))


def detect_local_ips() -> list[str]:
    ips: list[str] = []
    for info in socket.getaddrinfo(socket.gethostname(), None):
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
            if not ip.is_loopback:
                ips.append(str(ip))
        except ValueError:
            continue
    return sorted(set(ips))


def collect_report() -> dict[str, object]:
    uname = platform.uname()
    total_mem, avail_mem = read_mem_info()
    used_mem = None if total_mem is None or avail_mem is None else total_mem - avail_mem
    arch = ", ".join([x for x in platform.architecture() if x])

    report: dict[str, object] = {
        "app": {"name": APP_NAME, "version": APP_VERSION},
        "timestamp_utc": _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "timestamp_local": _dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "python": sys.version.split()[0],
        "system": {
            "OS": f"{uname.system} {uname.release}",
            "Version": uname.version,
            "Machine": uname.machine,
            "Processor": uname.processor or "N/A",
            "Architecture": arch or "N/A",
            "Hostname": socket.gethostname(),
            "FQDN": socket.getfqdn(),
            "Uptime": fmt_duration(get_uptime_seconds()),
            "Boot time (best effort)": run_command(["who", "-b"]) if os.name != "nt" else "N/A",
        },
        "cpu": {
            "Physical/Logical cores": f"{os.cpu_count() or 'N/A'} logical",
            "CPU model (Linux)": run_command(["bash", "-lc", "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2-"])
            if sys.platform.startswith("linux")
            else "N/A",
            "CPU frequency": run_command(["bash", "-lc", "lscpu | grep -i 'cpu mhz\|max mhz' | head -n 2"])
            if sys.platform.startswith("linux")
            else "N/A",
        },
        "memory": {
            "Total": bytes_to_human(total_mem),
            "Available": bytes_to_human(avail_mem),
            "Used": bytes_to_human(used_mem),
        },
        "network": {
            "Primary local IPs": ", ".join(detect_local_ips()) or "N/A",
            "Public IP (if available)": run_command(["bash", "-lc", "curl -s --max-time 3 ifconfig.me || true"])
            if shutil.which("curl")
            else "N/A",
            "Routing table (short)": run_command(["bash", "-lc", "ip route 2>/dev/null | head -n 5 || route -n 2>/dev/null | head -n 5"]),
        },
        "disk": disk_report(),
        "software": {
            "Python executable": sys.executable,
            "Pip version": run_command([sys.executable, "-m", "pip", "--version"]),
            "Git version": run_command(["git", "--version"]),
        },
        "runtime": {
            "Current user": run_command(["bash", "-lc", "whoami"]),
            "Working directory": str(Path.cwd()),
            "Shell": os.environ.get("SHELL", "N/A"),
            "Terminal": os.environ.get("TERM", "N/A"),
        },
    }
    return report


def print_report(report: dict[str, object]) -> None:
    title("BUNKER :: SYSTEM INTELLIGENCE REPORT")

    subsection("Run Context")
    kv(
        {
            "App": f"{report['app']['name']} v{report['app']['version']}",  # type: ignore[index]
            "Generated (UTC)": report["timestamp_utc"],
            "Generated (Local)": report["timestamp_local"],
            "Python": report["python"],
            "Script": __file__,
        }
    )

    subsection("System Overview")
    kv(report["system"])  # type: ignore[arg-type]

    subsection("CPU Details")
    kv(report["cpu"])  # type: ignore[arg-type]

    subsection("Memory Details")
    kv(report["memory"])  # type: ignore[arg-type]

    subsection("Network Details")
    kv(report["network"])  # type: ignore[arg-type]

    subsection("Disk / Filesystem Details")
    print_table(report["disk"])  # type: ignore[arg-type]

    subsection("Software Toolchain")
    kv(report["software"])  # type: ignore[arg-type]

    subsection("Runtime Context")
    kv(report["runtime"])  # type: ignore[arg-type]

    title("RAW JSON SNAPSHOT")
    print(textwrap.indent(json.dumps(report, indent=2), "  "))


def main() -> int:
    try:
        report = collect_report()
        print_report(report)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
