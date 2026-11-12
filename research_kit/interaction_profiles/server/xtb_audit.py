"""Module-scoped xTB evidence capture. No scientific imports or fallback engines."""
from contextlib import contextmanager
from pathlib import Path
import datetime,hashlib,json,math,re,shutil,subprocess,threading

_LOCK=threading.RLock()
def _sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def _write(path,obj):
    with Path(path).open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def _now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def identify_xtb(expected_sha256,expected_version,destination):
    """Probe an existing reviewed binary; never install or download."""
    destination=Path(destination);exe=shutil.which('xtb')
    if not exe or _sha(exe)!=expected_sha256:raise ValueError('Existing xTB binary differs from reviewed SHA256')
    done=subprocess.run([exe,'--version'],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30)
    text=done.stdout+done.stderr;(destination/'xtb_version.log').write_text(text,encoding='utf8')
    record={'schema':'private-xtb-identity/1','executable':str(Path(exe).resolve()),'sha256':_sha(exe),'version_stdout':done.stdout,'version_stderr':done.stderr,'version_exit_code':done.returncode,'reviewed_version_text':expected_version,'version_matches':bool(expected_version) and expected_version in text,'method_cli_explicit':False,'paper_expected_method':'GFN2-xTB','native_method_selection':'installed_xtb_default_no_explicit_gfn_argument','default_method_independently_verified':False,'scientific_acceptance':'NOT_ESTABLISHED'}
    _write(destination/'xtb_identity.private.json',record)
    if done.returncode!=0 or not record['version_matches'] or record['sha256']!=expected_sha256:raise ValueError('Actual xTB version probe failed or differs from review')
    return record

class _Proxy:
    def __init__(self,audit,original):self.audit,self.original=audit,original
    def __getattr__(self,key):return getattr(self.original,key)
    def _call(self,operation,*args,**kwargs):
        before=len(self.audit.records)
        try:return self.audit._invoke(operation,*args,**kwargs)
        except BaseException as error:
            if len(self.audit.records)==before:self.audit.capture_errors.append({'candidate':self.audit.context,'invocation_rejected_before_engine_start':True,'error':type(error).__name__+': '+str(error)})
            raise
    def check_call(self,*args,**kwargs):return self._call('check_call',*args,**kwargs)
    def check_output(self,*args,**kwargs):return self._call('check_output',*args,**kwargs)

class XtbAudit:
    """Observe only conformer_generation.subprocess, preserving native exceptions.

    The guarded route uses a single worker and attributes calls before evaluation.
    The observer writes evidence before upstream finally removes its temp folder.
    """
    def __init__(self,module,directory,identity,timeout_seconds,charge_sum_tolerance,max_atoms,owned_work_directory):
        self.module,self.directory,self.identity=module,Path(directory),identity
        self.timeout,self.charge_tolerance,self.max_atoms=timeout_seconds,charge_sum_tolerance,max_atoms
        self.owned_work=Path(owned_work_directory).resolve(strict=True)
        self.records=[];self.context=None;self.original=None;self.proxy=None;self.capture_errors=[]
    def __enter__(self):
        _LOCK.acquire()
        try:
            self.directory.mkdir(exist_ok=False);self.original=self.module.subprocess
            if isinstance(self.original,_Proxy):raise RuntimeError('Nested xTB observer refused')
            self.proxy=_Proxy(self,self.original);self.module.subprocess=self.proxy;return self
        except BaseException:_LOCK.release();raise
    def __exit__(self,kind,value,tb):
        changed=self.module.subprocess is not self.proxy;self.module.subprocess=self.original
        try:
            _write(self.directory/'index.private.json',{'schema':'private-native-xtb-audit/1','calls':self.records,'capture_errors':self.capture_errors,'single_worker':True,'module_binding_restored':True,'method_cli_explicit':False,'energy_unit':'hartree','timeout_scope':'each_xtb_subprocess_not_whole_molecule_or_batch','scientific_acceptance':'NOT_ESTABLISHED'})
            if changed:raise RuntimeError('Native subprocess observer replaced during evaluation')
        finally:_LOCK.release()
        return False
    @contextmanager
    def candidate(self,candidate_id,native_i):
        if self.context is not None:raise RuntimeError('Nested/concurrent candidate refused')
        if not re.fullmatch(r'generated_[0-9]+',candidate_id) or type(native_i) is not int:raise ValueError('Exact candidate/index required')
        self.context={'candidate_id':candidate_id,'native_i':native_i}
        try:yield
        finally:self.context=None
    def _copy(self,folder,cwd,name):
        source=cwd/name
        if not source.exists():return None
        if source.is_symlink() or not source.is_file() or source.stat().st_size>32*1024*1024:raise ValueError('Unexpected engine artifact type/size: '+name)
        target=folder/name;shutil.copyfile(source,target)
        return {'path':target.relative_to(self.directory).as_posix(),'sha256':_sha(target),'bytes':target.stat().st_size}
    def _assess(self,folder,charge,returncode,stage):
        issues=[];data={}
        try:
            lines=(folder/'input_mol.xyz').read_text(encoding='utf8').splitlines();count=int(lines[0])
            if not 0<count<=self.max_atoms or len(lines)!=count+2:raise ValueError('Input atom denominator outside reviewed scope')
            source_elements=[]
            for line in lines[2:]:
                fields=line.split()
                if len(fields)!=4 or not all(math.isfinite(float(x)) for x in fields[1:]):raise ValueError('Input coordinate rows incomplete/nonfinite')
                source_elements.append(fields[0])
            values=[float(x.strip()) for x in (folder/'charges').read_text().splitlines()]
            if len(values)!=count or not all(math.isfinite(x) for x in values):raise ValueError('Partial charge axis incomplete/nonfinite')
            total=math.fsum(values);data.update(atoms=count,requested_formal_charge=charge,partial_charge_sum=total,partial_charge_count=len(values))
            if abs(total-charge)>self.charge_tolerance:issues.append('partial_charge_sum_outside_prespecified_tolerance')
        except (OSError,ValueError,IndexError) as error:issues.append('input_or_charge_audit_failed:'+str(error))
        optimized_ok=None
        if stage=='relaxation':
            try:
                relaxed=(folder/'xtbopt.xyz').read_text(encoding='utf8').splitlines();n=int(relaxed[0])
                if n!=count or len(relaxed)!=n+2:raise ValueError('Relaxed atom denominator changed')
                for i,line in enumerate(relaxed[2:]):
                    fields=line.split()
                    if len(fields)!=4 or fields[0]!=source_elements[i] or not all(math.isfinite(float(x)) for x in fields[1:]):raise ValueError('Relaxed element/coordinate axis changed')
                optimized_ok=True
            except (OSError,ValueError,IndexError,UnboundLocalError) as error:optimized_ok=False;issues.append('optimized_coordinate_audit_failed:'+str(error))
        energy=None;normal=False;failed_marker=False;number=r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?)';log=folder/'engine.log'
        if log.exists():
            with log.open(encoding='utf8',errors='replace') as f:
                for line in f:
                    if 'normal termination of xtb' in line.lower():normal=True
                    if re.search(r'not converged|failed to converge|abnormal termination',line,re.I):failed_marker=True
                    match=re.search(r'TOTAL ENERGY\s+'+number,line)
                    if match:
                        value=float(match[1].replace('D','E').replace('d','e'))
                        if math.isfinite(value):energy=value
        if energy is None and (folder/'xtbopt.xyz').exists():
            with (folder/'xtbopt.xyz').open(encoding='utf8',errors='replace') as f:next(f,'');header=next(f,'')
            match=re.search(r'energy\s*[:=]?\s*'+number,header,re.I)
            if match:
                value=float(match[1].replace('D','E').replace('d','e'))
                if math.isfinite(value):energy=value
        if energy is None:issues.append('finite_engine_energy_not_observed')
        if not normal:issues.append('normal_xtb_termination_not_observed')
        if failed_marker:issues.append('engine_log_contains_unresolved_failure_marker')
        if returncode!=0:issues.append('engine_exit_not_zero_or_unavailable')
        data.update(energy_hartree=energy,normal_termination_observed=normal,optimized_coordinate_axis_valid=optimized_ok,partial_charge_unit='elementary_charge',evidence_issues=issues,evidence_complete=not issues);return data
    def _invoke(self,operation,*args,**kwargs):
        if self.context is None:raise RuntimeError('Unattributed native xTB call refused')
        if len(args)!=1 or not isinstance(args[0],(list,tuple)):raise ValueError('Pinned native argv form changed')
        native=list(args[0])
        timeout=kwargs.get('timeout')
        if len(native)<2 or native[0]!='xtb' or native[1]!='input_mol.xyz' or '--chrg' not in native or '--parallel' not in native or kwargs.get('shell',False) or type(timeout) not in (int,float) or not math.isclose(timeout,self.timeout,rel_tol=1e-12,abs_tol=1e-9):raise ValueError('Pinned native command/budget changed')
        if '--gfn' in native:raise ValueError('Native default-method command changed')
        exe=Path(self.identity['executable']);found=shutil.which('xtb')
        if not found or Path(found).resolve()!=exe.resolve() or _sha(exe)!=self.identity['sha256']:raise ValueError('Actual xTB binary changed before invocation')
        charge=int(native[native.index('--chrg')+1]);cwd=Path(kwargs['cwd']).resolve(strict=True)
        if not cwd.is_relative_to(self.owned_work) or cwd==self.owned_work or not cwd.is_dir():raise ValueError('Native xTB cwd escapes the fresh owned workspace')
        if {x.name for x in cwd.iterdir()}!={'input_mol.xyz'}:raise ValueError('Pre-existing native restart/output/unselected files are refused')
        index=len(self.records);folder=self.directory/('call_'+format(index,'06d'));folder.mkdir(exist_ok=False)
        row={**self.context,'call_index':index,'operation':operation,'stage':'relaxation' if '--opt' in native else 'single_point','native_argv':native,'executed_argv':[str(exe)]+native[1:],'cwd':str(cwd),'started':_now(),'finished':None,'returncode':None,'timed_out':False,'exception_type':None,'exception_message':None,'requested_formal_charge':charge,'timeout_seconds':kwargs['timeout'],'timeout_scope':'each_xtb_subprocess_not_whole_molecule_or_batch','xtb_sha256':self.identity['sha256'],'method_cli_explicit':False,'native_method_selection':'installed_xtb_default','energy_unit':'hartree','energy_scope':'isolated_conformer_not_binding_energy','artifacts':{},'scientific_acceptance':'NOT_ESTABLISHED'}
        self.records.append(row);actual=dict(kwargs);result=None
        try:
            row['artifacts']['input_mol.xyz']=self._copy(folder,cwd,'input_mol.xyz')
            if operation=='check_call':
                if actual.get('stdout')!=self.original.DEVNULL or actual.get('stderr')!=self.original.STDOUT:raise ValueError('Pinned native stream handling changed')
                with (folder/'engine.log').open('xb') as log:actual['stdout']=log;result=self.original.check_call(row['executed_argv'],**actual)
                row['returncode']=int(result)
            else:
                result=self.original.check_output(row['executed_argv'],**actual);self._save_output(folder/'engine.log',result);row['returncode']=0
            return result
        except BaseException as error:
            row['exception_type']=type(error).__name__;row['exception_message']=str(error)
            if isinstance(error,self.original.CalledProcessError):row['returncode']=error.returncode
            if isinstance(error,self.original.TimeoutExpired):row['timed_out']=True
            if operation=='check_output':
                try:self._save_output(folder/'engine.log',getattr(error,'output',None))
                except BaseException as capture_error:self.capture_errors.append({'call_index':index,'error':type(capture_error).__name__+': '+str(capture_error)})
            raise
        finally:
            try:
                for name in ('charges','xtbopt.xyz'):row['artifacts'][name]=self._copy(folder,cwd,name)
                log=folder/'engine.log'
                if log.exists():row['artifacts']['engine.log']={'path':log.relative_to(self.directory).as_posix(),'sha256':_sha(log),'bytes':log.stat().st_size}
                row.update(self._assess(folder,charge,row['returncode'],row['stage']));row['binary_unchanged_after_call']=_sha(exe)==self.identity['sha256']
                if not row['binary_unchanged_after_call']:row['evidence_issues'].append('executable_changed_during_call');row['evidence_complete']=False
            except BaseException as error:
                row['capture_error']=type(error).__name__+': '+str(error);row['evidence_complete']=False;self.capture_errors.append({'call_index':index,'error':row['capture_error']})
            row['finished']=_now()
            try:_write(folder/'receipt.private.json',row)
            except BaseException as error:
                row['capture_error']=type(error).__name__+': '+str(error);row['evidence_complete']=False;self.capture_errors.append({'call_index':index,'error':row['capture_error']})
    @staticmethod
    def _save_output(path,output):
        if output is None:Path(path).write_bytes(b'')
        elif isinstance(output,bytes):Path(path).write_bytes(output)
        elif isinstance(output,str):Path(path).write_text(output,encoding='utf8')
        else:raise TypeError('Unexpected subprocess output type')
