"""Verify a candidate complete order against a released table45 input."""
import argparse,json
from mwfas_benchmark import Benchmark,load_order,compare
p=argparse.ArgumentParser();p.add_argument('table45');p.add_argument('instance');p.add_argument('order_csv');a=p.parse_args()
b=Benchmark(a.table45);g=b.load(a.instance);o=load_order(a.order_csv,g);ref=b.saved_reference(a.instance)
print(json.dumps({'instance':a.instance,'saved_reference_run':ref['run_id'],**compare(g,o,ref['objective'],ref['kind'])},indent=2))
