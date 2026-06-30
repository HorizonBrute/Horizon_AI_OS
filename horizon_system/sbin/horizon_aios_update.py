#!/usr/bin/env python3
"""
Mirror Horizon_AI_OS upstream into the personal fork, then pull into the local install.

Flow:
  1. cd $HORIZON_ROOT/..
  2. git clone --bare <upstream>  -> ./bare/
  3. git push --mirror <personal> (from inside ./bare/<repo>.git)
  4. rm -rf ./bare/
  5. git pull  (from $HORIZON_ROOT)
"""

import os
import shutil
import subprocess
import sys

UPSTREAM = "https://github.com/HorizonBrute/Horizon_AI_OS"
PERSONAL = "https://github.com/HorizonBrute/Horizon.AIOS_personal"


def run(cmd, cwd=None):
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"[ERROR] Command failed (exit {result.returncode})")
        sys.exit(result.returncode)


def main():
    horizon_root = os.environ.get("HORIZON_ROOT")
    if not horizon_root:
        print("[ERROR] $HORIZON_ROOT is not set — source your AIOS profile first.")
        sys.exit(1)

    horizon_root = os.path.abspath(horizon_root)
    parent = os.path.dirname(horizon_root)
    bare_dir = os.path.join(parent, "bare")

    if os.path.exists(bare_dir):
        print(f"[ERROR] {bare_dir} already exists — remove it and retry.")
        sys.exit(1)

    try:
        print(f"\n[1/3] Cloning bare upstream into {bare_dir} ...")
        run(["git", "clone", "--bare", UPSTREAM, bare_dir], cwd=parent)

        print(f"\n[2/3] Mirroring to personal fork ...")
        run(["git", "push", "--mirror", PERSONAL], cwd=bare_dir)

    finally:
        if os.path.exists(bare_dir):
            print(f"\n      Cleaning up {bare_dir} ...")
            shutil.rmtree(bare_dir)

    print(f"\n[3/3] Pulling into local install ({horizon_root}) ...")
    run(["git", "pull"], cwd=horizon_root)

    print("\n[OK] Update complete.")


if __name__ == "__main__":
    main()
