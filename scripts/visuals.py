"""Reusable frosted background and source-video circular presenter."""
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import numpy as np
import math

def frosted_background(width, height, light=False):
    im=Image.new('RGBA',(width,height),'#DFEAF2' if light else '#102536')
    glow=Image.new('RGBA',im.size);d=ImageDraw.Draw(glow)
    for box,color in [((-.3,.03,.66,.58),(67,168,177,165)),((.31,.35,1.47,1.08),(65,93,175,160)),((-.35,.71,.55,1.42),(147,176,172,110))]:
        d.ellipse(tuple(round(v*(width if i%2==0 else height)) for i,v in enumerate(box)),fill=color)
    im=Image.alpha_composite(im,glow.filter(ImageFilter.GaussianBlur(width*.166)))
    arr=np.array(im);noise=np.random.default_rng(34).normal(0,1.4,(height,width,1));arr[:,:,:3]=np.clip(arr[:,:,:3].astype(float)+noise,0,255).astype('uint8');im=Image.fromarray(arr)
    glass=Image.new('RGBA',im.size);d=ImageDraw.Draw(glass);s=width/512
    d.rounded_rectangle((16*s,24*s,width-16*s,height-42*s),radius=32*s,fill=(255,255,255,85) if light else (185,222,237,17),outline=(255,255,255,110),width=max(1,round(s)))
    return Image.alpha_composite(im,glass).convert('RGB')

def circular_presenter(canvas, source, box, crop=None, preserve_all=False):
    """Fill a circular portrait from the original ROI. preserve_all is a legacy flag; no padding is added."""
    x,y,size=map(round,box)
    if size<8 or x<0 or y<0 or x+size>canvas.width or y+size>canvas.height:raise ValueError('Circle outside canvas')
    if crop is None:
        if preserve_all:bounds=(0,0,source.width,source.height)
        else:
            side=min(source.size);left=(source.width-side)//2;top=(source.height-side)//2
            bounds=(left,top,left+side,top+side)
    else:
        if len(crop)!=4 or not all(0<=v<=1 for v in crop):raise ValueError('Invalid normalized crop')
        bounds=tuple(round(v*(source.width if i%2==0 else source.height)) for i,v in enumerate(crop))
        if bounds[2]<=bounds[0] or bounds[3]<=bounds[1]:raise ValueError('Crop must have positive dimensions')
        if not preserve_all and abs((bounds[2]-bounds[0])-(bounds[3]-bounds[1]))>2:raise ValueError('Legacy crop must be square; preserve proportions')
    s=size/184;rim=max(2,round(3*s));inner=size-2*rim
    roi=source.crop(bounds)
    # Fill the circular window with actual source pixels; never letterbox a portrait.
    # The selected ROI must be visually checked to retain all hair and the full face.
    pic=ImageOps.fit(roi,(inner,inner),method=Image.Resampling.LANCZOS,centering=(.5,.5)).convert('RGBA')
    shadow=Image.new('RGBA',canvas.size);d=ImageDraw.Draw(shadow);offset=round(6*s)
    d.ellipse((x,y+offset,x+size,y+size+offset),fill=(3,13,26,105));shadow=shadow.filter(ImageFilter.GaussianBlur(7*s))
    result=Image.alpha_composite(canvas.convert('RGBA'),shadow)
    d=ImageDraw.Draw(result);d.ellipse((x,y,x+size-1,y+size-1),fill='white')
    mask=Image.new('L',(inner,inner));ImageDraw.Draw(mask).ellipse((0,0,inner-1,inner-1),fill=255);result.paste(pic,(x+rim,y+rim),mask)
    d=ImageDraw.Draw(result);d.arc((x+1,y+1,x+size-2,y+size-2),200,305,fill=(255,255,255,255),width=max(1,round(s)))
    canvas.paste(result.convert(canvas.mode))
