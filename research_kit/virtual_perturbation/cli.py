"""Private virtual perturbation: discovery, disabled server preparation and bounded return review."""
import argparse,json
from pathlib import Path
from contracts import read,catalog,prepare,write

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['catalog','plan','accept']);p.add_argument('--request',type=Path);p.add_argument('--out',type=Path);p.add_argument('--root',type=Path);a=p.parse_args()
    try:
        if a.operation=='catalog':result=catalog()
        elif a.operation=='plan':result=prepare(read(a.request),a.out)
        else:
            from acceptance import inspect
            r=read(a.request);result=inspect(a.request.parent/r['scientific_request'],a.root,r['selected_return_files'])
        if a.out and a.operation!='plan':write(a.out,result)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 2 if result.get('state')=='HOLD' else 0
    except (ValueError,KeyError,OSError,TypeError) as e:
        print(json.dumps({'state':'HOLD','error':str(e),'public_upload':False},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())
