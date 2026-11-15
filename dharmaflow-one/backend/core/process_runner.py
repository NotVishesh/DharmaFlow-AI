"""Subprocess execution compatible with Windows Selector and Proactor event loops."""
import asyncio
import subprocess
import sys
import threading
import time
from pathlib import Path
import psutil


def _kill_tree(process):
    # Windows venv python.exe may be a launcher with a separate interpreter child.
    try:
        descendants = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        descendants = []
    for child in reversed(descendants):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if process.poll() is None:
        process.kill()
    psutil.wait_procs(descendants, timeout=5)


async def run_process(*args: str, timeout: float = 1800, cwd: str | None = None,
                      log_path: Path | None = None) -> subprocess.CompletedProcess:
    cancelled = threading.Event()

    def execute():
        log = log_path.open('wb') if log_path else None
        try:
            with subprocess.Popen(args, cwd=cwd, stdin=subprocess.DEVNULL,
                    stdout=log or subprocess.PIPE, stderr=log or subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0) as process:
                deadline = time.monotonic() + timeout
                while True:
                    if cancelled.is_set() or time.monotonic() >= deadline:
                        _kill_tree(process)
                        process.communicate()
                        raise RuntimeError(f'{Path(args[0]).name} was cancelled or exceeded its {timeout:g}s timeout')
                    try:
                        stdout, stderr = process.communicate(timeout=min(.2, max(.001, deadline-time.monotonic())))
                        return subprocess.CompletedProcess(args, process.returncode, stdout or b'', stderr or b'')
                    except subprocess.TimeoutExpired:
                        continue
        finally:
            if log:
                log.close()

    task = asyncio.create_task(asyncio.to_thread(execute))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        cancelled.set()
        try:
            await task  # Reap the child before releasing the model guard.
        except Exception:
            pass
        raise
