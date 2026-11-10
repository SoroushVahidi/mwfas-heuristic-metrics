"""Optional existing EXP13 source transformation; no optimizer execution."""
import csv,gzip,json,sys
from pathlib import Path
from collections import defaultdict
from reconstruct_exp05_inputs import Fetcher,digest,require
STATES = {1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20,
          21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36,
          37, 38, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 53, 54, 55, 56}

def raw_edges(source: Path, parent: str) -> tuple[dict[tuple[str, str], int], int, int]:
    edge = defaultdict(int)
    loop = 0
    retained = 0
    if parent == "openflights":
        countries = {}
        with (source / "openflights-airports.dat").open(newline="") as stream:
            for row in csv.reader(stream):
                if row[0].isdigit():
                    countries[int(row[0])] = row[3]
        with (source / "openflights-routes.dat").open(newline="") as stream:
            for row in csv.reader(stream):
                if not row[3].isdigit() or not row[5].isdigit():
                    continue
                start, end = int(row[3]), int(row[5])
                if countries.get(start) != "United States" or countries.get(end) != "United States" or row[7] != "0":
                    continue
                if start == end:
                    loop += 1
                else:
                    edge[(f"airport:{start}", f"airport:{end}")] += 1
                    retained += 1
    elif parent == "census_lodes":
        with gzip.open(source / "de_od_main_JT00_2022.csv.gz", "rt", newline="") as stream:
            for row in csv.DictReader(stream):
                start, end = "tract:" + row["h_geocode"][:11], "tract:" + row["w_geocode"][:11]
                value = int(row["S000"])
                if not row["h_geocode"].startswith("10") or not row["w_geocode"].startswith("10") or value < 1:
                    raise ValueError("LODES source contract failed")
                if start == end:
                    loop += value
                else:
                    edge[start, end] += value
                    retained += 1
    elif parent == "irs_soi":
        with (source / "countyoutflow2122.csv").open(encoding="latin-1", newline="") as stream:
            for row in csv.DictReader(stream):
                start_state = int(row["y1_statefips"])
                end_state = int(row["y2_statefips"])
                start_county = int(row["y1_countyfips"])
                end_county = int(row["y2_countyfips"])
                if start_state not in STATES or end_state not in STATES or start_county < 1 or end_county < 1:
                    continue
                value = int(row["n1"])
                if value == -1:
                    continue  # IRS privacy suppression, not a negative migration weight.
                if value < 1:
                    raise ValueError("unexplained IRS nonpositive count")
                start = f"county:{start_state:02d}{start_county:03d}"
                end = f"county:{end_state:02d}{end_county:03d}"
                if start == end:
                    loop += value
                else:
                    edge[start, end] += value
                    retained += 1
    else:
        raise ValueError("unapproved source parent")
    return dict(edge), loop, retained
if __name__=='__main__':
 root=Path(__file__).resolve().parents[1];cache=Path(sys.argv[1]).resolve();require(not cache.is_relative_to(root),'cache outside package');f=Fetcher(cache)
 urls={'de_od_main_JT00_2022.csv.gz':'https://lehd.ces.census.gov/data/lodes/LODES8/de/od/de_od_main_JT00_2022.csv.gz','countyoutflow2122.csv':'https://www.irs.gov/pub/irs-soi/countyoutflow2122.csv'}
 specs=json.loads((root/'protocol/exp13_source_selection.json').read_text())['selected'];report=[]
 for spec in specs:
  for x in spec['source_files']:f.get(urls[x['name']],x['sha256'],x['name'])
  edges,loops,retained=raw_edges(cache,spec['source_parent']);require(loops==spec['original_loop_weight_constant'],'loop constant')
  vertices=sorted({v for edge in edges for v in edge});index={v:i for i,v in enumerate(vertices,1)};arcs=sorted((index[u],index[v],w)for(u,v),w in edges.items())
  b=(f'p graph {len(vertices)} {len(arcs)}\n'+''.join(f'a {u} {v} {w}\n'for u,v,w in arcs)).encode();require(digest(b)==spec['dimacs_sha256'],'graph bytes')
  report.append({'graph_id':spec['instance_id'],'dimacs_sha256':digest(b),'excluded_loop_weight':loops,'status':'PASS'})
 print(json.dumps({'status':'PASS','graphs':report,'upstream_fetches':f.receipts},indent=2))
