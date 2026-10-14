# 实验五设计与API说明

依据指导书“实验五_角点检测与尺度空间.docx”。主入口 run_lab5.py 加载配置与图片，调用 feature.py、lab5_scale.py，运行 pytest，校验图片/数组/输入哈希，最后通过 LatestRun('lab5') 发布最新结果并写报告。

## 角点接口与数学

输入为非空二维 uint8；读取边界允许 BGR/BGRA 并显式转灰度，核心算法拒绝隐式类型/通道转换。坐标约定 (x,y)，数组访问 img[y,x]，返回 int32、shape=(N,2)，无角点返回 (0,2)。非数组 TypeError；空图、非uint8、颜色数组及非法参数 ValueError。正式入口最短边≥16；底层Harris/Shi极小图安全返回空集。

| 接口 | 输出 | 关键行为 |
| --- | --- | --- |
| harris_response(img,k,block_size,ksize) | float32 H×W 的R | cornerHarris，REFLECT_101；k在(0,0.25)，窗口≥2，Sobel核3/5/7 |
| select_points(response,quality_level,min_distance,max_points) | int32 N×2 | R>quality×max(R)，3×3局部峰，按响应排序和欧氏最小距离抑制；相等分数按y/x稳定排序 |
| harris_corners(img,k=0.04,...) | int32 N×2 | 串联前两步；默认距离10、最多500点 |
| shi_tomasi_corners(img,max_corners=100,...) | int32 N×2 | goodFeaturesToTrack，useHarrisDetector=False；坐标四舍五入并限制在图内 |
| fast_corners(img,threshold=20) | int32 N×2 | FAST、nonmaxSuppression=True；允许理想二值棋盘检测为0 |
| manual_harris_response(img,...) | R、λ1/λ2、trace、determinant 字典 | Sobel/boxFilter构造M，不调用cornerHarris |

结构张量 M=[[a,b],[b,c]]，a=ΣIx²、b=ΣIxIy、c=ΣIy²；R=ac−b²−k(a+c)²。λ1/λ2由二阶矩阵的解析特征值计算。手写Sobel使用1/(255×blockSize×2^(ksize−1))缩放，boxFilter normalize=False，与API的uint8约定对齐。测试既比较非规则随机纹理的数值，也验证特征值重建trace/determinant，不仅检查棋盘图。

Harris阈值像素与抑制后的角点分别统计。Shi-Tomasi的100为上限，不制造额外点。检测器阈值和上限不同，数量不能直接当准确率；FAST接口也有KeyPoint响应，不声称其没有任何分数。记录单次耗时，不据此给出稳定性能排名。

## 尺度与差分接口

| 接口 | 输出 | 关键行为 |
| --- | --- | --- |
| gaussian_pyramid(img,levels=4) | uint8图像列表 | 第0层复制原图，后续pyrDown；尺寸ceil(n/2)，允许1至8层 |
| adjacent_dog(fine,coarse) | float32，fine同shape | coarse先转float32再INTER_LINEAR放大，计算coarse_up−fine |
| dog_displays(dog) | absolute/signed uint8 | |D|映射0–255；signed零为128，保留原始带符号数组；全零无除零 |
| dog_candidates(dog,...) | int32 N×2 | 对|D|选空间局部峰，默认质量0.1、间距6、最多150；平台按稳定次序取舍 |
| gaussian_dogs(img,sigma=1.6,scale_ratio=2^(1/3)) | 5张float32 DoG及6个σ | 同尺寸原图分别GaussianBlur，D_i=G_(i+1)−G_i |
| scale_extrema(dogs,contrast_threshold=2) | float64 N×4 | [x,y,DoG索引,带符号响应]，与空间/相邻尺度26邻点严格比较，排除首尾尺度/边界/等值平台 |

相邻pyrDown层resize差分为教学近似，不是相同采样网格的严格Gaussian DoG；因此另提供同尺寸Gaussian DoG分支。未实现完整SIFT中的多octave、亚像素、边缘剔除、描述子和匹配。坐标证据将3D极值的x/y/index明确序列化成整数。

## 测试、异常与文件责任

test_feature.py覆盖指导书五类必测，并检查49个已知交点的唯一匹配、参数、距离/数量上限、手写/API及输入保持。test_lab5_scale.py覆盖奇数金字塔、负差分、恒定图、26邻点的正负极值、边界/平台、非法参数、CLI错误和最新结果成功替换/失败保留。pytest.ini按项目src发现用例，整个测试套件同时回归实验二至四。pytest 9的JUnit总数含unittest子用例，报告区分主用例和子用例。

图片路径按项目根目录解释，禁止把原图指定到输出、证据或文档目录。prepare_chess.py是经用户授权的素材准备例外，只用排他创建新文件，已有不同内容拒绝覆盖；常规处理仍禁止写入data/input。来源记录用SHA-256与实际输入核对，换图不会继承旧棋盘的来源、格子数或交点真值。

run_lab5.py使用临时输出/证据目录完成pytest、PNG和NPZ回读、坐标/数组/尺寸及哈希检查后才替换lab5_latest。失败保留前次完整结果，其他实验不覆盖。默认图像27张；texture=null时省略纹理对比图，变成26张。代码、配置、pytest.ini和Markdown放入源码ZIP，环境/输入/输出/证据不放入。

## 官方参考

[OpenCV 特征检测API](https://docs.opencv.org/4.x/dd/d1a/group__imgproc__feature.html)说明cornerHarris及goodFeaturesToTrack；[FAST API](https://docs.opencv.org/4.x/df/d74/classcv_1_1FastFeatureDetector.html)说明阈值和非极大值抑制。[OpenCV滤波与pyrDown](https://docs.opencv.org/4.x/d4/d86/group__imgproc__filter.html)用于GaussianBlur、Sobel、boxFilter与金字塔。

手写响应缩放参考[OpenCV corner.cpp](https://github.com/opencv/opencv/blob/4.x/modules/imgproc/src/corner.cpp)，本机OpenCV 5.0.0已通过实际数值测试；源码版本差异以测试结果为准。[pytest调用文档](https://docs.pytest.org/en/stable/how-to/usage.html)用于python -m pytest和JUnit证据。
