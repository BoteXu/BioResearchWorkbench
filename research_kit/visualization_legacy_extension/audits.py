"""Figure deliverable metadata and color-role screening; never a scientific/visual approval."""
from pathlib import Path
import math,re,xml.etree.ElementTree as ET
from contracts import num,read,sha
def _rgb(h):return [int(h[i:i+2],16)/255 for i in (1,3,5)]
def _lum(rgb):
    linear=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb]
    return sum(a*b for a,b in zip(linear,[.2126,.7152,.0722]))
def _hex(rgb):return '#'+''.join(f'{round(x*255):02x}' for x in rgb)
def palette_audit(d):
    bg=_rgb(d['background']);bl=_lum(bg);rows=[]
    for name,h in d['colors'].items():
        rgba=[d['alpha']*v+(1-d['alpha'])*b for v,b in zip(_rgb(h),bg)];lum=_lum(rgba);ratio=(max(lum,bl)+.05)/(min(lum,bl)+.05);role=d['roles'][name];threshold={'normal_text':4.5,'large_text':3,'graphical':3}.get(role)
        rows.append({'name':name,'color':h,'display_color':_hex(rgba),'role':role,'contrast':ratio,'threshold_if_applicable':threshold,'decision':'REVIEW_CATEGORY_CUES' if threshold is None else 'SCREEN_PASS' if ratio>=threshold else 'CONTRAST_REVIEW','relative_luminance':lum})
    lum=[x['relative_luminance'] for x in rows];delta=[b-a for a,b in zip(lum,lum[1:])]
    return {'schema':'palette-role-screen/1','colors':rows,'ordered_luminance_monotonic':(all(x>=0 for x in delta) or all(x<=0 for x in delta)) if d.get('ordered') else None,'ordered_luminance_distinct':all(abs(x)>1e-4 for x in delta) if d.get('ordered') else None,'alpha':d['alpha'],'background':d['background'],'color_vision_simulation_performed':False,'accessibility_certified':False,'visual_acceptance':False}
def _length(value):
    m=re.fullmatch(r'([0-9.]+)(mm|cm|in|pt|px)?',str(value))
    if not m:raise ValueError('Unsupported explicit SVG physical length')
    return float(m[1])*{'mm':1,'cm':10,'in':25.4,'pt':25.4/72,'px':25.4/96,None:25.4/96}[m[2]]
def inspect(path,width_mm=None,min_dpi=300):
    f=Path(path)
    if not f.is_file() or f.is_symlink() or f.stat().st_size>40_000_000:raise ValueError('Select a bounded regular figure <=40 MB')
    if width_mm is not None:num(width_mm,1)
    result={'path':f.name,'sha256':sha(f),'bytes':f.stat().st_size,'format':f.suffix.lower(),'findings':[],'visual_acceptance':False,'journal_compliance_established':False}
    suffix=f.suffix.lower()
    if suffix=='.svg':
        raw=f.read_bytes()
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('SVG entity declarations refused')
        tree=ET.fromstring(raw);nodes=list(tree.iter())
        if len(nodes)>250000:raise ValueError('Too many SVG nodes; select a display subset or use cell rasterization')
        ns='{http://www.w3.org/2000/svg}';w=_length(tree.attrib.get('width'));h=_length(tree.attrib.get('height'));external=[]
        for el in nodes:
            for k,v in el.attrib.items():
                if k.endswith('href') and not v.startswith(('#','data:image/png;base64,','data:image/jpeg;base64,')):external.append(v)
            if el.tag.rsplit('}',1)[-1] in ('script','foreignObject'):result['findings'].append('ACTIVE_SVG_CONTENT_REQUIRES_REVIEW')
        result.update(width_mm=w,height_mm=h,editable_text_nodes=sum(el.tag==ns+'text' for el in nodes),raster_image_layers=sum(el.tag==ns+'image' for el in nodes),external_resource_count=len(external),has_title=bool(tree.find(ns+'title') is not None),has_description=bool(tree.find(ns+'desc') is not None),font_embedding_status='SVG_font_family_reference_not_embedded_font')
        if external:result['findings'].append('EXTERNAL_RESOURCE_NOT_OFFLINE')
        if width_mm is not None and abs(w-width_mm)>.1:result['findings'].append('PHYSICAL_WIDTH_DIFFERS')
        if not result['has_title'] or not result['has_description']:result['findings'].append('ACCESSIBLE_DESCRIPTION_MISSING')
    elif suffix in ('.png','.tif','.tiff','.jpg','.jpeg'):
        from PIL import Image
        with Image.open(f) as im:
            px,py=im.size
            if px*py>100_000_000:raise ValueError('Select a smaller export for bounded metadata inspection')
            dpi=im.info.get('dpi');effective=px/(width_mm/25.4) if width_mm is not None else None
            result.update(width_px=px,height_px=py,declared_dpi=list(dpi) if isinstance(dpi,(list,tuple)) else dpi,effective_dpi_at_target_width=effective,mode=im.mode,has_alpha='A' in im.getbands() or 'transparency' in im.info,icc_profile_present=bool(im.info.get('icc_profile')))
            if effective is not None and effective<min_dpi:result['findings'].append('EFFECTIVE_DPI_BELOW_TARGET')
    elif suffix=='.pdf':
        try:import fitz
        except ImportError:raise ValueError('Use the already bundled document Python runtime for PDF inspection; do not install a new environment')
        with fitz.open(f) as doc:
            if doc.needs_pass:raise ValueError('Encrypted PDF requires separately authorized access')
            result['pages']=len(doc);result['page_details']=[]
            for page in doc:
                fonts=[]
                for font in page.get_fonts(full=True):
                    xref=font[0];extracted=doc.extract_font(xref) if xref else ('','','',b'');fonts.append({'name':font[3],'type':font[2],'embedded':bool(extracted[3])})
                detail={'media_width_mm':page.mediabox.width*25.4/72,'media_height_mm':page.mediabox.height*25.4/72,'crop_width_mm':page.cropbox.width*25.4/72,'crop_height_mm':page.cropbox.height*25.4/72,'rotation':page.rotation,'fonts':fonts,'raster_images':len(page.get_images())};result['page_details'].append(detail)
                if width_mm is not None and abs(detail['crop_width_mm']-width_mm)>.1:result['findings'].append('PHYSICAL_WIDTH_DIFFERS')
                if any(not x['embedded'] for x in fonts):result['findings'].append('NONEMBEDDED_FONT_REQUIRES_REVIEW')
    else:raise ValueError('Supported figure metadata formats: SVG/PDF/PNG/TIFF/JPEG')
    result['findings']=sorted(set(result['findings']));result['state']='SCREEN_REVIEW' if result['findings'] else 'METADATA_SCREEN_PASS_NOT_VISUAL_APPROVAL';return result
def export_document(svg_path,outdir,width_px=1400):
    """Document rendering only; no analysis libraries. Original SVG remains editable."""
    import fitz
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=False);f=Path(svg_path)
    inspect(f)
    with fitz.open(f) as svg:
        pdf=svg.convert_to_pdf()
    pf=outdir/(f.stem+'.pdf');pf.write_bytes(pdf)
    with fitz.open(pf) as doc:
        p=doc[0];p.get_pixmap(matrix=fitz.Matrix(width_px/p.rect.width,width_px/p.rect.width),alpha=False).save(outdir/(f.stem+'.png'))
    return {'source_svg_sha256':sha(f),'files':[{'path':p.name,'sha256':sha(p)} for p in sorted(outdir.iterdir()) if p.is_file()],'state':'DOCUMENT_RENDERED_UNREVIEWED','analysis_performed':False}
