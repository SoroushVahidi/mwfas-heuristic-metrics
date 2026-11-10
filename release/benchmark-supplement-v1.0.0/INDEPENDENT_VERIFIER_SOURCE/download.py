"""Anonymous pinned download; Python standard library only."""
import csv, hashlib, json, os, sys, tarfile, urllib.request
from datetime import datetime, timezone
from pathlib import Path

def install_guard(root):
    allowed = ('/usr/lib/', '/usr/local/lib/', '/usr/share/zoneinfo/', '/etc/ssl/')
    files = {'/etc/resolv.conf','/etc/hosts','/etc/nsswitch.conf','/etc/gai.conf','/etc/localtime','/dev/urandom','/dev/null'}
    accesses=set()
    def guard(event,args):
        if event == 'open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(args[0])).resolve(); s=str(p)
            if not (p.is_relative_to(root) or s in files or s.startswith(allowed)):
                raise PermissionError('outside clean root: '+s)
            accesses.add(s)
        if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):
            raise PermissionError('subprocess forbidden')
    sys.addaudithook(guard)
    for p in ['/home/private-probe','/tmp/other-clean-room/probe']:
        try: open(p)
        except PermissionError: pass
        else: raise RuntimeError('guard probe failed')
    return accesses

def main():
    root=Path.cwd().resolve(); accesses=install_guard(root)
    pins=json.loads((root/'supplied_manifests/release_pins.json').read_text())
    records=[]
    (root/'downloads').mkdir(exist_ok=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for kind,url in pins['urls'].items():
        path=root/'downloads'/ {'code':'code.tar.gz','data':'table45.tar.gz','receipt':'package_receipt.json'}[kind]
        rec={'kind':kind,'url':url,'revision':pins['data_revision'] if kind!='code' else pins['code_revision'],'download_utc':datetime.now(timezone.utc).isoformat(),'file':str(path.relative_to(root)),'http_status':'','bytes':0,'sha256':'','expected_sha256':pins['download_sha256'][kind],'status':'FAIL','error':''}
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'independent-mwfas-clean-room/1'})
            with opener.open(request,timeout=60) as response, path.open('wb') as f:
                rec['http_status']=response.status
                while chunk:=response.read(1024*1024): f.write(chunk)
            rec['bytes']=path.stat().st_size;rec['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            if rec['sha256']!=rec['expected_sha256']: raise ValueError('archive checksum mismatch')
            rec['status']='PASS'
        except Exception as e:
            rec['error']=str(e)
        records.append(rec)
        print(json.dumps(rec),flush=True)
    with (root/'PUBLIC_DOWNLOAD_MANIFEST.tsv').open('w') as f:
        w=csv.DictWriter(f,records[0].keys(),delimiter='\t');w.writeheader();w.writerows(records)
    if any(r['status']!='PASS' for r in records):
        (root/'download_accesses.json').write_text(json.dumps(sorted(accesses),indent=2));sys.exit(1)
    for name in ['table45','code']:
        with tarfile.open(root/'downloads'/f'{name}.tar.gz') as tar:
            members=tar.getmembers()
            for m in members:
                if not (m.isfile() or m.isdir()) or not (root/m.name).resolve().is_relative_to(root): raise ValueError('unsafe member '+m.name)
            tar.extractall(root,filter='data')
    (root/'download_accesses.json').write_text(json.dumps(sorted(accesses),indent=2))
if __name__=='__main__': main()
