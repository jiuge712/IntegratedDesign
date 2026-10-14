"""Meaningful numeric, boundary, and latest-run transaction checks."""
from __future__ import annotations
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from common import ROOT, write_text
from lab2_arith import arithmetic
from lab2_hist import histogram, manual_equalize
from lab2_transform import gamma_transform, linear_transform
from latest_runs import LatestRun, remove_owned


class Lab2Tests(unittest.TestCase):
    def test_linear_known_values(self):
        a = np.array([[0, 100, 200, 255]], np.uint8)
        self.assertEqual(linear_transform(a).tolist(), [[30, 180, 255, 255]])

    def test_linear_negative_clips_without_absolute_value(self):
        self.assertEqual(linear_transform(np.array([[0, 20, 80]], np.uint8), 1, -30).tolist(), [[0, 0, 50]])

    def test_gamma_identity_and_endpoints(self):
        a = np.arange(256, dtype=np.uint8).reshape(16, 16)
        np.testing.assert_array_equal(gamma_transform(a, 1), a)
        self.assertEqual(gamma_transform(a, 2.2)[0, 0], 0)
        self.assertEqual(gamma_transform(a, 0.5)[-1, -1], 255)

    def test_gamma_direction(self):
        a = np.array([[64, 128, 192]], np.uint8)
        self.assertTrue(np.all(gamma_transform(a, 2.2) > a))
        self.assertTrue(np.all(gamma_transform(a, 0.5) < a))

    def test_gamma_invalid_parameters(self):
        for gamma in (0, -1, float("nan"), float("inf")):
            with self.subTest(gamma=gamma), self.assertRaises(ValueError):
                gamma_transform(np.zeros((1, 1), np.uint8), gamma)

    def test_histogram_known_bins(self):
        h = histogram(np.array([[0, 0, 2, 255]], np.uint8))
        self.assertEqual(h.shape, (256,))
        self.assertEqual(h[[0, 2, 255]].tolist(), [2, 1, 1])
        self.assertEqual(h.sum(), 4)

    def test_equalization_known_cdf(self):
        a = np.array([[10, 10, 20, 30]], np.uint8)
        result, lut = manual_equalize(a)
        self.assertEqual(result.tolist(), [[0, 0, 128, 255]])
        self.assertTrue(np.all(np.diff(lut.astype(int)) >= 0))

    def test_constant_black(self):
        a = np.zeros((3, 4), np.uint8)
        np.testing.assert_array_equal(manual_equalize(a)[0], a)

    def test_constant_white(self):
        a = np.full((3, 4), 255, np.uint8)
        np.testing.assert_array_equal(manual_equalize(a)[0], a)

    def test_constant_midgray(self):
        a = np.full((3, 4), 127, np.uint8)
        np.testing.assert_array_equal(manual_equalize(a)[0], a)

    def test_equalization_random_matches_api(self):
        rng = np.random.default_rng(42)
        for lo, hi in ((0, 256), (80, 120), (30, 256)):
            a = rng.integers(lo, hi, (71, 93), dtype=np.uint8)
            diff = np.abs(manual_equalize(a)[0].astype(int) - cv2.equalizeHist(a).astype(int))
            self.assertLessEqual(diff.max(), 1)

    def test_add_wrap_vs_saturation(self):
        r = arithmetic(np.array([[250]], np.uint8), np.array([[20]], np.uint8))
        self.assertEqual(r["add_numpy"].item(), 14)
        self.assertEqual(r["add_opencv"].item(), 255)

    def test_subtract_wrap_vs_saturation(self):
        r = arithmetic(np.array([[10]], np.uint8), np.array([[20]], np.uint8))
        self.assertEqual(r["subtract_numpy"].item(), 246)
        self.assertEqual(r["subtract_opencv"].item(), 0)
        self.assertEqual(r["absdiff"].item(), 10)

    def test_weighted_known_result(self):
        r = arithmetic(np.array([[10]], np.uint8), np.array([[20]], np.uint8), 0.6)
        self.assertEqual(r["blend"].item(), 14)

    def test_multiply_and_divide(self):
        r = arithmetic(np.array([[255, 40]], np.uint8), np.array([[128, 80]], np.uint8))
        self.assertEqual(r["multiply"][0, 0], 128)
        self.assertEqual(r["divide"][0, 1], 64)

    def test_division_by_zero(self):
        r = arithmetic(np.array([[10]], np.uint8), np.zeros((1, 1), np.uint8))
        self.assertEqual(r["divide"].item(), 0)

    def test_shape_mismatch(self):
        with self.assertRaises(ValueError):
            arithmetic(np.zeros((2, 3), np.uint8), np.zeros((3, 2), np.uint8))

    def test_reject_non_uint8_and_color(self):
        for a in (np.zeros((2, 2), np.uint16), np.zeros((2, 2), np.float32), np.zeros((2, 2, 3), np.uint8)):
            with self.subTest(shape=a.shape, dtype=a.dtype), self.assertRaises(ValueError):
                manual_equalize(a)

    def test_invalid_weight_and_alpha(self):
        a = np.zeros((1, 1), np.uint8)
        with self.assertRaises(ValueError):
            arithmetic(a, a, 1.2)
        with self.assertRaises(ValueError):
            linear_transform(a, float("nan"), 0)

    def test_latest_success_replaces_previous(self):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".tmp") as temp, patch("latest_runs.ROOT", Path(temp)):
            for value in ("first", "second"):
                with LatestRun("lab2") as run:
                    (run.output / "marker").write_text(value)
                    (run.evidence / "marker").write_text(value)
                    run.commit()
            self.assertEqual((Path(temp) / "data/output/lab2_latest/marker").read_text(), "second")
            self.assertEqual([p.name for p in (Path(temp) / "data/output").iterdir()], ["lab2_latest"])

    def test_latest_failure_preserves_previous(self):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".tmp") as temp, patch("latest_runs.ROOT", Path(temp)):
            with LatestRun("lab2") as run:
                (run.output / "marker").write_text("valid")
                run.commit()
            with self.assertRaises(RuntimeError):
                with LatestRun("lab2") as run:
                    (run.output / "marker").write_text("incomplete")
                    raise RuntimeError("simulated processing failure")
            self.assertEqual((Path(temp) / "data/output/lab2_latest/marker").read_text(), "valid")

    def test_cleanup_rejects_parent(self):
        with self.assertRaises(ValueError):
            remove_owned(ROOT / "data/output", ROOT / "data/output")


def main() -> int:
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Lab2Tests)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    text = stream.getvalue()
    print(text)
    write_text(ROOT / "evidence/lab2_self_test.log", text)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
