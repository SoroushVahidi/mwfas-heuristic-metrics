"""Fetch immutable public releases into a new directory and replay printed Table 9 and Figure 2.

Use Python 3.12 with -I -B and an empty environment (see README). The audit guard
rejects reads outside the clean directory, interpreter/system files and TLS/DNS
configuration. No token, private checkout, Wulver path, or old cache is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import runpy
import sys
import tarfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CODE_REPO = "SoroushVahidi/mwfas-heuristic-metrics"
DATA_REPO = "SoroushVahidi/mwfas-benchmark-extension"
RELEASE_PATH = "releases/exp28-v1-20261019"


def install_read_guard(root):
    libraries = [Path(x).resolve() for x in ("/usr/lib", "/usr/local/lib", "/lib", "/lib64",
                                             "/usr/share/zoneinfo", "/etc/ssl")]
    allowed_files = {"/etc/localtime", "/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf",
                     "/etc/gai.conf", "/proc/cpuinfo", "/dev/null", "/dev/urandom"}
    checked = set()

    def guard(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(args[0])).absolute()
            # Resolve symlinks too: archive extraction disallows external links.
            p = p.resolve()
            allowed = p.is_relative_to(root) or str(p) in allowed_files or any(p.is_relative_to(d) for d in libraries)
            if not allowed:
                raise PermissionError(f"anonymous replay rejects external file access: {p}")
            checked.add(str(p))
        elif event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn"):
            raise PermissionError("anonymous replay forbids subprocesses")
    sys.addaudithook(guard)
    return checked


def fetch(url, path):
    # Explicit unauthenticated request. No HF/GitHub client or credential lookup.
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mwfas-public-replay/2"}), timeout=60) as response:
        content = response.read()
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def extract(archive, destination):
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if not (member.isdir() or member.isfile()) or not (destination / member.name).resolve().is_relative_to(destination.resolve()):
                raise ValueError("unsafe archive member")
        tar.extractall(destination, filter="data")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--data-revision", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--full", action="store_true", help="Also verify all 143,241 archived orders and original event files")
    args = parser.parse_args()
    if not all(re.fullmatch("[0-9a-f]{40}", r) for r in (args.code_revision, args.data_revision)):
        raise ValueError("both public revisions must be immutable full commit hashes")
    if any(k in os.environ for k in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")):
        raise ValueError("use an empty environment: publication credentials must not enter this test")
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=False)
    os.chdir(root)
    # Cache platform information before the guard; platform.processor can spawn uname.
    hardware = {"platform": platform.platform(), "processor": platform.processor()}
    accesses = install_read_guard(root)
    for forbidden in ("/project/private-replay-probe", "/home/private-replay-probe"):
        try:
            open(forbidden, "rb")
        except PermissionError:
            pass
        else:
            raise RuntimeError("read guard is ineffective")
    start = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    base = f"https://huggingface.co/datasets/{DATA_REPO}/resolve/{args.data_revision}/{RELEASE_PATH}"
    urls = {"code": f"https://codeload.github.com/{CODE_REPO}/tar.gz/{args.code_revision}",
            "receipt": base + "/package_receipt.json", "data": base + "/exp28-light.tar.gz"}
    receipt_sha = fetch(urls["receipt"], root / "package_receipt.json")
    receipt = json.loads((root / "package_receipt.json").read_text())
    data_sha = fetch(urls["data"], root / "exp28-light.tar.gz")
    if data_sha != receipt["archives"]["exp28-light.tar.gz"]["sha256"]:
        raise ValueError("public archive hash mismatch")
    code_sha = fetch(urls["code"], root / "code.tar.gz")
    extract(root / "exp28-light.tar.gz", root)
    extract(root / "code.tar.gz", root)
    package = root / "exp28"
    if hashlib.sha256((package / "manifest.json").read_bytes()).hexdigest() != receipt["manifest_sha256"]:
        raise ValueError("public package manifest hash mismatch")
    code = root / ("mwfas-heuristic-metrics-" + args.code_revision)
    verifier = code / "release/public_reproducibility/replay_exp28.py"
    namespace = runpy.run_path(str(verifier))
    full_archive = full_inventory = None
    full_hashes = {}
    if args.full:
        for filename in ("exp28-full.tar.gz", "full_inventory.csv.gz"):
            urls[filename] = base + "/" + filename
            full_hashes[filename] = fetch(urls[filename], root / filename)
            if full_hashes[filename] != receipt["archives"][filename]["sha256"]:
                raise ValueError("full archive/inventory mismatch")
        full_archive, full_inventory = root / "exp28-full.tar.gz", root / "full_inventory.csv.gz"
    report = namespace["replay"](package, root / "results", full_archive, full_inventory)
    classification = "PUBLIC_REPLAYABLE" if report["status"] == "PASS" and args.full else "PASS_LIGHTWEIGHT_REPLAY" if report["status"] == "PASS" else "NOT VERIFIABLE"
    result = {"classification": classification, "status": report["status"], "started_utc": started, "elapsed_seconds": time.monotonic() - start,
              "code_revision": args.code_revision, "data_revision": args.data_revision,
              "urls": urls, "download_sha256": {"code": code_sha, "data": data_sha, "receipt": receipt_sha, **full_hashes},
              "anonymous": True, "fresh_directory": True, "read_guard": "PASS",
              "private_path_rejection_probes": "PASS", "subprocesses": "FORBIDDEN_AFTER_GUARD",
              "hardware": hardware, "command": sys.argv, "replay": report}
    (root / "accessed_files.json").write_text(json.dumps(sorted(accesses), indent=2) + "\n")
    (root / "public_replay.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "public_replay_receipt": str(root / "public_replay.json")}))
    if result["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
