"""Three required invariants on an actual seeded SIFT/matching/RANSAC chain."""
import cv2
import numpy as np
import pytest
from homography import match_and_estimate, project_points


@pytest.fixture(scope='module')
def controlled_pipeline():
    # Test fixture only, never substituted for the user's formal image pair.
    rng=np.random.default_rng(810)
    gray=rng.integers(0,256,(360,500),dtype=np.uint8)
    gray=cv2.GaussianBlur(gray,(3,3),.7)
    for i in range(30):
        xy=tuple(rng.integers([20,20],[480,340]).tolist())
        cv2.circle(gray,xy,int(rng.integers(3,14)),int(rng.integers(0,256)),2)
    left=cv2.cvtColor(gray,cv2.COLOR_GRAY2BGR)
    truth=np.array([[1.02,.035,21.],[-.02,1.01,16.],[.00004,-.00003,1.]])
    right=cv2.warpPerspective(left,truth,(550,400))
    result=match_and_estimate(left,right,threshold=3.)
    result['truth_right_to_left']=np.linalg.inv(truth)
    return result


def test_match_count_positive(controlled_pipeline):
    assert len(controlled_pipeline['matches'])>0


def test_homography_shape(controlled_pipeline):
    assert controlled_pipeline['H'].shape==(3,3)


def test_inlier_ratio_over_half(controlled_pipeline):
    assert controlled_pipeline['inliers'].mean()>.5


def test_chain_recovers_known_geometry(controlled_pipeline):
    probes=np.float64([[70,70],[430,60],[420,290],[80,300]])
    actual=project_points(probes,controlled_pipeline['H'])
    truth=project_points(probes,controlled_pipeline['truth_right_to_left'])
    assert np.max(np.linalg.norm(actual-truth,axis=1))<1.
