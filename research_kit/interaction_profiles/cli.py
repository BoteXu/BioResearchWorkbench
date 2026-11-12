"""Private molecular interaction profiles: local planning/returned summaries only."""
from pathlib import Path
import argparse,json
from contracts import read,write,prepare,METHODS
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['catalog','plan','accept','handoff','bind-reference-selections']);p.add_argument('--request',type=Path);p.add_argument('--out',type=Path);p.add_argument('--root',type=Path);a=p.parse_args()
    try:
        if a.operation=='catalog':
            from generation_contracts import BRANCHES
            result={'version':'1.2-private','actual_scientific_source_routes':METHODS,'generation_branches':BRANCHES,'scientific_runtime':{k:'NOT_RUN_SERVER_UNAVAILABLE' for k in METHODS},'generation_branch_runtime':{k:'NOT_RUN_SERVER_UNAVAILABLE' for k in BRANCHES},'scientific_acceptance':'NOT_ESTABLISHED','automatic_download':False,'public_upload':False}
        elif a.operation=='plan':result=prepare(read(a.request),a.out)
        elif a.operation=='bind-reference-selections':
            from reference_selection import bind_selections
            r=read(a.request);result=bind_selections(a.request.parent/r['reference_request'],a.root,r['selected_return_files'],read(a.request.parent/r['generation_project']),r['variant'])
        elif a.operation=='accept':
            from acceptance import inspect
            r=read(a.request);result=inspect(a.request.parent/r['scientific_request'],a.root,r['selected_return_files'])
        else:
            from handoff import prepare_link
            r=read(a.request);review=None
            if r.get('return_review') is not None and r.get('generation_review') is not None:raise ValueError('Use one reviewed return binding')
            if r.get('return_review',r.get('generation_review')) is not None:
                spec=r.get('return_review',r.get('generation_review'));review={'request_path':a.request.parent/r['scientific_request'],'returned_root':a.request.parent/spec['returned_root'],'selected_return_files':spec['selected_return_files']}
            result=prepare_link(read(a.request.parent/r['scientific_request']),read(a.request.parent/r['server_receipt']),r['selection'],a.request.parent/r['source_context'],a.request.parent/r['source_eligibility'],review)
        if a.out and a.operation!='plan':write(a.out,result)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 2 if result.get('state')=='HOLD' else 0
    except (OSError,ValueError,KeyError,TypeError) as e:print(json.dumps({'state':'HOLD','error':str(e),'public_upload':False},ensure_ascii=False));return 2
if __name__=='__main__':raise SystemExit(main())
