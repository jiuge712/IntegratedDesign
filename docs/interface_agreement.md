# 实验三预处理接口约定

实现：src/lab3_filter.py。

```python
def preprocess(img_bgr: np.ndarray, cfg: dict) -> np.ndarray:
    ...
```

输入为非空NumPy uint8，shape=(H,W,3)，BGR，0–255。输出为同尺寸、同类型、同顺序的新数组，不共享返回缓冲区、不修改输入。接口不读写文件、不添加随机噪声、不改变几何坐标。

| 参数 | 默认 | 约束 |
| --- | --- | --- |
| filter | gaussian | none/mean/gaussian/median/bilateral |
| kernel_size | 5 | ≥3的奇整数，均值/中值使用 |
| gaussian_sigma | 1.5 | 有限正数，自动高斯核 |
| bilateral_d | 7 | ≥3的奇整数 |
| sigma_color / sigma_space | 50 / 5 | 双边滤波正参数 |
| sharpen | usm | none/laplacian/usm |
| laplacian_amount | 0.8 | 有限非负，CV_64F带符号响应 |
| usm_amount | 0.6 | 有限非负，0表示不增强 |
| usm_sigma | 2.0 | 有限正数 |

未知配置键、方法、类型或参数引发ValueError；OpenCV底层异常由一键入口转换为ERROR/非零退出码。灰度或BGRA需在加载边界转BGR；数值接口严格接收BGR。固定顺序为滤波后锐化，可关闭相应方法。

```python
from pathlib import Path
from baseline_pipeline import read_image
from lab3_filter import preprocess

img = read_image(Path("data/input/photo.jpg"))  # 本例为uint8 BGR
out = preprocess(img, {"filter": "gaussian", "sharpen": "usm"})
assert out.shape == img.shape and out.dtype == img.dtype
```

在src运行/import，或将src加入模块搜索路径。run_lab3.py已完成真实调用，保存l3_interface_input_bgr.png、l3_interface_noisy_bgr.png和l3_interface_output_bgr.png，并验证输入不变。

评分先检查类型与尺寸；SSIM宽高≥7、data_range=255，彩色使用channel_axis=-1。正式评分表统一灰度参考，不隐式resize修复对应像素。MSE=0的PSNR为∞，JSON用null加标志表示。

参考：[OpenCV滤波接口](https://docs.opencv.org/4.x/d4/d86/group__imgproc__filter.html)、[scikit-image SSIM](https://scikit-image.org/docs/stable/api/skimage.metrics.html#skimage.metrics.structural_similarity)。

这是已实现的技术约定，小组共同确认应在真实讨论后补充参与者、日期和变更意见。
