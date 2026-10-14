"""Test corner contracts and known geometric intersections, not output snapshots."""
import numpy as np
import pytest

from feature import (harris_corners, harris_response, manual_harris_response,
                     shi_tomasi_corners, fast_corners, select_points)
from prepare_chess import chessboard


@pytest.fixture
def board():
    return chessboard()


def test_non_array_rejected():
    with pytest.raises(TypeError):
        harris_corners([[0, 255]])


def test_empty_image_rejected():
    with pytest.raises(ValueError):
        harris_corners(np.empty((0, 0), np.uint8))


@pytest.mark.parametrize('image', [np.zeros((8, 8), np.float32), np.zeros((8, 8, 3), np.uint8)])
def test_invalid_dtype_or_channels(image):
    with pytest.raises(ValueError):
        harris_corners(image)


@pytest.mark.parametrize('value', [0, 128, 255])
def test_constant_image_has_no_corners(value):
    image = np.full((20, 20), value, np.uint8)
    for detector in (harris_corners, shi_tomasi_corners, fast_corners):
        assert detector(image).shape == (0, 2)


@pytest.mark.parametrize('k', [0.04, 0.06, 0.1])
def test_chess_matches_49_known_intersections(board, k):
    points = harris_corners(board, k=k)
    expected = np.array([(x, y) for y in range(40, 320, 40) for x in range(40, 320, 40)])
    assert len(points) == 49
    distances = np.linalg.norm(expected[:, None, :] - points[None, :, :], axis=2)
    # Each geometric intersection has a distinct detection within 2 pixels.
    assert np.all(distances.min(axis=1) <= 2)
    assert len(np.unique(distances.argmin(axis=1))) == 49


def test_integer_xy_in_bounds(board):
    for detector in (harris_corners, shi_tomasi_corners, fast_corners):
        points = detector(board)
        assert points.ndim == 2 and points.shape[1] == 2
        assert np.issubdtype(points.dtype, np.integer)
        assert np.all((points[:, 0] >= 0) & (points[:, 0] < board.shape[1]))
        assert np.all((points[:, 1] >= 0) & (points[:, 1] < board.shape[0]))


def test_shi_count_cap(board):
    assert 10 < len(shi_tomasi_corners(board)) <= 100
    assert len(shi_tomasi_corners(board, max_corners=12)) == 12


def test_selection_suppresses_nearby_points_and_respects_cap():
    response = np.zeros((12, 12), np.float32)
    response[2, 2], response[2, 4], response[9, 9] = 10, 9, 8
    assert select_points(response, min_distance=3).tolist() == [[2, 2], [9, 9]]
    assert select_points(response, max_points=1).tolist() == [[2, 2]]


@pytest.mark.parametrize('k', [0, -0.1, 0.25, float('nan'), True])
def test_invalid_k(board, k):
    with pytest.raises(ValueError):
        harris_corners(board, k=k)


def test_invalid_selection_on_constant():
    with pytest.raises(ValueError):
        shi_tomasi_corners(np.zeros((8, 8), np.uint8), quality_level=0)


def test_tiny_image_empty():
    assert harris_corners(np.zeros((1, 1), np.uint8)).shape == (0, 2)


def test_manual_response_matches_api_on_nontrivial_image():
    image = np.random.default_rng(15).integers(0, 256, (64, 71), dtype=np.uint8)
    manual = manual_harris_response(image)
    api = harris_response(image)
    np.testing.assert_allclose(manual['response'], api, rtol=2e-5, atol=2e-8)
    assert np.corrcoef(manual['response'].ravel(), api.ravel())[0, 1] > 0.99999
    np.testing.assert_allclose(manual['lambda1'] + manual['lambda2'], manual['trace'], atol=1e-7)
    np.testing.assert_allclose(manual['lambda1'] * manual['lambda2'], manual['determinant'], atol=1e-7)


def test_k_increase_reduces_response_without_changing_input(board):
    before = board.copy()
    assert np.all(harris_response(board, k=0.1) <= harris_response(board, k=0.04) + 1e-8)
    np.testing.assert_array_equal(board, before)
