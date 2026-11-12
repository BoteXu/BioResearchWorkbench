"""Static Boolean grammar/QC only. Never evaluates source expressions or simulates states."""
import re
def boolnet_grammar(text):
    lines=[s.strip() for s in text.splitlines() if s.strip() and not s.lstrip().startswith('#')]
    if not lines or lines[0].replace(' ','').lower()!='targets,factors':raise ValueError('Native targets,factors header required')
    rules={}
    for line in lines[1:]:
        pieces=line.split(',')
        if len(pieces)!=2:raise ValueError('Exactly target and Boolean expression are required')
        target,expr=(s.strip() for s in pieces)
        if not re.fullmatch('[A-Za-z][A-Za-z0-9_]*',target) or target in rules or not re.fullmatch('[A-Za-z0-9_ &|!()]+',expr):raise ValueError('Duplicate/invalid node or executable expression refused')
        if any(v not in ('0','1') for v in re.findall(r'\b\d+\b',expr)):raise ValueError('Only binary Boolean constants are accepted')
        rules[target]=expr
    if not rules:raise ValueError('No logical rules')
    for expr in rules.values():
        if not set(re.findall('[A-Za-z][A-Za-z0-9_]*',expr))<=set(rules):raise ValueError('Unresolved Boolean input node')
    return rules
