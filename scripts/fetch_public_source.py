"""Fetch pinned MIT-licensed algorithm source into ignored cache."""
import argparse
import subprocess
from pathlib import Path

from mwfas_data.config import ROOT, load_project

parser = argparse.ArgumentParser()
parser.add_argument("--destination", type=Path, default=ROOT / "data/cache/source")
args = parser.parse_args()
config = load_project()
target = args.destination
target.parent.mkdir(parents=True, exist_ok=True)
if not (target / ".git").exists():
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"destination exists and is not a git checkout: {target}")
    subprocess.run(["git", "init", str(target)], check=True)
subprocess.run(["git", "-C", str(target), "fetch", "--depth=1",
                f'https://github.com/{config["source_repo"]}.git', config["source_revision"]], check=True)
subprocess.run(["git", "-C", str(target), "checkout", "--detach", "FETCH_HEAD"], check=True)
actual = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
if actual != config["source_revision"]:
    raise SystemExit(f"source revision mismatch: {actual}")
print(f"verified source at {actual}: {target}")
