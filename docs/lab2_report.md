# 实验二图像基本运算与直方图均衡化报告

运行时间：2026-10-13T21:16:38+08:00；程序版本 2.0.0。
本次使用用户提供的动漫插画。按用户确认的方案，由同一原图派生偏暗与低对比度测试图，不将它们描述为两次独立拍摄的照片。

正式检查 13 项，全部通过；原始输入 SHA-256 保持不变。处理与绘图总耗时 4596.401 ms。

## 输入与参数

| 项目 | 实际值 |
| --- | --- |
| normal | D:\IntegratedDesign\project_i\data\input\photo.jpg |
| dark | 从 normal 派生：clip(0.45*gray,0,255) |
| low_contrast | 从 normal 派生：clip(0.3*gray+80,0,255) |
| alpha | 1.5 |
| beta | 30.0 |
| gamma_bright | 2.2 |
| gamma_dark | 0.5 |
| blend_weight | 0.6 |

## 灰度变换

线性变换使用浮点计算后 clip 到 [0,255] 并转 uint8；避免直接在 uint8 中计算造成回绕。伽马采用指导书统一公式 `255*(r/255)^(1/gamma)`，gamma=2.2 提亮，gamma=0.5 压暗。转换采用截断，与指导书代码一致。

关键实现：`np.clip(alpha*image.astype(np.float64)+beta,0,255).astype(np.uint8)`；`255*(image/255.0)**(1/gamma)`。代码见 src/lab2_transform.py。

![线性与伽马对比](../data/output/lab2_latest/l2_transform_compare.png)

![两种伽马方向](../data/output/lab2_latest/l2_gamma_compare.png)

![灰度变换映射曲线](../data/output/lab2_latest/l2_transform_curves.png)

## 图像代数运算

对同尺寸 uint8 灰度图 A（偏暗）与 B（正常）进行运算。NumPy 加法按模 256 回绕；cv2.add 饱和到 255。混合采用 cv2.addWeighted；减法分别展示回绕、饱和截断与绝对差。补充归一化乘法 A*B/255 与比例除法 128*A/B；除数为 0 时输出 0。

加法回绕与饱和结果不同的像素占比为 22.0554%；除数为零的像素数为 0。

本次 A 由 B 缩暗得到，A 的每个像素都不大于 B，所以饱和减法 A-B 的结果为全黑；绝对差另图展示亮度差异。这符合截断规则。

关键调用：`np.add(A,B)`、`cv2.add(A,B)`、`cv2.addWeighted(A,w,B,1-w,0)`、`cv2.subtract(A,B)`。代码见 src/lab2_arith.py。

![代数运算对比](../data/output/lab2_latest/l2_arith_compare.png)

![减法乘法与除法](../data/output/lab2_latest/l2_arith_extra.png)

## 直方图统计

使用 `cv2.calcHist([gray],[0],None,[256],[0,256])`，横轴为灰度值，纵轴为像素数量；PDF 为直方图除以像素数，CDF 为 PDF 的累加。低对比度版本通过缩放灰度范围生成，因此分布更集中；不是另一张独立照片。

![暗图正常图低对比度图及直方图](../data/output/lab2_latest/l2_hist_compare.png)

| 图像 | 均值 | 标准差 | 灰度范围 | 信息熵 bit | 255 像素比例 |
| --- | --- | --- | --- | --- | --- |
| normal | 142.9223 | 46.9217 | 7–255 | 7.3866 | 0.01% |
| dark | 63.8377 | 21.1168 | 3–114 | 6.217 | 0.00% |
| low_contrast | 122.4261 | 14.0797 | 82–156 | 5.6501 | 0.00% |
| linear | 125.5053 | 31.6783 | 34–201 | 6.217 | 0.00% |
| gamma_bright | 133.0638 | 22.7971 | 33–176 | 6.0663 | 0.00% |
| gamma_dark | 17.2732 | 10.1812 | 0–50 | 5.1083 | 0.00% |
| equalized_dark | 129.7142 | 74.0468 | 0–255 | 6.1635 | 0.21% |
| equalized_normal | 128.4702 | 73.7941 | 0–255 | 7.1301 | 0.21% |

## 手写均衡化与 API 对比

手写版本用 np.bincount 统计频数、累计 CDF，取第一个非零频数对应的 CDF_min，计算 `round((CDF-CDF_min)*255/(N-CDF_min))`，再查表映射。计算保留浮点精度，结果为单通道 uint8。恒定图像保持不变，避免分母为 0。

指导书还给出不扣 CDF_min 的直接 CDF 公式，此版本另存 direct_cdf 文件作原理比较。扣除 CDF_min 并处理恒定图，有助于与 cv2.equalizeHist 的实际行为比较；不将全黑图错误地变成全白。

差值先转 int16 再相减，避免 uint8 的负值回绕。允许最多 1 个灰度级的舍入差，记录所有差异像素而非只显示图像。代码见 src/lab2_hist.py。

| 输入 | 最大差值 | 差异像素数 | 差异比例 | 平均绝对误差 |
| --- | --- | --- | --- | --- |
| dark | 0 | 0 | 0.000000% | 0.0 |
| normal | 0 | 0 | 0.000000% | 0.0 |

![两张输入的原图手写API及对应直方图](../data/output/lab2_latest/l2_eq_compare.png)

均衡化改变亮度分布，并不保证视觉更自然；对亮度正常图也可能放大纹理与压缩噪声。应结合均值、标准差和并排图评价，而不是宣称任何输入都更好看。

## 需求评审与 API 调研

docs/mvp_review.md 对实验一的全部需求逐项给出 MVP 必须、可推迟或删除的范围判断，并记录三条以上技术评审意见。当前完成的是技术自评，课堂小组互评需要同学实际参与后另行填写，不编造参与者和课堂记录。docs/api_notes.md 记录三个指定 API 的签名、参数与官方来源。

## 正式验证与证据

| 检查 | 结果 |
| --- | --- |
| 灰度变换保持尺寸及 uint8 类型 | PASS |
| gamma_bright 的方向符合 1/gamma 公式 | PASS |
| gamma_dark 的方向符合 1/gamma 公式 | PASS |
| NumPy 加法符合模 256 | PASS |
| OpenCV 加法符合饱和截断 | PASS |
| 混合值处于两图像素范围内 | PASS |
| 减法与绝对差符合预期 | PASS |
| 零除数输出为零 | PASS |
| 暗图正常图低对比度图直方图计数完整 | PASS |
| dark 手写均衡化与 API 最大差值 ≤1 | PASS |
| normal 手写均衡化与 API 最大差值 ≤1 | PASS |
| 处理结果无损回读、所有对比图可解码 | PASS |
| 原始输入 SHA-256 保持不变 | PASS |

22 项数值、边界与结果替换自检见 evidence/lab2_self_test.log。正式运行的结果属性、输入前后哈希、参数、环境与检查结论见 evidence/lab2_latest/results.json，实际命令见 run.log，完整直方图/CDF/LUT见 histograms.json。

## 输出保留与复现

个人结果固定保存至 data/output/lab2_latest，证据至 evidence/lab2_latest。每次成功运行替换此前完整结果；校验失败保留上次完整结果并明确报错。原始输入不删除。实验一独立保存在 lab1_latest。复现步骤和图片替换方法见 docs/lab2_reproduction.md。

## 结论与限制

本次完成实验二全部必做技术任务及提交材料。图像操作只针对单通道 uint8；不同尺寸的运算输入明确拒绝，需用户先对齐。派生素材用于受控对比，不能支持不同真实拍摄场景上的泛化结论。自适应局部伽马为指导书加分项，本次不纳入 MVP。
