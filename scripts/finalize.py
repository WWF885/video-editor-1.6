"""Fail-closed delivery gate. Human visual findings are attestations, not detection."""
import argparse,hashlib,json
from pathlib import Path
from run import check_environment,VERSION
CHECKS=('original_opening','approved_title_and_keywords','paragraph_scene_changes','summary_no_corner_number','single_line_captions','hair_and_face_visible','circle_filled_and_positioned','no_content_occlusion','caption_timing_checked','cover_two_lines_four_chars','board_static_under_three_seconds','logic_is_clear','presenter_is_secondary')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def validate(video,review,report,environment):
    if report.get('renderer_version')!=VERSION or report.get('standard_version')!=VERSION:raise ValueError('Wrong renderer version')
    if report.get('full_decode')!='passed' or report.get('single_line_validation') is not True:raise ValueError('Technical checks incomplete')
    if report.get('board_static_audit',{}).get('status')!='passed':raise ValueError('Board static audit missing or failed')
    if report.get('cover_validation') is not True or report.get('head_geometry_validation') is not True or report.get('board_motion_interval',99)>3:raise ValueError('New cover/head/motion technical checks incomplete')
    if not review.get('logic_evidence'):raise ValueError('Record scene logic and actual speech alignment findings')
    if not review.get('head_evidence'):raise ValueError('Record circle samples at scene start/middle/end and motion extremes')
    if report.get('output_sha256')!=sha(video):raise ValueError('Video differs from rendered candidate')
    if report.get('package_fingerprint')!=environment['package_fingerprint']:raise ValueError('Package differs from rendering environment')
    if review.get('video_sha256')!=sha(video) or review.get('report_sha256')!=sha(video.with_suffix('.review.json')):raise ValueError('Visual review is not bound to this video and report')
    if not isinstance(review.get('reviewer'),str) or not review['reviewer'].strip():raise ValueError('Record actual reviewer')
    if not isinstance(review.get('evidence'),list) or not review['evidence'] or any(not isinstance(e,str) or not e.strip() for e in review['evidence']):raise ValueError('Record sampled frames/time ranges and findings')
    if any(review.get('checks',{}).get(k) is not True for k in CHECKS):raise ValueError('Visual checks incomplete; repair before delivery')
    if review.get('shoulders') not in ('visible','limited_by_source'):raise ValueError('Inspect shoulders; record source limitation explicitly')
    if review['shoulders']=='limited_by_source' and not review.get('source_limitation'):raise ValueError('Explain source limitation')
    if review.get('listening_review') not in ('passed','not_performed'):raise ValueError('Record listening review honestly')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--video',required=True);parser.add_argument('--review',required=True);a=parser.parse_args()
    video=Path(a.video).resolve();env=check_environment()
    from verify_standard import samples
    from run import ROOT
    if samples()!=json.loads((ROOT/'assets/reference-raster.json').read_text()):raise SystemExit('DELIVERY BLOCKED: standard raster mismatch')
    report=json.loads(video.with_suffix('.review.json').read_text());review=json.loads(Path(a.review).read_text())
    try:validate(video,review,report,env)
    except ValueError as error:raise SystemExit('DELIVERY BLOCKED: '+str(error))
    result={'status':'approved_for_delivery','standard_version':VERSION,'package_fingerprint':env['package_fingerprint'],'video_sha256':sha(video),'review_sha256':sha(a.review),'listening_review':review['listening_review'],'shoulders':review['shoulders'],'source_limitation':review.get('source_limitation')}
    video.with_suffix('.delivery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
