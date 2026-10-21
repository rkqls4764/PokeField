"""Convenience entry point; validation failure returns a nonzero exit code."""
import argparse
from common import ROOT, Path
from collect_pokemon import collect
from process_pokemon import process
from validate_pokemon import validate
from analyze_api import analyze
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=ROOT); p.add_argument('--ids',type=int,nargs='+'); p.add_argument('--workers',type=int,default=6)
    a=p.parse_args(); collect(a.root,a.ids,a.workers); process(a.root); analyze(a.root)
    report=validate(a.root); raise SystemExit(0 if report['validation_passed'] else 1)
