# 实验四 API 与参数约定

已检查OpenCV官方文档并在本机OpenCV 5.0.0调用验证。以下接口输入按本实验统一为单通道uint8。

## Sobel

`cv2.Sobel(src, ddepth, dx, dy[, dst[, ksize[, scale[, delta[, borderType]]]]]) -> dst`。本实验ddepth=CV_64F，dx/dy分别为1/0和0/1，核3与5；保留负梯度，hypot计算幅值，atan2计算弧度方向。显示时再归一化，常量图避免除零。

依据：[OpenCV图像滤波](https://docs.opencv.org/4.x/d4/d86/group__imgproc__filter.html)。

## Canny

`cv2.Canny(image, threshold1, threshold2[, edges[, apertureSize[, L2gradient]]]) -> edges`。较低值负责连接，较高值负责强边缘种子。L2gradient=True使用欧氏梯度范数，默认False则为L1；本实验显式选True、apertureSize=3并先高斯平滑。程序要求low<high，不默默交换用户参数。

依据：[OpenCV特征检测及Canny](https://docs.opencv.org/4.x/dd/d1a/group__imgproc__feature.html)。

## threshold 与 adaptiveThreshold

`cv2.threshold(src, thresh, maxval, type[, dst]) -> retval,dst`。固定THRESH_BINARY中src>thresh才是maxval；加THRESH_OTSU返回实际全局自动阈值。当前uint8灰度保证256bin解释一致。

`cv2.adaptiveThreshold(src, maxValue, adaptiveMethod, thresholdType, blockSize, C[, dst]) -> dst`。本实验maxValue=255、Gaussian局部统计、THRESH_BINARY，窗口默认31奇数，局部统计减C=5。光照变化下局部阈值更灵活，但不是语义目标识别。

依据：[OpenCV阈值变换](https://docs.opencv.org/4.x/d7/d1b/group__imgproc__misc.html)。

原始梯度阈值、独立显示归一化、输入光照来源和无标签情况下的统计含义已写入报告与详细设计，避免把API参数或图像观感当作准确率证据。
