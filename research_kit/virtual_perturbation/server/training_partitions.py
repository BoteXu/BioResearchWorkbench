"""Biological-unit partition review only; no model fitting or scientific package imports."""
def inspect_ledger(rows,training_units,evaluation_units,evaluation_scope):
    permitted={'TRAINING','VALIDATION','CALIBRATION','PREPROCESSING_FIT','TEST','UNUSED'};pairs=set();parts={k:set() for k in permitted}
    if not rows:raise ValueError('Training unit ledger is empty')
    for row in rows:
        unit=row.get('unit_id');role=row.get('role')
        if not isinstance(unit,str) or not unit.strip() or role not in permitted or (unit,role) in pairs:raise ValueError('Training ledger has missing, duplicate or unrecognized unit/partition identity')
        pairs.add((unit,role));parts[role].add(unit)
    if parts['TRAINING']!=set(training_units):raise ValueError('Declared training units differ from actual training ledger')
    fitted=set().union(*(parts[r] for r in ('TRAINING','VALIDATION','CALIBRATION','PREPROCESSING_FIT')))
    overlap=sorted(set(evaluation_units)&fitted)
    if evaluation_scope=='heldout_donor' and overlap:raise ValueError('Held-out donors entered model fitting, validation/model selection, calibration or preprocessing fitting')
    return {'partition_units':{k:sorted(v) for k,v in parts.items()},'fitted_or_model_selection_units':sorted(fitted),'evaluation_units':list(evaluation_units),'evaluation_overlap_with_fitted_units':overlap,'evaluation_scope':evaluation_scope,'scope':'training_receipt_bound_declared_unit_ledger_not_independent_audit_of_pretraining_membership','external_generalization_established':False}
