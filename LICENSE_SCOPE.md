# License and credit scope

Copyright (c) 2026 Soroush Vahidi for his original contributions.

- `src/mwfas_data/*.py`, `scripts/*.py`, `release/*.py`, and `tests/*.py`: MIT, [full text](LICENSES/MIT.txt). These files use separately installed dependencies; their licenses are not replaced by MIT.
- `README.md`, `LICENSE_SCOPE.md`, `.gitignore`, `docs/*.md`, `CITATION.cff`, `configs/*.json`, `data/manifests/*.json`, `release/public_reference_manifest.csv`, `release/manifest.json`, `release/CHECKSUMS.sha256`, and `tests/fixtures/triangle.dimacs`: CC BY 4.0 for author-controlled original content, [full text](LICENSES/CC-BY-4.0.txt). Factual references, URLs, source hashes, and third-party rights are not relicensed.
- `pyproject.toml` and `uv.lock`: MIT for author-authored configuration only. Dependency package contents remain under their own licenses.
- `LICENSES/MIT.txt` and `LICENSES/CC-BY-4.0.txt`: their own published license texts.

The `release/public_reference_manifest.csv` is a list of references and hashes. This repository does not grant rights to any referenced graph, ordering, Hugging Face file, external code, or solver material. The original Hugging Face dataset has its own limited CC BY 4.0 notice. Consult [source attribution](docs/SOURCE_ATTRIBUTION.md) before using source data.

Please cite the dataset and this software as described in [CITATION.cff](CITATION.cff). Scholarly citation guidance is separate from MIT's conditions.

## Table 4/5 reproducibility release (2026-10-19)

`release/public_reproducibility/*.py` and the added tests are author-owned MIT
code. `release/public_reproducibility/*.md` is CC BY 4.0 documentation. The
separately versioned HF release licenses its author-generated synthetic graph,
order, task, numerical-evidence and metadata files under CC BY 4.0 and its
original project/statistical code under MIT, as listed in its file manifest.
These grants do not extend to dependency packages or external source software.
