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
    import copy
    cases=[]
    bad=copy.deepcopy(plan);bad['opening_title']['approved']=False;cases.append((bad,'Confirm opening_title'))
    bad=copy.deepcopy(plan);bad['scenes'][0]['template']='presenter';cases.append((bad,'First scene'))
    bad=copy.deepcopy(plan);bad['scenes'][2]['template']=bad['scenes'][1]['template'];cases.append((bad,'Adjacent paragraphs'))
    bad=copy.deepcopy(plan);bad['paragraphs'][1]['summary']='';cases.append((bad,'paragraph summary'))
    bad=copy.deepcopy(plan);bad['presenter']['framing_confirmed']=False;cases.append((bad,'Circle needs'))
    for bad,expected in cases:
        try:validate_standard_plan(bad,cues,font)
        except ValueError as error:
            if expected not in str(error):raise AssertionError('Unexpected validation error: '+str(error))
        else:raise AssertionError('Required user preference was not enforced: '+expected)
    # Regression: the circle must be filled with source pixels, including near its edges.
    from visuals import circular_presenter
    source=Image.new('RGB',(300,600),(201,33,61));canvas=Image.new('RGB',(220,220),(15,29,43))
    circular_presenter(canvas,source,(18,18,184),[0,0,1,1],preserve_all=True)
    for point in [(110,39),(110,181),(39,110),(181,110),(110,110)]:
        if canvas.getpixel(point)!=(201,33,61):raise AssertionError('Circular portrait contains letterbox/padding instead of source pixels')
    return rows

def main():
    check_environment();actual=samples();expected=json.loads((ROOT/'assets/reference-raster.json').read_text())
    if actual!=expected:raise SystemExit('Raster verification failed: check pinned environment, full package and font; do not silently render a different style')
    print(json.dumps({'profile':'wenfeng-standard-v1','standard_version':'1.2','raster_samples':len(actual),'status':'passed'},ensure_ascii=False))
if __name__=='__main__':main()
