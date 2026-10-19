"""Independently replay printed Table 9 and every numerical Figure 2 point."""
from __future__ import annotations
import csv
from decimal import Decimal
import gzip
import hashlib
import io
import json
import math
import platform
import runpy
import shutil
import statistics
import sys
import tarfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKS = runpy.run_path(str(HERE / 'exp28_checks.py'))
need, sha, graph, score = (CHECKS[k] for k in ('need', 'sha', 'graph', 'score'))


def read(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def horizons(task):
    return (30, 120) if task['graph_id'].startswith(('exp04_', 'exp06_')) else (120, 300)


class BytesOrder:
    def __init__(self, data):
        self.data = data

    def read_text(self):
        return self.data.decode()

    def open(self, **kwargs):
        return io.StringIO(self.read_text(), newline=kwargs.get('newline'))


def verify_full(archive, inventory_path, graphs, tasks, expected_events):
    """Verify every original permitted byte and every complete saved order."""
    with gzip.open(inventory_path, 'rt', newline='') as stream:
        inventory = {r['path']: r for r in csv.DictReader(stream)}
    need(len(inventory) == 286750, 'full archive inventory count')
    seen, order_values = set(), {}
    event_count = order_count = 0
    cache = {}
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            need(member.isfile() and member.name in inventory and member.name not in seen, 'full archive member')
            seen.add(member.name)
            data = tar.extractfile(member).read()
            rec = inventory[member.name]
            need(int(Decimal(member.pax_headers['mtime'])*10**9) == int(rec['source_mtime_ns']), 'archival nanosecond timestamp')
            digest = hashlib.sha256(data).hexdigest()
            need(digest == rec['sha256'] and len(data) == int(rec['bytes']), 'full file hash/size')
            if rec['kind'] == 'event':
                e = json.loads(data)
                envelope = expected_events[(e['task_id'], e['index'])]
                need(e == envelope['event'] and digest == envelope['event_sha256'] and
                     int(rec['source_mtime_ns']) == envelope['event_mtime_ns'], 'full/light event identity')
                event_count += 1
            elif rec['kind'] == 'saved_order':
                tid = member.name.split('/')[2]
                task = tasks[tid]
                key = (task['graph_id'], task['arm'].startswith('xiong_'), digest)
                if key not in cache:
                    n, arcs = graphs[task['graph_id']]
                    cache[key] = score(BytesOrder(data), task['arm'], n, arcs)
                order_values[member.name] = (digest, cache[key], int(rec['source_mtime_ns']))
                order_count += 1
    need(seen == set(inventory) and event_count == order_count == 143241, 'full archive incomplete')
    for envelope in expected_events.values():
        e = envelope['event']
        name = f"effective/tasks/{e['task_id']}/{e['order_file']}"
        need(order_values[name] == (e['order_sha256'], e['reported_objective'], envelope['order_mtime_ns']),
             'full saved-order objective/hash/publication mismatch')
    return {'files': len(seen), 'events': event_count, 'orders': order_count,
            'unique_graph_order_encodings_scored': len(cache), 'status': 'PASS'}


def replay(package, output, full_archive=None, full_inventory=None):
    output.mkdir(parents=True, exist_ok=False)
    delivery = read(package / 'manifest.json')
    names = set()
    for rec in delivery['files']:
        path = package / rec['path']
        need(path.resolve().is_relative_to(package.resolve()) and rec['path'] not in names, 'manifest path/duplicate')
        names.add(rec['path'])
        need(path.stat().st_size == rec['bytes'] and sha(path) == rec['sha256'], 'package member changed: '+rec['path'])
    source_module = runpy.run_path(str(HERE / 'recover_exp28_sources.py'))
    sources = source_module['recover'](read(package / 'sources.json'), output / 'upstream', package / 'graphs')
    if not all(s['status'] == 'PASS' for s in sources):
        result = {'status': 'NOT VERIFIABLE', 'sources': sources, 'table9': 'NOT VERIFIABLE', 'figure2': 'NOT VERIFIABLE'}
        write(output / 'replay.json', result)
        return result
    effective = package / 'effective'
    manifest, protocol = read(effective / 'manifest.json'), read(package / 'protocol_broad.json')
    for rec in read(package/'reference/original_code_manifest.json'):
        need(sha(HERE/'exp28_original'/rec['path']) == rec['sha256'], 'original code snapshot hash')
    for key, filename in [('controller_sha256','campaign.py'), ('worker_sha256','worker.py'),
                          ('instrumented_ipsns_sha256','ipsns_pinned_instrumented.py'),
                          ('independent_auditor_sha256','audit.py')]:
        need(sha(HERE/'exp28_original/experiments/exp28_anytime'/filename) == manifest[key], 'original executed source hash')
    need(sha(effective / 'manifest.json') == '639706bdcedcb02a89d1e145f62d65ca5072d738906bd0b1fe06d2c7d9611960', 'original manifest pin')
    need(sha(package / 'protocol_broad.json') == manifest['protocol_sha256'] ==
         'c389a6ffd31b3fd66c8a868e6cf95e95a61414b3e12648655f37573c807e8310', 'protocol pin')
    need(manifest['tasks'] == protocol['tasks'] and len(protocol['tasks']) == 117, 'task roster')
    tasks = {t['task_id']: t for t in manifest['tasks']}
    need(len(tasks) == 117 and sum(t['cap_seconds'] for t in tasks.values()) == protocol['nominal_cap_seconds'], 'task identities/caps')
    graphs = {gid: graph(package / 'graphs' / (gid+'.d'), meta) for gid, meta in manifest['inputs'].items()}
    need(len(graphs) == 13, 'graph coverage')
    provenance = read(effective / 'recovery_provenance.json')
    need(sha(effective/'recovery_provenance.json') == 'cf4b162dea4139b4f929a581914244190466b71ef5540018dfa4ddc78f7f055c', 'recovery pin')
    old = package / 'original_before_recovery'
    tid = provenance['recovered_task_id']
    for filename, key in [('manifest.json', 'original_manifest_sha256'), ('audit_report.json', 'original_audit_report_sha256'),
                          ('checkpoints/'+tid+'.json', 'original_invalid_checkpoint_sha256')]:
        need(sha(old/filename) == provenance[key], 'original recovery evidence changed')
    need(read(old/'manifest.json')['tasks'] == manifest['tasks'], 'original/effective selection identities differ')
    need(sha(old/'checksums.sha256') == '89176452fe3b6378fd87b7e91b4a96f4dab65e5f59338549a50486cf75b55c2d', 'original production seal')
    old_seal = {name: h for h, name in (line.split('  ', 1) for line in (old/'checksums.sha256').read_text().splitlines())}
    selection = read(package/'task_selection.json')
    need(len(selection) == 117 and {r['task_id'] for r in selection} == set(tasks), 'selection roster')
    for rec in selection:
        name = 'checkpoints/'+rec['task_id']+'.json'
        replaced = rec['task_id'] == provenance['recovered_task_id']
        need(rec['original_checkpoint_sha256'] == old_seal[name] and
             rec['effective_checkpoint_sha256'] == sha(effective/name) and
             ((old_seal[name] != sha(effective/name)) == replaced) and
             rec['selection'] == ('DECLARED_REPLACEMENT' if replaced else 'UNCHANGED_ORIGINAL'), 'selection lineage')
    original_cp = read(old/'checkpoints'/(tid+'.json'))
    need(original_cp['status'] == 'INVALID' and original_cp['task_wall_seconds'] > 120, 'original INVALID not retained')
    seals = (effective / 'checksums.sha256').read_text().splitlines()
    need(len(seals) == 120, 'effective seal coverage')
    for line in seals:
        expected, name = line.split('  ', 1)
        need((effective/name).resolve().is_relative_to(effective.resolve()) and sha(effective/name) == expected, 'effective seal')
    checkpoints = {tid: read(effective/'checkpoints'/(tid+'.json')) for tid in tasks}
    need(Counter(cp['status'] for cp in checkpoints.values()) == {'PASS': 98, 'TIMEOUT': 19}, 'statuses recoded')
    need(checkpoints[provenance['recovered_task_id']]['status'] == 'TIMEOUT' and
         sha(effective/'checkpoints'/(provenance['recovered_task_id']+'.json')) ==
         'f4e5c372ddb6ee51b12f282bba209d51fe3e01fe81f571118b12c2f98452c550', 'replacement checkpoint')
    scans, selected, events, prior = {}, {}, {}, {}
    for tid, task in tasks.items():
        cp = checkpoints[tid]
        need(all(cp[k] == v for k, v in task.items()), 'checkpoint task mismatch')
        need(cp['wall_budget_compliant'] and 0 <= cp['task_wall_seconds'] <= task['cap_seconds'] and
             abs(cp['deadline_monotonic'] - cp['start_monotonic'] - task['cap_seconds']) < 1e-6 and
             cp['end_unix_ns'] >= cp['start_unix_ns'] and cp['child_cpu_seconds'] >= 0, 'controller timing')
        scans[tid] = {'task_id': tid, 'events_checked': 0, 'first': {str(b): None for b in horizons(task)},
                      'best': {str(b): None for b in horizons(task)}, 'first_index': {}, 'best_index': {},
                      'boundary_disagreements': []}
    with gzip.open(package/'events.jsonl.gz', 'rt') as stream:
        for line in stream:
            envelope = json.loads(line)
            e = envelope['event']
            tid = e['task_id']
            task, cp, scan = tasks[tid], checkpoints[tid], scans[tid]
            i = scan['events_checked']
            seed = task['seed'] if i == 0 or not task['arm'].startswith('xiong_') else 1+((task['seed']*1000003+i*104729)%2147483646)
            need(e['index'] == i and e['seed'] == seed, 'event identity/seed sequence')
            need(envelope['event_path'] == f'effective/tasks/{tid}/event_{i:06d}.json', 'event path')
            need(Path(e['order_file']).name == e['order_file'], 'unsafe ordering path')
            actual_ns = envelope['event_mtime_ns'] - cp['start_unix_ns']
            need(0 <= actual_ns < task['cap_seconds']*10**9 and
                 cp['start_unix_ns'] <= envelope['order_mtime_ns'] <= envelope['event_mtime_ns'], 'actual publication deadline/causality')
            need(0 <= e['elapsed_seconds'] < task['cap_seconds'] and
                 cp['start_monotonic'] <= e['saved_monotonic'] < cp['deadline_monotonic'] and
                 abs(e['elapsed_seconds']-(e['saved_monotonic']-cp['start_monotonic'])) < 1e-7 and
                 e['elapsed_seconds'] >= prior.get(tid, 0), 'monotonic clock')
            prior[tid] = e['elapsed_seconds']
            if task['arm'] == 'ipsns':
                extra = e['extra']
                need(extra['graph_sha256'] == task['graph_sha256'] and extra['kind'] in
                     ('wmsf_seed','lr_seed_improvement','complete_initializer','refinement_improvement') and
                     isinstance(extra['iteration'], int) and extra['iteration'] >= 0, 'IPSNS provenance')
                need(i != 0 or (extra['kind'] == 'wmsf_seed' and extra['iteration'] == 0), 'IPSNS initializer')
            events[(tid, i)] = envelope
            for budget in horizons(task):
                b = str(budget)
                reported, published = e['elapsed_seconds'] <= budget, actual_ns <= budget*10**9
                if reported != published:
                    scan['boundary_disagreements'].append(i)
                if reported and published:
                    if scan['first'][b] is None:
                        scan['first'][b], scan['first_index'][b] = actual_ns/1e9, i
                    if scan['best'][b] is None or e['reported_objective'] < scan['best'][b]:
                        scan['best'][b], scan['best_index'][b] = e['reported_objective'], i
            scan['events_checked'] += 1
    need(len(events) == 143241, 'event coverage')
    for tid, scan in scans.items():
        need(scan['events_checked'] == checkpoints[tid]['event_count'] and not scan['boundary_disagreements'], 'event count/boundary')
        indices = set(scan['first_index'].values()) | set(scan['best_index'].values())
        scan['selected_witnesses_checked'] = len(indices)
        need(all(v is not None for v in scan['best'].values()), 'missing horizon incumbent')
        for i in indices:
            e = events[(tid, i)]['event']
            name = f"effective/tasks/{tid}/{e['order_file']}"
            task = tasks[tid]
            n, arcs = graphs[task['graph_id']]
            need(sha(package/name) == e['order_sha256'] and
                 score(package/name, task['arm'], n, arcs) == e['reported_objective'], 'selected objective/permutation/DAG')
            selected[name] = e['order_sha256']
    need(len(selected) == 160 and set(selected) == set(read(package/'selection.json')['selected_order_paths']), 'witness roster')
    full_result = {'status': 'NOT REQUESTED', 'orders': 0}
    if full_archive is not None:
        need(sha(full_archive) == delivery['full_archive_sha256'] and
             sha(full_inventory) == delivery['full_inventory_sha256'], 'full archive pins')
        full_result = verify_full(full_archive, full_inventory, graphs, tasks, events)
    # Reuse accepted statistical formulas with freshly reconstructed scans.
    stats_input = output/'statistics_inputs'
    stats_input.mkdir()
    for path in effective.iterdir():
        if path.is_file():
            shutil.copyfile(path, stats_input/path.name)
    for gid in graphs:
        write(stats_input/('graph-'+gid+'.json'), {'scans': [scans[t['task_id']] for t in tasks.values() if t['graph_id']==gid]})
    stats_module = runpy.run_path(str(HERE/'exp28_statistics.py'))
    summary = stats_module['main'](stats_input, package/'protocol_broad.json')
    need(summary == read(package/'reference/integration_summary.json'), 'frozen integration statistics differ')
    write(output/'integration_summary.json', summary)
    lookup = {(t['graph_id'],t['arm'],t['seed']): t['task_id'] for t in tasks.values()}
    figure = []
    expected_figure = {(r['graph_id'],int(r['budget_seconds'])):r for r in read(package/'reference/figure2.json')}
    for gid, cfg in protocol['graphs'].items():
        for budget in horizons({'graph_id':gid}):
            a = scans[lookup[(gid,'ipsns',1)]]['best'][str(budget)]
            b = scans[lookup[(gid,'xiong_single',1)]]['best'][str(budget)]
            ref = expected_figure[(gid,budget)]
            need(a == int(ref['ipsns_objective']) and b == int(ref['comparator_objective']) and
                 math.isclose((a-b)/cfg['total_weight'],float(ref['normalized_difference']),abs_tol=1e-14), 'Figure 2 data')
            figure.append({'graph_id':gid,'family':cfg['family'],'horizon_seconds':budget,
                           'ipsns_objective':a,'rasstar_objective':b,'total_weight':cfg['total_weight'],
                           'gain_pp':100*(b-a)/cfg['total_weight'],'status':'PASS'})
    need(len(figure) == 26, 'Figure 2 point count')
    write(output/'figure2_points.json', figure)
    cells = []
    for row_index, ref in enumerate(read(package/'reference/table9.json')):
        cohort = 'synthetic' if ref['cohort']=='Selected synthetic' else 'empirical'
        arm = 'xiong_single' if ref['arm']=='Single' else 'xiong_restarts'
        budgets = [int(b) for b in ref['horizon'].split('/')]
        previous = None
        for budget in budgets:
            group = next(r for r in summary['comparisons'] if r['cohort']==cohort and r['budget_seconds']==budget and r['comparator']==arm)
            actual = {'pairs':group['paired'], 'wtl':f"{group['wins']}/{group['ties']}/{group['losses']}",
                      'median_gain_pp':f"{group['median_ipsns_gain_pp']:+.3f}"}
            need(all(actual[k] == ref[k] for k in actual), 'printed Table 9 cell differs')
            values = [(gid,scans[lookup[(gid,'ipsns',1)]]['best'][str(budget)],
                       scans[lookup[(gid,arm,1)]]['best'][str(budget)]) for gid in graphs
                      if gid.startswith(('exp04_','exp06_')) == (cohort=='synthetic')]
            need(previous is None or values == previous, 'slash-combined horizons differ')
            previous = values
        for key in ('pairs','wtl','median_gain_pp'):
            cells.append({'row':row_index+1,'column':key,'expected':ref[key],'actual':actual[key],'status':'PASS'})
        cells.append({'row':row_index+1,'column':'horizon','expected':ref['horizon'],'actual':'/'.join(map(str,budgets)),'status':'PASS'})
    write(output/'table9_cells.json',cells)
    result = {'status':'PASS','table9':'PASS','figure2':'PASS',
              'graphs':len(graphs),'tasks':len(tasks),'statuses':dict(Counter(cp['status'] for cp in checkpoints.values())),
              'events':len(events),'selected_orders':len(selected),'budget_rows':234,'paired_rows':182,
              'table9_displayed_numeric_cells':len(cells),'figure2_points':len(figure),
              'full_archive':full_result,'sources':sources,'python':sys.version,
              'seeds':'Original task seeds retained (IPSNS 1 and 2); statistics bootstrap seed 28',
              'validation':'Graph identity; complete permutations; weighted objectives; retained DAGs; publication eligibility; historical selection; all cells/points',
              'hardware_note':'Manifest login CPU is not verified per-task hardware; no cross-hardware speed claim.'}
    write(output/'replay.json',result)
    return result


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('package',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--full-archive',type=Path)
    p.add_argument('--full-inventory',type=Path)
    a = p.parse_args()
    result = replay(a.package,a.output,a.full_archive,a.full_inventory)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status']=='PASS' else 2)
