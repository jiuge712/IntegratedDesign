# 实验七 特征匹配与误匹配分析

运行时间：2026-10-27T20:33:53+08:00；版本7.0.0。

依据实验七_特征匹配与误匹配分析.docx，完成SIFT、BF/KNN、ratio三档、最近邻互查、双向ratio、距离阈值补充、FLANN速度对比、随机抽样及人工标注工具。真实结对评审和人工误配标签由本人/同学提供；技术自走查不冒充结对活动。

自动验证：187项主用例、15项子用例，失败0、错误0、跳过0；正式检查14项通过。

## 个人照片与SIFT

| 角色 | 实际路径 | 原始shape | 工作shape | SIFT实例 |
| --- | --- | --- | --- | --- |
| image1 | D:\IntegratedDesign\project_i\data\input\seven-1.jpg | [3072, 4096, 3] | [3072, 4096, 3] | 33057 |
| image2 | D:\IntegratedDesign\project_i\data\input\seven-2.jpg | [3072, 4096, 3] | [3072, 4096, 3] | 29086 |

两张图分别使用用户提供的seven-1.jpg、seven-2.jpg，SHA-256在results.json；max_input_side=0，0为保留原尺寸，非0仅在超出上限时等比缩小，不改原文件。均为图书馆场景，有大面积共同建筑；人物、反射和遮挡不同，不能将其当作已知仿射派生图。未用匹配数捏造精确重叠率。

SIFT配置：{'nfeatures': 0, 'nOctaveLayers': 3, 'contrastThreshold': 0.04, 'edgeThreshold': 10.0, 'sigma': 1.6, 'enable_precise_upscale': False}。描述子为float32 N×128，原关键点与描述子不截断，坐标在各自工作图上；矩阵记录原照片到工作图像素中心的映射。

![输入和特征](../data/output/lab7_latest/l7_inputs_keypoints.png)

## KNN与提纯

BFMatcher使用NORM_L2、crossCheck=False，双向knnMatch(k=2)。前向最近邻候选33057条，具有完整两邻点的查询33057个；只有完整两邻点且d2>0时才做d1<阈值×d2。重复的零距离两邻点视为歧义，避免除零；目标只有一个描述子时仍保留最近邻信息，但不伪造ratio。

| ratio阈值 | 单向ratio（保留率） | 互为最近邻且前向ratio | 双向ratio（最终） | 最终/原始候选 | 人工样本明确数/抽取数 | 样本误匹配率 |
| --- | --- | --- | --- | --- | --- | --- |
| 0.6 | 83（0.25%） | 81 | 58 | 0.18% | 0/50 | 待人工标注 |
| 0.75 | 344（1.04%） | 284 | 175 | 0.53% | 0/50 | 待人工标注 |
| 0.9 | 4102（12.41%） | 2281 | 1148 | 3.47% | 0/50 | 待人工标注 |

“互为最近邻”要求A→B和B→A首邻点互指；“双向ratio”还要求两边都过同一ratio阈值，后者是指导书步骤3示例的实际行为，更严格。不能在BFMatcher(crossCheck=True)上直接做k=2；本实现显式反向匹配。上表人工误匹配率的总体为各阈值“双向ratio最终集合”，不是原始KNN或单向ratio集合。

默认展示阈值0.75，绝对L2距离上限max_distance=None。候选、ratio与最终三张图都以固定seed均匀抽取最多50条展示，全部匹配数见表/JSON；图中灰色/蓝色表示处理阶段，不能将蓝色直接解释为人工确认正确。

![提纯前后比较](../data/output/lab7_latest/l7_before_after.png)

![阈值数量对比](../data/output/lab7_latest/l7_threshold_counts.png)

![最近邻距离比](../data/output/lab7_latest/l7_ratio_distribution.png)

比值越低表示最近邻比次近邻更独特，是区分度指标；建筑重复窗格、反射和移动人物仍可能导致误配。宽阈值通常保留更多匹配，也接受更多歧义；降低阈值与互查可能减少误配，同时也丢失真实对应。没有人工标签时不据数量宣布“准确率显著上升”。

## 绝对距离补充

| L2上限 | 默认ratio最终集合保留数 |
| --- | --- |
| 100.0 | 32 |
| 200.0 | 158 |
| 300.0 | 175 |

距离阈值基于OpenCV实际缩放的SIFT L2值，不假定单位范数，也不把它与ratio阈值混为一谈。绝对距离筛选不能提供正确标签。

## BF与FLANN加分对比

| 后端 | 双向构建+KNN中位ms | 最小ms | 重复次数 |
| --- | --- | --- | --- |
| bf | 1650.8617 | 1636.9518 | 3 |
| flann | 1142.8429 | 1138.2425 | 3 |

先分别预热，再测双向匹配，包含构造和FLANN索引时间；不包括SIFT提取/绘图/人工标注。FLANN KD-tree trees=5、checks=50、随机seed=7。

FLANN与BF在可比较查询上的首邻点索引一致率51.96%；默认阈值最终配对Jaccard=0.8316。FLANN近似搜索可能改变第一/第二邻点和ratio，不能只比较速度宣称结果完全一致；本机时延不代表其他机器性能。

## 人工误匹配率与操作方法

每个阈值最终集合均匀无放回抽50对，随机seed=7，不足则全取；不同组重复抽中的同一配对共用标签。共需查看137个唯一配对。固定配对ID绑定输入哈希、工作尺寸、SIFT配置、OpenCV版本、关键点及描述子；换图/提取变化后旧标签拒绝使用。

打开data/output/lab7_latest/annotate.html，可调局部观察半径或全图定位，在紫色十字处核对是否为同一物理点。填写真实标注者，按正确/错误/不确定逐对记录；导出CSV放入data/annotations，按reproduction.md用--labels重跑。每组另有5张sample_阈值_页号.png样本页和labels_template.csv。

只在该组所有抽取样本都明确标为correct/incorrect后输出误配率=incorrect/(correct+incorrect)，并给出Wilson 95%区间；uncertain不当作错误或正确，未完成时率为null/“待人工标注”。不足50的样本会明确说明未满足50对要求；不合并不同阈值样本伪装成每组50对。

阈值0.6：correct=0，incorrect=0，uncertain=0，未标=50，误匹配率=待人工标注，95%区间=None；50对条件完成=False。
阈值0.75：correct=0，incorrect=0，uncertain=0，未标=50，误匹配率=待人工标注，95%区间=None；50对条件完成=False。
阈值0.9：correct=0，incorrect=0，uncertain=0，未标=50，误匹配率=待人工标注，95%区间=None；50对条件完成=False。

当前没有人工标签的组不提供虚构误配率，也不把互查、ratio、RANSAC或单应性内点当人工真值。人工完成后才基于数量与抽样误配率作最终阈值选择；0.75只是本次默认工作点。实验八的RANSAC与图像拼接未执行。

## 代码评审与缺陷

lab7_code_review.md提供正确性/边界/性能/可读性清单、至少5条明确标为技术自走查的意见及防护验证，并保留真实结对记录。defects.md登记编号、日期、位置、严重度、状态、处理者和验证；真实结对意见、修复人和日期由参与者填写，不伪造同学评审。个人待办见user_tasks.md。

## 自动检查与复现

| 检查 | 结果 |
| --- | --- |
| pytest全部通过无跳过 | PASS |
| 两图描述子N×128与关键点逐行对应 | PASS |
| 前后向KNN覆盖全部查询 | PASS |
| 所有匹配索引合法 | PASS |
| 三阶段提纯关系自洽 | PASS |
| 阈值增大时接受集合不减 | PASS |
| 抽样不重复且属于对应最终集合 | PASS |
| 无标签不伪造误匹配率 | PASS |
| 人工样本数和误率分母自洽 | PASS |
| 描述子归档回读一致 | PASS |
| 全部PNG可回读 | PASS |
| 标注页面和模板已生成 | PASS |
| 原始两张照片哈希不变 | PASS |
| 持久人工标签不被覆盖 | PASS |

所有处理图PNG无损回读；descriptors.npz保留全部描述子，keypoints.json及matches.json保留关键点和各阶段完整索引/距离；annotation_manifest.json固定抽样列表，parameters/metrics以results.json与metrics.csv为准。标签源文件和输入前后哈希不变。

一键入口测试临时文件显式放在D盘项目.tmp/pytest_lab7。输出与证据分别只保留lab7_latest，失败保留此前完整结果；永久人工CSV放data/annotations，避免被重跑清理。源码包deliverables/lab7_source.zip排除照片/输出/证据/标签与环境。统一复现及图片要求覆盖实验一至七。

Git功能分支与PR实际状态见lab7_git_workflow.md及Git证据。程序结果、技术自审与代理操作不代表个人标注、结对评审或课程提交已经完成。

官方依据：[OpenCV匹配教程](https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html)、[BFMatcher](https://docs.opencv.org/4.x/d3/da1/classcv_1_1BFMatcher.html)。
