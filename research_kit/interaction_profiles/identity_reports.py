"""Complete identity-preparation lineage checks; scalar metadata only, no chemistry imports.

These checks establish return consistency. Graph/coordinate preservation measurements
are server reports bound to exact source and output bytes, not a local chemical rerun.
"""
import re
from contracts import digest
from postanalysis_contracts import identity_policy,ISOTOPE_SCOPE
from server.return_binding import receipt_index
from generation_reports import candidate_report_issues,SUCCESS

CONSISTENT='RETURN_BUNDLE_CONSISTENT_REQUIRES_SCIENTIFIC_REVIEW'
PREPARED='IDENTITY_PREPARED_REQUIRES_NEW_QC'


def _hash(value):
    return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None


def _text(value):
    return isinstance(value,str) and bool(value.strip())


def _file(value):
    return isinstance(value,dict) and _hash(value.get('sha256')) and type(value.get('bytes')) is int and value['bytes']>0


def _same_file(left,right):
    return _file(left) and _file(right) and all(left.get(k)==right.get(k) for k in ('sha256','bytes'))


def _inventory(value):
    if not isinstance(value,list):return False
    identities=[]
    for row in value:
        if not isinstance(row,dict) or set(row)!={'atomic_number','isotope','count'}:return False
        if any(type(row[k]) is not int or row[k]<1 for k in row) or row['atomic_number']>118:return False
        identities.append((row['atomic_number'],row['isotope']))
    return identities==sorted(set(identities))


def _source_axis(v,content,bound,spec):
    prefix=v+'/';issues=[]
    receipt=content[prefix+'origin_receipt_snapshot.private.json']
    original,invalid=receipt_index(receipt.get('outputs'))
    issues.extend('origin_'+x for x in invalid)
    snapshot=content[prefix+'origin_eligibility_snapshot.private.json']
    if not _same_file(bound.get(prefix+'origin_eligibility_snapshot.private.json'),original.get('eligible_candidate_outputs.private.json')):
        issues.append('origin_eligibility_snapshot_not_bound_to_original_receipt')
    review=content[prefix+'origin_lineage.private.json'].get('source_review',{})
    if not isinstance(review,dict) or review.get('state')!=CONSISTENT or review.get('issues')!=[]:
        issues.append('identity_origin_complete_source_review_not_accepted')
    if not isinstance(snapshot,list) or any(not isinstance(x,dict) for x in snapshot):
        raise ValueError('Complete original eligible candidate snapshot required')
    keys=[(x.get('variant'),x.get('candidate_id')) for x in snapshot]
    if any(not _text(a) or not _text(b) for a,b in keys) or len(set(keys))!=len(keys):
        issues.append('origin_eligibility_snapshot_candidate_axis_invalid')
    by_id={x.get('candidate_id'):x for x in snapshot if x.get('variant')==spec['origin_variant']}
    for cid in spec['candidate_ids']:
        old=by_id.get(cid,{})
        canonical=spec['origin_variant']+'/'+cid+'.sdf'
        constraint=spec['origin_variant']+'/'+cid+'.constraints.private.json'
        contract=spec['origin_variant']+'/generation_contract.private.json'
        if (not old or old.get('path')!=canonical or old.get('constraint_report_path')!=constraint
                or old.get('eligibility')!='REQUIRES_NEW_DOWNSTREAM_QC' or old.get('constraints_passed') is not True
                or not _same_file(old,original.get(canonical))
                or not _hash(old.get('constraint_report_sha256'))
                or old.get('constraint_report_sha256')!=original.get(constraint,{}).get('sha256')
                or not _file(original.get(constraint))
                or old.get('generation_contract_sha256')!=original.get(contract,{}).get('sha256')
                or not _file(original.get(contract)) or not _hash(old.get('generation_options_sha256'))
                or any(not _text(old.get(k)) for k in ('state_id','parent_id','microstate_id'))):
            issues.append('selected_identity_source_not_qualified_or_original_receipt_bound')
    return issues,by_id,original


def _source_report(v,cid,content,bound,old,original):
    prefix=v+'/';issues=[];path=prefix+cid+'.source_constraints.private.json'
    report=content.get(path)
    expected=original.get(old.get('constraint_report_path'),{})
    if (not isinstance(report,dict) or not _same_file(bound.get(path),expected)
            or bound.get(path,{}).get('sha256')!=old.get('constraint_report_sha256')):
        return ['original_constraint_report_missing_or_not_original_receipt_bound']
    actual=report.get('actual_sdf',{})
    if (report.get('candidate_id')!=cid or report.get('state')!=SUCCESS or report.get('failure_reason')
            or any(report.get(k) is not True for k in ('chemical_valid','actual_structure_QC','saved_SDF_readback_verified','constraints_passed','hard_constraints_assessed','eligible'))
            or actual.get('path')!=cid+'.sdf' or not _same_file(actual,old)
            or any(actual.get(k)!=old.get(k) for k in ('state_id','parent_id','microstate_id'))
            or report.get('generation_contract_sha256')!=old.get('generation_contract_sha256')
            or report.get('generation_options_sha256')!=old.get('generation_options_sha256')):
        issues.append('original_candidate_constraint_or_saved_state_identity_changed')
    try:
        request=content[prefix+'origin_request_snapshot.private.json']
        contract=content[prefix+'origin_generation_contract_snapshot.private.json']
        record={'candidate_id':cid,'state':SUCCESS,'generation_contract_sha256':old.get('generation_contract_sha256')}
        issues.extend('source_'+x for x in candidate_report_issues(request,contract,report,record,original,old.get('variant')))
    except (KeyError,TypeError,ValueError,IndexError):
        issues.append('original_candidate_complete_constraint_report_malformed')
    return issues


def inspect_identity_variant(v,content,bound,p,spec,eligible):
    prefix=v+'/';issues=[]
    records=content[prefix+'identity_records.private.json'];policy=content[prefix+'identity_policy.private.json']
    if not isinstance(policy,dict) or digest(policy)!=digest(identity_policy(p)):issues.append('actual_identity_policy_or_software_changed')
    if (not isinstance(records,list) or not records or any(not isinstance(x,dict) for x in records)
            or [x.get('candidate_id') for x in records]!=spec['candidate_ids']
            or len(set(spec['candidate_ids']))!=len(spec['candidate_ids'])):
        raise ValueError('Complete selected identity records required once in request order')
    si,source,original=_source_axis(v,content,bound,spec);issues.extend(si)
    prepared={};groups={}
    for row in records:
        cid=row['candidate_id'];report=prefix+cid+'.identity.private.json';old=source.get(cid,{})
        if content.get(report)!=row:issues.append('complete_identity_report_disagrees')
        if row.get('identity_policy_sha256')!=digest(policy):issues.append('identity_policy_hash_changed')
        if (any(row.get(k)!=old.get(k) for k in ('microstate_id','state_id'))
                or row.get('source_parent_id')!=old.get('parent_id')
                or row.get('source_sdf_path')!=old.get('path')
                or row.get('source_sdf_sha256')!=old.get('sha256')
                or type(row.get('source_sdf_bytes')) is not int or row.get('source_sdf_bytes')!=old.get('bytes')):
            issues.append('identity_record_does_not_preserve_original_source_identity')
        if row.get('state')==PREPARED:
            prepared[cid]=row
            parent_smiles=row.get('canonical_parent_smiles')
            parent='COMPUTED_GROUP_'+digest({'policy_sha256':digest(policy),'canonical_parent_smiles':parent_smiles})
            if not _text(parent_smiles) or row.get('parent_id')!=parent:issues.append('computed_parent_group_key_changed')
            if any(row.get(k) is not True for k in ('original_graph_preserved','original_atom_order_preserved','original_coordinates_preserved','prepared_sdf_readback_verified','source_constraints_passed','no_candidates_dropped')) or row.get('grouping_is_physiological_state_prediction') is not False:
                issues.append('original_state_pose_or_grouping_scope_not_preserved')
            hashes=('original_graph_sha256','prepared_graph_sha256','original_coordinates_sha256','prepared_coordinates_sha256')
            if (any(not _hash(row.get(k)) for k in hashes)
                    or row.get('original_graph_sha256')!=row.get('prepared_graph_sha256')
                    or row.get('original_coordinates_sha256')!=row.get('prepared_coordinates_sha256')):
                issues.append('original_and_prepared_graph_or_coordinate_fingerprints_disagree')
            if (not _text(row.get('original_canonical_isomeric_smiles'))
                    or row.get('original_microstate_smiles')!=old.get('microstate_id')
                    or not _text(row.get('original_microstate_smiles'))
                    or type(row.get('original_formal_charge')) is not int or type(row.get('parent_formal_charge')) is not int):
                issues.append('original_or_parent_chemical_state_fields_invalid')
            nt=row.get('enumerated_tautomers')
            if p['parent_policy']=='state_graph':
                if (row.get('enumeration_status')!='NOT_REQUESTED_STATE_GRAPH' or type(nt) is not int or nt!=1
                        or parent_smiles!=row.get('original_canonical_isomeric_smiles')
                        or row.get('parent_formal_charge')!=row.get('original_formal_charge')):
                    issues.append('state_graph_parent_differs_from_original_state')
            elif row.get('enumeration_status')!='Completed' or type(nt) is not int or not 1<=nt<=p['max_tautomers']:
                issues.append('tautomer_enumeration_not_complete_or_bounded')
            if p['parent_policy']=='charge_preserving_tautomer' and row.get('parent_formal_charge')!=row.get('original_formal_charge'):
                issues.append('charge_preserving_parent_changed_charge')
            if (not _inventory(row.get('original_isotope_inventory')) or not _inventory(row.get('parent_isotope_inventory'))
                    or row.get('original_isotope_inventory')!=row.get('parent_isotope_inventory') or row.get('isotope_policy_scope')!=ISOTOPE_SCOPE):
                issues.append('isotope_inventory_or_preservation_policy_changed')
            path=prefix+cid+'.identity.sdf';src=prefix+cid+'.source_constraints.private.json'
            declared={'sha256':row.get('prepared_sdf_sha256'),'bytes':row.get('prepared_sdf_bytes')}
            if row.get('prepared_sdf_path')!=cid+'.identity.sdf' or not _same_file(declared,bound.get(path)):
                issues.append('prepared_identity_SDF_not_source_bound')
            if (row.get('source_constraint_report_path')!=cid+'.source_constraints.private.json'
                    or not _hash(row.get('source_constraint_report_sha256'))
                    or row.get('source_constraint_report_sha256')!=bound.get(src,{}).get('sha256')
                    or row.get('source_constraint_report_sha256')!=old.get('constraint_report_sha256')
                    or row.get('source_generation_contract_sha256')!=old.get('generation_contract_sha256')):
                issues.append('source_constraint_binding_changed')
            issues.extend(_source_report(v,cid,content,bound,old,original))
            if row.get('error'):issues.append('prepared_identity_carries_failure_reason')
            groups.setdefault(parent,[]).append(cid)
        elif row.get('state')!='PREPARATION_FAILED' or not _text(row.get('error')) or row.get('parent_id') is not None:
            issues.append('missing_identity_failure_state_or_reason')
    for row in records:
        members=groups.get(row.get('parent_id'),[])
        if (type(row.get('parent_group_size')) is not int or row.get('parent_group_size')!=len(members)
                or row.get('group_representative_for_display_only') is not (bool(members) and row['candidate_id']==members[0])
                or row.get('no_candidates_dropped') is not True):issues.append('identity_group_denominator_changed')
    expected_groups={'policy_sha256':digest(policy),'groups':groups,'duplicates_retained':True,'identity_scope':'computed_grouping_not_independent_biological_or_experimental_entities'}
    if content[prefix+'parent_groups.private.json']!=expected_groups:issues.append('computed_parent_groups_changed')
    if not isinstance(eligible,list) or any(not isinstance(x,dict) for x in eligible):raise ValueError('Exact eligible identity output list required')
    if {x.get('candidate_id') for x in eligible}!=set(prepared) or len(eligible)!=len(prepared):issues.append('identity_eligibility_denominator_changed')
    for e in eligible:
        cid=e.get('candidate_id');row=prepared.get(cid,{})
        report=prefix+str(cid)+'.identity.private.json';path=prefix+str(cid)+'.identity.sdf';src=prefix+str(cid)+'.source_constraints.private.json'
        if (e.get('path')!=path or not _same_file(e,bound.get(path))
                or e.get('sha256')!=row.get('prepared_sdf_sha256') or e.get('bytes')!=row.get('prepared_sdf_bytes')):
            issues.append('identity_eligibility_points_to_different_prepared_SDF')
        if (any(e.get(k)!=row.get(k) for k in ('parent_id','microstate_id','state_id','identity_policy_sha256','source_sdf_sha256'))
                or e.get('variant')!=v or e.get('eligibility')!='REQUIRES_NEW_DOWNSTREAM_QC'
                or e.get('identity_report_path')!=report or not _hash(e.get('identity_report_sha256'))
                or not _file(bound.get(report)) or e.get('identity_report_sha256')!=bound.get(report,{}).get('sha256')
                or e.get('source_constraint_report_path')!=src
                or e.get('source_constraint_report_sha256')!=row.get('source_constraint_report_sha256')
                or e.get('constraints_preserved_by_exact_graph_atom_order_and_coordinate_invariance') is not True):
            issues.append('identity_eligibility_report_or_chemical_identity_changed')
    n=len(records);metrics={'requested_count':n,'prepared_count':len(prepared),'prepared_fraction':len(prepared)/n,'computed_parent_groups':len(groups)}
    if metrics['prepared_fraction']<p['minimum_prepared_fraction']:issues.append('prespecified_prepared_fraction_failed')
    return sorted(set(issues)),records,metrics
