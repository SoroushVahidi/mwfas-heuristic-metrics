Author-owned synthetic graphs, order outputs, task/status projections and analysis
receipts: Soroush Vahidi, CC BY 4.0. Replay code: MIT; license texts are in the
parent `licenses` directory. Location-prefix redactions are documented in the
lineage ledger. All original scientific statuses and values remain unchanged.

Third-party graph files are **not included**. `sources.py` retrieves their pinned
upstream bytes, checks SHA-256, and implements the exact recorded transformations:

* Stanford SNAP: CollegeMsg (Panzarasa et al.), Email-Eu-core (Leskovec et al.),
  Wiki-Vote (Leskovec et al.); https://snap.stanford.edu/data/ . Retain original
  dataset attribution and follow each source's terms for further redistribution.
* EXIOBASE-derived LOP benchmark, Zenodo record 20554376; source zip and each
  selected member are independently hash-pinned. The selected integer matrices
  are not relabeled as the underlying EXIOBASE database or redistributed here.
* Ali Dasdan, graph-benchmarks commit
  77e5b8b4f1e1a1b8e80cfb9430f90492ffee3675. Download original files from that
  commit; retain the upstream license and attribution. No claim of historical
  Hugging Face byte identity is made.
* OpenFlights: jpatokal/openflights commit
  56a3cce4d50309cb79948103a48c7f87d09b3056. OpenFlights database licensing applies
  (ODbL/Database Contents License, https://openflights.org/data.php).
* U.S. Census Bureau LEHD LODES8 Delaware 2022 OD main JT00; U.S. IRS SOI county
  outflow 2021–2022. These U.S. government data are downloaded directly from
  their declared agencies with content hashes; agency attribution is preserved.

Wikimedia graph/order artifacts and EXP04/06 inputs are consumed at their existing
public immutable dataset revisions, under those releases' existing license scopes.
The original-author RASstar executable and Gurobi are not redistributed or needed
for saved-order replay. Original source revisions remain in the run manifests.
