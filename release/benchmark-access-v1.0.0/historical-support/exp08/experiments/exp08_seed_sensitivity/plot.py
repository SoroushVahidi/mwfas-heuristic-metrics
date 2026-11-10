"""Render the independently validated EXP08 convergence CSV with matplotlib."""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


def plot(csv_path: Path, png_path: Path, pdf_path: Path) -> None:
    curves = defaultdict(lambda: defaultdict(list))
    with csv_path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            curves[row["instance_id"]][int(row["seed"])].append(
                (int(row["iteration"]), float(row["best_backward_weight"])))
    columns = 3
    rows = math.ceil(len(curves) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(12, 3 * rows), sharex=True, squeeze=False)
    for ax, (instance, seeds) in zip(axes.flat, sorted(curves.items())):
        for seed, points in sorted(seeds.items()):
            points.sort()
            ax.step([x for x, _ in points], [y for _, y in points], where="post",
                    linewidth=1.5, alpha=.7, label=f"seed {seed}")
        ax.set_title(instance.replace("exp04_", ""), fontsize=10)
        ax.set_ylabel("Best backward weight")
        ax.set_xlim(0, 50)
        ax.grid(alpha=.25)
    for ax in list(axes.flat)[len(curves):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("Iteration")
    axes[0, 0].legend(fontsize=7, ncol=2)
    fig.suptitle("IPSNS best objective by iteration across five seeds")
    fig.tight_layout()
    fig.savefig(png_path, dpi=180)
    fig.savefig(pdf_path)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    args = parser.parse_args()
    plot(args.csv, args.png, args.pdf)
