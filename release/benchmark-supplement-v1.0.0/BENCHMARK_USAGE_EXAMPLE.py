"""Run: python3 -I -B BENCHMARK_USAGE_EXAMPLE.py /path/to/table45"""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parent/'INDEPENDENT_VERIFIER_SOURCE/usage_example.py'),run_name='__main__')
