# 实验五：角点检测与尺度空间

运行时间：2026-10-14T21:09:09+08:00；程序版本 5.0.0。

指导书：实验五_角点检测与尺度空间.docx。完成 Harris 三组 k、Shi-Tomasi、FAST 补充对比、四层 pyrDown 金字塔、相邻层浮点差分及候选区域、pytest 与手写 Harris 加分对比。

本次 pytest 共 107 项用例及 15 项子用例，失败 0、错误 0、跳过 0；正式检查 14 项全部通过。测试日志/JUnit 为 evidence/lab5_latest/pytest.log、pytest.xml。

## 素材与参数

棋盘来源：用户明确授权程序绘制的标准棋盘格（哈希匹配来源记录）。

你已授权程序绘制标准棋盘作为正式素材：8×8 格、每格 40 像素，320×320 灰度PNG，共有 49 个内部交点。不是实拍照片；换图后按新文件重新判断来源。

| 输入角色 | 实际路径 | SHA-256 |
| --- | --- | --- |
| chess | D:\IntegratedDesign\project_i\data\input\chess.png | 22f716138ce9e00efedf9f6e1803095237b13586f3282798a1a67fffe287f088 |
| texture | D:\IntegratedDesign\project_i\data\input\photo.jpg | acc5a25095f7bcdd150c85bad654e6c13cbd20e9d5a670f1780086207b449ae1 |

| 参数 | 值 |
| --- | --- |
| chess | data/input/chess.png |
| texture | data/input/photo.jpg |
| harris_k_values | [0.04, 0.06, 0.1] |
| block_size | 2 |
| sobel_ksize | 3 |
| quality_level | 0.01 |
| min_distance | 10.0 |
| max_harris_corners | 500 |
| max_shi_corners | 100 |
| fast_threshold | 20 |
| pyramid_levels | 4 |
| dog_sigma | 1.6 |
| dog_scale_ratio | 1.2599210498948732 |
| dog_contrast_threshold | 2.0 |
| max_dog_candidates | 150 |

## Harris 参数实验

M 为局部梯度二阶矩阵，R=det(M)−k·trace(M)²。响应先按相对最大正响应阈值筛选，再做 3×3 局部最大值和最小距离抑制，返回 int32 的 (x,y) 坐标；阈值像素数不等于角点个数。

| k | 角点数 | 原始最大 R | 原始最小 R | 阈值像素数 | 检测及选点 ms |
| --- | --- | --- | --- | --- | --- |
| 0.04 | 49 | 0.07812500 | -0.04000000 | 441 | 2.9121 |
| 0.06 | 49 | 0.07031250 | -0.06000000 | 441 | 2.3438 |
| 0.1 | 49 | 0.05468750 | -0.10000000 | 441 | 2.3025 |

![Harris三组参数](../data/output/lab5_latest/l5_harris_compare.png)

固定 M 时 k 增大会降低 R。但每组阈值是各自最大 R 的 1%，不是相同绝对阈值；规则棋盘的交点相似，所以三组角点数量可以相同。不能将本例概括为“k 越大角点必然越少”。

## Shi-Tomasi 与 FAST

Shi-Tomasi 以 min(λ1,λ2) 选择局部强角点，maxCorners=100 是上限；若只有49个合适交点，结果不需凑满100。FAST 使用圆周亮暗比较，threshold=20、非极大值抑制开启。

| 检测器 | 棋盘角点数 | 单次耗时 ms |
| --- | --- | --- |
| harris_0.04 | 49 | 2.9121 |
| harris_0.06 | 49 | 2.3438 |
| harris_0.1 | 49 | 2.3025 |
| shi_tomasi | 49 | 0.9148 |
| fast | 0 | 0.0553 |

![检测器对比](../data/output/lab5_latest/l5_detector_compare.png)

精确二值棋盘的交点可能不满足 FAST 连续圆周条件，结果为0也如实保留。配置提供纹理图时另做对照，避免把理想棋盘上的结果推广到所有图。计时包含 Python 包装/选点，单次测量受缓存和调度影响，不构成性能排名。

| 检测器 | 插画角点数 |
| --- | --- |
| harris_0.04 | 225 |
| harris_0.06 | 213 |
| harris_0.1 | 197 |
| shi_tomasi | 100 |
| fast | 1635 |

![个人插画检测器对照](../data/output/lab5_latest/l5_texture_compare.png)

## λ1–λ2 平面与手写 Harris

两个特征值都小对应平坦区域；一大一小对应边缘；两个都大对应角点。散点按本次二阶矩阵取样，不把显示位置作为检测阈值。

![特征值平面](../data/output/lab5_latest/l5_lambda_plane.png)

手写分支使用 Sobel、非归一化 boxFilter 构造 M，R=ac−b²−k(a+c)²，不调用 cornerHarris。与 API 原始 R 的相关系数为 1.0，最大绝对差为 0。恒定响应时相关系数无定义，JSON 用 null 表示，改用绝对差验证。

![手写与API响应](../data/output/lab5_latest/l5_manual_compare.png)

已按 uint8 的255及 Sobel/窗口尺度归一化；浮点运算顺序可导致微小差异。本次数值一致性通过，不是对任意OpenCV版本逐位一致的保证。

## 四层高斯金字塔

| 层 | 宽×高 | Harris角点数 |
| --- | --- | --- |
| 0 | 320×320 | 49 |
| 1 | 160×160 | 49 |
| 2 | 80×80 | 49 |
| 3 | 40×40 | 16 |

![金字塔](../data/output/lab5_latest/l5_pyramid_compare.png)

第0层为原图，后续层 pyrDown：先低通再约2倍降采样；奇数尺寸取 ceil(n/2)。对子层使用同样的 blockSize、Sobel核和 minDistance（单位为当前层像素），会影响可保留的角点数。图板各层缩放到自己的面板显示，真实尺寸见表和单层文件。不能由四层都出现角点直接宣称尺度不变。

## 相邻层 DoG 近似与候选区域

先将粗层 float32 resize 到细层尺寸，再计算 coarse_up−fine，保留正负响应。绝对值图显示强度，signed图用128表示零、亮/暗分别表示正/负；原始差分保存在 raw_arrays.npz。直接对uint8做cv2.subtract会饱和负值，本实现避免该问题。

| 相邻层 | 最小值 | 最大值 | 空间候选数 |
| --- | --- | --- | --- |
| 0→1 | -127.125 | 127.125 | 150 |
| 1→2 | -110.500 | 110.500 | 150 |
| 2→3 | -106.625 | 106.625 | 77 |

![相邻层差分及候选](../data/output/lab5_latest/l5_dog_compare.png)

黄色圈为 |DoG| 的空间局部峰值区域（质量阈值0.1、间距6像素），不是完整SIFT关键点。候选数受 max_dog_candidates 上限限制，达到上限时不能由数量比较真实极值总量；等值峰按行列次序取舍。随着降采样，交界逐渐模糊、细节合并，候选区域位置/数量可能变化。坐标记录含当前层坐标和按2^level映射的原图坐标。

另外在原图同尺寸计算六个 Gaussian σ、五张真正 Gaussian DoG，对中间三层与26邻点做严格正/负极值及对比度阈值筛选；等值平台不算严格极值，首尾尺度和最外像素边界不参与。

σ=[1.6, 2.015873679831797, 2.5398416831491195, 3.2, 4.031747359663594, 5.079683366298239]；三维候选共 196 个。

![同尺寸Gaussian DoG](../data/output/lab5_latest/l5_gaussian_dog_compare.png)

这里未实现多octave、亚像素定位、边缘响应剔除、方向/描述子和匹配，因此只能称尺度空间候选演示，不报告SIFT准确率或尺度不变性。

## 自动检查与证据

| 检查 | 结果 |
| --- | --- |
| pytest 全部通过且无跳过 | PASS |
| Harris 三组 k 坐标整数且不越界 | PASS |
| Shi-Tomasi 坐标合法且数量不超过配置上限 | PASS |
| FAST 坐标合法（允许零结果） | PASS |
| 手写 R 与 API 数值一致 | PASS |
| 特征值重建 trace 和 determinant | PASS |
| 四层尺寸满足 ceil(n/2) | PASS |
| 相邻差分保留 float32 且与细层同尺寸 | PASS |
| DoG 空间候选坐标合法 | PASS |
| Gaussian DoG 五层和尺度候选边界合法 | PASS |
| 所有原始数组均有限 | PASS |
| NPZ 回读原始数组一致 | PASS |
| 全部 PNG 可回读 | PASS |
| 原始输入 SHA-256 不变 | PASS |

results.json 保存参数、输入哈希和统计；coordinates.json 保存角点/候选坐标；metrics.csv 为检测器数据；raw_arrays.npz 为原始响应、特征值和DoG。所有PNG均通过回读；manifest.json记录输出哈希。pytest.log是真实运行文本，不冒充终端截图。

## Git、复现与提交

按 feature/l5-corner 分支开发、提交并合并main；远程目标为用户指定仓库，实际提交及推送状态见 lab5_git_workflow.md 和 evidence/lab5_git.log。复现时用git log、git remote -v及git ls-remote检查当前状态，不将本地合并当作远程推送证据。

统一 reproduction.md / image_requirements.md 已覆盖实验一至五。最新结果位于 data/output/lab5_latest 与 evidence/lab5_latest；失败保留前次完整结果，原图不变。源码包为 deliverables/lab5_source.zip，图片/输出/证据另交。

你本人需复现、截取真实pytest通过画面、填写个人信息并提交；若老师要求实拍棋盘则补实拍素材。user_tasks.md中的既有及新增事项默认未完成，仅在你明确告知后更新。
