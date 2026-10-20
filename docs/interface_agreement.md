# 预处理与特征提取接口约定

实现：src/lab3_filter.py。

本文件保留实验三预处理契约，实验六SIFT契约追加于末尾；既有小组确认状态不因技术实现新增而自动改变。

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

## 实验六SIFT提取接口

```python
from features import extract_sift
kps, desc = extract_sift(img, cfg=None)
```

src/features.py接收非空uint8灰度/BGR/BGRA，明确转灰度并舍弃Alpha，返回KeyPoint列表和float32 (N,128)描述子，行与关键点严格对应。无特征返回[]、(0,128)，不返回None。关键点pt=(x,y)为工作图浮点像素，size是直径，angle单位度；不使用实验五Harris的整数坐标输出契约。

cfg字段为nfeatures（整数≥0）、nOctaveLayers（整数≥1）、contrastThreshold/edgeThreshold/sigma（有限正数）和enable_precise_upscale（bool）。None使用规范默认值，未知键与不合法图像/参数明确报错；接口不读写文件、不修改图像或cfg。参数与错误详情见lab6_design.md。

run_lab6.py可按显式max_input_side在外围生成工作尺寸，记录原图到工作图的像素中心矩阵。后续使用工作图xy时相机内参也应在对应尺度，或先映回原图，不混用像素坐标。描述子按OpenCV实际缩放存储，不假定单位范数；匹配使用L2。该技术接口已实现，不等于完成真实小组接口确认，user_tasks.md的课堂任务保持原状态。
