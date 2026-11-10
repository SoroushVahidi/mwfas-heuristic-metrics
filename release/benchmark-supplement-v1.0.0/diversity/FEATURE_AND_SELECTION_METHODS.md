# Feature definitions, coverage bins and profile selection

The primary implementation is Python 3.12 standard library code. Each graph's raw, canonical weighted and canonical labeled topology hashes must match the authoritative register/audit before features are accepted. The independent validator uses a different parser plus SciPy's directed strong-component implementation. All 442 inputs passed; none was substituted, omitted or imputed.

## Representation and feature definitions

- Integer formats preserve every declared vertex `1..n`, including isolates. Standard headers are `p sp n m` or `p graph n m`. Ali uses the documented `p NAME n m` form; the fifth arc field is a transit-time annotation, not the MWFAS weight. Both forms reject invalid endpoints, counts, nonpositive/noninteger weights, self-loops and duplicate arcs.
- Wikimedia's published representation has UTF-8 endpoint labels, a trailing `kept_arcs` count, and the historical transformation header. All incident labels and arc multiplicities are preserved. There is no separate declared isolated-vertex set; measured counts describe this recorded graph, not unobserved original source vertices. No parallel records occur in these three actual inputs, but the parser and tests support their multiplicity contract.
- `n` is declared/represented vertex count; `m` counts directed arc records. `density` is unique directed endpoint pairs divided by `n(n−1)`; `arc_record_density` uses m. Both agree for all current inputs. Empty or singleton density is defined as zero.
- In/out degrees count arc records. Average in-degree and out-degree are m/n. Maximum, population CV, population standardized third moment, Gini, top-decile share and HHI are reported for in-degree, out-degree and total degree. Total degree is in+out. Zero-variance skew is defined as zero; this is a convention, not an estimated tail exponent.
- Strong components use iterative Kosaraju traversal. Cyclic components are size >1 because all input contracts exclude loops. We report SCC count, nontrivial SCC count, largest SCC size/fraction, arc fraction internal to nontrivial SCCs, vertex fraction in nontrivial SCCs, and weight fraction on those arcs. None is an optimal-feedback-set size or intrinsic-hardness estimate.
- Reciprocal-edge fraction is the proportion of unique directed endpoint pairs whose reverse exists. A reciprocal dyad contributes two directed arcs. It ignores weights.
- Weight statistics use strictly positive integer weights: min, max, mean, population CV/skew, Gini, top-decile share, HHI, range, max/min ratio and distinct-value count. The top decile includes the heaviest `ceil(m/10)` arcs. `tied_arc_fraction` counts arcs whose weight value occurs more than once; `weight_duplicate_excess_fraction = 1 − distinct_weights/m`. These two tie measures are deliberately distinct. Sorting ties does not change weighted sums.
- `NA` means undefined/inapplicable, not zero. Empty-graph weight statistics are NA; all actual 442 graphs have positive arc counts, so their structural/weight features are defined. Numerical-reference gaps are NA when there is no applicable reference. No missing solver result is replaced by a heuristic result.
- Raw objective/reference arithmetic remains integer. Feature ratios/moments use double-precision arithmetic and are descriptive, not exact mathematical proofs. Unnormalized total weights are exact integers. Excluded source-loop constants are preserved in a separate metadata field and not silently added to active-graph features.

`GRAPH_DIVERSITY_FEATURES.tsv` also carries exact graph/parent IDs, cohort, generator family or collection subgroup, recorded weight regime, normalization, input hashes, public-access and current rights classes, verified-witness coverage, existing numerical-reference class, original outcome status counts and existing heuristic-gap descriptors. No distinct weighted variants are merged.

## Coverage bins

Numeric cut points come from empirical one-third/two-third quantiles with each labeled topology identity carrying total mass one. Thus the 99 paired EXP06 weight variants do not double the influence of their topology on structural boundaries. Weight-feature quantiles also use this weighting, splitting each pair's total mass across its two weight versions. All equal-valued records stay together; these are benchmark-relative coverage bins, not universal definitions of small, hard or dense.

| Dimension | Lower / middle boundary | Middle / upper boundary |
|---|---:|---:|
| Vertices | 28 | 240 |
| Directed density | 0.0252100840 | 0.1481481481 |
| Largest SCC vertex fraction | 0.8 | 0.9833333333 |
| Arc fraction internal to cyclic SCCs | 0.7916666667 | 0.9883333333 |
| Cyclic vertex fraction | 0.8 | 0.9833333333 |
| Reciprocal directed-arc fraction | 0.0222222222 | 0.0791666667 |
| Total-degree Gini | 0.1527777778 | 0.2361111111 |
| Heaviest-decile weight share | 0.1891633546 | 0.2001415261 |
| Weight CV | 0.5703252797 | 0.5983561389 |

Lower is `x ≤ cut1`; middle is `cut1 < x ≤ cut2`; upper is `x > cut2`. Exact values are in `BIN_DEFINITIONS.json`. The very narrow middle weight bands are themselves evidence of the dominant uniform-weight regime. Calling the lower cyclic tercile “weakly cyclic” would be misleading: it extends to 79.17% cyclic arcs. We therefore retain relative labels, add the exact acyclic/mixed/all-cyclic boundary categories, and report actual ranges. Size landmarks of 1,000/10,000 and the descriptive ≤10% cyclic-arc tail are transparent supplementary diagnostics, not selection thresholds or hardness classes.

`STRUCTURAL_COVERAGE_MATRIX.tsv` includes all, table45, traceable-empirical and EXP05 scopes; zero-count cells are explicit. `STRUCTURAL_CROSS_COVERAGE.tsv` crosses size, density, origin and reference categories to expose missing combinations that marginal summaries conceal.

## Weighting and independence

For each scope, coverage is reported as:

1. Raw record fraction.
2. Topology-balanced fraction: each contract-scoped labeled topology receives equal total weight; weight variants share it.
3. Registered-parent-balanced fraction: each register parent receives equal total weight. This remains dominated by generated-topology groups and is **not** a count of independent empirical sources.
4. Generator-family / empirical-parent / collection-balanced fraction: each generator family or named empirical parent or unresolved Ali collection receives equal weight. This is an explicit descriptive sensitivity scheme, not a population sampling model.

The primary empirical source-aware interpretation uses only the 44 traceable empirical views, with each of eight named parent lineages assigned 1/8 total mass and its views sharing that mass. EXP05 uses four parents at 1/4 each. Collection origins and statistical independence remain unresolved; source identity is not an independence proof. Inverse source-share HHI is a concentration index, not an inferential effective sample size.

`SOURCE_DOMAIN_MAP.tsv` gives a transparent five-domain grouping of the eight traceable empirical parents: communication, economic input-output, online governance, web navigation, and transportation/mobility. Ali remains mixed/unresolved. Alternative reasonable domain taxonomies do not create additional original datasets.

## Optional profile algorithm

`analyze_coverage.py` constructs profiles deterministically from existing records:

1. Rank-normalize n, density, cyclic-arc fraction, largest-SCC fraction, total-degree Gini, heaviest-decile weight share and reciprocity over distinct observed values. Use mean L1 distance for medoids; no learned model or fitted embedding.
2. For table45, group by existing generator family × recorded weight regime × actual design size. Select each cell's medoid, avoiding an already selected labeled topology. Tie-break on graph ID. There are 33 supported cells, not a newly filled factorial design.
3. Greedily add records that cover the most uncovered marginal feature-bin/support/difficulty labels; tie-break by overall medoid distance then graph ID. Keep topology uniqueness. This adds one record, giving a 34-record core.
4. For the broader source-diverse profile, retain that core; add one medoid from each of the eight traceable empirical parents and each of the five represented Ali subdirectories. Ali subdirectories are collection strata, not invented scientific parents. Add further uncovered marginal witnesses only if needed; permit at most two records per empirical parent. None was needed here. The result is 47 records / 47 labeled topology identities.
5. Verify all profiles' hash/record joins and actual coverage. Save exact choices/reasons in `BALANCED_SUBSET_MANIFEST.tsv` and explicit analysis weights in `BALANCED_PROFILE_WEIGHTS.tsv`.

The profiles cover the observed marginal bins and named source strata, **not every interaction, size extremum, generation parameter, repeated seed or matched-weight pair**. This is a deterministic coverage heuristic, not an optimal set-cover proof or a pre-registered experimental test set. Reference/historical difficulty labels are used for descriptive coverage; selection does not target an algorithm's wins. A benchmark-generalization claim must not be based on this selected sample alone. Use the full 99 EXP06 topology pairs for paired weight-effect inference.
