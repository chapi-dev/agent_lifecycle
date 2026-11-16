"""Probe SQLite locking and recovery on a mounted filesystem before using it."""

from __future__ import annotations

import argparse
from contextlib import closing
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
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


def wait_for(path: Path, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while not path.is_file():
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for {path.name}")
        time.sleep(0.1)


def signal(path: Path) -> None:
    path.touch(exist_ok=False)


def shared_probe(directory: Path, run_id: str, role: str, timeout: float) -> None:
    if not directory.is_dir():
        raise ValueError("The target must be an existing directory")
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("The run ID must be a 32-character lowercase hexadecimal UUID")
    if timeout <= 0:
        raise ValueError("The timeout must be positive")

    folder = directory / f"sqlite-probe-peer-{run_id}"
    if role == "coordinator":
        folder.mkdir()
        completed = False
        try:
            path = folder / "probe.db"
            with closing(connect(path)) as db:
                db.execute("CREATE TABLE probe (value INTEGER NOT NULL)")
                db.execute("INSERT INTO probe VALUES (0)")
                db.commit()
                signal(folder / "database-ready")
                wait_for(folder / "peer-ready", timeout)
                db.execute("BEGIN IMMEDIATE")
                signal(folder / "lock-held")
                wait_for(folder / "lock-checked", timeout)
                db.rollback()

            signal(folder / "crash-requested")
            wait_for(folder / "crash-complete", timeout)
            with closing(connect(path)) as db:
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("SQLite integrity check failed after the peer crashed")
                if db.execute("SELECT value FROM probe").fetchone()[0] != 0:
                    raise RuntimeError("The peer's crashed transaction was not rolled back")

            signal(folder / "increment-requested")
            wait_worker(run_worker(path, "increment"), "coordinator writer")
            wait_for(folder / "increment-complete", timeout)
            with closing(connect(path)) as db:
                if db.execute("SELECT value FROM probe").fetchone()[0] != 50:
                    raise RuntimeError("Concurrent committed writes were lost")
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("SQLite integrity check failed after concurrent writes")
            signal(folder / "probe-complete")
            wait_for(folder / "peer-finished", timeout)
            completed = True
        finally:
            if completed:
                # Only remove files from the directory this run created.
                for name in (
                    "database-ready", "peer-ready", "lock-held", "lock-checked",
                    "crash-requested", "crash-complete", "increment-requested",
                    "increment-complete", "probe-complete", "peer-finished",
                    "probe.db", "probe.db-journal",
                ):
                    (folder / name).unlink(missing_ok=True)
                folder.rmdir()
            else:
                print(f"Probe files retained at {folder}; remove only after both clients stop.", file=sys.stderr)
    else:
        wait_for(folder / "database-ready", timeout)
        path = folder / "probe.db"
        signal(folder / "peer-ready")
        wait_for(folder / "lock-held", timeout)
        wait_worker(run_worker(path, "locked"), "peer lock")
        signal(folder / "lock-checked")
        wait_for(folder / "crash-requested", timeout)
        wait_worker(run_worker(path, "crash"), "peer crash")
        signal(folder / "crash-complete")
        wait_for(folder / "increment-requested", timeout)
        wait_worker(run_worker(path, "increment"), "peer writer")
        signal(folder / "increment-complete")
        wait_for(folder / "probe-complete", timeout)
        signal(folder / "peer-finished")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("locked", "crash", "increment"), help=argparse.SUPPRESS)
    parser.add_argument("--role", choices=("coordinator", "peer"), help="Run the two-client probe")
    parser.add_argument("--run-id", help="Shared, unique 32-character lowercase hexadecimal UUID")
    parser.add_argument("--timeout", type=float, default=120, help="Seconds to wait for each peer signal")
    parser.add_argument("directory", type=Path, help="Existing mounted directory to test")
    args = parser.parse_args()
    try:
        if args.worker:
            worker(args.directory, args.worker)
        elif args.role:
            if not args.run_id:
                raise ValueError("--run-id is required with --role")
            shared_probe(args.directory, args.run_id, args.role, args.timeout)
            print(f"PASS: {args.role} completed the two-client probe.")
            print("Run each role on a separate client; also test real app restarts and rollouts.")
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
