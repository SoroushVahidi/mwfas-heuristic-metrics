"""Build indexed full and lightweight archives from the completed EXP28 stage.

Transfer integrity only: no objective rescoring or optimization. Original bytes
remain unchanged. Empirical graph files are excluded and recovered upstream.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import shutil
import tarfile
from collections import Counter
from pathlib import Path

ARCHIVE = '1332cbacf81ad954dff853810687f4bb4a469966ca5639a913f104b8f80fe7f3'
INVENTORY = '4b3d3e3b4a2f54c30fac4c596a6bca92a65c04dcb15dc95b1bfb78ee958300af'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def add_selection_evidence(light, original_seal):
    if sha(original_seal) != '89176452fe3b6378fd87b7e91b4a96f4dab65e5f59338549a50486cf75b55c2d':
        raise ValueError('original production seal differs')
    shutil.copyfile(original_seal, light/'original_before_recovery/checksums.sha256')
    old = {name: h for h, name in (line.split('  ', 1) for line in original_seal.read_text().splitlines())}
    manifest = json.loads((light/'effective/manifest.json').read_text())
    provenance = json.loads((light/'effective/recovery_provenance.json').read_text())
    selection = []
    for task in manifest['tasks']:
        tid = task['task_id']
        name = 'checkpoints/'+tid+'.json'
        effective = sha(light/'effective'/name)
        replaced = tid == provenance['recovered_task_id']
        if (effective == old[name]) == replaced:
            raise ValueError('original-versus-recovered selection mismatch')
        selection.append({'task_id': tid, 'selection': 'DECLARED_REPLACEMENT' if replaced else 'UNCHANGED_ORIGINAL',
                          'original_checkpoint_sha256': old[name], 'effective_checkpoint_sha256': effective})
    write(light/'task_selection.json', selection)


def build(original, output, repository, original_seal):
    if sha(original / 'exp28-original-evidence.tar.gz') != ARCHIVE or sha(original / 'file_inventory.csv') != INVENTORY:
        raise ValueError('completed archive/inventory integrity failure')
    output.mkdir(parents=True, exist_ok=False)
    light = output / 'exp28'
    light.mkdir()
    with (original / 'file_inventory.csv').open(newline='') as stream:
        inventory = {r['path']: r for r in csv.DictReader(stream)}
    if len(inventory) != 286754:
        raise ValueError('archive inventory coverage')
    checkpoints, states, selected_bytes, excluded, counts = {}, {}, {}, [], Counter()
    entries = []
    def save(name, data):
        path = light / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    with gzip.open(light / 'events.jsonl.gz', 'wt') as event_output, \
         gzip.open(output / 'full_inventory.csv.gz', 'wt', newline='') as inv_output, \
         tarfile.open(original / 'exp28-original-evidence.tar.gz', 'r|gz') as source, \
         tarfile.open(str(output / 'exp28-full.tar.gz'), 'w|gz', compresslevel=1) as full:
        writer = csv.DictWriter(inv_output, fieldnames=['path', 'sha256', 'bytes', 'source_mtime_ns', 'kind', 'release_scope'])
        writer.writeheader()
        seen = set()
        pending = None
        for member in source:
            if not member.isfile() or member.name not in inventory or member.name in seen:
                raise ValueError('unexpected archive entry')
            seen.add(member.name)
            record = inventory[member.name]
            data = source.extractfile(member).read()
            if re.search(rb'AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|hf_[A-Za-z0-9]{25,}|-----BEGIN [A-Z ]*PRIVATE KEY', data):
                raise ValueError('possible secret in intended archive member: ' + member.name)
            if hashlib.sha256(data).hexdigest() != record['sha256'] or len(data) != int(record['bytes']):
                raise ValueError('archived member integrity: ' + member.name)
            counts[record['kind']] += 1
            if record['release_scope'] == 'THIRD_PARTY_INPUT_PRIVATE_STAGING_ONLY':
                excluded.append({k: v for k, v in record.items() if k != 'source'})
                continue
            full.addfile(member, io.BytesIO(data))
            writer.writerow({k: record[k] for k in writer.fieldnames})
            name = member.name
            if record['kind'] == 'checkpoint':
                cp = json.loads(data)
                checkpoints[cp['task_id']] = cp
                states[cp['task_id']] = {'first': {}, 'best': {}, 'paths': {}}
                save(name, data)
            elif record['kind'] == 'event':
                event = json.loads(data)
                tid = event['task_id']
                cp, state = checkpoints[tid], states[tid]
                order_name = f"effective/tasks/{tid}/{event['order_file']}"
                order_record = inventory[order_name]
                published_ns = int(record['source_mtime_ns']) - cp['start_unix_ns']
                envelope = {'event': event, 'event_path': name, 'event_sha256': record['sha256'],
                            'event_mtime_ns': int(record['source_mtime_ns']),
                            'order_mtime_ns': int(order_record['source_mtime_ns'])}
                event_output.write(json.dumps(envelope, sort_keys=True) + '\n')
                changed = False
                for budget in ((30, 120) if tid.startswith(('exp04_', 'exp06_')) else (120, 300)):
                    if published_ns <= budget * 10**9 and event['elapsed_seconds'] <= budget:
                        if budget not in state['first']:
                            state['first'][budget] = order_name
                            changed = True
                        if budget not in state['best'] or event['reported_objective'] < state['best'][budget]:
                            state['best'][budget] = event['reported_objective']
                            state['paths'][budget] = order_name
                            changed = True
                pending = order_name if changed else None
            elif record['kind'] == 'saved_order':
                if name == pending:
                    selected_bytes[name] = data
                pending = None
            elif record['kind'] != 'worker_metadata':
                save(name, data)
        if seen != set(inventory):
            raise ValueError('archive is incomplete')
    if counts['event'] != 143241 or len(checkpoints) != 117 or len(excluded) != 4:
        raise ValueError('effective coverage changed')
    selected = {p for s in states.values() for p in (*s['first'].values(), *s['paths'].values())}
    if len(selected) != 160:
        raise ValueError('first/best witness selection changed')
    for path in sorted(selected):
        save(path, selected_bytes[path])
    write(light / 'selection.json', {'selected_order_paths': sorted(selected), 'rule': 'first and earliest strict best at each horizon; same task at both horizons'})
    write(light / 'excluded_graphs.json', excluded)
    shutil.copyfile(repository / 'release/public_reproducibility/exp28_sources.json', light / 'sources.json')
    for source, target in [('EXP28.md','README.md'), ('exp28_execution.json','execution_context.json'),
                           ('licenses/CC-BY-4.0.txt','LICENSES/CC-BY-4.0.txt'),
                           ('licenses/MIT.txt','LICENSES/MIT.txt'),
                           ('exp28_original/source_manifest.json','reference/original_code_manifest.json')]:
        save(target, (repository / 'release/public_reproducibility' / source).read_bytes())
    manuscript = (repository / 'manuscript/manuscript.tex').read_text()
    table = manuscript[manuscript.index('Selected synthetic & 30/120 & Single'):]
    table = table[:table.index('\\bottomrule')]
    cells = []
    for line in table.splitlines():
        fields = [s.strip().removesuffix('\\\\') for s in line.split('&')]
        if len(fields) == 6:
            cells.append({'cohort': fields[0], 'horizon': fields[1], 'arm': fields[2],
                          'pairs': int(fields[3]), 'wtl': fields[4],
                          'median_gain_pp': fields[5].strip('$')})
    if len(cells) != 5:
        raise ValueError('frozen printed Table 9 shape')
    save('reference/table9.tex', table.encode())
    write(light / 'reference/table9.json', cells)
    shutil.copyfile(repository / 'manuscript/EXP28_INTEGRATION_SUMMARY.json', light / 'reference/integration_summary.json')
    shutil.copyfile(repository / 'manuscript/figures/exp28_matched_budget.pdf', light / 'reference/figure2.pdf')
    shutil.copyfile(repository / 'analysis/exp28_integration/make_figure.py', light / 'reference/original_figure_generator.py')
    with (light / 'effective/paired_inventory.csv').open(newline='') as stream:
        figure = [r for r in csv.DictReader(stream) if r['comparator'] == 'xiong_single']
    if len(figure) != 26:
        raise ValueError('Figure 2 point coverage')
    write(light / 'reference/figure2.json', figure)
    add_selection_evidence(light, original_seal)
    for path in sorted(light.rglob('*')):
        if path.is_file():
            entries.append({'path': str(path.relative_to(light)), 'sha256': sha(path), 'bytes': path.stat().st_size,
                            'license': 'LICENSE_TEXT' if 'LICENSES' in path.parts else 'MIT' if path.suffix=='.py' else 'CC-BY-4.0-author-controlled'})
    write(light / 'manifest.json', {'format': 'exp28-public-v1', 'files': entries,
                                  'original_archive_sha256': ARCHIVE, 'original_inventory_sha256': INVENTORY,
                                  'full_archive_sha256': sha(output / 'exp28-full.tar.gz'),
                                  'full_inventory_sha256': sha(output / 'full_inventory.csv.gz'),
                                  'original_files_verified': len(seen), 'public_full_files': len(seen)-len(excluded),
                                  'events': 143241, 'selected_orders': 160,
                                  'manuscript_sha256': sha(repository / 'manuscript/manuscript.tex'),
                                  'licensing': 'Author-owned outputs/metadata CC BY 4.0; empirical inputs retrieved separately under upstream terms.',
                                  'timestamp_evidence': 'Original filesystem mtime_ns captured by completed archival job 1430243; not cryptographic trusted timestamps.'})
    with tarfile.open(output / 'exp28-light.tar.gz', 'w:gz') as tar:
        tar.add(light, arcname='exp28', recursive=True)
    write(output / 'package_receipt.json', {'format': 'exp28-public-package-v1',
          'validation': 'PASS_TRANSFER_INTEGRITY_ONLY', 'files': counts,
          'archives': {n: {'sha256': sha(output/n), 'bytes': (output/n).stat().st_size}
                       for n in ('exp28-light.tar.gz', 'exp28-full.tar.gz', 'full_inventory.csv.gz')},
          'manifest_sha256': sha(light / 'manifest.json'), 'excluded_empirical_graphs': 4,
          'original_archive_sha256': ARCHIVE, 'original_inventory_sha256': INVENTORY})
    print(json.dumps({'status': 'PASS_TRANSFER_INTEGRITY_ONLY', 'files': len(seen), 'orders': len(selected)}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--repository', default=Path('.'), type=Path)
    p.add_argument('--original-seal', required=True, type=Path)
    a = p.parse_args()
    build(a.original, a.output, a.repository, a.original_seal)
