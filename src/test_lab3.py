"""Numerical, noise, interface, boundary and retention tests for experiment three."""
from __future__ import annotations
import io
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from skimage.metrics import peak_signal_noise_ratio
from common import ROOT,write_text
from lab3_filter import gaussian_noise,salt_pepper_noise,filter_image,sharpen_image,preprocess
from lab3_metrics import psnr,ssim,quality
from latest_runs import LatestRun


class Lab3Tests(unittest.TestCase):
    def setUp(self):
        self.gray=np.full((15,17),100,np.uint8)

    def test_gaussian_reproducible(self):
        np.testing.assert_array_equal(gaussian_noise(self.gray,25,42),gaussian_noise(self.gray,25,42))

    def test_gaussian_zero_and_clipping(self):
        np.testing.assert_array_equal(gaussian_noise(self.gray,0,0),self.gray)
        out=gaussian_noise(self.gray,1000,0)
        self.assertEqual(out.min(),0)
        self.assertEqual(out.max(),255)

    def test_noise_does_not_mutate(self):
        before=self.gray.copy()
        gaussian_noise(self.gray)
        salt_pepper_noise(self.gray)
        np.testing.assert_array_equal(self.gray,before)

    def test_salt_pepper_only_replaces_extremes(self):
        out,_=salt_pepper_noise(self.gray,0.5,0)
        self.assertEqual(set(np.unique(out)),{0,100,255})

    def test_salt_pepper_zero_and_full(self):
        np.testing.assert_array_equal(salt_pepper_noise(self.gray,0,0)[0],self.gray)
        self.assertTrue(np.all(np.isin(salt_pepper_noise(self.gray,1,0)[0],[0,255])))

    def test_salt_pepper_seed_and_fraction(self):
        a=np.full((300,300),127,np.uint8)
        out,info=salt_pepper_noise(a,0.1,11)
        np.testing.assert_array_equal(out,salt_pepper_noise(a,0.1,11)[0])
        self.assertAlmostEqual(info['selected_fraction'],0.1,delta=0.005)

    def test_mean_impulse_known_center(self):
        a=np.zeros((9,9),np.uint8)
        a[4,4]=255
        self.assertEqual(filter_image(a,'mean',3)[4,4],28)

    def test_median_removes_isolated_impulse(self):
        a=np.zeros((9,9),np.uint8)
        a[4,4]=255
        self.assertTrue(np.all(filter_image(a,'median',3)==0))

    def test_filters_preserve_constant(self):
        for method in ('mean','gaussian','median','bilateral'):
            with self.subTest(method=method):
                np.testing.assert_array_equal(filter_image(self.gray,method),self.gray)

    def test_laplacian_signed_known_impulse(self):
        a=np.zeros((9,9),np.uint8)
        a[4,4]=10
        out=sharpen_image(a,'laplacian',laplacian_amount=0.8)
        self.assertEqual(out[4,4],42)
        self.assertEqual(out[4,3],0)

    def test_usm_zero_amount(self):
        a=np.random.default_rng(0).integers(0,256,(15,17),dtype=np.uint8)
        np.testing.assert_array_equal(sharpen_image(a,'usm',usm_amount=0),a)

    def test_sharpen_constant(self):
        for method in ('laplacian','usm'):
            np.testing.assert_array_equal(sharpen_image(self.gray,method),self.gray)

    def test_invalid_filter_parameters(self):
        for kernel in (0,2,3.5,True):
            with self.subTest(kernel=kernel),self.assertRaises(ValueError):
                filter_image(self.gray,'median',kernel)
        with self.assertRaises(ValueError):
            filter_image(self.gray,'gaussian',gaussian_sigma=0)

    def test_invalid_noise_parameters(self):
        for sigma in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                gaussian_noise(self.gray,sigma)
        with self.assertRaises(ValueError):
            salt_pepper_noise(self.gray,1.1)

    def test_psnr_identity(self):
        self.assertTrue(math.isinf(psnr(self.gray,self.gray)))
        self.assertIsNone(quality(self.gray,self.gray)['psnr_db'])

    def test_psnr_known_mse_and_api(self):
        b=np.full_like(self.gray,110)
        self.assertAlmostEqual(psnr(self.gray,b),28.1308036086791,places=10)
        self.assertAlmostEqual(psnr(self.gray,b),peak_signal_noise_ratio(self.gray,b,data_range=255),places=12)

    def test_psnr_subtraction_does_not_wrap(self):
        a=np.zeros_like(self.gray)
        b=np.full_like(self.gray,255)
        self.assertEqual(psnr(a,b),0)

    def test_ssim_identity_and_shape_errors(self):
        self.assertAlmostEqual(ssim(self.gray,self.gray),1.0)
        with self.assertRaises(ValueError):
            ssim(self.gray,self.gray[:7])
        with self.assertRaises(ValueError):
            ssim(self.gray[:3,:3],self.gray[:3,:3])

    def test_bgr_interface_immutable_and_channel_order(self):
        a=np.zeros((15,17,3),np.uint8)
        a[:]=[20,80,160]
        before=a.copy()
        out=preprocess(a,{'filter':'gaussian','sharpen':'usm'})
        self.assertEqual(out.shape,a.shape)
        self.assertEqual(out.dtype,np.uint8)
        self.assertFalse(np.shares_memory(out,a))
        np.testing.assert_array_equal(out,before)
        np.testing.assert_array_equal(a,before)

    def test_interface_rejects_gray_dtype_and_unknown_config(self):
        with self.assertRaises(ValueError):
            preprocess(self.gray,{})
        with self.assertRaises(ValueError):
            preprocess(np.zeros((9,9,3),np.uint16),{})
        with self.assertRaises(ValueError):
            preprocess(np.zeros((9,9,3),np.uint8),{'gausian_sigma':1.5})
        with self.assertRaises(ValueError):
            preprocess(np.zeros((9,9,3),np.uint8),{'filter':'unknown'})

    def test_latest_lab3_replaces_previous(self):
        (ROOT/'.tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as tmp,patch('latest_runs.ROOT',Path(tmp)):
            for value in ('first','second'):
                with LatestRun('lab3') as latest:
                    (latest.output/'marker').write_text(value)
                    latest.commit()
            self.assertEqual((Path(tmp)/'data/output/lab3_latest/marker').read_text(),'second')
            self.assertEqual([p.name for p in (Path(tmp)/'data/output').iterdir()],['lab3_latest'])

    def test_latest_lab3_failure_keeps_previous(self):
        (ROOT/'.tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.tmp') as tmp,patch('latest_runs.ROOT',Path(tmp)):
            with LatestRun('lab3') as latest:
                (latest.output/'marker').write_text('good')
                latest.commit()
            with self.assertRaises(RuntimeError):
                with LatestRun('lab3') as latest:
                    raise RuntimeError('simulated failure')
            self.assertEqual((Path(tmp)/'data/output/lab3_latest/marker').read_text(),'good')


def main():
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Lab3Tests))
    print(stream.getvalue())
    write_text(ROOT/'evidence/lab3_self_test.log',stream.getvalue())
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
