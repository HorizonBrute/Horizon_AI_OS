#!/usr/bin/env python3
"""Check whether monitor_aios.py is running. Prints 'running' or 'stopped'."""
import subprocess, sys

def main():
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True
            )
            print("running" if "monitor_aios" in r.stdout else "stopped")
        else:
            r = subprocess.run(["pgrep", "-f", "monitor_aios.py"], capture_output=True)
            print("running" if r.returncode == 0 else "stopped")
    except Exception:
        print("unknown")

if __name__ == "__main__":
    main()
