"""Detached launcher for the table-order backend (dev).

Starts uvicorn in a fully detached child process that survives the parent
terminal/CLI session (breaks away from the parent Job Object), writes its
PID to server.pid and all output to server.log, then returns immediately so
the calling shell is not blocked.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# pythonw.exe has no console window, so it is not tied to the terminal session.
PYW = os.path.join(HERE, ".venv", "Scripts", "pythonw.exe")
PY = os.path.join(HERE, ".venv", "Scripts", "python.exe")
RUNNER = PYW if os.path.isfile(PYW) else PY
LOG = os.path.join(HERE, "server.log")
PID = os.path.join(HERE, "server.pid")

cmd = [
    RUNNER, "-m", "uvicorn", "app.main:create_app", "--factory",
    "--host", "127.0.0.1", "--port", "8000",
    "--timeout-graceful-shutdown", "5",
]

# Windows creation flags:
#   DETACHED_PROCESS (0x08)            - no inherited console
#   CREATE_NEW_PROCESS_GROUP (0x200)   - own process group
#   CREATE_BREAKAWAY_FROM_JOB (0x1000000) - escape the terminal's Job Object
# The Job breakaway is what lets the server outlive the CLI session.
BASE_FLAGS = 0x00000008 | 0x00000200
BREAKAWAY = 0x01000000


def _spawn(flags):
    log = open(LOG, "ab", buffering=0)
    return subprocess.Popen(
        cmd, cwd=HERE, stdout=log, stderr=log,
        stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True,
    )


try:
    proc = _spawn(BASE_FLAGS | BREAKAWAY)
except OSError:
    # Some environments disallow breakaway (job without the limit set); fall back.
    proc = _spawn(BASE_FLAGS)

with open(PID, "w") as f:
    f.write(str(proc.pid))
print("STARTED_PID", proc.pid)
sys.exit(0)
