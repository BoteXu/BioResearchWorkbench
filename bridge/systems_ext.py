"""Local pathway activity and bounded PPI graphs with evidence-type boundaries."""
import hashlib
import json
import math
import re
from pathlib import Path
from transcriptomics_ext import _context,_folder,_finish,_workflow,_read,_frames,_capacity
from compute_policy import require_local


@_workflow
def score_pathway_activity(expression_path: str, metadata_path: str, gene_sets_path: str, context: dict, matrix_kind: str, min_size: int = 15, max_size: int = 500, seed: int = 42) -> dict:
    """Sample-level ssGSEA for declared log2 normalized expression with local versioned gene sets; descriptive scores only."""
    require_local();_context(context)
    if matrix_kind!='log2_normalized' or not 5<=min_size<=max_size<=2000:
        raise ValueError('Provide log2 normalized expression and valid gene-set size limits')
    for key in ('gene_set_source','gene_set_version','gene_namespace'):
        if not context.get(key): raise ValueError('Record gene-set source, version and matching gene namespace')
    matrix,meta = _frames(expression_path,metadata_path,False)
    _capacity(matrix,'normalized')
    if (matrix.var(axis=0)==0).any(): raise ValueError('Constant expression sample blocks pathway scoring')
    from omics_ext import _gene_sets
    sets = _gene_sets(gene_sets_path)
    coverage = []
    eligible = {}
    for term,genes in sets.items():
        unique = set(genes)
        overlap = sorted(unique&set(matrix.index))
        included = min_size<=len(overlap)<=max_size
        coverage.append({'term':term,'original_unique_genes':len(unique),'measured_genes':len(overlap),'coverage_fraction':len(overlap)/len(unique) if unique else 0,'eligible':included})
        if included: eligible[term]=overlap
    if not eligible: raise ValueError('No gene set has enough measured genes; review species/identifier mapping')
    folder = _folder('pathway_activity')
    import pandas as pd
    pd.DataFrame(coverage).to_csv(folder/'gene_set_coverage.csv',index=False)
    import gseapy as gp
    result = gp.ssgsea(data=matrix,gene_sets=eligible,outdir=str(folder/'ssgsea'),sample_norm_method='rank',min_size=min_size,max_size=max_size,permutation_num=0,threads=2,no_plot=True,seed=seed,verbose=False)
    rows = result.res2d
    rows.to_csv(folder/'all_pathway_scores.csv',index=False)
    scores = rows.pivot(index='Term',columns='Name',values='ES').loc[:,matrix.columns]
    scores.to_csv(folder/'pathway_es.csv')
    meta.to_csv(folder/'sample_metadata.csv')
    return _finish(folder,{'workflow':'ssgsea','gene_sets_included':len(eligible),'samples':matrix.shape[1],'seed':seed,'input_hashes':{role:hashlib.sha256(Path(path).read_bytes()).hexdigest() for role,path in {'expression':expression_path,'metadata':metadata_path,'gene_sets':gene_sets_path}.items()},'context':context,'limitations':['ssGSEA scores are relative descriptive enrichment, not pathway activation, causality or differential-expression tests.','No p-value is generated with zero permutations.','NES normalization depends on the analyzed dataset and is not automatically comparable across datasets.','Repeated units and cross-sample batch effects still require a design-aware downstream analysis.']})


def query_string_network(identifiers: list, species_taxid: int, network_type: str = 'functional', required_score: int = 700, public_data_authorized: bool = False) -> dict:
    """Retrieve a bounded public STRING network only after explicit authorization; predicted physical edges remain predictions."""
    if public_data_authorized is not True: raise ValueError('Explicit authorization is required before identifiers are sent to STRING')
    if not isinstance(identifiers,list) or not 2<=len(identifiers)<=50 or len(set(identifiers))!=len(identifiers) or any(not isinstance(g,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,60}',g) for g in identifiers):
        raise ValueError('Provide two to fifty distinct explicit public protein/gene identifiers')
    if species_taxid not in {9606,10090,10116} or network_type not in {'functional','physical'} or type(required_score) is not int or not 0<=required_score<=999:
        raise ValueError('Specify supported taxonomy, functional/physical network and a 0..999 confidence threshold')
    from http_client import get_json
    data = get_json('https://string-db.org/api/json/network',{'identifiers':'\r'.join(identifiers),'species':species_taxid,'required_score':required_score,'network_type':network_type,'add_nodes':0,'caller_identity':'BiomniDirectTools'})
    if not isinstance(data,list): raise ValueError('Unexpected STRING network response')
    if len(data)>5000: raise ValueError('Network exceeds retrieval limit')
    found = set()
    for row in data:
        if int(row.get('ncbiTaxonId',species_taxid))!=species_taxid: raise ValueError('STRING species mismatch')
        found.update([row.get('preferredName_A',''),row.get('preferredName_B','')])
    return {'success':True,'species_taxid':species_taxid,'network_type':network_type,'required_score':required_score,'query_identifiers':identifiers,'returned_edges':len(data),'returned_names':sorted(found),'source_rows':data,'candidate_coverage_complete':False,'limitations':['The current STRING API and raw source receipt are retained; record its database version from source documentation.','Functional edges include predicted associations; physical edges include predicted physical interactions.','Missing edges or unmatched names do not establish absence; identifier mapping is not asserted exhaustive.','A query subgraph has selection bias and is not the complete interactome.']}


@_workflow
def analyze_ppi_network(edges_path: str, context: dict, network_type: str, identifier_namespace: str, score_threshold: float = 0.7, nodes: list = None, seed: int = 42, resolution: float = 1.) -> dict:
    """QC an explicit confidence-weighted undirected PPI edge table, then compute bounded centrality and Louvain communities."""
    require_local();_context(context)
    if network_type not in {'functional','physical','unknown'} or not identifier_namespace or not context.get('network_source') or not context.get('network_version'):
        raise ValueError('Record network type, identifier namespace, source and database version')
    if not 0<score_threshold<=1 or not 0<resolution<=5: raise ValueError('Invalid network score or community threshold')
    h,r = _read(edges_path)
    if not {'source','target','score'}<=set(h[1:]): raise ValueError('Edge CSV/TSV first column is a unique edge ID, followed by source,target,score')
    if len(r)>10000 or nodes and len(nodes)>2000: raise ValueError('Large PPI networks belong on the server')
    import networkx as nx
    graph = nx.Graph()
    if nodes:
        if len(set(nodes))!=len(nodes) or any(not isinstance(n,str) or not n for n in nodes): raise ValueError('Explicit nodes must be distinct nonempty identifiers')
        graph.add_nodes_from(nodes)
    filtered,self_edges,duplicates = [],[],[]
    for row in r:
        item = dict(zip(h,row))
        a,b = item['source'],item['target']
        try: score = float(item['score'])
        except ValueError: raise ValueError('PPI confidence must be numeric')
        if not a or not b or not math.isfinite(score) or not 0<=score<=1: raise ValueError('PPI nodes and confidence are malformed')
        if a==b: self_edges.append(row[0]);continue
        if score<score_threshold: filtered.append(row[0]);continue
        if graph.has_edge(a,b): duplicates.append(row[0]); score=max(score,graph[a][b]['score'])
        graph.add_edge(a,b,score=score,distance=1./score)
        if len(graph)>2000: raise ValueError('Local PPI node limit exceeded')
    if not graph.number_of_edges(): raise ValueError('No usable PPI edges remain after QC')
    folder = _folder('ppi_analysis')
    qc = {'input_rows':len(r),'excluded_below_threshold':filtered,'excluded_self_edges':self_edges,'collapsed_duplicate_edges':duplicates,'duplicate_rule':'maximum confidence, never summed','score_threshold':score_threshold,'nodes':len(graph),'edges':graph.number_of_edges(),'input_sha256':hashlib.sha256(Path(edges_path).read_bytes()).hexdigest()}
    (folder/'preanalysis_qc.json').write_text(json.dumps(qc,indent=2),encoding='utf8')
    degree = dict(graph.degree())
    between = nx.betweenness_centrality(graph,weight='distance',k=min(100,len(graph)),seed=seed)
    closeness = nx.closeness_centrality(graph,distance='distance')
    communities = nx.community.louvain_communities(graph,weight='score',resolution=resolution,seed=seed)
    assignment = {node:i for i,community in enumerate(communities) for node in community}
    import pandas as pd
    rows = [{'node':n,'degree':degree[n],'weighted_degree':float(graph.degree(n,weight='score')),'betweenness':between[n],'closeness':closeness[n],'community':assignment[n]} for n in graph]
    pd.DataFrame(rows).sort_values('degree',ascending=False).to_csv(folder/'node_metrics.csv',index=False)
    nx.write_graphml(graph,folder/'network.graphml')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    chosen = sorted(graph,key=lambda n:degree[n],reverse=True)[:100]
    sub = graph.subgraph(chosen)
    fig,ax = plt.subplots(figsize=(9,7))
    nx.draw_networkx(sub,pos=nx.spring_layout(sub,seed=seed,weight='score'),node_size=80,font_size=6,ax=ax)
    ax.set_title('At most 100 highest-degree nodes; a display subset')
    fig.savefig(folder/'network.png',dpi=150,bbox_inches='tight');plt.close(fig)
    return _finish(folder,{'workflow':'ppi_network','context':context,'network_type':network_type,'identifier_namespace':identifier_namespace,'preanalysis_qc':qc,'connected_components':nx.number_connected_components(graph),'isolated_nodes':len(list(nx.isolates(graph))),'communities':len(communities),'seed':seed,'resolution':resolution,'betweenness_sample_nodes':min(100,len(graph)),'limitations':['Network centrality and community membership do not establish therapeutic targets or causal mechanisms.','Confidence is used as Louvain weight and its inverse as shortest-path distance; it is not a physical distance.','Betweenness is sampled for large graphs; ranks can depend on seed and database bias.','No unsupported edge provenance, physical binding or complete identifier coverage is inferred.']})
