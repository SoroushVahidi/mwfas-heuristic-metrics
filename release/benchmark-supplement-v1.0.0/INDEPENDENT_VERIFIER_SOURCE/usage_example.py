"""Usage: python usage_example.py /path/to/table45 [exp06/instance_id]."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mwfas_benchmark import Benchmark,compare

def main():
    benchmark=Benchmark(sys.argv[1]);key=sys.argv[2] if len(sys.argv)>2 else benchmark.instances()[0]
    graph=benchmark.load(key)
    candidate=list(graph.vertices) # Trivial deterministic increasing-ID ordering.
    reference=benchmark.saved_reference(key)
    report={'instance':key,'vertices':len(graph.vertices),'arcs':len(graph.arcs),'candidate_method':'increasing_vertex_id_smoke_test','saved_reference_run':reference['run_id'],**compare(graph,candidate,reference['objective'],reference['kind'])}
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
