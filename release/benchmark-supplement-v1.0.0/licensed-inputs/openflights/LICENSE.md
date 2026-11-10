# OpenFlights derivative database

This graph is derived from the OpenFlights Airport and Route Databases, https://openflights.org/data.php, snapshot jpatokal/openflights commit 56a3cce4d50309cb79948103a48c7f87d09b3056. Attribution: OpenFlights and its contributors; transformation by Soroush Vahidi.

The source databases and this derivative database are available under the Open Database License 1.0: https://opendatacommons.org/licenses/odbl/1-0/. Individual database contents use the Database Contents License 1.0: https://opendatacommons.org/licenses/dbcl/1-0/. The graph file is NOT covered by the release's general CC BY notice.

Transformation: retain non-stop routes with numeric airport IDs and both airports in the United States; aggregate parallel route records as integer weights, remove self-loops while retaining their documented constant, sort labels, assign contiguous integer vertex IDs, and serialize directed weighted arcs. Source hashes and the exact transformation are in ../../profile_tools/upstream_specs.json and ../../profile_tools/recover_exp28_sources.py. No source endorsement is implied. No warranties; unsuitable for navigation.
