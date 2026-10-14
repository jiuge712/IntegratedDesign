"""Signed difference, scale extrema, CLI errors and latest-only regression tests."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import numpy as np
import pytest

from common import ROOT
from lab5_scale import gaussian_pyramid, adjacent_dog, dog_displays, gaussian_dogs, scale_extrema
from latest_runs import LatestRun


def test_pyramid_odd_dimensions_and_input_unchanged():
    image = np.arange(99, dtype=np.uint8).reshape(9, 11)
    original = image.copy()
    assert [a.shape for a in gaussian_pyramid(image)] == [(9, 11), (5, 6), (3, 3), (2, 2)]
    np.testing.assert_array_equal(image, original)


def test_signed_difference_and_absolute_display_preserve_negative():
    fine = np.array([[0, 255], [0, 255]], np.uint8)
    dog = adjacent_dog(fine, np.array([[128]], np.uint8))
    assert dog.dtype == np.float32
    np.testing.assert_array_equal(dog, [[128, -127], [128, -127]])
    displays = dog_displays(dog)
    assert displays['absolute'][0, 1] > 250
    assert displays['signed'][0, 1] < 5


def test_constant_dog_has_no_extrema_and_no_divide_by_zero():
    image = np.full((32, 32), 80, np.uint8)
    pyramid = gaussian_pyramid(image)
    assert np.all(adjacent_dog(*pyramid[:2]) == 0)
    assert np.all(dog_displays(np.zeros((3, 3)))['signed'] == 128)
    dogs, sigmas = gaussian_dogs(image)
    assert len(dogs) == 5 and len(sigmas) == 6
    assert scale_extrema(dogs).shape == (0, 4)


def test_26_neighbor_extrema_positive_negative_and_boundary():
    dogs = [np.zeros((9, 9), np.float32) for _ in range(5)]
    dogs[1][2, 2] = 8
    dogs[3][6, 6] = -9
    dogs[0][4, 4] = 100  # outer scale excluded
    dogs[2][0, 4] = 100  # outer row excluded
    assert scale_extrema(dogs).tolist() == [[2, 2, 1, 8], [6, 6, 3, -9]]
    assert scale_extrema(dogs, contrast_threshold=9).shape == (0, 4)


def test_equal_plateau_not_strict_extremum():
    dogs = [np.zeros((5, 5)) for _ in range(3)]
    dogs[1][2, 2:4] = 10
    assert scale_extrema(dogs).shape == (0, 4)


@pytest.mark.parametrize('levels', [0, 9, 2.5, True])
def test_pyramid_invalid_levels(levels):
    with pytest.raises(ValueError):
        gaussian_pyramid(np.zeros((8, 8), np.uint8), levels)


def test_extrema_invalid_shapes():
    with pytest.raises(ValueError):
        scale_extrema([np.zeros((4, 4)), np.zeros((5, 5)), np.zeros((4, 4))])


def test_latest_replacement_and_failure_preserves_completed_pair(tmp_path):
    # latest_runs cleanup requires its ROOT to own the entire temporary tree.
    with patch('latest_runs.ROOT', tmp_path):
        for value in ('first', 'second'):
            with LatestRun('lab5') as latest:
                (latest.output / 'marker').write_text(value)
                (latest.evidence / 'marker').write_text(value)
                latest.commit()
        with pytest.raises(RuntimeError):
            with LatestRun('lab5') as latest:
                raise RuntimeError('simulated incomplete run')
        for parent in (tmp_path / 'data/output', tmp_path / 'evidence'):
            assert [p.name for p in parent.iterdir()] == ['lab5_latest']
            assert (parent / 'lab5_latest/marker').read_text() == 'second'


@pytest.mark.parametrize('mode', ['missing_image', 'unknown_config'])
def test_cli_reports_error_without_traceback(tmp_path, mode):
    command = [sys.executable, '-X', 'utf8', str(ROOT / 'src/run_lab5.py')]
    if mode == 'missing_image':
        command += ['--chess', str(tmp_path / 'nonexistent.png')]
    else:
        config = tmp_path / 'bad.json'
        config.write_text(json.dumps({'unexpected': 1}))
        command += ['--config', str(config)]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 1
    assert 'ERROR:' in result.stderr and 'Traceback' not in result.stderr
