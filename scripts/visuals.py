"""Reusable frosted background and source-video circular presenter."""
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import numpy as np
import math

def frosted_background(width, height, light=False):
    # Quiet frosted charcoal / warm ivory, with very restrained material grain.
    top,bottom=((247,243,234),(235,230,220)) if light else ((31,41,69),(25,33,57))
    yy=np.linspace(0,1,height)[:,None,None]
    arr=np.broadcast_to(np.array(top)[None,None,:]*(1-yy)+np.array(bottom)[None,None,:]*yy,(height,width,3)).copy()
    noise=np.random.default_rng(34).normal(0,.45,(height,width,1));arr=np.clip(arr+noise,0,255).astype('uint8')
    im=Image.fromarray(arr).convert('RGBA');light_layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(light_layer)
    d.ellipse((-width*.45,height*.02,width*.65,height*.55),fill=(92,137,192,40 if not light else 16))
    d.ellipse((width*.67,height*.37,width*1.3,height*.85),fill=(199,155,89,27 if not light else 20))
    d.ellipse((width*.1,height*.5,width*.8,height*.85),fill=(77,127,120,13 if not light else 8))
    return Image.alpha_composite(im,light_layer.filter(ImageFilter.GaussianBlur(width*.30))).convert('RGB')

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

def rounded_square_presenter(canvas,source,box,crop=None):
    x,y,size=map(round,box)
    if x<0 or y<0 or x+size>canvas.width or y+size>canvas.height:raise ValueError('Presenter outside canvas')
    bounds=tuple(round(v*(source.width if i%2==0 else source.height)) for i,v in enumerate(crop)) if crop else (0,0,*source.size)
    rim=2;inner=size-2*rim;radius=round(size*.16)
    pic=ImageOps.fit(source.crop(bounds),(inner,inner),Image.Resampling.LANCZOS).convert('RGBA')
    shadow=Image.new('RGBA',canvas.size);d=ImageDraw.Draw(shadow);d.rounded_rectangle((x,y+4,x+size,y+size+4),radius=radius,fill=(3,9,20,100))
    result=Image.alpha_composite(canvas.convert('RGBA'),shadow.filter(ImageFilter.GaussianBlur(5)))
    ImageDraw.Draw(result).rounded_rectangle((x,y,x+size-1,y+size-1),radius=radius,fill='white')
    mask=Image.new('L',(inner,inner));ImageDraw.Draw(mask).rounded_rectangle((0,0,inner-1,inner-1),radius=max(1,radius-rim),fill=255)
    result.paste(pic,(x+rim,y+rim),mask);canvas.paste(result.convert(canvas.mode))
