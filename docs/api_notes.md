# 实验二 OpenCV API 调研记录

调研日期：2026 年 10 月 13 日。运行环境使用 OpenCV 5.0.0；已在线检查 OpenCV 官方公开 Python 接口说明，并在本机实际调用以下接口。数组只接受单通道 uint8；彩色素材先转灰度。

## calcHist

Python 签名：`cv2.calcHist(images, channels, mask, histSize, ranges[, hist[, accumulate]]) -> hist`。

本实验调用 `cv2.calcHist([gray], [0], None, [256], [0,256])`：images 为图像列表；channels=[0] 选择灰度通道；mask=None 统计整张图；histSize=[256] 表示 256 个灰度区间；ranges=[0,256] 上界不含 256；accumulate 默认 False，重新统计而非累加此前结果。单通道统计返回 256×1 的 float32 计数数组，图中纵轴是计数，归一化后才是概率。

验证时把计数总和与图像像素数比较，也用已知灰度数组验证各个 bin。彩色图可以通过 channels 指定通道统计，本实验先转灰度便于统一比较；“彩色图直接调用任何 calcHist 都会报错”不是通用 API 规则。

依据：[OpenCV calcHist 官方说明](https://docs.opencv.org/4.x/d6/dc7/group__imgproc__hist.html)。

## equalizeHist

Python 签名：`cv2.equalizeHist(src[, dst]) -> dst`。

src 必须为 8 位单通道数组，输出具有同样尺寸和类型。灰度 uint16 和浮点输入应明确拒绝，不能假定此 API 会保留 16 位像素。手写版本统计直方图和累计分布，扣除第一个非零 CDF 值并映射到 0–255；恒定图像保持原值以避免除零。

验证时分别对偏暗图和正常图计算 int16 差值、最大误差、差异像素数和差异比例。均衡化改变灰度分布，不保证每个灰度 bin 都有同样数量，也不保证任何图像的观感更佳。

依据：[OpenCV equalizeHist 官方说明](https://docs.opencv.org/4.x/d6/dc7/group__imgproc__hist.html)。

## addWeighted

Python 签名：`cv2.addWeighted(src1, alpha, src2, beta, gamma[, dst[, dtype]]) -> dst`。

本实验调用 `cv2.addWeighted(A, 0.6, B, 0.4, 0)`，计算 `0.6*A+0.4*B+0`。alpha 与 beta 为两张图的权重，gamma 为输出加性偏移，**不是伽马校正指数参数**；dtype 省略时按输入类型输出。本实验要求图像尺寸、类型相同，并选用 alpha+beta=1 的凸组合。uint8 输出会取整并饱和到有效范围。

cv2.add 对 uint8 做饱和加法；NumPy 的 uint8 相加按模 256 回绕，两者不等价。实验用 250+20 的数值测试验证结果分别为 255 与 14。

依据：[OpenCV 数组运算和 addWeighted 官方说明](https://docs.opencv.org/4.x/d2/de8/group__core__array.html)。

## 指导书中需要统一的约定

伽马统一采用 `255*(r/255)^(1/gamma)`。在这一公式下 gamma>1 提亮，gamma<1 压暗；指导书前部图例及原理中的个别方向说明不能替代它明确指定的公式。

CDF_min 应取**第一个非零计数对应的累计值**，而不总是对包括空 bin 的 CDF 取全局最小值。直接 CDF、是否扣除 CDF_min、截断和四舍五入的选择均会影响与 API 的差异。程序保存直接 CDF 版本与归一化版本，并单独检查恒定图像。
