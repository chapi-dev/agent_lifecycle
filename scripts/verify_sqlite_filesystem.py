"""Probe SQLite locking and recovery on a mounted filesystem before using it."""

from __future__ import annotations

import argparse
from contextlib import closing
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def connect(path: Path, timeout: float = 5) -> sqlite3.Connection:
    db = sqlite3.connect(path, timeout=timeout)
    if db.execute("PRAGMA journal_mode=DELETE").fetchone()[0].lower() != "delete":
        raise RuntimeError("The filesystem did not enable DELETE journaling")
    db.execute("PRAGMA synchronous=FULL")
    return db


def worker(path: Path, action: str) -> None:
    if action == "locked":
        db = sqlite3.connect(path, timeout=0.25)
        try:
            db.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
        else:
            raise RuntimeError("A second writer acquired an existing write lock")
        finally:
            db.close()
    elif action == "crash":
        import os

        db = connect(path)
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE probe SET value = 9999")
        os._exit(0)
    elif action == "increment":
        db = connect(path, timeout=15)
        try:
            for _ in range(25):
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE probe SET value = value + 1")
                db.commit()
        finally:
            db.close()
    else:
        raise ValueError(f"Unknown probe action: {action}")


def run_worker(path: Path, action: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker", action, str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_worker(process: subprocess.Popen, action: str) -> None:
    try:
        stdout, stderr = process.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise RuntimeError(f"{action} probe timed out") from None
    if process.returncode:
        raise RuntimeError(f"{action} probe failed: {stderr.strip() or stdout.strip()}")


def verify(directory: Path) -> None:
    if not directory.is_dir():
        raise ValueError("The target must be an existing directory")
    with tempfile.TemporaryDirectory(prefix="sqlite-probe-", dir=directory) as tmp:
        path = Path(tmp) / "probe.db"
        db = connect(path)
        try:
            db.execute("CREATE TABLE probe (value INTEGER NOT NULL)")
            db.execute("INSERT INTO probe VALUES (0)")
            db.commit()
            db.execute("BEGIN IMMEDIATE")
            wait_worker(run_worker(path, "locked"), "lock")
            db.rollback()
        finally:
            db.close()

        wait_worker(run_worker(path, "crash"), "crash recovery")
        with closing(connect(path)) as check:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("SQLite integrity check failed after a crash")
            if check.execute("SELECT value FROM probe").fetchone()[0] != 0:
                raise RuntimeError("The crashed transaction was not rolled back")

        processes = [run_worker(path, "increment") for _ in range(4)]
        failures = []
        for process in processes:
            try:
                wait_worker(process, "concurrent writer")
            except RuntimeError as exc:
                failures.append(str(exc))
        if failures:
            raise RuntimeError("; ".join(failures))
        with closing(connect(path)) as check:
            if check.execute("SELECT value FROM probe").fetchone()[0] != 100:
                raise RuntimeError("Concurrent committed writes were lost")
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("SQLite integrity check failed after concurrent writes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("locked", "crash", "increment"), help=argparse.SUPPRESS)
    parser.add_argument("directory", type=Path, help="Existing mounted directory to test")
    args = parser.parse_args()
    try:
        if args.worker:
            worker(args.directory, args.worker)
        else:
            verify(args.directory)
            print("PASS: locking, crash rollback, concurrent writes and integrity.")
            print("A passing probe does not guarantee safety under all failures or deployments.")
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
