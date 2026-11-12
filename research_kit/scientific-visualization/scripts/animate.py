"""Molecular trajectories from supplied coordinates, with common frame bounds."""
from pathlib import Path
import io,json,re
import numpy as np,matplotlib.pyplot as plt
from PIL import Image
from design_system import use_style,journal_size

def trajectory_gif(data,outdir,stem='fig_trajectory',overwrite=False,**options):
    xyz=np.asarray(data['coordinates']);times=np.asarray(data['times']);unit=data['unit']
    if xyz.ndim!=3 or xyz.shape[2]!=3 or len(xyz)!=len(times) or not np.isfinite(xyz).all():raise ValueError('Finite frame × atom × XYZ coordinates and one time per frame required')
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*',stem):raise ValueError('Plain output stem required')
    if len(xyz)>2000:raise ValueError('Select a bounded trajectory preview explicitly')
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True);path=out/(stem+'.gif')
    if path.exists() and not overwrite:raise FileExistsError(path)
    use_style();fig=plt.figure(figsize=journal_size(options.get('width','single'),.82));ax=fig.add_subplot(111,projection='3d');center=(xyz.min(axis=(0,1))+xyz.max(axis=(0,1)))/2;half=np.max(np.ptp(xyz,axis=(0,1)))*.53
    frames=[]
    for i,coords in enumerate(xyz):
        ax.clear();ax.plot(*coords.T,color='#3B6F91',lw=1.3,alpha=.9);ax.scatter(*coords[[0,-1]].T,s=22,c=['#4C9685','#CA7354'],depthshade=False);ax.set(xlim=(center[0]-half,center[0]+half),ylim=(center[1]-half,center[1]+half),zlim=(center[2]-half,center[2]+half));ax.set_box_aspect([1,1,1]);ax.view_init(elev=22,azim=-55);ax.set_axis_off();ax.set_title(data.get('title','Supplied molecular trajectory')+'\n'+f'{times[i]:g} {data.get("time_unit","ns")}',fontsize=9,pad=0)
        buf=io.BytesIO();fig.savefig(buf,format='png',dpi=150);buf.seek(0)
        with Image.open(buf) as im:frames.append(im.convert('RGB').copy())
    plt.close(fig);duration=int(options.get('duration_ms',350));frames[0].save(path,save_all=True,append_images=frames[1:],duration=duration,loop=0,disposal=2)
    representatives=[]
    for i in sorted(set([0,len(frames)//2,len(frames)-1])):
        f=out/f'{stem}_frame_{i:03d}.png';frames[i].save(f);representatives.append(str(f))
    for im in frames:im.close()
    return path,{'frame_count':len(xyz),'duration_ms':duration,'unit':unit,'time_unit':data.get('time_unit','ns'),'bounds_common_to_all_frames':True,'representatives':representatives,'outputs':[str(path),*representatives],'status':'RENDERED_UNREVIEWED'}
