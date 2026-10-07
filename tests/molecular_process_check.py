"""Actual installed bridge and MCP contract acceptance; synthetic results and no external queries/engine execution."""
import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_molecular_drylab import C, splice, regulatory, interaction, perturbation, MolecularTests


async def mcp_check(host):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from jsonschema import validate
    params=StdioServerParameters(command=sys.executable,args=[str(host/'.local/mcp_server.py')],env={**os.environ,'PYTHONUTF8':'1'})
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize();tools={t.name:t for t in (await session.list_tools()).tools}
            for name,args in [('biomni_molecular_plan',{'task':'splicing','context':C}),('biomni_splicing_audit',{'records':[splice()],'context':C}),('biomni_regulatory_audit',{'records':[regulatory()],'context':C})]:
                assert tools[name].outputSchema
                result=await session.call_tool(name,args);assert not result.isError;assert result.structuredContent
                validate(result.structuredContent,tools[name].outputSchema)
                assert result.structuredContent['success'] is True
            invalid=await session.call_tool('biomni_molecular_plan',{'task':'arbitrary_command','context':C})
            assert invalid.isError
            a=await session.call_tool('biomni_tool_availability',{'category':'molecular_biology','name':'audit_splicing_results'})
            validate(a.structuredContent,tools['biomni_tool_availability'].outputSchema)
            assert a.structuredContent['current_environment_verified'] is True


def main():
    p=argparse.ArgumentParser();p.add_argument('--installation');a=p.parse_args()
    host=Path(a.installation) if a.installation else Path(os.environ['RUNNER_TEMP'])/'BiomniCore'
    # Fixture imports must not leave checkout implementations cached in an installed-runtime acceptance.
    source_dir=Path(__file__).resolve().parents[1]/'bridge'
    for name,module in list(sys.modules.items()):
        filename=getattr(module,'__file__',None)
        if filename and Path(filename).resolve().is_relative_to(source_dir):del sys.modules[name]
    sys.path[:]=[p for p in sys.path if Path(p or '.').resolve()!=source_dir]
    sys.path.insert(0,str(host/'.local'));import bridge
    assert Path(bridge.__file__).resolve().parent==(host/'.local').resolve()
    assert bridge.readiness()['bridge_version']=='2.13'
    fixtures=MolecularTests();cases=[('audit_splicing_results',{'records':[splice()],'context':C}),('audit_regulatory_links',{'records':[regulatory()],'context':C}),('audit_protein_annotations',{'records':[fixtures.protein()],'context':C}),('audit_interaction_records',{'records':[interaction()],'context':C}),('audit_perturbation_results',{'records':[perturbation()],'context':C})]
    nodes,edges=fixtures.graph();cases.append(('audit_mechanism_graph',{'nodes':nodes,'edges':edges,'evidence_records':[{**interaction(),'kind':'interaction'}],'context':C}))
    for name,args in cases:
        r=bridge.run_tool('molecular_biology',name,args);assert r['success'];raw=Path(r['result_file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==r['sha256'];d=json.loads(raw);assert d['qc_gate_pass'] is True;assert d['scientific_validity']=='not_established'
    bad=splice();bad['evidence_type']='gene_expression';r=bridge.run_tool('molecular_biology','audit_splicing_results',{'records':[bad],'context':C});assert r['success'] and json.loads(Path(r['result_file']).read_bytes())['qc_gate_pass'] is False
    from molecular_biology_ext import PIPELINES
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);local=root/'input.json';local.write_text('{"synthetic":true}',encoding='utf8')
        qc=root/'qc.json';qc.write_text('{"gate_pass":true,"scope":"synthetic preparation contract only"}',encoding='utf8')
        qc_inputs=[{'id':'fixture','path':str(local)}]
        remote_inputs=[{'path':n,'sha256':'a'*64} for n in ['samples.csv','reference.fa','reference.gtf']]
        references={'assembly':C['assembly'],'source_version':C['source_version']}
        for pipeline,spec in PIPELINES.items():
            design={'remote_inputs':remote_inputs,'pipeline_commit':spec['commit'],'statistical_consultation_recorded':True}
            bound=bridge.run_tool('code_review','bind_analysis_qc',{'inputs':qc_inputs,'design':design,'references':references,'qc_receipt_path':str(qc),'assessment':{'decision':'pass','checks':['synthetic contract fixture'],'limitations':['not a real sequencing dataset']}})
            assert bound['success']
            parameters={'input':'samples.csv','fasta':'reference.fa','outdir':'results','profile':'singularity'}
            if spec['annotation']:parameters['gtf']='reference.gtf'
            args={'pipeline':pipeline,'parameters':parameters,'qc_binding_file':bound['result_file'],'qc_binding_sha256':bound['sha256'],'qc_inputs':qc_inputs,'design':design,'references':references,'remote_workdir':'/synthetic/work','expected_host':'synthetic-compute','expected_outputs':['results/report.html'],'context':{**C,'assay':'synthetic preparation','limitations':['no engine execution']},'inputs':remote_inputs}
            prepared=bridge.run_tool('molecular_biology','prepare_molecular_pipeline',args);assert prepared['success']
            data=json.loads(Path(prepared['result_file']).read_bytes());assert data['submitted'] is False
            assert data['pipeline_commit']==spec['commit'] and spec['commit'] in data['argv']
            local.write_text('{"synthetic":false}',encoding='utf8')
            rejected=bridge.run_tool('molecular_biology','prepare_molecular_pipeline',args);assert rejected['success'] is False
            local.write_text('{"synthetic":true}',encoding='utf8')
    asyncio.run(mcp_check(host));print('INSTALLED_MOLECULAR_CALLS_AND_TYPED_MCP_CONTRACTS_OK')


if __name__=='__main__':main()
