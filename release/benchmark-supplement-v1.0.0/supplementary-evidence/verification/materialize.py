"""Export one logical witness to a reviewer-chosen file outside the package."""
import sys,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1];index=json.loads((root/'witnesses/index.json').read_text());r=next(r for r in index['records']if r['original_path']==sys.argv[1]);dest=Path(sys.argv[2]).resolve();assert not dest.is_relative_to(root)and not dest.exists();b=(root/r['storage_path']).read_bytes();assert hashlib.sha256(b).hexdigest()==r['storage_sha256'];dest.write_bytes(b);print(json.dumps(r,indent=2))
