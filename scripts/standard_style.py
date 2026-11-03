"""Locked Wenfeng V4 glass composition. Content is configurable; visual tokens are not.

Input frames are the renderer's 512x902 conformed source. The caller converts a
public source-normalized presenter crop to ``_presenter_crop_base`` on a copy of
the scene. No media decoding, audio changes, random layout or network access.
"""
import math
import re
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from visuals import circular_presenter, frosted_background

PROFILE = 'wenfeng-standard-v1'
W, H, FPS = 512, 902, 30
NAVY, INK, WHITE, CYAN, BLUE = '#0B1526', '#15263D', '#F7F9FC', '#58E5D0', '#2671D9'
TRANSITION_SECONDS = .24
TEMPLATES = ('opening', 'presenter', 'path', 'statement', 'amplifier', 'compare', 'list', 'media')
TOP_FIELDS = {'style_profile', 'standard_version', 'width', 'height', 'fps', 'cuts', 'scenes', 'presenter', 'duration', 'opening_title', 'paragraphs'}
COMMON_FIELDS = {'start', 'end', 'template', 'title', 'subtitle', 'show_presenter', 'presenter_position', 'presenter', 'reason'}
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


def validate_standard_plan(plan, cues, fontpath):
    """Validate the entire public fixed-style plan before opening the encoder."""
    if set(plan) - TOP_FIELDS:
        raise ValueError('Unsupported standard plan fields: ' + ', '.join(sorted(set(plan) - TOP_FIELDS)))
    if plan.get('style_profile') != PROFILE or plan.get('standard_version') != '1.1':
        raise ValueError('Use style_profile=wenfeng-standard-v1, standard_version=1.1')
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
        if not isinstance(config, dict) or set(config) - {'crop', 'framing_confirmed'}:
            raise ValueError('Standard presenter allows only crop and framing_confirmed')
        if 'crop' in config:
            _crop(config['crop'], 'presenter.crop')
        if 'framing_confirmed' in config and not isinstance(config['framing_confirmed'],bool):
            raise ValueError('framing_confirmed must be boolean after visual inspection')
    presenter(plan.get('presenter', {}))
    opening=plan.get('opening_title')
    if not isinstance(opening,dict) or set(opening)-{'text','approved','source','candidates'} or opening.get('approved') is not True or opening.get('source') not in ('user','chosen'):
        raise ValueError('Confirm opening_title text before rendering: approved=true, source=user or chosen')
    title_value=opening.get('text')
    if not isinstance(title_value,str) or not title_value.strip() or '\n' in title_value or '\r' in title_value:
        raise ValueError('opening_title.text must be a nonempty title')
    def art_lines(value):
        lines=[];line=''
        for ch in value:
            if font(38).getlength(line+ch)>440 and line:lines.append(line);line=''
            line+=ch
        if line:lines.append(line)
        if len(lines)>2:raise ValueError('Opening art title needs at most two lines at fixed font size; shorten title')
        return lines
    art_lines(title_value)
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
        if index==0:
            if scene.get('title')!=title_value:raise ValueError('First scene title must match the approved opening title')
            art_lines(scene['title'])
        else:text(scene.get('title', ''),38,440,'title')
        text(scene.get('subtitle', ''), 19, 440, 'subtitle')
        presenter(scene.get('presenter', {}))
        if not isinstance(scene.get('show_presenter', True), bool):
            raise ValueError('show_presenter must be boolean')
        if scene.get('presenter_position', 'bottom_right') not in ('bottom_left', 'bottom_right'):
            raise ValueError('Circle position is bottom_left or bottom_right')
        if template in ('path','amplifier','compare','list','media') and scene.get('show_presenter',True):
            config=scene.get('presenter',plan.get('presenter',{}))
            if config.get('framing_confirmed') is not True or 'crop' not in config:
                raise ValueError('Circle needs an explicitly inspected crop with full hair and both shoulders, framing_confirmed=true')
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
            x = 40 if scene.get('presenter_position') == 'bottom_left' else 288
            crop = scene.get('_presenter_crop_base')
            if crop is None:
                crop = self.plan.get('_presenter_crop_base')
            circular_presenter(im, frame, (x, 606, 184), crop, preserve_all=True)

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
        lines=[];line=''
        for ch in value:
            if self.font(38).getlength(line+ch)>440 and line:lines.append(line);line=''
            line+=ch
        if line:lines.append(line)
        mask=Image.new('L',(W,H));md=ImageDraw.Draw(mask)
        shadow=Image.new('RGBA',(W,H));sd=ImageDraw.Draw(shadow)
        outline=Image.new('RGBA',(W,H));od=ImageDraw.Draw(outline)
        for j,line in enumerate(lines):
            yy=104+j*53
            sd.text((259,yy+4),line,font=self.font(38),fill=(0,0,0,220),anchor='mm',stroke_width=3)
            od.text((256,yy),line,font=self.font(38),fill=(0,0,0,0),anchor='mm',stroke_width=3,stroke_fill=(6,20,33,255))
            md.text((256,yy),line,font=self.font(38),fill=255,anchor='mm')
            md.text((256.6,yy),line,font=self.font(38),fill=255,anchor='mm')
        im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3)))
        im.alpha_composite(outline)
        gradient=Image.new('RGBA',(W,H));gd=ImageDraw.Draw(gradient)
        for yy in range(H):
            q=max(0,min(1,(yy-77)/100));color=tuple(round(a*(1-q)+b*q) for a,b in zip((247,255,253),(88,229,208)))
            gd.line((0,yy,W,yy),fill=(*color,255))
        gradient.putalpha(mask);im.alpha_composite(gradient)

    def render(self, original_frame, t, scene_index, scene, *, media_image=None):
        if original_frame.size != (W,H):
            raise ValueError('StandardStyle requires a conformed 512x902 frame')
        template = scene['template']; u = max(0,t-scene['start']); p = smooth(u/.42)
        light = template in ('statement','compare','media') or (template == 'path' and scene_index % 2 == 1)
        im = original_frame.convert('RGBA') if template=='opening' else self.backgrounds[light].copy().convert('RGBA'); d=ImageDraw.Draw(im)
        ink, accent, muted = (INK,BLUE,'#758599') if light else (WHITE,CYAN,'#8FA7BC')
        summary=self.plan['paragraphs'][scene_index]['summary']
        title=scene.get('title','');subtitle=scene.get('subtitle','')
        if template=='opening':
            # Keep the original first frame intact beneath the header/title overlays.
            veil=Image.new('RGBA',(W,H));vd=ImageDraw.Draw(veil)
            for yy in range(224):vd.line((0,yy,W,yy),fill=(6,17,29,round(185*(1-yy/224))))
            im=Image.alpha_composite(im,veil);d=ImageDraw.Draw(im)
            sw=self.font(18).getlength(summary);d.rounded_rectangle((24,20,42+sw,57),radius=12,fill=(10,27,42,180))
            self.text(d,(33,38),summary,18,WHITE,'lm')
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
        im=self._caption(im,t)
        d=ImageDraw.Draw(im);d.rectangle((32,871,480,873),fill='#344B5A');d.rectangle((32,871,32+448*min(1,max(0,t/self.duration)),873),fill=accent)
        return im.convert('RGB')
