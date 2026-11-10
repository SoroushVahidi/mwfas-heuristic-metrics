# Private EXP22 method-literature crosswalk

Checked against the current private `manuscript/references.bib` and the prior independent literature/baseline audits on 18 October 2026. “Tested” means an implementation actually ran in a named campaign, not that the published authors' implementation was authenticated. This table is preparatory; it adds no manuscript citation or BibTeX entry.

| Work and final identity | Current key / version relation | Relevance and tested software |
|---|---|---|
| Eades, Lin & Smyth, *Information Processing Letters* 47 (1993), DOI `10.1016/0020-0190(93)90079-O` | `eades1993heuristic`; final article cited | Ordering lineage. Weighted igraph wrapper tested EXP04/06/12/13; original author software not claimed. |
| Demetrescu & Finocchi, *Information Processing Letters* 86 (2003), DOI `10.1016/S0020-0190(02)00491-X` | `demetrescu2003feedback`; final cited | Combinatorial/local-ratio context; LR-TA project source tested, no author-software authentication. |
| Cavallaro, Cutello & Pavone, *J. Combin. Optim.* 48:30 (2024), DOI `10.1007/s10878-024-01209-8` | `cavallaro2024stable`; final cited | Minimal/stable FAS; no authenticated external executable tested. |
| Cavallaro & Cutello, SEKE 2025, DOI `10.18293/seke2025-049` | `cavallaro2025weighted`; final proceedings cited; `(S)` may appear as short-paper marker | Weighted WMSF/L2 lineage; project implementation tested, external author executable not tested. |
| Cavallaro, Cutello & Pavone, *Computers & Operations Research* 184 (2025) 107247, DOI `10.1016/j.cor.2025.107247` | **Not in current bibliography**; final article supersedes use of any earlier version for this work | Weighted/minimal/stable method context; implementation not tested. Verify exact objective/contract before any future method claim. |
| Xiong et al., *Computers & Operations Research* 169 (2024) 106724, DOI `10.1016/j.cor.2024.106724` | `xiong2024small`; final article cited | Original source RASstar at `8340e163…` tested EXP10/11/12/13; weighted invocation validated separately from paper's cardinality emphasis. |
| Bader et al., *Social Network Analysis and Mining* 15:68 (2025), DOI `10.1007/s13278-025-01491-2` | `bader2025rocket`; final article cited | EXP09 tested serial C component only; full Rocket-Crane not tested. EXP09B source audit blocked fidelity. |
| Hecht, Gonciarz & Horvát, *ACM Journal of Experimental Algorithmics* 26 (2021), DOI `10.1145/3447652` | **Not in current bibliography**; use final article, not preprint | TIGHT/TIGHT-CUT candidate, no weighted full-order adapter/authenticated executable tested. |
| Vahidi, IPSNS, SSRN DOI `10.2139/ssrn.6281222` | **Not in current bibliography** under current published-only journal policy; preprint, not independent published evidence | Project-frozen implementation tested EXP03–08/10/11; disclose overlap with prior algorithm manuscript before reference-task decision. |
| Vahidi, *The Journal of Supercomputing* 82:705 (2026), DOI `10.1007/s11227-026-08852-4` | `vahidi2026ranking`; published final cited; arXiv `2412.16181` is related earlier version, not another contribution | Accepted ranking paper; no separate OURS-Reach arm tested in EXP22. |
| Martí, Reinelt & Duarte, *Computational Optimization and Applications* 51 (2012), DOI `10.1007/s10589-010-9384-9` | `marti2012benchmark`; final cited | Dense LOP benchmarking context, not tested as software arm. |
| Fagiolo, Baioletti & Santucci, PPSN XIX, DOI `10.1007/978-3-032-36214-8_25` | `fagiolo2027linear`; publisher's cited print year 2027, first online 2026 | LOP/EXIOBASE context; no competing software tested. |

No publication is counted twice merely because a preprint or earlier conference record exists. Future reference integration requires a separate claim-to-source check and overlap review.
