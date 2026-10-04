"""Structured bounded DuckDB reads; no user SQL, table functions or remote endpoints."""
import json
import re
import threading
from pathlib import Path
from academic_common import artifact, digest


def _name(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,100}',value):raise ValueError('Simple explicit table/column identifiers required')
    return '"'+value+'"'


def query_selected_table(database_path: str, table_name: str, columns: list, filters: list = None, limit: int = 100, order_by: str = '') -> dict:
    """Read selected columns with bound scalar predicates from one local DuckDB table; deny external I/O and arbitrary SQL."""
    import duckdb
    initial=Path(database_path).expanduser()
    if any(p.is_symlink() for p in [initial,*initial.parents]):raise ValueError('Linked database paths refused')
    path=initial.resolve(strict=True)
    if not path.is_file() or path.suffix.lower()!='.duckdb' or path.stat().st_size>200_000_000:raise ValueError('Select a bounded .duckdb database; large queries belong on the server')
    if type(limit) is not int or not 1<=limit<=500 or not isinstance(columns,list) or not 1<=len(columns)<=30 or len(set(columns))!=len(columns):raise ValueError('Select 1 to 30 columns and at most 500 rows')
    table=_name(table_name);selection=','.join(_name(x) for x in columns)
    predicates=filters or []
    if not isinstance(predicates,list) or len(predicates)>20:raise ValueError('At most 20 predicates')
    where=[];args=[]
    for p in predicates:
        if not isinstance(p,dict) or set(p)!={'column','op','value'} or p['op'] not in ['=','!=','>','>=','<','<=']:raise ValueError('Only bound scalar predicates supported')
        if type(p['value']) not in (str,int,float,bool) or isinstance(p['value'],str) and len(p['value'])>1000:raise ValueError('Bound scalar value required')
        where.append(_name(p['column'])+' '+p['op']+' ?');args.append(p['value'])
    sql='SELECT '+selection+' FROM '+table+(' WHERE '+' AND '.join(where) if where else '')+(' ORDER BY '+_name(order_by) if order_by else '')+' LIMIT '+str(limit+1)
    # Refuse extension auto-loading, external filesystem/network functions and SET changes.
    conn=duckdb.connect(str(path),read_only=True,config={'enable_external_access':'false','autoinstall_known_extensions':'false','autoload_known_extensions':'false','threads':'1','memory_limit':'128MB'})
    timer=threading.Timer(10,conn.interrupt);timer.start()
    try:
        conn.execute('SET lock_configuration=true')
        cur=conn.execute(sql,args);names=[c[0] for c in cur.description];rows=cur.fetchmany(limit+1)
    finally:timer.cancel();conn.close()
    data=[dict(zip(names,r)) for r in rows[:limit]]
    serialized=json.dumps(data,default=str,allow_nan=False)
    if len(serialized)>100_000:raise ValueError('Selected result exceeds response bound')
    data=json.loads(serialized)
    return artifact('table_query',{'table_name':table_name,'columns':columns,'records':data,'truncated':len(rows)>limit,'read_only':True,
            'source_bytes':path.stat().st_size,'limitations':['No statistical inference, full-table audit or scientific validation is performed.','This fixed interface is restricted in process; the owner account remains responsible for filesystem permissions.']})
