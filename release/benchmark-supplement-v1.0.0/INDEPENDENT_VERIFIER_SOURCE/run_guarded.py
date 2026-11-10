"""Run a script inside this clean root with file-read guard and access receipt."""
import json,platform,runpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from download import install_guard
platform.platform();platform.processor() # caches OS-only identification before subprocess ban
root=Path.cwd().resolve();script=Path(sys.argv[1]).resolve();sys.argv=sys.argv[1:]
accesses=install_guard(root)
try:runpy.run_path(str(script),run_name='__main__')
finally:(root/(script.stem+'_accesses.json')).write_text(json.dumps(sorted(accesses),indent=2))
