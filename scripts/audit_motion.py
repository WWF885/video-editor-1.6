"""Sample board content at 5fps, excluding captions, progress and presenter circles."""
import subprocess
import numpy as np

def audit_motion(video,plan):
    command=['ffmpeg','-nostdin','-v','error','-i',str(video),'-vf','fps=5,scale=256:451','-pix_fmt','gray','-f','rawvideo','-']
    process=subprocess.Popen(command,stdout=subprocess.PIPE);previous=None;last_scene=None;last_change=0;max_gap=0;index=0;rows=[];board=False;scene_start=0
    try:
        while True:
            data=process.stdout.read(256*451)
            if not data:break
            if len(data)!=256*451:raise ValueError('Truncated motion audit decode')
            t=index/5;index+=1;scene_index=next((i for i,s in enumerate(plan['scenes']) if s['start']<=t<s['end']),None)
            if scene_index!=last_scene:
                if board:rows.append({'scene':last_scene,'max_static_seconds':round(max(max_gap,t-last_change),2)})
                previous=None;last_change=t;max_gap=0;last_scene=scene_index
            if scene_index is None:board=False;continue
            scene=plan['scenes'][scene_index];board=scene['template'] not in ('opening','presenter')
            if not board:previous=None;continue
            frame=np.frombuffer(data,np.uint8).reshape(451,256).astype(np.int16)
            # Analyze actual knowledge content; summary/title/captions/rail do not count.
            mask=np.zeros((451,256),bool);mask[121:297 if scene.get('show_presenter',False) else 395,12:244]=True
            if scene['template'] in ('path','amplifier','list','compare','media') and scene.get('show_presenter',False):
                size=scene.get('presenter_size',184)
                if scene.get('presenter_position')=='top':
                    x,y,w,h=scene['presenter_space'];size=min(size,int(w*512),int(h*902));cx=(x+w/2)*256;cy=(y+h/2)*451
                else:cx=128;cy=(790-size/2)/2
                yy,xx=np.ogrid[:451,:256];mask[(xx-cx)**2+(yy-cy)**2<((size/2+14)/2)**2]=False
            if previous is not None:
                changed=(np.abs(frame-previous)>12)&mask
                if changed.sum()>=max(12,mask.sum()*.001):
                    max_gap=max(max_gap,t-last_change);last_change=t
            previous=frame
        if board:
            end=min(plan['scenes'][last_scene]['end'],index/5);rows.append({'scene':last_scene,'max_static_seconds':round(max(max_gap,end-last_change),2)})
    finally:
        process.stdout.close()
    if process.wait()!=0:raise ValueError('Motion audit decode failed')
    failures=[r for r in rows if r['max_static_seconds']>3.0]
    return {'status':'failed' if failures else 'passed','sample_fps':5,'threshold_note':'Content pixel-change screening; requires visual review to confirm meaningful motion','scenes':rows,'failures':failures}
