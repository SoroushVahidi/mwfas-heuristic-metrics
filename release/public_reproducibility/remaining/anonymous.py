"""Fresh anonymous public-only remaining-table replay. Run with Python -I -B and env -i."""
import argparse,hashlib,json,os,platform,re,runpy,sys,tarfile,time,urllib.request
from pathlib import Path
STDLIB=Path(os.__file__).resolve().parent

def guard_reads(root):
    libraries=[Path(x).resolve() for x in ['/usr/lib','/usr/local/lib','/lib','/lib64','/usr/share/zoneinfo','/etc/ssl']]+[STDLIB]
    allowed={'/etc/localtime','/etc/resolv.conf','/etc/hosts','/etc/nsswitch.conf','/etc/gai.conf','/proc/cpuinfo','/dev/null','/dev/urandom'};accesses=set()
    def guard(event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(args[0])).resolve()
            if not(p.is_relative_to(root) or str(p) in allowed or any(p.is_relative_to(d) for d in libraries)):raise PermissionError('private/external input rejected: '+str(p))
            accesses.add(str(p.relative_to(root)) if p.is_relative_to(root) else str(p))
        elif event in ['subprocess.Popen','os.system','os.exec','os.posix_spawn']:raise PermissionError('subprocess forbidden during replay')
    sys.addaudithook(guard);return accesses

def fetch(url,path):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'MWFAS-anonymous-replay/1'}),timeout=90) as r:b=r.read()
    path.write_bytes(b);return hashlib.sha256(b).hexdigest()

def extract(path,dest):
    with tarfile.open(path) as t:
        for m in t.getmembers():
            if not(m.isfile() or m.isdir()) or not(dest/m.name).resolve().is_relative_to(dest):raise ValueError('unsafe archive')
        t.extractall(dest,filter='data')

def main():
    p=argparse.ArgumentParser();p.add_argument('--code-revision',required=True);p.add_argument('--data-revision',required=True);p.add_argument('--scope',choices=['J1','J2','J3','J4'],required=True);p.add_argument('--directory',type=Path,required=True);a=p.parse_args()
    if not all(re.fullmatch('[0-9a-f]{40}',s) for s in [a.code_revision,a.data_revision]):raise ValueError('immutable revisions required')
    if any(k in os.environ for k in ['HF_TOKEN','HUGGING_FACE_HUB_TOKEN','GH_TOKEN','GITHUB_TOKEN']):raise ValueError('credentials forbidden')
    root=a.directory.resolve();root.mkdir(parents=True,exist_ok=False);os.chdir(root);hardware=platform.platform();accesses=guard_reads(root)
    for path in ['/project/private-probe','/home/private-probe']:
        try:open(path,'rb')
        except PermissionError:pass
        else:raise ValueError('private-path rejection failed')
    base=f'https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/resolve/{a.data_revision}/releases/remaining-v1-20261019'
    urls={'package_receipt':base+'/package.json','archive':base+'/remaining.tar.gz','code':f'https://codeload.github.com/SoroushVahidi/mwfas-heuristic-metrics/tar.gz/{a.code_revision}'};hashes={}
    hashes['package_receipt']=fetch(urls['package_receipt'],root/'package.json');pkg=json.loads((root/'package.json').read_text());hashes['archive']=fetch(urls['archive'],root/'remaining.tar.gz')
    if hashes['archive']!=pkg['archive_sha256']:raise ValueError('archive hash mismatch')
    hashes['code']=fetch(urls['code'],root/'code.tar.gz');extract(root/'code.tar.gz',root);package=root/'package';package.mkdir();extract(root/'remaining.tar.gz',package)
    if hashlib.sha256((package/'manifest.json').read_bytes()).hexdigest()!=pkg['manifest_sha256']:raise ValueError('manifest hash mismatch')
    code=root/('mwfas-heuristic-metrics-'+a.code_revision)/'release/public_reproducibility/remaining';sys.path[:]=[str(code)]+[p for p in sys.path if p and any(Path(p).resolve().is_relative_to(Path(q)) for q in ['/usr/lib','/usr/local/lib','/lib','/lib64',STDLIB])]
    namespace=runpy.run_path(str(code/'replay.py'));result=namespace['run'](argparse.Namespace(package=package,output=root/'results',scope=a.scope,mode='public',original=None))
    report={'status':result['status'],'scope':a.scope,'classification':result.get('classification','NOT_VERIFIABLE'),'code_revision':a.code_revision,'data_revision':a.data_revision,'urls':urls,'download_sha256':hashes,'anonymous':True,'fresh_directory':True,'private_path_rejection_probes':'PASS','read_guard':'PASS','interpreter_standard_library':str(STDLIB),'subprocesses':'FORBIDDEN','hardware':hardware,'replay':result}
    (root/'accessed_files.json').write_text(json.dumps(sorted(accesses),indent=2)+'\n');(root/'public_replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'scope':a.scope}),flush=True);return result['status']=='PASS'
if __name__=='__main__':
    try:raise SystemExit(0 if main() else 1)
    except Exception as error:
        import traceback
        dest=Path(sys.argv[sys.argv.index('--directory')+1])
        if dest.exists():(dest/'bootstrap_failure.json').write_text(json.dumps({'status':'FAIL','error':str(error),'traceback':traceback.format_exc()},indent=2)+'\n')
        raise

