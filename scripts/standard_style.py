"""Locked Wenfeng V4 glass composition. Content is configurable; visual tokens are not.

Input frames are the renderer's 512x902 conformed source. The caller converts a
public source-normalized presenter crop to ``_presenter_crop_base`` on a copy of
the scene. No media decoding, audio changes, random layout or network access.
"""
import math
import re
import unicodedata
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from visuals import circular_presenter, frosted_background

PROFILE = 'wenfeng-standard-v1'
W, H, FPS = 512, 902, 30
NAVY, INK, WHITE, CYAN, BLUE = '#0B1526', '#15263D', '#F7F9FC', '#58E5D0', '#2671D9'
TRANSITION_SECONDS = .24
TEMPLATES = ('opening', 'presenter', 'path', 'statement', 'amplifier', 'compare', 'list', 'media')
TOP_FIELDS = {'style_profile', 'standard_version', 'width', 'height', 'fps', 'cuts', 'scenes', 'presenter', 'duration', 'opening_title', 'paragraphs'}
COMMON_FIELDS = {'start', 'end', 'template', 'title', 'subtitle', 'show_presenter', 'presenter_position', 'presenter_size', 'presenter_space', 'presenter', 'reason'}
CONTENT_FIELDS = {
    'opening': set(),
    'presenter': set(),
    'path': {'nodes', 'takeaway'},
    'statement': {'before', 'after'},
    'amplifier': {'traits', 'center', 'metric', 'metric_note'},
    'compare': {'columns'},
    'list': {'items'},
    'media': {'asset', 'asset_in', 'asset_out', 'asset_crop', 'media_box', 'focus', 'asset_audio'},
}


def smooth(value):
    return 1 - (1 - max(0, min(1, value))) ** 3


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return value


def _crop(value, label):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f'{label} must be [left,top,right,bottom]')
    if not all(0 <= _number(v, label) <= 1 for v in value) or value[0] >= value[2] or value[1] >= value[3]:
        raise ValueError(f'{label} must be a positive normalized crop')


def opening_title_lines(opening, font):
    value=opening['text'];lines=opening.get('lines');highlights=opening.get('highlights',[])
    if any(not ch.isalnum() for ch in value):
        raise ValueError('Cover title must contain no punctuation, whitespace or symbols')
    if not isinstance(lines,list) or len(lines)!=2 or any(not isinstance(v,str) or not 1<=len(v)<=4 or font.getlength(v)>440 for v in lines) or ''.join(lines)!=value:
        raise ValueError('Cover title requires exactly two explicit lines, one to four characters per line')
    if not isinstance(highlights,list) or not 1<=len(highlights)<=3 or any(not isinstance(k,str) or not k or not any(k in line for line in lines) for k in highlights):
        raise ValueError('Cover keywords must occur within one line')
    return lines


def validate_presenter_geometry(config, source_size):
    """Check a manually inspected full-head envelope against the actual cover crop."""
    sw,sh=source_size;crop=config['crop'];head=config['head_box']
    l,t,r,b=[v*(sw if i%2==0 else sh) for i,v in enumerate(crop)]
    cx,cy=(l+r)/2,(t+b)/2;radius=min(r-l,b-t)*.45
    points=config.get('head_outline') or [[x,y] for x in (head[0],head[2]) for y in (head[1],head[3])]
    for nx,ny in points:
        if math.hypot(nx*sw-cx,ny*sh-cy)>radius:
            raise ValueError('Full hair/face head_box is clipped by the circle; widen or reposition source crop')


def validate_standard_plan(plan, cues, fontpath):
    """Validate the entire public fixed-style plan before opening the encoder."""
    if set(plan) - TOP_FIELDS:
        raise ValueError('Unsupported standard plan fields: ' + ', '.join(sorted(set(plan) - TOP_FIELDS)))
    if plan.get('style_profile') != PROFILE or plan.get('standard_version') != '1.6':
        raise ValueError('Use style_profile=wenfeng-standard-v1, standard_version=1.6')
    for key, value in [('width', W), ('height', H), ('fps', FPS)]:
        if plan.get(key, value) != value:
            raise ValueError(f'Standard mode locks {key}={value}')
    @lru_cache(16)
    def font(size):
        return ImageFont.truetype(str(fontpath), size)
    def text(value, size, limit, label, required=False):
        if not isinstance(value, str) or (required and not value.strip()) or any(ch in value for ch in ('\n', '\r', '\\N')):
            raise ValueError(f'{label} must be one nonempty line' if required else f'{label} must be one line')
        if font(size).getlength(value) > limit:
            raise ValueError(f'{label} is too wide for the fixed template; simplify the graphic text or split the speech with real timing')
    def timed(items, scene, size, limit, label, count):
        if not isinstance(items, list) or len(items) > count:
            raise ValueError(f'{label} requires at most {count} items')
        for item in items:
            if not isinstance(item, dict) or set(item) != {'at', 'text'}:
                raise ValueError(f'{label} items require exactly at,text')
            if not scene['start'] <= _number(item['at'], label) < scene['end']:
                raise ValueError(f'{label} item is outside scene')
            text(item['text'], size, limit, label, True)
    def presenter(config):
        if not isinstance(config, dict) or set(config) - {'crop', 'framing_confirmed', 'head_box', 'head_outline'}:
            raise ValueError('Standard presenter allows crop, head_box and framing_confirmed')
        if 'crop' in config:
            _crop(config['crop'], 'presenter.crop')
        if 'head_box' in config:
            _crop(config['head_box'], 'presenter.head_box')
        if 'head_outline' in config:
            points=config['head_outline']
            if not isinstance(points,list) or not 8<=len(points)<=64 or any(not isinstance(v,list) or len(v)!=2 or any(not 0<=_number(c,'head_outline')<=1 for c in v) for v in points):
                raise ValueError('head_outline requires 8 to 64 inspected normalized contour points')
            if 'head_box' not in config:raise ValueError('head_outline also needs its full-head bounding box')
            bounds=[min(v[0] for v in points),min(v[1] for v in points),max(v[0] for v in points),max(v[1] for v in points)]
            if any(abs(a-b)>.002 for a,b in zip(bounds,config['head_box'])):raise ValueError('head_outline must cover the complete head_box extrema')
        if 'framing_confirmed' in config and not isinstance(config['framing_confirmed'],bool):
            raise ValueError('framing_confirmed must be boolean after visual inspection')
    if not plan.get('cuts') or plan['cuts'][0].get('in')!=0:raise ValueError('Cover must use original source frame zero; first cut must start at zero')
    presenter(plan.get('presenter', {}))
    opening=plan.get('opening_title')
    if not isinstance(opening,dict) or set(opening)-{'text','approved','source','candidates','lines','highlights'} or opening.get('approved') is not True or opening.get('source') not in ('user','chosen'):
        raise ValueError('Confirm opening_title text before rendering: approved=true, source=user or chosen')
    title_value=opening.get('text')
    if not isinstance(title_value,str) or not title_value.strip() or '\n' in title_value or '\r' in title_value:
        raise ValueError('opening_title.text must be a nonempty title')
    opening_title_lines(opening, font(96))
    if opening.get('source')=='chosen':
        candidates=opening.get('candidates')
        if not isinstance(candidates,list) or len(candidates)!=3 or any(not isinstance(v,str) or not v.strip() for v in candidates) or title_value not in candidates:
            raise ValueError('Chosen opening title requires exactly three candidates and must match the chosen candidate')
    paragraphs=plan.get('paragraphs')
    if not isinstance(paragraphs,list) or not paragraphs:raise ValueError('Provide speech-aligned paragraphs with summaries')
    p_end=0
    for paragraph in paragraphs:
        if not isinstance(paragraph,dict) or set(paragraph)!={'start','end','summary'}:raise ValueError('Paragraphs require exactly start,end,summary')
        pa,pb=_number(paragraph['start'],'paragraph.start'),_number(paragraph['end'],'paragraph.end')
        if abs(pa-p_end)>1e-6 or pb<=pa:raise ValueError('Paragraphs must be contiguous from zero')
        text(paragraph['summary'],18,360,'paragraph summary',True);p_end=pb
    scenes = plan.get('scenes')
    if not isinstance(scenes, list) or not scenes:
        raise ValueError('Standard mode requires explicit contiguous scenes')
    if len(scenes)!=len(paragraphs):raise ValueError('Each speech paragraph requires its own scene')
    previous = 0
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict) or scene.get('template') not in TEMPLATES:
            raise ValueError('Unknown standard template')
        template = scene['template']
        if index==0 and template!='opening':raise ValueError('First scene must use opening: original full-frame video')
        if index and template=='opening':raise ValueError('Opening is only allowed as the first scene')
        if index and template==scenes[index-1]['template']:raise ValueError('Adjacent paragraphs must change display template')
        extra = set(scene) - COMMON_FIELDS - CONTENT_FIELDS[template]
        if extra:
            raise ValueError('Unsupported standard scene fields: ' + ', '.join(sorted(extra)))
        start, end = _number(scene.get('start'), 'start'), _number(scene.get('end'), 'end')
        if start < 0 or end <= start or abs(start - previous) > 1e-6:
            raise ValueError('Standard scenes must be contiguous, start at zero and have positive duration')
        if abs(start-paragraphs[index]['start'])>1e-6 or abs(end-paragraphs[index]['end'])>1e-6:raise ValueError('Each scene must match its speech paragraph timing')
        previous = end
        if template not in ('opening','presenter') and end-start>12:
            raise ValueError('Board scene exceeds 12 seconds; split at a meaningful speech boundary and change template')
        if index==0:
            if scene.get('title')!=title_value:raise ValueError('First scene title must match the approved opening title')
            opening_title_lines(opening, font(96))
        else:text(scene.get('title', ''),38,440,'title')
        text(scene.get('subtitle', ''), 19, 440, 'subtitle')
        presenter(scene.get('presenter', {}))
        if not isinstance(scene.get('show_presenter', True), bool):
            raise ValueError('show_presenter must be boolean')
        position=scene.get('presenter_position','bottom_center')
        if position not in ('bottom_center','bottom_left','bottom_right','top'):
            raise ValueError('Use bottom_center or top for circle position')
        size=scene.get('presenter_size',184)
        if isinstance(size,bool) or not isinstance(size,int) or not 120<=size<=220:
            raise ValueError('presenter_size must be an integer from 120 to 220px')
        if position=='top':
            space=scene.get('presenter_space')
            if not isinstance(space,list) or len(space)!=4:
                raise ValueError('Top circle requires an inspected empty presenter_space [x,y,width,height]')
            x,y,w,h=[_number(v,'presenter_space') for v in space]
            if min(x,y,w,h)<0 or x+w>1 or y<.27 or y+h>.68 or min(w*W,h*H)<120:
                raise ValueError('Top empty space must fit a 120px circle inside the upper content safe area')
        if template in ('path','amplifier','compare','list','media') and scene.get('show_presenter',True):
            config=scene.get('presenter',plan.get('presenter',{}))
            if config.get('framing_confirmed') is not True or 'crop' not in config or 'head_box' not in config:
                raise ValueError('Circle needs an explicitly inspected crop with full hair and complete face, framing_confirmed=true')
        if template == 'path':
            if len(scene.get('nodes', [])) != 2:
                raise ValueError('Path requires exactly two timed nodes')
            timed(scene['nodes'], scene, 31, 170, 'nodes', 2)
            text(scene.get('takeaway', ''), 26, 236, 'takeaway')
        elif template == 'statement':
            text(scene.get('before', ''), 44, 420, 'before', True)
            text(scene.get('after', ''), 68, 440, 'after', True)
        elif template == 'amplifier':
            if scene.get('metric') and scene.get('traits'):
                raise ValueError('Use traits or metric in one amplifier scene; split to show both')
            if scene.get('metric'):
                text(scene['metric'], 96, 440, 'metric', True)
                text(scene.get('metric_note', ''), 14, 420, 'metric_note')
            else:
                if not scene.get('traits'):
                    raise ValueError('Amplifier requires traits or metric')
                timed(scene['traits'], scene, 30, 148, 'traits', 3)
                text(scene.get('center', '个人IP'), 29, 128, 'center', True)
        elif template == 'compare':
            columns = scene.get('columns')
            if not isinstance(columns, list) or len(columns) != 2:
                raise ValueError('Compare requires exactly two columns')
            for col in columns:
                if not isinstance(col, dict) or set(col) != {'title', 'items'}:
                    raise ValueError('Columns require title,items')
                text(col['title'], 28, 190, 'column title', True)
                timed(col['items'], scene, 25, 190, 'column items', 3)
        elif template == 'list':
            if not scene.get('items'):
                raise ValueError('List requires one to three items')
            timed(scene['items'], scene, 34, 340, 'items', 3)
        elif template == 'media':
            text(scene.get('asset', ''), 1, 100000, 'asset', True)
            if scene.get('asset_audio', 'mute') != 'mute':
                raise ValueError('Standard mode auxiliary audio is muted')
            for key in ('asset_in', 'asset_out'):
                if key in scene and _number(scene[key], key) < 0:
                    raise ValueError('Media source times must be nonnegative')
            if 'asset_crop' in scene:
                _crop(scene['asset_crop'], 'asset_crop')
            box = scene.get('media_box', [.06, .28, .88, .58])
            if not isinstance(box, list) or len(box) != 4 or not all(0 <= _number(v, 'media_box') <= 1 for v in box):
                raise ValueError('media_box requires normalized x,y,width,height')
            x, y, width, height = box
            if width <= 0 or height <= 0 or x + width > 1 or y + height > .89 or y < .27:
                raise ValueError('Keep media inside title and caption safe regions: y>=.27, bottom<=.89')
            for mark in scene.get('focus', []):
                if not isinstance(mark, dict) or set(mark) != {'at', 'box'}:
                    raise ValueError('Focus marks require exactly at,box')
                if not start <= _number(mark['at'], 'focus.at') < end:
                    raise ValueError('Focus timing outside scene')
                _crop(mark['box'], 'focus.box')
    if 'duration' in plan and abs(_number(plan['duration'], 'duration') - previous) > .001:
        raise ValueError('Duration differs from final scene end')
    previous_caption = 0
    for cue in cues:
        if set(cue) - {'start', 'end', 'text', 'highlights'}:
            raise ValueError('Unsupported caption fields')
        start, end = _number(cue.get('start'), 'caption.start'), _number(cue.get('end'), 'caption.end')
        if start < previous_caption - 1e-6 or end <= start or start < 0 or end > previous + .001:
            raise ValueError('Captions must be ordered, non-overlapping and inside the edit')
        previous_caption = end
        text(cue.get('text'), 26, 448, 'caption', True)
        keys = cue.get('highlights', [])
        if not isinstance(keys, list) or len(keys) > 2 or len(set(keys)) != len(keys):
            raise ValueError('Use zero to two distinct highlight terms')
        for key in keys:
            if not isinstance(key, str) or not key or key not in cue['text']:
                raise ValueError('Highlight must occur in its actual caption')
    return {'style_profile': PROFILE, 'duration': previous, 'scenes': len(scenes), 'captions': len(cues)}


class StandardStyle:
    """Render one fixed-style frame. Validate public input before instantiation."""
    def __init__(self, plan, cues, fontpath):
        self.plan, self.cues, self.fontpath = plan, cues, str(fontpath)
        self.backgrounds = {False: frosted_background(W, H), True: frosted_background(W, H, True)}
        self.duration = plan['scenes'][-1]['end']

    @lru_cache(24)
    def font(self, size):
        return ImageFont.truetype(self.fontpath, size)

    def text(self, draw, xy, value, size=25, color=WHITE, anchor='mm'):
        draw.text(xy, str(value), font=self.font(size), fill=color, anchor=anchor)

    def panel(self, im, box, fill, radius=18):
        ImageDraw.Draw(im).rounded_rectangle(box, radius=radius, fill=fill)

    def arrow(self, draw, a, b, progress, color):
        p = smooth(progress)
        if p <= 0:
            return
        x, y = a; endx = x + (b[0] - x) * p; endy = y + (b[1] - y) * p
        draw.line((x, y, endx, endy), fill=color, width=3)
        if p > .95:
            angle = math.atan2(endy-y, endx-x)
            draw.polygon([(endx, endy), (endx-9*math.cos(angle-.5), endy-9*math.sin(angle-.5)), (endx-9*math.cos(angle+.5), endy-9*math.sin(angle+.5))], fill=color)

    def circle(self, im, frame, scene):
        if scene.get('show_presenter', True):
            size=scene.get('presenter_size',184)
            if scene.get('presenter_position')=='top':
                sx,sy,sw,sh=scene['presenter_space']
                size=min(size,int(sw*W),int(sh*H))
                x=round((sx+sw/2)*W-size/2);y=round((sy+sh/2)*H-size/2)
            else:
                x=(W-size)//2;y=790-size
            crop = scene.get('_presenter_crop_base')
            if crop is None:
                crop = self.plan.get('_presenter_crop_base')
            circular_presenter(im, frame, (x, y, size), crop, preserve_all=True)

    def _caption(self, im, t):
        cue = next((c for c in self.cues if c['start'] <= t < c['end']), None)
        if cue is None:
            return im
        value, keys = cue['text'], cue.get('highlights', [])
        width = self.font(26).getlength(value); x = (W-width)/2; y = 837
        layer = Image.new('RGBA', (W,H)); draw = ImageDraw.Draw(layer)
        draw.rounded_rectangle((x-14,y-25,x+width+14,y+25), radius=12, fill=(7,18,32,240))
        pattern = '(' + '|'.join(re.escape(k) for k in sorted(keys, key=len, reverse=True)) + ')' if keys else None
        for span in re.split(pattern, value) if pattern else [value]:
            if not span:
                continue
            hot = span in keys
            self.text(draw, (x,y), span,26,CYAN if hot else WHITE,'lm')
            if hot:
                self.text(draw, (x+.45,y), span,26,CYAN,'lm')
            x += self.font(26).getlength(span)
        return Image.alpha_composite(im,layer)

    def art_title(self, im, value):
        opening=self.plan['opening_title'];font=self.font(96)
        lines=opening_title_lines(opening,font)
        shadow=Image.new('RGBA',(W,H));sd=ImageDraw.Draw(shadow)
        foreground=Image.new('RGBA',(W,H));d=ImageDraw.Draw(foreground)
        keywords=sorted(opening['highlights'],key=len,reverse=True)
        for j,line in enumerate(lines):
            bbox=font.getbbox(line,anchor='lm')
            yy=H/2+(j-.5)*112-(bbox[1]+bbox[3])/2
            x=256-font.getlength(line)/2
            sd.text((x+3,yy+5),line,font=font,anchor='lm',fill=(0,0,0,220),stroke_width=4)
            spans=re.split('('+'|'.join(re.escape(k) for k in keywords)+')',line)
            for span in spans:
                if not span:continue
                color='#FFE36D' if span in keywords else '#F7FFFD'
                d.text((x,yy),span,font=font,anchor='lm',fill=color,stroke_width=5,stroke_fill='#061421')
                d.text((x+.7,yy),span,font=font,anchor='lm',fill=color,stroke_width=1,stroke_fill=color)
                x+=font.getlength(span)
        im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3)))
        im.alpha_composite(foreground)

    def _board_motion(self, im, scene, t, accent):
        u=t-scene['start'];beat=int(u/2.4);phase=(u%2.4)/.65
        template=scene['template'];boxes=[]
        if template=='path':
            boxes=[(38+j*246,300,228+j*246,420) for j,v in enumerate(scene['nodes']) if t>=v['at']]
        elif template=='amplifier':
            if scene.get('metric'):boxes=[(40,275,472,420)]
            else:boxes=[(40,254+j*102,205,326+j*102) for j,v in enumerate(scene['traits']) if t>=v['at']]+[(330,348,474,437)]
        elif template=='list':boxes=[(38,345+j*89,474,414+j*89) for j,v in enumerate(scene['items']) if t>=v['at']]
        elif template=='compare':
            boxes=[(28+j*240,330+k*74,244+j*240,394+k*74) for j,col in enumerate(scene['columns']) for k,v in enumerate(col['items']) if t>=v['at']]
        elif template=='statement':boxes=[(40,435,472,540)]
        elif template=='media':
            marks=[v for v in scene.get('focus',[]) if t>=v['at']]
            x,y,w,h=scene.get('media_box',[.06,.28,.88,.58]);boxes=[(x*W,y*H,(x+w)*W,(y+h)*H)]
            if marks:
                # Existing focus stays semantically authoritative; animate its enclosing frame.
                box=marks[beat%len(marks)]['box'];a,b,c,e=box
                boxes=[((x+a*w)*W,(y+b*h)*H,(x+c*w)*W,(y+e*h)*H)]
        if not boxes:return
        left,top,right,bottom=boxes[beat%len(boxes)]
        # One brief content-directed emphasis per beat; no perimeter tracing.
        # Rotate motion language by graphic type rather than drawing loops.
        if phase>=1.35:return
        wave=math.sin(math.pi*min(1,phase/1.35))
        left,top,right,bottom=map(round,(left,top,right,bottom))
        region=im.crop((left,top,right,bottom))
        if template=='media':
            zoom=1+.045*wave
            pic=region.resize((round(region.width*zoom),round(region.height*zoom)),Image.Resampling.LANCZOS)
            ox=(pic.width-region.width)//2;oy=(pic.height-region.height)//2
            im.paste(pic.crop((ox,oy,ox+region.width,oy+region.height)),(left,top))
        elif template=='list':
            # Soft fill briefly selects the spoken checklist row; no border.
            layer=Image.new('RGBA',(W,H));d=ImageDraw.Draw(layer)
            rgb=tuple(bytes.fromhex(accent[1:]));d.rounded_rectangle((left,top,right,bottom),radius=18,fill=(*rgb,round(42*wave)))
            im.alpha_composite(layer)
            zoom=1+.025*wave
            pic=im.crop((left,top,right,bottom)).resize((round((right-left)*zoom),round((bottom-top)*zoom)),Image.Resampling.LANCZOS)
            im.paste(pic,(round((left+right-pic.width)/2),round((top+bottom-pic.height)/2)))
        else:
            # Node cards lift gently; a conclusion gets a brief word-size emphasis.
            zoom=1+(.055 if template=='statement' else .045)*wave
            pic=region.resize((round(region.width*zoom),round(region.height*zoom)),Image.Resampling.LANCZOS)
            lift=round((5 if template in ('path','amplifier','compare') else 0)*wave)
            im.paste(pic,(round((left+right-pic.width)/2),round((top+bottom-pic.height)/2)-lift))
        if template in ('path','amplifier'):
            connections=[]
            if template=='path' and all(t>=v['at'] for v in scene['nodes']):connections=[((235,360),(275,360))]
            if template=='amplifier' and scene.get('traits'):
                connections=[((215,290+j*102),(326,392)) for j,v in enumerate(scene['traits']) if t>=v['at']]
            if connections:
                start,end=connections[beat%len(connections)];q=min(1,phase/1.35)
                vx,vy=end[0]-start[0],end[1]-start[1];length=math.hypot(vx,vy)
                px,py=start[0]+vx*q,start[1]+vy*q
                tail=max(0,q-.23);d=ImageDraw.Draw(im)
                d.line((start[0]+vx*tail,start[1]+vy*tail,px,py),fill=accent,width=6)
                dx,dy=vx/length,vy/length
                d.polygon([(px+4*dx,py+4*dy),(px-7*dx+4*dy,py-7*dy-4*dx),(px-7*dx-4*dy,py-7*dy+4*dx)],fill=accent)

    def render(self, original_frame, t, scene_index, scene, *, media_image=None):
        if original_frame.size != (W,H):
            raise ValueError('StandardStyle requires a conformed 512x902 frame')
        template = scene['template']; u = max(0,t-scene['start']); p = smooth(u/.42)
        light = template in ('statement','compare','media') or (template == 'path' and scene_index % 2 == 1)
        im = original_frame.convert('RGBA') if template=='opening' else self.backgrounds[light].copy().convert('RGBA'); d=ImageDraw.Draw(im)
        ink, accent, muted = (INK,BLUE,'#758599') if light else (WHITE,CYAN,'#8FA7BC')
        summary=self.plan['paragraphs'][scene_index]['summary']
        title=scene.get('title','');subtitle=scene.get('subtitle','')
        if template=='opening' and t>=.5/FPS:
            # Only encoded frame zero is the cover. Never hold its title during playback.
            return self._caption(original_frame.convert('RGBA'),t).convert('RGB')
        if template=='opening':
            # Keep the original first frame intact beneath the header/title overlays.
            veil=Image.new('RGBA',(W,H));vd=ImageDraw.Draw(veil)
            for yy in range(H):vd.line((0,yy,W,yy),fill=(6,17,29,round(65*max(0,1-abs(yy-H/2)/220))))
            im=Image.alpha_composite(im,veil);d=ImageDraw.Draw(im)
            self.art_title(im,title)
        else:
            d.line((32,103,480,103),fill='#CED9E5' if light else '#294052',width=1)
            self.text(d,(32,63),summary,18,muted,'lm')
            self.text(d,(256,157+round(12*(1-p))),title,38,accent)
            if subtitle:self.text(d,(256,215),subtitle,19,ink)
        if template=='presenter':
            # Aspect-preserving original source, no artificial subject enlargement.
            thumb=original_frame.resize((324,571),Image.Resampling.LANCZOS)
            mask=Image.new('L',(324,571));ImageDraw.Draw(mask).rounded_rectangle((0,0,323,570),radius=22,fill=255)
            im.paste(thumb,(94,256),mask)
        elif template=='path':
            nodes=scene['nodes']
            for j,node in enumerate(nodes):
                if t < node['at']:
                    continue
                x=38+j*246;dy=round(14*(1-smooth((t-node['at'])/.28)))
                self.panel(im,(x,300+dy,x+190,420+dy),'#FFFFFF' if light else '#19364A',20);d=ImageDraw.Draw(im)
                self.text(d,(x+95,360+dy),node['text'],31,accent if j else ink)
            if t>=max(v['at'] for v in nodes):
                self.arrow(d,(235,360),(275,360),(t-max(v['at'] for v in nodes))/.3,accent)
            if scene.get('takeaway'):
                self.text(d,(38,510),scene['takeaway'],26,ink,'lm')
            self.circle(im,original_frame,scene)
        elif template=='statement':
            self.text(d,(256,291),scene['before'],44,'#95A1B0')
            width=self.font(44).getlength(scene['before']);d.line((256-width/2,291,256+width/2,291),fill='#B8C3CF',width=2)
            self.arrow(d,(256,348),(256,409),u/.42,BLUE)
            self.text(d,(256,488+round(18*(1-p))),scene['after'],68,BLUE)
        elif template=='amplifier':
            if scene.get('metric'):
                self.text(d,(256,345),scene['metric'],96,accent)
                if scene.get('metric_note'):
                    self.text(d,(256,526),scene['metric_note'],14,muted)
            else:
                for j,item in enumerate(scene['traits']):
                    if t<item['at']:
                        continue
                    yy=254+j*102;self.panel(im,(40,yy,205,yy+72),'#173247');d=ImageDraw.Draw(im)
                    self.text(d,(122,yy+36),item['text'],30,ink)
                    self.arrow(d,(215,yy+36),(326,392),(t-item['at'])/.42,accent)
                self.panel(im,(330,348,474,437),'#1D4A51');d=ImageDraw.Draw(im)
                self.text(d,(402,392),scene.get('center','个人IP'),29,accent)
            self.circle(im,original_frame,scene)
        elif template=='list':
            for j,item in enumerate(scene['items']):
                if t<item['at']:
                    continue
                dy=round(18*(1-smooth((t-item['at'])/.3)));y=345+j*89
                self.panel(im,(38+dy,y,474,y+69),'#173247');d=ImageDraw.Draw(im)
                self.text(d,(69+dy,y+34),f'0{j+1}',16,muted)
                self.text(d,(277+dy,y+34),item['text'],34,accent)
            self.circle(im,original_frame,scene)
        elif template=='compare':
            for j,col in enumerate(scene['columns']):
                x=28+j*240;self.panel(im,(x,270,x+216,575),'#FFFFFF' if j==0 else '#DBECFF');d=ImageDraw.Draw(im)
                self.text(d,(x+108,307),col['title'],28,INK if j==0 else BLUE)
                for k,item in enumerate(col['items']):
                    if t>=item['at']:
                        dy=round(9*(1-smooth((t-item['at'])/.25)))
                        self.text(d,(x+108,362+k*74+dy),item['text'],25,INK if j==0 else BLUE)
            self.circle(im,original_frame,scene)
        elif template=='media':
            if media_image is None:
                raise ValueError('Media template requires decoded media_image from the caller')
            pic=media_image.convert('RGB');crop=scene.get('asset_crop')
            if crop:
                pic=pic.crop(tuple(round(v*(pic.width if i%2==0 else pic.height)) for i,v in enumerate(crop)))
            x,y,w,h=scene.get('media_box',[.06,.28,.88,.58]);x,y,w,h=round(x*W),round(y*H),round(w*W),round(h*H)
            scale=min(w/pic.width,h/pic.height);pic=pic.resize((max(1,round(pic.width*scale)),max(1,round(pic.height*scale))),Image.Resampling.LANCZOS)
            px,py=x+(w-pic.width)//2,y+(h-pic.height)//2;im.paste(pic,(px,py));d=ImageDraw.Draw(im)
            for mark in scene.get('focus',[]):
                if t>=mark['at']:
                    a,b,c,e=mark['box'];d.rectangle((px+a*pic.width,py+b*pic.height,px+c*pic.width,py+e*pic.height),outline=accent,width=3)
            self.circle(im,original_frame,scene)
        if template not in ('opening','presenter'):self._board_motion(im,scene,t,accent)
        if scene_index and u<TRANSITION_SECONDS:
            q=u/TRANSITION_SECONDS;layer=Image.new('RGBA',(W,H));ld=ImageDraw.Draw(layer)
            if scene_index%3==0:
                x=round(W*q);ld.rectangle((x,0,W,H),fill=(88,229,208,round(110*(1-q))))
            elif scene_index%3==1:
                y=round(H*q);ld.rectangle((0,y,W,min(H,y+140)),fill=(38,113,217,round(145*(1-q))))
            else:
                ld.rectangle((0,0,W,H),fill=(240,248,255,round(65*(1-q))))
            im=Image.alpha_composite(im,layer)
        # Caption is last so transitions never interrupt a speech cue.
        if template!='opening':im=self._caption(im,t)
        if template=='opening':return im.convert('RGB')
        d=ImageDraw.Draw(im);d.rectangle((32,871,480,873),fill='#344B5A');d.rectangle((32,871,32+448*min(1,max(0,t/self.duration)),873),fill=accent)
        return im.convert('RGB')
