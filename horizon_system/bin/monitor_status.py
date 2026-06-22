#!/usr/bin/env python3
"""Check whether monitor_aios.py is running. Prints 'running' or 'stopped'."""
import subprocess, sys

def main():
    try:
        if sys.platform == "win32":
            # tasklist does not expose the command line, so it can't match the
            # script name. Query Win32_Process (which has CommandLine) instead.
            ps = (
                "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
                "| Where-Object { $_.CommandLine -match 'monitor_aios' }) "
                "{ 'running' } else { 'stopped' }"
            )
            r = subprocess.run(
                ["powershell", "-NonInteractive", "-Command", ps],
                capture_output=True, text=True
            )
            print("running" if "running" in r.stdout else "stopped")
        else:
            r = subprocess.run(["pgrep", "-f", "monitor_aios.py"], capture_output=True)
            print("running" if r.returncode == 0 else "stopped")
    except Exception:
        print("unknown")

if __name__ == "__main__":
    main()
