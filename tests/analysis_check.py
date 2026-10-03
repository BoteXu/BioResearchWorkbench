"""Real optional-backend checks on fixed synthetic inputs; not scientific validation."""
import json
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))


def main():
    os.environ['BIOMNI_COMPUTE_EDITION'] = 'local'
    import numpy as np
    import pandas as pd
    from transcriptomics_ext import run_bulk_rnaseq,run_normalized_expression,aggregate_pseudobulk,run_small_single_cell
    from qc_ext import preflight_transcriptomics,compare_analysis_results
    from molecular_ext import molecular_descriptors,run_vina_docking
    from systems_ext import score_pathway_activity,analyze_ppi_network
    from software_ext import register_local_software
    context = {'species':'synthetic','model':'synthetic engineering fixture','assay':'synthetic expression','biological_unit':'synthetic independent donor','contrast':'case versus control','limitations':['Not experimental data or biological validation'],'input_source':'generated locally with fixed seed','input_processing':'synthetic unnormalized integer counts or explicitly generated log2 expression'}
    checks = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        rng = np.random.default_rng(42)
        names = ['sample'+str(i) for i in range(12)]
        genes = ['gene'+str(i) for i in range(300)]
        means = rng.uniform(30,150,size=(300,12))
        means[:15,6:]*=5;means[15:30,:6]*=5
        counts = pd.DataFrame(rng.negative_binomial(20,20/(20+means)),index=genes,columns=names)
        meta = pd.DataFrame({'condition':['control']*6+['case']*6,'unit':['unit'+str(i) for i in range(12)]},index=names)
        cp,mp = root/'counts.csv',root/'metadata.csv'
        counts.to_csv(cp);meta.to_csv(mp)
        qc = preflight_transcriptomics(str(cp),str(mp),'raw_counts','condition','unit','case','control',context)
        assert qc['qc_gate_pass'] and qc['input_hashes']
        checks.append('preanalysis_qc')
        sets=root/'gene_sets.json';sets.write_text(json.dumps({'up_fixture':genes[:15],'down_fixture':genes[15:30],'neutral_fixture':genes[50:80]}))
        result = run_bulk_rnaseq(str(cp),str(mp),'condition','unit','case','control',context,threads=1,gene_sets_path=str(sets))
        de = pd.read_csv(Path(result['output_directory'])/'differential_expression.csv',index_col=0)
        assert de.loc[genes[:15],'log2FoldChange'].median()>1
        assert de.loc[genes[15:30],'log2FoldChange'].median()<-1
        assert result['preanalysis_qc']['qc_gate_pass']
        checks.append('pydeseq2_direction_and_qc')
        assert result['enrichment']['state']=='completed'
        checks.append('directional_ora_and_gsea')
        bad=counts.copy();bad.iloc[:,0]=0;bp=root/'empty_library.csv';bad.to_csv(bp)
        failed=preflight_transcriptomics(str(bp),str(mp),'raw_counts','condition','unit','case','control',context)
        assert not failed['qc_gate_pass'] and not failed['formal_analysis_allowed']
        try:
            run_bulk_rnaseq(str(bp),str(mp),'condition','unit','case','control',context)
        except ValueError: pass
        else: raise AssertionError('QC failure was bypassed')
        checks.append('qc_blocks_formal_fit')
        reverse = run_bulk_rnaseq(str(cp),str(mp),'condition','unit','control','case',context,threads=1)
        rev = pd.read_csv(Path(reverse['output_directory'])/'differential_expression.csv',index_col=0)
        assert np.allclose(de.log2FoldChange,-rev.log2FoldChange,atol=0.02)
        checks.append('pydeseq2_contrast_reversal')
        rscript = os.environ.get('RSCRIPT','Rscript')
        all_paths = [str(Path(result['output_directory'])/'differential_expression.csv')]
        for method in ('edgeR_ql','limma_voom'):
            output = run_bulk_rnaseq(str(cp),str(mp),'condition','unit','case','control',context,method=method,rscript=rscript)
            path = Path(output['output_directory'])/'differential_expression.csv'
            frame = pd.read_csv(path,index_col=0)
            assert frame.loc[genes[:15],'log2FoldChange'].median()>1
            all_paths.append(str(path)); checks.append(method)
        compare = compare_analysis_results(all_paths,context)
        assert len(compare['comparisons'])==3
        checks.append('method_agreement')
        expr = np.log2(counts+1); ep = root/'expression.csv';expr.to_csv(ep)
        activity=score_pathway_activity(str(ep),str(mp),str(sets),{**context,'gene_set_source':'synthetic fixture','gene_set_version':'1','gene_namespace':'synthetic gene IDs'},'log2_normalized')
        assert activity['samples']==12 and activity['gene_sets_included']==3
        checks.append('ssgsea_coverage_and_scores')
        edges=root/'edges.csv';edges.write_text('edge,source,target,score\ne1,A,B,0.9\ne2,B,C,0.8\ne3,A,B,0.7\ne4,C,C,1.0\ne5,C,D,0.1\n')
        ppi=analyze_ppi_network(str(edges),{**context,'network_source':'synthetic fixture','network_version':'1'},'functional','synthetic IDs',nodes=['A','B','C','D'])
        assert ppi['preanalysis_qc']['edges']==2 and ppi['isolated_nodes']==1
        assert len(ppi['preanalysis_qc']['collapsed_duplicate_edges'])==1
        checks.append('ppi_qc_centrality_communities')
        for test in ('ebayes','treat'):
            output = run_normalized_expression(str(ep),str(mp),'condition','unit','case','control',context,'log2_normalized',rscript=rscript,test=test)
            frame = pd.read_csv(Path(output['output_directory'])/'differential_expression.csv',index_col=0)
            assert frame.loc[genes[:15],'log2FoldChange'].median()>1
            checks.append('limma_'+test)
        cells = ['cell'+str(i) for i in range(120)]
        cell_genes = ['MT-gene0','MT-gene1']+genes[:198]
        cell_counts = pd.DataFrame(rng.poisson(4,size=(200,120)),index=cell_genes,columns=cells)
        cm = pd.DataFrame({'unit':['unit'+str(i//10) for i in range(120)],'condition':['control']*60+['case']*60,'cell_type':['curated_fixture']*120},index=cells)
        scp,smp = root/'cell_counts.csv',root/'cell_metadata.csv';cell_counts.to_csv(scp);cm.to_csv(smp)
        pseudo = aggregate_pseudobulk(str(scp),str(smp),'unit','condition','cell_type','curated_fixture',context,min_cells=5)
        summed = pd.read_csv(Path(pseudo['output_directory'])/'counts.csv',index_col=0)
        assert np.array_equal(summed.iloc[:,0].to_numpy(),cell_counts.iloc[:,:10].sum(axis=1).to_numpy())
        assert pseudo['retained_groups']==12
        checks.append('pseudobulk_exact_sums')
        single = run_small_single_cell(str(scp),str(smp),'unit',context,'MT-',min_genes=10,hvg_genes=100,neighbors=8,resolution_grid=[0.5,1.])
        assert single['retained_cells']==120 and Path(single['output_directory'],'processed.h5ad').exists()
        checks.append('scanpy_qc_clustering')
        props = molecular_descriptors(['CCO','invalid-smiles'])
        assert props['rows'][0]['state']=='computed' and props['rows'][1]['state']=='invalid'
        checks.append('rdkit_descriptors')
        if not os.environ.get('VINA'): raise RuntimeError('VINA executable required for the complete optional suite')
        registered=register_local_software('vina',os.environ['VINA'])
        assert registered['version_probe_pass']
        checks.append('persistent_vina_interface')
        def atom(serial,x):
            return f'ATOM  {serial:5d}  C   UNK A   1    {x:8.3f}{0.:8.3f}{0.:8.3f}  1.00  0.00    {0.:6.3f} C\n'
        receptor,ligand = root/'receptor.pdbqt',root/'ligand.pdbqt'
        receptor.write_text(atom(1,0),encoding='utf8')
        ligand.write_text('ROOT\n'+atom(1,2)+'ENDROOT\nTORSDOF 0\n',encoding='utf8')
        docking = run_vina_docking(str(receptor),str(ligand),[0,0,0],[10,10,10],context,vina=os.environ['VINA'],exhaustiveness=1,poses=1,threads=1,timeout_seconds=120)
        assert docking['results']['poses']
        checks.append('vina_synthetic_execution')
    print(json.dumps({'pass':True,'checks':checks,'limitations':['Synthetic checks establish listed engineering behavior only.','No clinical data, biological mechanism, native HarmonyOS hardware or docking accuracy is validated.']},indent=2))


if __name__=='__main__': main()
