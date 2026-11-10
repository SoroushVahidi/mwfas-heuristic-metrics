import json,hashlib,fnmatch,types
from pathlib import Path as RealPath,PurePosixPath
class EvidenceFS:
 def __init__(self,root,records,excluded=()):
  self.root=RealPath(root);self.records={r['original_path']:r for r in records};self.hashmap={}
  for r in excluded:self.records[r['original_path']]=dict(r,excluded=True)
  self.children={}
  for name in self.records:self.children.setdefault(str(PurePosixPath(name).parent),[]).append(name)
  fs=self
  class Path:
   def __init__(self,*parts):self.key=str(PurePosixPath(*(str(x)for x in parts)))
   def __str__(self):return self.key
   def __repr__(self):return self.key
   def __hash__(self):return hash(self.key)
   def __eq__(self,other):return self.key==str(other)
   def __truediv__(self,other):return Path(self.key,str(other))
   @property
   def parent(self):return Path(PurePosixPath(self.key).parent)
   @property
   def name(self):return PurePosixPath(self.key).name
   def with_suffix(self,s):return Path(PurePosixPath(self.key).with_suffix(s))
   def stat(self):return types.SimpleNamespace(st_mtime_ns=fs.records[self.key]['mtime_ns'])
   def read_bytes(self):
    r=fs.records[self.key]
    if r.get('excluded'):b=('HASH_ONLY:'+r['sha256']).encode()
    else:b=(fs.root/r.get('storage_path','objects/'+r['sha256'])).read_bytes()
    fs.hashmap[hashlib.sha256(b).hexdigest()]=r['sha256'];return b
   def glob(self,pattern):return [Path(k)for k in fs.children.get(self.key,[])if fnmatch.fnmatch(PurePosixPath(k).name,pattern)]
   def __lt__(self,other):return self.key<str(other)
  self.Path=Path
 def sha(self,b):
  h=hashlib.sha256(b).hexdigest();return self.hashmap.get(h,h)
