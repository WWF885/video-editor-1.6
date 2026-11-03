"""Check fixed template raster samples, without FFmpeg decode or speech inference."""
import hashlib,json
from pathlib import Path
from PIL import Image
from run import ROOT,check_environment
from standard_style import StandardStyle,validate_standard_plan

def samples():
    plan=json.loads((ROOT/'assets/standard-demo.json').read_text());cues=json.loads((ROOT/'assets/demo-captions.json').read_text());font=ROOT/'assets/fonts/NotoSansCJKsc-Regular.otf'
    validate_standard_plan(plan,cues,font);style=StandardStyle(plan,cues,font)
    frame=Image.open(ROOT/'assets/reference-source.png').convert('RGB');media=Image.open(ROOT/'assets/demo-insert.png').convert('RGB');rows=[]
    for i,scene in enumerate(plan['scenes']):
        for dt in (0,.08,.20,.60,1.75):
            t=round(scene['start']+dt,6)
            if t>=scene['end']:continue
            sc=dict(scene);sc['_presenter_crop_base']=plan['presenter']['crop']
            image=style.render(frame,t,i,sc,media_image=media if sc['template']=='media' else None)
            rows.append({'time':t,'sha256':hashlib.sha256(image.tobytes()).hexdigest()})
    # Content-only standard mode must reject visual overrides.
    broken=dict(plan,theme='pink')
    try:validate_standard_plan(broken,cues,font)
    except ValueError:pass
    else:raise AssertionError('Visual override was silently accepted')
    return rows

def main():
    check_environment();actual=samples();expected=json.loads((ROOT/'assets/reference-raster.json').read_text())
    if actual!=expected:raise SystemExit('Raster verification failed: check pinned environment, full package and font; do not silently render a different style')
    print(json.dumps({'profile':'wenfeng-standard-v1','raster_samples':len(actual),'status':'passed'},ensure_ascii=False))
if __name__=='__main__':main()
