"""Stop the table-order backend started by run_server.py.

Reads server.pid and kills that process tree (the launcher child and its
uvicorn worker). Safe to run even if the server is already stopped.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PID = os.path.join(HERE, "server.pid")


def main() -> int:
    if not os.path.isfile(PID):
        print("NO_PID_FILE")
        return 0
    with open(PID) as f:
        pid = f.read().strip()
    if not pid:
        print("EMPTY_PID")
        return 0
    # /T kills the whole tree, /F forces it.
    r = subprocess.run(
        ["taskkill", "/PID", pid, "/T", "/F"],
        capture_output=True, text=True,
    )
    print("STOP_RC", r.returncode)
    try:
        os.remove(PID)
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
