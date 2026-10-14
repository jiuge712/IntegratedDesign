"""Numeric and boundary checks for edges, segmentation, and latest result retention."""
from __future__ import annotations
import io
import json
import math
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
import numpy as np
from common import ROOT,write_text
from lab4_edges import sobel_gradients,unit_gray,canny_edges,nonmaximum_suppression,hysteresis,manual_canny,edge_agreement
from lab4_segment import threshold_segments,adaptive_segment,uneven_illumination,binary_statistics
from latest_runs import LatestRun


class Lab4Tests(unittest.TestCase):
    def setUp(self):
        self.constant=np.full((41,43),100,np.uint8)

    def test_constant_sobel_zero_without_division(self):
        for kernel in (3,5):
            g=sobel_gradients(self.constant,kernel)
            self.assertTrue(np.all(g['magnitude_display']==0))
            self.assertTrue(np.isfinite(g['direction_radians']).all())

    def test_sobel_known_ramp_direction(self):
        y,x=np.indices((9,9))
        g=sobel_gradients((x*10+y*20).astype(np.uint8))
        self.assertEqual(g['gx'][4,4],80)
        self.assertEqual(g['gy'][4,4],160)
        self.assertAlmostEqual(g['magnitude'][4,4],math.sqrt(32000))
        self.assertAlmostEqual(g['direction_radians'][4,4],math.atan2(160,80))

    def test_signed_negative_gradient_preserved(self):
        a=np.tile(np.arange(9,dtype=np.uint8)[::-1]*20,(9,1))
        g=sobel_gradients(a)
        self.assertEqual(g['gx'][4,4],-160)
        self.assertGreater(g['gx_display'][4,4],0)

    def test_sobel_kernels_and_normalization(self):
        a=np.zeros((21,21),np.uint8)
        a[:,10:]=255
        for kernel in (3,5):
            g=sobel_gradients(a,kernel)
            self.assertEqual(g['magnitude_display'].shape,a.shape)
            self.assertEqual(g['magnitude_display'].max(),255)

    def test_sobel_invalid_kernel_and_dtype(self):
        for kernel in (2,7,True,3.0):
            with self.assertRaises(ValueError):
                sobel_gradients(self.constant,kernel)
        with self.assertRaises(ValueError):
            sobel_gradients(self.constant.astype(np.uint16))

    def test_normalization_known_values(self):
        self.assertEqual(unit_gray(np.array([[0,2,4]],float)).tolist(),[[0,127,255]])
        with self.assertRaises(ValueError):
            unit_gray(np.array([[float('nan')]]))

    def test_canny_constant_empty(self):
        self.assertTrue(np.all(canny_edges(self.constant)==0))

    def test_canny_rectangle_and_binary(self):
        a=np.zeros((64,64),np.uint8)
        a[15:49,15:49]=255
        edges=canny_edges(a,50,150)
        self.assertTrue(np.any(edges))
        self.assertTrue(np.isin(edges,[0,255]).all())

    def test_canny_density_with_rising_thresholds(self):
        a=np.random.default_rng(13).integers(0,256,(51,57),dtype=np.uint8)
        counts=[np.count_nonzero(canny_edges(a,*pair)) for pair in ((50,150),(100,200),(150,250))]
        self.assertTrue(counts[0]>=counts[1]>=counts[2])

    def test_canny_invalid_thresholds_and_sigma(self):
        for pair in ((150,50),(-1,50),(1,1),(0,float('nan'))):
            with self.assertRaises(ValueError):
                canny_edges(self.constant,*pair)
        with self.assertRaises(ValueError):
            canny_edges(self.constant,blur_sigma=-1)

    def test_nms_keeps_horizontal_peak(self):
        mag=np.tile([0,1,3,1,0],(5,1)).astype(float)
        out=nonmaximum_suppression(mag,np.zeros_like(mag))
        self.assertEqual(out[2].tolist(),[0,0,3,0,0])

    def test_nms_breaks_equal_plateau(self):
        mag=np.tile([0,2,2,0,0],(5,1)).astype(float)
        out=nonmaximum_suppression(mag,np.zeros_like(mag))
        self.assertEqual(out[2].tolist(),[0,2,0,0,0])

    def test_nms_45_degrees_uses_image_row_coordinates(self):
        mag=np.zeros((5,5),float)
        mag[2,2]=3
        mag[1,1]=4
        out=nonmaximum_suppression(mag,np.full_like(mag,math.pi/4))
        self.assertEqual(out[2,2],0)

    def test_nms_tiny_and_invalid_shapes(self):
        self.assertTrue(np.all(nonmaximum_suppression(np.ones((2,2)),np.zeros((2,2)))==0))
        with self.assertRaises(ValueError):
            nonmaximum_suppression(np.ones((3,3)),np.zeros((3,2)))

    def test_hysteresis_connected_weak_chain(self):
        mag=np.zeros((5,9),float)
        mag[2,1:5]=[160,60,60,60]
        mag[2,7]=60
        out=hysteresis(mag,50,150)
        self.assertTrue(np.all(out[2,1:5]==255))
        self.assertEqual(out[2,7],0)

    def test_hysteresis_diagonal_and_no_seed(self):
        mag=np.zeros((5,5),float)
        mag[1,1]=160
        mag[2,2]=60
        self.assertEqual(hysteresis(mag,50,150)[2,2],255)
        self.assertTrue(np.all(hysteresis(np.full((5,5),60.),50,150)==0))

    def test_hysteresis_zero_background(self):
        self.assertTrue(np.all(hysteresis(np.zeros((4,4)),0,1)==0))

    def test_manual_canny_constant(self):
        result=manual_canny(self.constant)
        self.assertTrue(np.all(result['edges']==0))

    def test_agreement_empty_and_disjoint(self):
        a=np.zeros((4,4),np.uint8)
        self.assertEqual(edge_agreement(a,a)['iou'],1)
        a[1,1]=255
        b=np.zeros_like(a)
        b[2,2]=255
        self.assertEqual(edge_agreement(a,b)['iou'],0)

    def test_fixed_threshold_strict_comparison(self):
        result=threshold_segments(np.array([[127,128,129]],np.uint8))
        self.assertEqual(result['fixed'].tolist(),[[0,0,255]])

    def test_otsu_two_levels(self):
        a=np.array([[0,0,200,200]],np.uint8)
        result=threshold_segments(a)
        self.assertEqual(result['otsu_threshold'],0)
        self.assertEqual(result['otsu'].tolist(),[[0,0,255,255]])

    def test_adaptive_constant_and_validation(self):
        self.assertTrue(np.all(adaptive_segment(self.constant,31,5)==255))
        for block in (1,4,31.0,True):
            with self.assertRaises(ValueError):
                adaptive_segment(self.constant,block,5)

    def test_illumination_known_gain_and_source_unchanged(self):
        a=np.full((3,3),100,np.uint8)
        out,gain=uneven_illumination(a,0.2,1)
        self.assertEqual(out[1].tolist(),[20,60,100])
        self.assertTrue(np.all(a==100))
        np.testing.assert_allclose(gain[1],[0.2,0.6,1])

    def test_illumination_invalid(self):
        with self.assertRaises(ValueError):
            uneven_illumination(self.constant,0,1)

    def test_binary_statistics_known_halves(self):
        result=binary_statistics(np.array([[0,0,255,255]],np.uint8))
        self.assertEqual(result['white_fraction'],0.5)
        self.assertEqual(result['left_white_fraction'],0)
        self.assertEqual(result['right_white_fraction'],1)

    def test_latest_lab4_replacement_and_failure(self):
        (ROOT/'.tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as temp,patch('latest_runs.ROOT',Path(temp)):
            for value in ('first','second'):
                with LatestRun('lab4') as latest:
                    (latest.output/'marker').write_text(value)
                    latest.commit()
            with self.assertRaises(RuntimeError):
                with LatestRun('lab4') as latest:
                    raise RuntimeError('simulated failure')
            self.assertEqual((Path(temp)/'data/output/lab4_latest/marker').read_text(),'second')
            self.assertEqual([p.name for p in (Path(temp)/'data/output').iterdir()],['lab4_latest'])

    def test_cli_missing_input_reports_error(self):
        command=[sys.executable,'-X','utf8',str(ROOT/'src/run_lab4.py'),'--texture',str(ROOT/'.tmp/no_such_cli_input.png')]
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,1)
        self.assertIn('ERROR:',result.stderr)
        self.assertNotIn('Traceback',result.stderr)

    def test_cli_unknown_config_reports_error(self):
        (ROOT/'.tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as temp:
            config=Path(temp)/'invalid.json'
            config.write_text(json.dumps({'unexpected_field':1}),encoding='utf-8')
            result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'src/run_lab4.py'),'--config',str(config)],
                                  capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,1)
            self.assertIn('ERROR:',result.stderr)
            self.assertNotIn('Traceback',result.stderr)


def main():
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Lab4Tests))
    print(stream.getvalue())
    write_text(ROOT/'evidence/lab4_self_test.log',stream.getvalue())
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
