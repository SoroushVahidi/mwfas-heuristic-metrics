# Public diversity descriptors and optional benchmark profiles

The two profiles contain existing record IDs only. They do not redistribute graphs. The 34-record table45 core is wholly in the pinned public archive. The 47-record option has 35 directly released inputs and 12 upstream-route inputs. Routes and prior verification status are in PROFILE_ACCESS_VERIFICATION.tsv. Upstream availability does not confer redistribution rights; Wikimedia requires its separate representation adapter. Use ../profile_tools/resolve_profiles.py for exact public/upstream resolution; selection remains an optional proposed evaluation profile.

Reproduce selection with Python 3.12, standard library only:

```bash
python3 -B scripts/analyze_coverage.py .
```

This recalculates coverage and the deterministic manifests from supplied audited features; it does not read graph files or run optimization. Run from a copy if preserving every shipped output byte matters. All exact selections reproduce the prior audit, apart from removal of workstation-only receipt paths. Methods, feature definitions, weight conventions and profile limits are in FEATURE_AND_SELECTION_METHODS.md. The complete 99 EXP06 topology pairs remain necessary for paired weight analysis.
