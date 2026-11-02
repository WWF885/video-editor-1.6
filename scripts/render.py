"""Render speech-timed knowledge graphics and ONE measured subtitle line."""
import argparse,json,subprocess,tempfile,re
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import av
from captions import validate

def run(*args):return subprocess.run(['ffmpeg','-nostdin','-v','error','-y',*map(str,args)],check=True)
def probe(path):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
def fit(img,w,h):
    r=min(w/img.width,h/img.height);return img.resize((max(1,round(img.width*r)),max(1,round(img.height*r))),Image.Resampling.LANCZOS)
def main():
    p=argparse.ArgumentParser()
    for n in ('source','plan','captions','font','output'):p.add_argument('--'+n,required=True)
    a=p.parse_args();planpath=Path(a.plan).resolve();plan=json.load(open(planpath));src=Path(a.source).resolve();out=Path(a.output).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    if src==out:raise ValueError('Never overwrite original')
    meta=probe(src);duration=float(meta['format']['duration']);W=int(plan.get('width',512));H=int(plan.get('height',902));fps=int(plan.get('fps',30));size=round(W*.048)
    if W%2 or H%2 or min(W,H,fps)<=0:raise ValueError('Use positive even picture dimensions')
    @lru_cache(maxsize=32)
    def font(n):return ImageFont.truetype(a.font,round(n*W/512))
    cues=json.load(open(a.captions));validate(cues,font(25),W*.74)
    cuts=plan.get('cuts',[{'in':0,'out':duration}]);total=0;mapping=[]
    for c in cuts:
        if not 0<=c['in']<c['out']<=duration+.01:raise ValueError('Invalid source cut')
        mapping.append(dict(source_in=c['in'],source_out=c['out'],start=total));total+=c['out']-c['in']
    scenes=plan.get('scenes',[]);prev=0
    for s in scenes:
        if not 0<=s['start']<s['end']<=total+.01 or s['start']<prev:raise ValueError('Scene overlap/range')
        if s['mode'] not in ('overlay','card','steps','flow','compare','media'):raise ValueError('Unknown mode')
        if len(s.get('items',[]))>8:raise ValueError('Split dense scenes')
        prev=s['end']
        for v in s.get('items',[]):
            if not s['start']<=v['at']<s['end']:raise ValueError('Item outside scene')
    if cues and cues[-1]['end']>total+.05:raise ValueError('Caption beyond edit')
    dark=plan.get('theme','light')=='dark'
    if plan.get('theme','light') not in ('light','dark'):raise ValueError('Invalid theme')
    bg0,bg1,ink,accent,card=('#0A171B','#102328','#F3F7F7','#45E1C4','#15312F') if dark else ('#DFEDFD','#FFEBDD','#172737','#246CC8','#FFFFFF')
    def rgb(s):return np.array(tuple(bytes.fromhex(s[1:])))
    bg=Image.new('RGB',(W,H));d=ImageDraw.Draw(bg)
    for y in range(H):
        u=y/max(H-1,1);d.line((0,y,W,y),fill=tuple((rgb(bg0)*(1-u)+rgb(bg1)*u).astype(int)))
    def rect(d,box,fill=card,outline=None):d.rounded_rectangle(tuple(round(v*W/512) for v in box),radius=round(20*W/512),fill=fill,outline=outline,width=2)
    def txt(d,xy,t,n=25,color=ink):
        if any(x in t for x in ('\n','\r','\\N')):raise ValueError('Graphic text must also be a short single line')
        f=font(n)
        if f.getlength(t)>W*.86:raise ValueError('Graphic too wide; simplify')
        d.text(tuple(v*W/512 for v in xy),t,font=f,fill=color,anchor='mm')
    media={}
    for i,s in enumerate(scenes):
        if s['mode']=='media':
            path=(planpath.parent/s['asset']).resolve()
            try:media[i]=('image',Image.open(path).convert('RGB'))
            except Exception:
                c=av.open(str(path));vs=c.streams.video[0];media[i]=('video',c,iter(c.decode(video=0)),None)
    def media_frame(i,s,t):
        entry=media[i]
        if entry[0]=='image':return entry[1]
        target=s.get('asset_in',0)+t-s['start'];kind,c,it,current=entry
        while current is None or float(current.time or 0)<target:
            try:current=next(it)
            except StopIteration:raise ValueError('Auxiliary video too short; do not loop silently')
        media[i]=(kind,c,it,current);return current.to_image()
    with tempfile.TemporaryDirectory(prefix='knowledge-edit-') as td:
        base=Path(td)/'base.mkv';g=[]
        has_audio=any(s['codec_type']=='audio' for s in meta['streams'])
        for i,c in enumerate(cuts):
            g.append(f"[0:v]trim=start={c['in']}:end={c['out']},setpts=PTS-STARTPTS,scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={fps}[v{i}]")
            if has_audio:g.append(f"[0:a]atrim=start={c['in']}:end={c['out']},asetpts=PTS-STARTPTS[a{i}]")
        g.append(''.join(f'[v{i}]'+(f'[a{i}]' if has_audio else '') for i in range(len(cuts)))+f'concat=n={len(cuts)}:v=1:a={int(has_audio)}[v]'+('[a]' if has_audio else ''))
        args=['-i',src,'-filter_complex',';'.join(g),'-map','[v]']
        if has_audio:args+=['-map','[a]','-c:a','pcm_s16le']
        run(*args,'-c:v','libx264','-preset','fast','-crf','18',base)
        cmd=['ffmpeg','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-i',str(base),'-map','0:v:0']
        if has_audio:cmd+=['-map','1:a:0','-c:a','aac','-b:a','160k']
        cmd+=['-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
        enc=subprocess.Popen(cmd,stdin=subprocess.PIPE);container=av.open(str(base))
        try:
            for idx,f in enumerate(container.decode(video=0)):
                t=idx/fps;original=f.to_image();active=next(((i,s) for i,s in enumerate(scenes) if s['start']<=t<s['end']),None)
                im=original.copy()
                if active:
                    si,s=active;inset=s['mode']!='overlay'
                    if inset:
                        im=bg.copy();thumb=fit(original,round(W*.40),round(H*.39));x=(W-thumb.width)//2;y=round(H*.46)
                        mask=Image.new('L',thumb.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,thumb.width-1,thumb.height-1),radius=round(W*.035),fill=255)
                        im.paste(thumb,(x,y),mask)
                    # Short graphic-only fade/slide; audio and A-roll never retimed.
                    layer=Image.new('RGBA',(W,H));dr=ImageDraw.Draw(layer)
                    if s.get('title'):rect(dr,(30,40,482,99));txt(dr,(256,70),s['title'],23)
                    items=[v for v in s.get('items',[]) if v['at']<=t]
                    if s['mode']=='media':
                        pic=fit(media_frame(si,s,t),round(W*.88),round(H*.30));layer.paste(pic,((W-pic.width)//2,round(H*.13)))
                    elif s['mode']=='compare':
                        for col in (0,1):rect(dr,(30+col*241,128,241+col*241,342),outline=accent if col else None)
                        counts=[0,0]
                        for v in items:
                            col=int(v.get('column',0))
                            if col not in (0,1):raise ValueError('Invalid compare column')
                            row=counts[col];counts[col]+=1
                            if row>=4:raise ValueError('Too many compare rows')
                            n=21
                            if font(n).getlength(v['text'])>W*.37:raise ValueError('Compare label too wide')
                            txt(dr,(135+col*241,163+row*46),v['text'],n,accent if col else ink)
                    else:
                        if s['mode']!='overlay' and items:rect(dr,(30,124,482,362))
                        for j,v in enumerate(items):
                            if j>=4:raise ValueError('Split list after four visible rows')
                            move=round(10*(1-min(1,(t-v['at'])/.22))**3);y=155+j*57+move
                            if s['mode']=='steps':
                                rr=W/512;dr.ellipse(tuple(int(q*rr) for q in (54,y-15,84,y+15)),fill=accent);txt(dr,(69,y),str(j+1),17,'#FFFFFF');xx=282
                            else:xx=256
                            txt(dr,(xx,y),v['text'],23,accent)
                            if s['mode']=='flow' and j and t>=v['at']+.1:
                                rr=W/512;dr.line(tuple(int(q*rr) for q in (256,y-39,256,y-25)),fill=accent,width=3);dr.polygon([(int(q*rr),int(r*rr)) for q,r in ((251,y-30),(261,y-30),(256,y-23))],fill=accent)
                    alpha=min(1,(t-s['start'])/.18);layer.putalpha(layer.getchannel('A').point(lambda x:int(x*alpha)));im=Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')
                cue=next((c for c in cues if c['start']<=t<c['end']),None)
                if cue:
                    dr=ImageDraw.Draw(im);fnt=font(25);text=cue['text'];keys=[k for k in cue.get('highlights',[]) if k][:2]
                    rx=re.compile('('+ '|'.join(re.escape(k) for k in sorted(keys,key=len,reverse=True))+')') if keys else None
                    spans=rx.split(text) if rx else [text];x=(W-fnt.getlength(text))/2;y=H*float(plan.get('caption_y',.71))
                    for span in spans:
                        if not span:continue
                        hot=span in keys;dr.text((x,y),span,font=fnt,fill=accent if hot else '#FFFFFF',anchor='lm',stroke_width=2,stroke_fill='#102024')
                        if hot:dr.text((x+.5,y),span,font=fnt,fill=accent,anchor='lm',stroke_width=0)
                        x+=fnt.getlength(span)
                enc.stdin.write(im.tobytes())
        finally:
            enc.stdin.close();container.close()
        if enc.wait()!=0:raise RuntimeError('Encode failed')
    run('-i',out,'-f','null','-')
    report={'source_to_final':mapping,'duration':total,'single_line_validation':True,'listening_review':'not_performed','normal_speed_playback_review':'not_performed','full_decode':'passed'}
    out.with_suffix('.review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
