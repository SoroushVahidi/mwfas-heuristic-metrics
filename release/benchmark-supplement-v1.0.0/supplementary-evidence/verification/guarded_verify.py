"""Run full verification with network/process denial and filesystem-read confinement.
stdlib and installed NumPy may load from interpreter library directories; evidence
can only be opened from the extracted package. Writes are restricted to stdout.
"""
import sys
sys.dont_write_bytecode=True
import json,os,socket
from pathlib import Path
import verify
root=verify.ROOT.resolve();allowed=[root,Path(sys.base_prefix)/'lib',Path(sys.prefix)/'lib'];opened=set();denied=[]
def guard(event,args):
 if event.startswith(('socket.','subprocess.','os.exec','os.spawn'))or event=='os.system':
  denied.append(event);raise PermissionError('offline verification forbids network/process creation')
 if event=='open'and isinstance(args[0],(str,bytes,os.PathLike)):
  p=Path(os.fsdecode(args[0])).resolve();mode=args[1];flags=args[2]
  if isinstance(mode,str)and any(x in mode for x in 'wax+')or flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT):raise PermissionError('verification is read-only')
  if not any(p.is_relative_to(a)for a in allowed):raise PermissionError('outside extracted evidence/runtime: '+str(p))
  opened.add(str(p.relative_to(root))if p.is_relative_to(root)else'RUNTIME_LIBRARY')
sys.addaudithook(guard)
try:socket.getaddrinfo('offline-check.invalid',80)
except PermissionError:pass
else:raise RuntimeError('network guard failed')
result=verify.run();result['clean_room']={'network_denial_test':'PASS','evidence_reads_confined_to_extracted_package':True,'read_only':True,'distinct_opened_paths':len(opened),'denied_probe_events':denied,'original_evidence_directories_used':False}
print(json.dumps(result,sort_keys=True,indent=2))
