"""Verified standard entrypoint. Refuse silently different styling or dependencies."""
import argparse
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "wenfeng-standard-v1"
VERSION = "1.5"
SKILL_NAME = "wwf-video-editor-v1-5"

def check_environment():
    failures = []
    if platform.python_version() != "3.12.14":
        failures.append("Use Python 3.12.14 or the provided Dockerfile; found " + platform.python_version())
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"): continue
        package, expected = line.strip().split("==", 1)
        try: found = version(package)
        except PackageNotFoundError: found = "missing"
        if found != expected: failures.append(f"{package}: require {expected}, found {found}")
    tools = {}
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        if path is None:
            failures.append(f"Install FFmpeg (including {tool}) and put it on PATH, or use the Dockerfile")
        else:
            result = subprocess.run([path, "-version"], capture_output=True, text=True, check=True)
            tools[tool] = result.stdout.splitlines()[0]
    manifest_path = ROOT / "assets" / "standard-manifest.json"
    if not manifest_path.is_file():
        failures.append("Missing assets/standard-manifest.json; download the complete standard release")
    else:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("version") != VERSION:
            failures.append("Package version mismatch; install the complete v" + VERSION)
        if manifest.get("profile") != PROFILE:
            failures.append("Standard manifest profile mismatch")
        files = manifest.get("files", {})
        font = "assets/fonts/NotoSansCJKsc-Regular.otf"
        if font not in files: failures.append("Standard manifest must include the bundled font checksum")
        actual_files={str(f.relative_to(ROOT)) for f in ROOT.rglob("*") if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc" and f.name != "standard-manifest.json" and f.name != "README.md"}
        if actual_files != set(files):
            failures.append("Incomplete or mixed package file list; replace the entire installation")
        for relative, expected in files.items():
            path = (ROOT / relative).resolve()
            if not path.is_relative_to(ROOT):
                failures.append("Manifest path escapes package: " + relative); continue
            if not path.is_file(): failures.append("Missing standard asset: " + relative)
            elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                failures.append("Standard asset modified: " + relative)
    if failures:
        raise SystemExit("Standard environment check failed:\n- " + "\n- ".join(failures) + "\nInstall packages with: python -m pip install -r requirements.txt")
    return {"skill_name":SKILL_NAME,"standard_version":VERSION,"package_fingerprint":hashlib.sha256(manifest_path.read_bytes()).hexdigest(),"python": platform.python_version(), "packages": {line.split("==")[0]: version(line.split("==")[0]) for line in (ROOT / "requirements.txt").read_text().splitlines() if "==" in line}, **tools}

def main():
    parser = argparse.ArgumentParser(description="Render the locked Wenfeng standard template")
    parser.add_argument("--version", action="version", version=SKILL_NAME+" "+VERSION)
    parser.add_argument("--source")
    parser.add_argument("--plan")
    parser.add_argument("--captions")
    parser.add_argument("--output")
    parser.add_argument("--check", action="store_true", help="Verify dependencies and standard checksums")
    parser.add_argument("--demo", action="store_true", help="Render synthetic standard calibration; no actual spoken captions")
    parser.add_argument("--demo-dir", default="standard-demo-output")
    args = parser.parse_args()
    environment = check_environment()
    from verify_standard import samples
    reference=json.loads((ROOT/'assets/reference-raster.json').read_text())
    if samples()!=reference:raise SystemExit('Standard raster check failed; restore the complete package and pinned environment before rendering')
    environment['reference_raster_samples_passed']=len(reference)
    if args.check:
        print(json.dumps(environment, ensure_ascii=False, indent=2)); return
    if args.demo:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "demo.py"), "--output-dir", args.demo_dir, "--render"], check=True); return
    if not all((args.source, args.plan, args.captions, args.output)):
        parser.error("Provide --source, --plan, --captions, --output, or use --demo / --check")
    plan = json.loads(Path(args.plan).read_text())
    if plan.get("style_profile", PROFILE) != PROFILE:
        parser.error("run.py accepts only wenfeng-standard-v1; custom/legacy rendering uses render.py explicitly")
    if plan.get("standard_version", "1.5") != "1.5":
        parser.error("Unsupported standard_version; use the matching release")
    # Make omitted profile explicit; never mutate the author's plan on disk.
    if "style_profile" not in plan:
        parser.error("Set plan.style_profile to wenfeng-standard-v1; a legacy plan is never silently reinterpreted")
    output = Path(args.output).resolve()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "render.py"), "--source", args.source,
                    "--plan", args.plan, "--captions", args.captions,
                    "--font", str(ROOT / "assets" / "fonts" / "NotoSansCJKsc-Regular.otf"), "--output", str(output)], check=True)
    cues=json.loads(Path(args.captions).read_text())
    def timestamp(t):
        n=round(t*1000)
        return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'
    output.with_suffix('.srt').write_text(''.join(f"{i+1}\n{timestamp(c['start'])} --> {timestamp(c['end'])}\n{c['text']}\n\n" for i,c in enumerate(cues)),encoding='utf-8')
    report_path=output.with_suffix(".review.json")
    report=json.loads(report_path.read_text())
    report.update(delivery_status="candidate_pending_visual_review",standard_version=VERSION,package_fingerprint=environment["package_fingerprint"],output_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    output.with_suffix(".environment.json").write_text(json.dumps(environment, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
