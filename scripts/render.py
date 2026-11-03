"""Render speech-timed knowledge graphics and ONE measured subtitle line."""
import argparse,json,subprocess,tempfile,re,hashlib,wave,math
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import av
from captions import validate
from visuals import frosted_background, circular_presenter

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
    cues=json.load(open(a.captions));profile=plan.get('style_profile')
    if profile not in (None,'legacy','wenfeng-standard-v1'):raise ValueError('Unknown style_profile')
    standard=profile=='wenfeng-standard-v1'
    style=None
    if standard:
        from standard_style import StandardStyle, validate_standard_plan
        validate_standard_plan(plan,cues,a.font);style=StandardStyle(plan,cues,a.font)
    else:validate(cues,font(25),W*.74)
    cuts=plan.get('cuts',[{'in':0,'out':duration}]);total=0;mapping=[]
    for c in cuts:
        if not 0<=c['in']<c['out']<=duration+.01:raise ValueError('Invalid source cut')
        mapping.append(dict(source_in=c['in'],source_out=c['out'],start=total));total+=c['out']-c['in']
    scenes=plan.get('scenes',[]);prev=0
    for s in scenes:
        if not 0<=s['start']<s['end']<=total+.01 or s['start']<prev:raise ValueError('Scene overlap/range')
        if not standard and s['mode'] not in ('overlay','card','steps','flow','compare','media'):raise ValueError('Unknown mode')
        if len(s.get('items',[]))>8:raise ValueError('Split dense scenes')
        prev=s['end']
        for v in s.get('items',[]):
            if not s['start']<=v['at']<s['end']:raise ValueError('Item outside scene')
    if standard and abs(scenes[-1]['end']-total)>.02:raise ValueError('Standard scenes must cover complete edited duration')
    if cues and cues[-1]['end']>total+.05:raise ValueError('Caption beyond edit')
    dark=plan.get('theme','light')=='dark'
    if plan.get('theme','light') not in ('light','dark'):raise ValueError('Invalid theme')
    bg0,bg1,ink,accent,card=('#0A171B','#102328','#F3F7F7','#45E1C4','#15312F') if dark else ('#DFEDFD','#FFEBDD','#172737','#246CC8','#FFFFFF')
    def rgb(s):return np.array(tuple(bytes.fromhex(s[1:])))
    bg=Image.new('RGB',(W,H));d=ImageDraw.Draw(bg)
    for y in range(H):
        u=y/max(H-1,1);d.line((0,y,W,y),fill=tuple((rgb(bg0)*(1-u)+rgb(bg1)*u).astype(int)))
    if plan.get('background','frosted')=='frosted':bg=frosted_background(W,H,not dark)
    def rect(d,box,fill=card,outline=None):d.rounded_rectangle(tuple(round(v*W/512) for v in box),radius=round(20*W/512),fill=fill,outline=outline,width=2)
    def txt(d,xy,t,n=25,color=ink):
        if any(x in t for x in ('\n','\r','\\N')):raise ValueError('Graphic text must also be a short single line')
        f=font(n)
        if f.getlength(t)>W*.86:raise ValueError('Graphic too wide; simplify')
        d.text(tuple(v*W/512 for v in xy),t,font=f,fill=color,anchor='mm')
    def normalized_box(box):
        if len(box)!=4 or not all(isinstance(v,(int,float)) and 0<=v<=1 for v in box) or box[2]<=0 or box[3]<=0 or box[0]+box[2]>1.00001 or box[1]+box[3]>1.00001:raise ValueError('Invalid media_box x,y,width,height')
        return tuple(round(v*(W if i%2==0 else H)) for i,v in enumerate(box))
    source_video=next(v for v in meta['streams'] if v['codec_type']=='video')
    sw,sh=source_video['width'],source_video['height']
    rotation=next((float(v.get('rotation',0)) for v in source_video.get('side_data_list',[]) if 'rotation' in v),float(source_video.get('tags',{}).get('rotate',0)))
    if round(rotation)%180:sw,sh=sh,sw
    def source_crop_to_base(crop):
        if crop is None:return None
        if len(crop)!=4 or not all(0<=v<=1 for v in crop) or crop[0]>=crop[2] or crop[1]>=crop[3]:raise ValueError('Invalid source presenter crop')
        scale=min(W/sw,H/sh);dw=round(sw*scale);dh=round(sh*scale);ox=(W-dw)//2;oy=(H-dh)//2
        return [(ox+crop[0]*dw)/W,(oy+crop[1]*dh)/H,(ox+crop[2]*dw)/W,(oy+crop[3]*dh)/H]
    def draw_presenter(im,original,s):
        if not s.get('show_presenter',True):return
        if plan.get('presenter_shape','circle')=='circle':
            cfg=s.get('presenter',plan.get('presenter',{}));diameter=round(W*cfg.get('diameter',.36))
            circular_presenter(im,original,(W*cfg.get('x',.56),H*cfg.get('y',.67),diameter),source_crop_to_base(cfg.get('crop')))
        else:
            thumb=fit(original,round(W*.40),round(H*.39));x=(W-thumb.width)//2;y=round(H*.46)
            mask=Image.new('L',thumb.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,thumb.width-1,thumb.height-1),radius=round(W*.035),fill=255);im.paste(thumb,(x,y),mask)
    media={}
    for i,s in enumerate(scenes):
        if s.get('mode',s.get('template'))=='media':
            if s.get('asset_audio','mute')!='mute':raise ValueError('Built-in renderer supports muted auxiliary audio only; use an explicit audio mix for other needs')
            path=(planpath.parent/s['asset']).resolve()
            normalized_box(s.get('media_box',[.06,.14,.88,.70]))
            try:
                with Image.open(path) as pic:media[i]={'kind':'image','image':pic.convert('RGB')}
            except (OSError,ValueError):
                md=probe(path);vmeta=next(v for v in md['streams'] if v['codec_type']=='video');length=float(vmeta.get('duration',md['format']['duration']))
                begin=float(s.get('asset_in',0));end=float(s.get('asset_out',length))
                if not 0<=begin<end<=length+.001 or begin+s['end']-s['start']>end+.001:raise ValueError('Auxiliary video too short or invalid asset range')
                c=av.open(str(path));it=iter(c.decode(video=0));first=next(it,None)
                if first is None:raise ValueError('Empty auxiliary video')
                if first.time is None:raise ValueError('Auxiliary video needs presentation timestamps')
                media[i]={'kind':'video','container':c,'iterator':it,'current':first,'next':next(it,None),'origin':float(first.time)}
    def media_frame(i,s,t):
        entry=media[i]
        if entry['kind']=='image':return entry['image']
        target=float(s.get('asset_in',0))+t-s['start']
        while entry['next'] is not None:
            nxt=entry['next']
            if nxt.time is None:raise ValueError('Missing auxiliary timestamp')
            if float(nxt.time)-entry['origin']>target+1e-7:break
            entry['current']=nxt;entry['next']=next(entry['iterator'],None)
        return entry['current'].to_image()
    def media_picture(si,s,t):
        pic=media_frame(si,s,t)
        crop=s.get('asset_crop')
        if crop is not None:
            if len(crop)!=4 or not all(0<=v<=1 for v in crop) or crop[0]>=crop[2] or crop[1]>=crop[3]:raise ValueError('Invalid asset crop left,top,right,bottom')
            pic=pic.crop(tuple(round(v*(pic.width if i%2==0 else pic.height)) for i,v in enumerate(crop)))
        x,y,w,h=normalized_box(s.get('media_box',[.06,.14,.88,.70]));pic=fit(pic,w,h);px=x+(w-pic.width)//2;py=y+(h-pic.height)//2
        return pic,px,py
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
        cmd=['ffmpeg','-nostdin','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-i',str(base)]
        if has_audio and standard:
            sr=48000;sound=np.zeros((math.ceil(total*sr)+sr//2,2),np.float32)
            for j,sc in enumerate(scenes[1:]):
                k=round(sc['start']*sr);u=np.arange(round(.11*sr))/sr
                tone=(np.sin(2*np.pi*(650-220*u)*u)*.7+np.random.default_rng(j).normal(0,.1,len(u)))*.012*np.exp(-u*42)*np.minimum(1,u/.006)
                sound[k:k+len(u)]+=tone[:,None]
            sfx=Path(td)/'accents.wav'
            with wave.open(str(sfx),'w') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes((np.clip(sound,-1,1)*32767).astype('<i2').tobytes())
            measured=subprocess.run(['ffmpeg','-nostdin','-v','info','-i',str(base),'-vn','-af','volumedetect','-f','null','-'],capture_output=True,text=True,check=True).stderr
            maximum=re.search(r'max_volume: ([^ ]+) dB',measured)
            normalize=bool(maximum and maximum.group(1)!='-inf' and float(maximum.group(1))>-70)
            audio_filter='[1:a][2:a]amix=inputs=2:duration=first:normalize=0'+(',loudnorm=I=-16:TP=-1.5:LRA=11' if normalize else '')+'[a]'
            cmd+=['-i',str(sfx),'-filter_complex',audio_filter,'-map','[a]','-c:a','aac','-b:a','160k','-ar','48000']
        elif has_audio:cmd+=['-map','1:a:0','-c:a','aac','-b:a','160k']
        cmd+=['-map','0:v:0','-c:v','libx264','-preset','fast','-crf','18' if standard else '19','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
        enc=subprocess.Popen(cmd,stdin=subprocess.PIPE);container=av.open(str(base));raster_hash=hashlib.sha256();frame_count=0
        try:
            for idx,f in enumerate(container.decode(video=0)):
                t=idx/fps;original=f.to_image();active=next(((i,s) for i,s in enumerate(scenes) if s['start']<=t<s['end']),None)
                if standard:
                    if active is None:raise ValueError('Standard timeline requires a scene at every frame')
                    si,sc=active;sc=dict(sc);cfg=sc.get('presenter',plan.get('presenter',{}));sc['_presenter_crop_base']=source_crop_to_base(cfg.get('crop'))
                    pic=media_frame(si,sc,t) if sc.get('template')=='media' else None
                    im=style.render(original,t,si,sc,media_image=pic);raw=im.tobytes();raster_hash.update(raw);frame_count+=1;enc.stdin.write(raw);continue
                im=original.copy()
                if active:
                    si,s=active;inset=s['mode']!='overlay'
                    if inset:
                        im=bg.copy()
                        if s['mode']!='media':draw_presenter(im,original,s)
                    # Short graphic-only fade/slide; audio and A-roll never retimed.
                    layer=Image.new('RGBA',(W,H));dr=ImageDraw.Draw(layer)
                    if s.get('title'):rect(dr,(30,40,482,99));txt(dr,(256,70),s['title'],23)
                    items=[v for v in s.get('items',[]) if v['at']<=t]
                    if s.get('mode',s.get('template'))=='media':
                        pic,px,py=media_picture(si,s,t);layer.paste(pic,(px,py))
                        # Highlight coordinates refer to the displayed (after-crop) asset.
                        for mark in s.get('focus',[]):
                            if not s['start']<=mark['at']<s['end']:raise ValueError('Focus timing outside scene')
                            if t<mark['at']:continue
                            q=mark['box']
                            if len(q)!=4 or not all(0<=v<=1 for v in q) or q[0]>=q[2] or q[1]>=q[3]:raise ValueError('Invalid focus box')
                            dr.rectangle((px+q[0]*pic.width,py+q[1]*pic.height,px+q[2]*pic.width,py+q[3]*pic.height),outline=accent,width=max(2,round(W/170)))
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
                    alpha=1 if s['start']==0 else min(1,(t-s['start'])/.18);layer.putalpha(layer.getchannel('A').point(lambda x:int(x*alpha)));im=Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')
                    if s.get('mode',s.get('template'))=='media':draw_presenter(im,original,s)
                cue=next((c for c in cues if c['start']<=t<c['end']),None)
                if cue:
                    dr=ImageDraw.Draw(im);fnt=font(25);text=cue['text'];keys=[k for k in cue.get('highlights',[]) if k][:2]
                    rx=re.compile('('+ '|'.join(re.escape(k) for k in sorted(keys,key=len,reverse=True))+')') if keys else None
                    spans=rx.split(text) if rx else [text];x=(W-fnt.getlength(text))/2;y=H*float(plan.get('caption_y',.925))
                    for span in spans:
                        if not span:continue
                        hot=span in keys;dr.text((x,y),span,font=fnt,fill=accent if hot else '#FFFFFF',anchor='lm',stroke_width=2,stroke_fill='#102024')
                        if hot:dr.text((x+.5,y),span,font=fnt,fill=accent,anchor='lm',stroke_width=0)
                        x+=fnt.getlength(span)
                raw=im.tobytes();raster_hash.update(raw);frame_count+=1;enc.stdin.write(raw)
        finally:
            enc.stdin.close();container.close()
            for entry in media.values():
                if entry['kind']=='video':entry['container'].close()
        if enc.wait()!=0:raise RuntimeError('Encode failed')
    run('-i',out,'-f','null','-')
    report={'source_to_final':mapping,'duration':total,'input_hashes':{name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in [('source',src),('plan',a.plan),('captions',a.captions)]},'style_profile':profile or 'legacy','renderer_version':'1.3' if standard else 'legacy','raster_sha256':raster_hash.hexdigest(),'frame_count':frame_count,'font_sha256':hashlib.sha256(Path(a.font).read_bytes()).hexdigest(),'single_line_validation':True,'listening_review':'not_performed','normal_speed_playback_review':'not_performed','full_decode':'passed','auxiliary_audio':'muted','media_used':[{'scene_start':scenes[i]['start'],'scene_end':scenes[i]['end'],'asset':scenes[i]['asset'],'reason':scenes[i].get('reason',''),'asset_in':scenes[i].get('asset_in',0)} for i in media]}
    out.with_suffix('.review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
