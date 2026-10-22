"""System probe and capability diagnostic utilities."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def probe_python_runtime() -> Dict[str, Any]:
    """Inspect the Python execution environment."""
    return {
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
        "is_64bit": sys.maxsize > 2**32,
        "gil_enabled": True,
    }


def probe_host_platform() -> Dict[str, Any]:
    """Inspect host OS, hardware, and architecture."""
    return {
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count() or 1,
    }


def probe_workspace_storage(workspace_path: Path) -> Dict[str, Any]:
    """Check storage capacity and write permissions for the workspace."""
    exists = workspace_path.exists()
    writable = False
    if exists:
        test_file = workspace_path / f".write_test_{os.getpid()}.tmp"
        try:
            with open(test_file, "w") as f:
                f.write("probe")
            writable = True
            test_file.unlink()
        except Exception:
            writable = False

    disk_usage = shutil.disk_usage(str(workspace_path if exists else workspace_path.parent))
    return {
        "exists": exists,
        "is_writable": writable,
        "path": str(workspace_path.resolve()),
        "total_gb": round(disk_usage.total / (1024**3), 2),
        "free_gb": round(disk_usage.free / (1024**3), 2),
    }


def probe_git_status(workspace_path: Path) -> Dict[str, Any]:
    """Inspect Git repository state."""
    try:
        branch = subprocess.check_output(
            ["git", "-C", str(workspace_path), "branch", "--show-current"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        ).strip()
        status_out = subprocess.check_output(
            ["git", "-C", str(workspace_path), "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        ).strip()
        return {
            "is_git_repo": True,
            "branch": branch or "HEAD",
            "is_dirty": bool(status_out),
            "uncommitted_count": len(status_out.splitlines()) if status_out else 0,
        }
    except Exception:
        return {
            "is_git_repo": False,
            "branch": None,
            "is_dirty": False,
            "uncommitted_count": 0,
        }


def run_full_system_probe(workspace_path: Path) -> Dict[str, Any]:
    """Aggregate full hardware, runtime, storage, and VCS diagnostics."""
    return {
        "python": probe_python_runtime(),
        "platform": probe_host_platform(),
        "storage": probe_workspace_storage(workspace_path),
        "git": probe_git_status(workspace_path),
    }
