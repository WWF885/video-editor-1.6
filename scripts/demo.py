"""Generate public, deterministic calibration assets; these are NOT real speech/person footage."""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, FPS, DURATION = 512, 902, 30, 16

def prepare(output_dir):
    from PIL import Image, ImageDraw, ImageFont
    output_dir = Path(output_dir).resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    font_path = ROOT / "assets/fonts/NotoSansCJKsc-Regular.otf"
    if not font_path.is_file(): raise SystemExit("Download the complete standard package: bundled font is missing")
    fonts = {n: ImageFont.truetype(str(font_path), n) for n in (18,22,26,32)}
    def text(draw, xy, s, n=22, fill="#F7F9FC"):
        draw.text(xy, s, font=fonts[n], fill=fill, anchor="mm")
    # The obvious geometric silhouette is a framing target, not a generated identity.
    command = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "512x902", "-r", "30", "-i", "-",
               "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "16", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(output_dir / "demo-source.mp4")]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for frame_number in range(FPS * DURATION):
            t = frame_number / FPS; im = Image.new("RGB", (WIDTH, HEIGHT), "#E8EEF2"); draw = ImageDraw.Draw(im)
            draw.rectangle((24,24,488,878), outline="#93A6B6", width=2)
            text(draw,(256,54),"合成校准素材 · 非真人",22,"#33465B")
            text(draw,(256,92),"无口播，字幕仅为排版测试",18,"#51677D")
            for y in range(140,800,80): draw.line((24,y,488,y),fill="#D0DCE5",width=1)
            # Hair cap and upper-body guide make clipping easy to see.
            draw.rounded_rectangle((130,405,406,730),radius=70,fill="#7B99B1")
            draw.ellipse((182,150,370,370),fill="#405B73")
            draw.ellipse((193,191,359,386),fill="#B9CCD9")
            draw.arc((181,151,371,358),180,360,fill="#21384E",width=20)
            text(draw,(276,285),"构图",26,"#21384E");text(draw,(276,320),"测试替身",22,"#21384E")
            hand_x = 122 + round(20 * math.sin(2 * math.pi * t / 3))
            draw.ellipse((hand_x,450,hand_x+65,515),fill="#B9CCD9")
            text(draw,(267,560),"头发与上半身边界",18,"#102536")
            draw.line((32,830,480,830), fill="#9FB1C0",width=4)
            draw.line((32,830,32+round(448*frame_number/(FPS*DURATION-1)),830),fill="#2671D9",width=4)
            text(draw,(256,862),f"校准帧 {frame_number:03d} / {FPS*DURATION-1}",18,"#33465B")
            process.stdin.write(im.tobytes())
    finally:
        process.stdin.close()
    if process.wait() != 0: raise RuntimeError("Calibration source generation failed")
    image = Image.new("RGB",(700,440),"#F7F9FC"); draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((16,16,684,424),radius=24,fill="#DBECFF",outline="#8EAAC7",width=2)
    text(draw,(350,66),"演示素材 · 非真实数据",32,"#15263D")
    text(draw,(350,132),"截图和图表应保留必要上下文",26,"#2671D9")
    draw.rounded_rectangle((84,154,616,286),radius=18,fill="white")
    text(draw,(350,220),"在这里框出重要信息",32,"#15263D")
    text(draw,(350,355),"此素材仅用于测试等比展示与重点框",22,"#51677D")
    image.save(output_dir / "demo-insert.png")
    shutil.copyfile(ROOT / "assets/standard-demo.json", output_dir / "plan.json")
    shutil.copyfile(ROOT / "assets/demo-captions.json", output_dir / "captions.json")
    metadata = {"synthetic":True,"contains_real_person":False,"contains_speech":False,"caption_purpose":"layout_test_only","duration":DURATION,"fps":FPS}
    (output_dir / "fixture.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    return output_dir

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",default="standard-demo-output")
    group=parser.add_mutually_exclusive_group();group.add_argument("--prepare-only",action="store_true");group.add_argument("--render",action="store_true")
    args=parser.parse_args();output_dir=prepare(args.output_dir)
    if args.render:
        subprocess.run([sys.executable,str(ROOT / "scripts/run.py"),"--source",str(output_dir/"demo-source.mp4"),"--plan",str(output_dir/"plan.json"),"--captions",str(output_dir/"captions.json"),"--output",str(output_dir/"standard-demo.mp4")],check=True)
    print(output_dir)

if __name__=="__main__": main()
