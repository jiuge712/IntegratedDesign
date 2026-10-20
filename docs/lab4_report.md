# 实验四边缘检测与图像分割报告

运行时间：2026-10-20T19:51:21+08:00。程序版本 5.0.0。

本次完成 Sobel 3/5 核、三组 Canny、固定/Otsu/自适应阈值及手写 NMS/滞后连接对比。详细设计、编码规范和技术自走查已完成；课堂两两走查由实际参与者补充，待办见 user_tasks.md。

28 项数值/边界/命令行自检通过，正式检查 12 项通过；原始输入哈希保持不变。处理、绘图、回读和检查耗时 6969.984 ms。

## 输入与参数

| 图片角色 | 来源 |
| --- | --- |
| texture | D:\IntegratedDesign\project_i\data\input\photo.jpg |
| uneven | 用户提供文件：D:\IntegratedDesign\project_i\data\input\uneven_real.jpg |

| 参数 | 实际值 |
| --- | --- |
| illumination_left_gain | 0.35 |
| illumination_right_gain | 1.0 |
| sobel_kernels | [3, 5] |
| canny_pairs | [[50, 150], [100, 200], [150, 250]] |
| canny_blur_sigma | 1.0 |
| fixed_threshold | 128 |
| adaptive_block_size | 31 |
| adaptive_c | 5.0 |
| manual_pair_index | 1 |

清晰纹理图来自用户提供的插画。若 uneven 为 null，本次光照不均图通过从左到右的乘性增益派生，属于受控模拟；若配置真实路径则使用个人提供的图。报告与证据记录实际来源，不把模拟图描述为实拍照片。

![输入及光照不均版本](../data/output/lab4_latest/l4_input_compare.png)

## Sobel 梯度与核尺寸

用 CV_64F 分别计算 Gx/Gy，幅值为 hypot(Gx,Gy)，方向为 atan2(Gy,Gx)，单位弧度；数组 y 轴向下。原始带符号梯度与方向保存在 raw_gradients.npz。显示单方向图取绝对值，幅值归一化至 0–255；最大值为 0 时返回全黑图，避免恒定图除零。

每个核的显示图单独归一化，不能只根据显示亮度比较原始梯度大小。核为 5 的算子覆盖更大邻域、导数尺度也不同，原始幅值如下。

| 核尺寸 | 原始最大幅值 | 原始平均幅值 | 方向单位 |
| --- | --- | --- | --- |
| 3 | 865.7078 | 31.2611 | radians |
| 5 | 10071.0049 | 436.0744 | radians |

![两个核的X/Y及幅值图](../data/output/lab4_latest/l4_sobel_compare.png)

## Canny 双阈值参数实验

先显式高斯平滑（sigma=1.0），再调用 Canny，apertureSize=3、L2gradient=True。三组阈值共用相同输入，手写加分分支也共用该平滑设置。阈值作用于原始梯度幅值，不作用于已归一化的显示图。低阈值用于连接，高阈值用于选择强边缘种子。

| 低阈值 | 高阈值 | 边缘像素数 | 边缘比例 |
| --- | --- | --- | --- |
| 50 | 150 | 30976 | 3.8728% |
| 100 | 200 | 20650 | 2.5818% |
| 150 | 250 | 11104 | 1.3883% |

![三组双阈值对比](../data/output/lab4_latest/l4_canny_compare.png)

本次较高的双阈值保留较少边缘。低阈值组合有利于保留发丝、绳索和细纹理，也可能保留噪声；高阈值更强调明显轮廓，可能漏掉弱边缘。可先从 100/200 的中间设置观察，再结合目标轮廓、断裂和纹理量调整；密度更低不自动等于检测更准确。

## 固定阈值与 Otsu

固定阈值 T=128：gray>T 为 255，否则为 0。Otsu 用全局直方图最大化类间方差，返回实际自动阈值。二值区域表示亮度划分，不凭空赋予人物或物体语义。

| 场景 | 方法 | 阈值 | 白色比例 | 左半白色比例 | 右半白色比例 |
| --- | --- | --- | --- | --- | --- |
| texture | fixed | 128 | 67.7501% | 81.3873% | 54.1129% |
| texture | otsu | 128.0 | 67.7501% | 81.3873% | 54.1129% |
| uneven | fixed | 128 | 5.0765% | 7.7010% | 2.4521% |
| uneven | otsu | 66.0 | 41.4481% | 38.1375% | 44.7586% |
| uneven | adaptive | local | 86.4805% | 85.9114% | 87.0497% |

![清晰图固定与Otsu](../data/output/lab4_latest/l4_threshold_compare.png)

本次清晰图的 Otsu 阈值恰好等于固定阈值，两张分割图完全一致；这也是有效实验结果，并不为了制造差异改动阈值。

## 光照不均与自适应阈值

自适应阈值采用 ADAPTIVE_THRESH_GAUSSIAN_C，blockSize=31、C=5.0；局部阈值为邻域高斯统计减去 C。它能随局部亮度变化，而 Otsu 在整张图上只给一个阈值。

![光照不均下三种分割](../data/output/lab4_latest/l4_adaptive_compare.png)

左右区域的白色比例提供可复查统计，不是分割准确率。自适应结果可保留局部变化，也可能因窗口和 C 放大纹理或使均匀区变白；没有人工目标标注时不能断言“正确分割所有目标”或报告语义 IoU。

## 手写 NMS 与双阈值连接 加分对比

手写分支使用四个方向区间的 NMS，沿梯度方向比较邻点；一侧严格大于、另一侧大于等于以打破幅值平台，最外一圈置零。滞后连接以强边缘为种子，使用队列追踪八邻域中满足低阈值的弱边缘，孤立弱边缘舍弃。角度采用图像坐标，45° 对应 NW/SE 比较。

比较阈值为 [100, 200]。手写/API 不同像素为 66，比例 0.008252%，边缘集合 IoU=0.996811。

![平滑NMS手写与API边缘](../data/output/lab4_latest/l4_manual_compare.png)

这些数值表示两种实现的一致性，不是对真实边缘标签的准确率。方向量化、相等幅值处理、边界和阈值等号策略会产生差异，不宣称加分版本逐像素复刻 OpenCV。

## 软件工程产出与正式检查

detailed_design.md 覆盖 L3/L4 函数输入、输出、算法、异常和数据流；coding_standards.md 规定命名、注释、模块职责与验证方式；design_walkthrough.md 记录至少三条已落实的技术自走查意见，并保留真实两两走查填写位置。

| 检查 | 结果 |
| --- | --- |
| Sobel 原始梯度保留有限 float64 | PASS |
| Sobel 幅值等于 sqrt(Gx²+Gy²) | PASS |
| Sobel 显示图保持尺寸和 uint8 | PASS |
| 三组 Canny 均为同尺寸 0/255 二值 | PASS |
| 固定阈值符合严格大于 T | PASS |
| Otsu 返回有效阈值和匹配的分割图 | PASS |
| 自适应结果为同尺寸 0/255 二值 | PASS |
| 手写 NMS 有限非负且未放大原始幅值 | PASS |
| 手写滞后连接输出为同尺寸二值 | PASS |
| 浮点梯度归档回读一致 | PASS |
| 全部输出图片可回读且处理图无损 | PASS |
| 原始输入 SHA-256 保持不变 | PASS |

results.json 与 metrics.csv 保存输入哈希、参数、阈值和密度；raw_gradients.npz 保存浮点梯度/方向、NMS及可用的增益图。PNG 回读校验无损，实际命令见 run.log。所有证据位于 evidence/lab4_latest。

## 复现与待完成事项

统一 reproduction.md 和 image_requirements.md 已覆盖实验一至四，后续每完成一个实验都继续更新。个人结果只保留 data/output/lab4_latest 的最近一次完整运行，校验失败保留旧结果，其他实验不覆盖。源码包为 deliverables/lab4_source.zip。

你需要亲自完成的真实课堂活动、课程要求下的实拍素材/截图及最终提交步骤记录在 user_tasks.md；代码和技术材料已完成，不编造小组成员、签名或未发生的走查。
