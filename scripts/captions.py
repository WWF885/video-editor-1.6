"""Build measured, strictly single-line subtitles from genuinely timed words."""
import argparse,json,re
from pathlib import Path
from PIL import ImageFont

def validate(cues,font,width):
    last=0
    for i,c in enumerate(cues):
        t=c['text']
        if not t or any(x in t for x in ('\n','\r','\\N','\\n','{','}','\\')):raise ValueError(f'cue {i}: invalid text or line break')
        if not 0<=c['start']<c['end'] or c['start']<last-1e-6:raise ValueError(f'cue {i}: invalid/overlapping timing')
        if round(c['end']*100)<=round(c['start']*100):raise ValueError(f'cue {i}: zero ASS duration after quantization')
        if font.getlength(t)>width:raise ValueError(f'cue {i}: too wide; obtain finer real alignment')
        # Highlight is bold: measure actual heavier font when supplied; reserve 8% otherwise.
        if font.getlength(t)*1.08>width:raise ValueError(f'cue {i}: insufficient emphasis margin')
        last=c['end']

def build(segments,font,width,keywords):
    cues=[]
    def add(a,b,t):
        t=t.strip(' ，,。.!！?？;；:：')
        if not t:return
        matches=[k for k in keywords if k and k in t]
        matches+=re.findall(r'\d+(?:\.\d+)?(?:%|％|倍|元|万|亿|秒|分钟|小时|年)?',t)
        cues.append(dict(start=float(a),end=float(b),text=t,highlights=list(dict.fromkeys(matches))[:2]))
    for s in segments:
        if any(x in s['text'] for x in ('\n','\r','\\N','\\n')):raise ValueError('Input subtitle contains a line break; normalize transcript before alignment')
        t=s['text'].strip()
        prev=float(s['start'])
        for w in s.get('words',[]):
            a,b=float(w['start']),float(w['end'])
            if not s['start']-1e-7<=a<b<=s['end']+1e-7 or a<prev-1e-7:raise ValueError('Invalid word alignment')
            prev=b
        if font.getlength(t)*1.08<=width and not any(x in t for x in ('\n','\r')):
            add(s['start'],s['end'],t);continue
        words=s.get('words')
        if not words:raise ValueError('Long sentence has no real word timestamps; alignment required')
        # Never substitute an approved script for differently recognized speech silently.
        canonical=lambda x:re.sub(r'[\s，,。.!！?？;；:：]','',x)
        if canonical(''.join(w.get('word',w.get('text','')) for w in words))!=canonical(t):
            raise ValueError('Sentence and timed words disagree; realign corrected text')
        merged=[]
        for w in words:
            w=dict(w);piece=w.get('word',w.get('text',''))
            prior=merged[-1].get('word',merged[-1].get('text','')) if merged else ''
            join=bool(merged) and (bool(re.search(r'\d(?:\.\d+)?$',prior) and re.fullmatch(r'(?:%|％|倍|元|万|亿|秒|分钟|小时|年)',piece.strip())) or prior.strip() in ('不','未','非','无','没'))
            if join:
                merged[-1]['word']=prior+piece;merged[-1]['end']=w['end']
            else:merged.append(w)
        words=merged
        buf='';start=end=None;prev=float(s['start'])
        for w in words:
            piece=w.get('word',w.get('text',''));a,b=float(w['start']),float(w['end'])
            if not s['start']-1e-7<=a<b<=s['end']+1e-7 or a<prev-1e-7:raise ValueError('Invalid word alignment')
            prev=b
            if font.getlength(piece)*1.08>width:raise ValueError('An aligned word is too wide; finer alignment required')
            if buf and font.getlength(buf+piece)*1.08>width:
                add(start,end,buf);buf='';start=None
            if start is None:start=a
            buf+=piece;end=b
            if re.search(r'[，,。.!！?？;；]$',piece) and len(buf)>=5:
                add(start,end,buf);buf='';start=None
        if buf:add(start,end,buf)
    validate(cues,font,width)
    return cues

def stamp(t,ass=False):
    n=round(t*(100 if ass else 1000));scale=100 if ass else 1000
    return f'{n//(3600*scale):02d}:{n//(60*scale)%60:02d}:{n//scale%60:02d}'+('.'+f'{n%100:02d}' if ass else ','+f'{n%1000:03d}')

def main():
    p=argparse.ArgumentParser();p.add_argument('--transcript',required=True);p.add_argument('--font',required=True);p.add_argument('--width',type=int,default=512);p.add_argument('--height',type=int,default=902);p.add_argument('--keywords',default='');p.add_argument('--out',required=True);a=p.parse_args()
    size=round(a.width*.048);f=ImageFont.truetype(a.font,size);cs=build(json.load(open(a.transcript)),f,a.width*.74,a.keywords.split(','));out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.with_suffix('.json').write_text(json.dumps(cs,ensure_ascii=False,indent=2))
    out.with_suffix('.srt').write_text(''.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}\n\n' for i,c in enumerate(cs)))
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {a.width}
PlayResY: {a.height}
WrapStyle: 2
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{f.getname()[0]},{size},&H00FFFFFF,&H00FFFFFF,&H00201810,&H00000000,0,0,0,0,100,100,0,0,1,2,0,5,0,0,0,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    events=[]
    for c in cs:
        t=c['text'];keys=c['highlights'];rx=re.compile('|'.join(re.escape(k) for k in sorted(keys,key=len,reverse=True))) if keys else None
        if rx:t=rx.sub(lambda m:'{\\c&H00C4E145&\\b1}'+m.group()+'{\\c&H00FFFFFF&\\b0}',t)
        events.append(f'Dialogue: 0,{stamp(c["start"],True)},{stamp(c["end"],True)},Default,,0,0,0,,{{\\q2\\pos({a.width//2},{round(a.height*.71)})}}{t}\n')
    out.with_suffix('.ass').write_text(header+''.join(events));print(json.dumps({'cues':len(cs),'single_line':True}))
if __name__=='__main__':main()
