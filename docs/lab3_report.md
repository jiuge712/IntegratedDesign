# 实验三空间滤波与图像增强报告

运行时间：2026-10-13T21:49:16+08:00。程序版本：3.0.0。
本次使用用户提供的插画 `D:\IntegratedDesign\project_i\data\input\photo.jpg`，灰度尺寸为 [671, 1192]。含噪图从该图派生，原图作为评价参考。原始输入 SHA-256 保持不变。

22 项程序自检通过；本次正式检查 9 项全部通过。完整处理、绘图、回读及评分耗时 4746.871 ms。

## 背景与参数

空间滤波利用局部邻域进行平滑，锐化则强化局部变化。实验对同一参考图加入两类受控噪声，分别比较滤波的去噪与细节保留；不是对真实拍摄噪声类型的推断。

| 参数 | 实际值 |
| --- | --- |
| seed | 0 |
| gaussian_noise_sigma | 25.0 |
| salt_pepper_probability | 0.1 |
| kernel_size | 5 |
| gaussian_sigma | 1.5 |
| laplacian_amount | 0.8 |
| usm_amount | 0.6 |
| usm_sigma | 2.0 |
| bilateral_d | 7 |
| sigma_color | 50.0 |
| sigma_space | 5.0 |
| pipeline_filter | gaussian |
| pipeline_sharpen | usm |

高斯噪声使用 seed 的 RNG；椒盐噪声使用 seed+1 的独立 RNG，两者固定后重复运行相同。均值和中值核为 5×5，高斯采用 (0,0) 自动核、sigma=1.5。均值/高斯/拉普拉斯边界为 REFLECT_101，中值边界由 OpenCV 使用 REPLICATE。

## 两类噪声与三种滤波

高斯噪声：`clip(gray.astype(float64)+rng.normal(0,sigma,shape),0,255).astype(uint8)`。椒盐噪声根据均匀随机掩码将像素置 0 或 255；当前概率 0.1 表示两类合计，每类为一半。

本次椒盐掩码选中比例为 10.0181%。该值描述噪声生成时选中的像素，不把原图已有黑白像素计为生成噪声。

调用 `cv2.blur`、`cv2.GaussianBlur` 和 `cv2.medianBlur`，两类噪声复用同一组方法与参数。额外实现双边滤波作为指导书加分对比。所有结果保存为 PNG，避免 JPEG 压缩改变评分。

![高斯噪声滤波对比](../data/output/lab3_latest/l3_gaussian_compare.png)

![椒盐噪声滤波对比](../data/output/lab3_latest/l3_salt_pepper_compare.png)

![双边滤波补充对比](../data/output/lab3_latest/l3_bilateral_compare.png)

## PSNR 与 SSIM 评分

PSNR 手写计算 `10*log10(255^2/MSE)`，差值先转 float64；MSE=0 时为正无穷。JSON 用 psnr_db=null 和 psnr_infinite=true 表示无穷，不输出非法 JSON 数值。SSIM 调用 scikit-image，显式设置 data_range=255、win_size=7，保持两图同尺寸，不做隐式缩放。

| 场景 | 方法 | PSNR dB | SSIM | MSE | 平均梯度 |
| --- | --- | --- | --- | --- | --- |
| reference | original | ∞ | 1.000000 | 0.0000 | 31.2611 |
| gaussian | noisy | 20.2713 | 0.238611 | 610.8695 | 120.5382 |
| gaussian | mean | 28.7571 | 0.773665 | 86.5701 | 35.5362 |
| gaussian | gaussian | 29.2528 | 0.800750 | 77.2319 | 34.1347 |
| gaussian | median | 28.9560 | 0.719651 | 82.6961 | 40.2408 |
| gaussian | bilateral | 29.1253 | 0.671812 | 79.5329 | 43.3832 |
| salt_pepper | noisy | 15.4045 | 0.147503 | 1873.4124 | 158.4142 |
| salt_pepper | mean | 25.9509 | 0.608271 | 165.1923 | 45.7142 |
| salt_pepper | gaussian | 26.3200 | 0.647538 | 151.7326 | 43.3010 |
| salt_pepper | median | 32.6807 | 0.952528 | 35.0763 | 23.8288 |
| salt_pepper | bilateral | 16.7276 | 0.191128 | 1381.4133 | 121.1895 |
| sharpen | original | ∞ | 1.000000 | 0.0000 | 31.2611 |
| sharpen | laplacian | 26.6296 | 0.906495 | 141.2930 | 54.8765 |
| sharpen | usm | 33.7076 | 0.976814 | 27.6898 | 42.6703 |

本次 gaussian 场景 PSNR 最优为 gaussian，SSIM 最优为 gaussian；该结论仅对应本图、参数和噪声实现，不把指导书示例分数直接当作实测。
本次 salt_pepper 场景 PSNR 最优为 median，SSIM 最优为 median；该结论仅对应本图、参数和噪声实现，不把指导书示例分数直接当作实测。

平均梯度用于观察局部变化，但噪声也会提高梯度；不能单独把较高梯度当作更好的去噪或重建质量。PSNR/SSIM 是相对参考图的保真评价，不以“超过 28 dB”作为所有图像的强制通过条件。

## 拉普拉斯与 USM 锐化

拉普拉斯使用 CV_64F 保存正负响应，计算 `clip(img-0.8*Laplacian(img),0,255)`。USM 使用 `img+0.6*(img-GaussianBlur(img,sigma=2.0))`，通过 addWeighted 舍入与饱和。锐化作用于原始灰度参考图；另保存轻度模糊图的锐化演示。

![原图与两种锐化](../data/output/lab3_latest/l3_sharpen_compare.png)

![轻度模糊图锐化对比](../data/output/lab3_latest/l3_blurred_sharpen_compare.png)

![局部边缘与纹理放大](../data/output/lab3_latest/l3_detail_compare.png)

锐化可能提高梯度同时降低相对原图的 PSNR/SSIM，这是对原图作修改的结果，不自动等于算法失效。要结合局部图观察过冲、黑边、亮边及噪声放大。

## SFM 架构与预处理接口

![SFM 数据流与实验三边界](../data/output/lab3_latest/l3_architecture.png)

`preprocess(img_bgr: np.ndarray, cfg: dict) -> np.ndarray` 接收 uint8 BGR 数组，返回同尺寸同类型的全新 BGR 数组，不修改输入，不读写文件。配置规定滤波和锐化方法。已演示从原图读取为 BGR、生成含噪 BGR、调用预处理并保存结果。

本次预处理边界包括去噪与增强；特征、匹配、几何、点云、可视化是整体架构中的后续模块约定，没有在实验三实现。完整格式及异常约定见 architecture.md 和 interface_agreement.md。小组协商由实际参与者确认，本次提供已实现并验证的技术约定。

## 正式验证

| 检查 | 结果 |
| --- | --- |
| 固定种子高斯噪声可重复 | PASS |
| 固定种子椒盐噪声可重复 | PASS |
| 椒盐变更像素只能为 0 或 255 | PASS |
| 全部滤波和锐化输出保持尺寸和 uint8 | PASS |
| 参考图 PSNR=∞ SSIM=1 | PASS |
| 所有非同一图评分为有限有效数值 | PASS |
| preprocess 返回同尺寸 BGR 并保持输入 | PASS |
| 保存图像与所有对比图可回读 | PASS |
| 参考原文件 SHA-256 未改变 | PASS |

日志、原图前后哈希、噪声种子、版本、输出属性和参数见 evidence/lab3_latest/results.json；评分同时保存 quality.csv。源码与说明见 deliverables/lab3_source.zip。

## 复现与限制

统一复现文档 reproduction.md 覆盖实验一至三；统一图片要求 image_requirements.md 按实验列出素材条件。后续每完成一个实验必须更新这两个入口，此要求已写入项目 AGENTS.md。

个人结果仅保留 data/output/lab3_latest 和 evidence/lab3_latest 的最近一次完整运行；生成和校验失败时保留上次结果。输入图片继续保留，其他实验的最新结果不受本次运行影响。

当前参考图是动漫插画，不是无噪声传感器标定图；其原有纹理和压缩痕迹属于参考信号。效果结论不推广为所有建筑照片、真实噪声或 SFM 下游性能。更换个人图片后无需改源码，但图像宽高必须至少为 7 以计算当前 SSIM。
