"""One-command technical M1 demonstration; real classroom review remains pending."""
from run_lab8 import main

if __name__=='__main__':
    code=main()
    if code==0:
        print('\nM1 technical demonstration: SIFT -> BF KNN/ratio -> RANSAC -> warp -> feather')
        print('L8-FR-01/02: features.py + matching.py + homography.py; keypoints/matches evidence')
        print('L8-FR-03/04: homography.py + run_lab8.py; green/red matches and stitch PNGs')
        print('L8-FR-05/06: test_pipeline.py + test_lab8.py; pytest.log/xml and latest-run checks')
        print('Full traceability and 5-minute agenda: docs/lab8_m1_review.md')
        print('Real participants, capture angle, review scores and classroom records remain pending.')
    raise SystemExit(code)
