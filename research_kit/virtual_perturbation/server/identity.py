"""Read-only package code inventory on the already provisioned server. Fits nothing."""
from pathlib import Path
import importlib.metadata,subprocess,sys,platform,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import sha,digest

def fingerprint(method):
    if sys.platform!='linux' or 'microsoft' in platform.release().lower():raise RuntimeError('Inspect existing server specialist environments, never initialize local scientific packages')
    if method in ('bulk_virtual_ko','singlecell_virtual_ko','boolnet'):
        package={'bulk_virtual_ko':'bulkKnk','singlecell_virtual_ko':'scTenifoldKnk','boolnet':'BoolNet'}[method]
        r=subprocess.run(['Rscript','--vanilla','-e',"cat(find.package('"+package+"'))"],capture_output=True,text=True,check=True)
        root=Path(r.stdout.strip()).resolve(strict=True)
        files=[f for f in root.rglob('*') if f.is_file() and (f.suffix in ('.rdb','.rdx','.R','.r','.so') or f.name in ('DESCRIPTION','NAMESPACE'))]
        rows={p.relative_to(root).as_posix():sha(p) for p in sorted(files)}
    else:
        package={'genki':'GenKI','gears':'cell-gears','geneformer':'geneformer','dynamo':'dynamo-release','celloracle':'celloracle','metabolic_gene_deletion':'cobra','cpa':'cpa-tools','scgpt':'scgpt','maboss':'maboss'}[method]
        dist=importlib.metadata.distribution(package);rows={}
        for p in sorted(dist.files or []):
            if p.suffix in ('.py','.so','.pyd') and '..' not in p.parts:
                actual=dist.locate_file(p)
                if not actual.is_file():raise ValueError('Installed backend code member missing')
                rows[str(p)]=sha(actual)
    if not rows:raise ValueError('No installed backend code identity could be inspected')
    return {'method':method,'package':package,'code_sha256':digest(rows),'code_files':rows,'scope':'package_code_inventory_not_dependency_or_scientific_validation'}

if __name__=='__main__':print(json.dumps(fingerprint(sys.argv[1]),indent=2))
