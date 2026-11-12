"""Local bounded hypothesis handoff. Predicted results never become observed target evidence."""
from contracts import read,sha,digest

def hypothesis_link(request,receipt,link,context_path=None):
    if receipt.get('state')!='COMPLETED' or receipt.get('exit_code')!=0 or receipt.get('plan_sha256')!=request.get('plan_sha256'):raise ValueError('Actual completed exact source plan required')
    if receipt.get('measurement_state')!='predicted' or link.get('destination_measurement_state')!='predicted':raise ValueError('Virtual perturbations can only enter a predicted-hypothesis channel')
    if link.get('destination_use') not in ('hypothesis_prioritization','conditional_pathway_followup','plan_measured_validation'):raise ValueError('Unsupported virtual-KO downstream claim')
    if any(not link.get(k) for k in ('species','annotation_version','source_role','target_workflow','limitations','independent_unit')):raise ValueError('Exact cross-flow scientific context required')
    if link.get('target_is_experimental_validation') is not False:raise ValueError('Prediction is not experimental validation')
    from contracts import catalog
    spec=catalog()['methods'][request['method']]
    if link.get('source_score_kind')!=spec['score_kind']:raise ValueError('Exact model-output semantics must survive the handoff')
    semantics=link.get('destination_input_semantics')
    allowed={'hypothesis_score'}
    if request['method'] in ('bulk_virtual_ko','celloracle','gears','cpa','scgpt'):allowed.add('predicted_expression_delta')
    if request['method'] in ('boolnet','maboss'):allowed.add('logical_state_probability_change')
    if request['method']=='dynamo':allowed.add('velocity_change')
    if request['method']=='metabolic_gene_deletion':allowed.add('metabolic_objective_or_flux_change')
    if request['method'] in ('genki','geneformer','singlecell_virtual_ko'):allowed.add('unsigned_model_distance')
    if semantics not in allowed:raise ValueError('Embedding/logic/velocity/flux responses cannot be relabeled as RNA expression or observed evidence')
    if link['destination_use']=='conditional_pathway_followup' and (request['method'] in ('geneformer','boolnet','maboss','dynamo','metabolic_gene_deletion') or not __import__('re').fullmatch('[a-f0-9]{64}',link.get('approved_identifier_mapping_sha256',''))):raise ValueError('Gene-level pathway followup needs a reviewed gene-response mapping; other output spaces remain hypothesis scores')
    if link['source_role'] not in spec['roles'] or link['source_file']!='primary/'+link['source_role']+'.tsv':raise ValueError('Only the exact declared scientific result role can be handed off')
    context_record=[r for r in request['inputs'] if r['id']=='context']
    if context_path is None or len(context_record)!=1 or sha(context_path)!=context_record[0]['sha256']:raise ValueError('Exact source scientific context is required for the cross-flow link')
    context=read(context_path)
    for key in ('species','annotation_version','independent_unit'):
        if link[key]!=context[key]:raise ValueError('Cross-flow scientific context changed: '+key)
    records={r['path']:r for r in receipt['outputs']};file=link['source_file']
    if file not in records or records[file]['sha256']!=link['source_sha256']:raise ValueError('Handoff uses unbound predicted output')
    return {'state':'PREPARED_HYPOTHESIS_LINK_NOT_DISPATCHED','measurement_state':'predicted','source_plan_sha256':request['plan_sha256'],'source_output_sha256':link['source_sha256'],'cross_flow_context':link,'review_sha256':digest(link),'new_downstream_QC_required':True,'observed_target_evidence_created':False,'public_upload':False}
