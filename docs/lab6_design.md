# 实验六 SIFT模块设计

本实验为SFM的特征提取阶段实现可复用接口，完成SIFT参数对比和已知旋转/缩放验证。与实验五的Harris模块src/feature.py区分，SIFT按指导书放在src/features.py；匹配只用于本次不变性统计，实验七的完整匹配分析未提前实施。

## 数据流和接口

run_lab6.py读取config/lab6_images.json和个人图片，执行明确记录的工作尺寸缩放，调用extract_sift，进行参数实验，生成三类已知变换并再次提取。lab6_geometry.py完成全画布仿射、全描述子KNN和已知矩阵误差计算。lab6_report.py只根据实际数据生成报告。通过测试/回读/哈希校验后，由LatestRun('lab6')发布最近一次结果。

```python
from features import extract_sift
kps, desc = extract_sift(img, cfg=None)
```

| 项目 | 约定 |
| --- | --- |
| 图像 | 非空uint8，灰度/BGR/BGRA；BGR/BGRA明确转灰度，Alpha舍弃，不修改原数组 |
| cfg | None或字典；nfeatures、nOctaveLayers、contrastThreshold、edgeThreshold、sigma、enable_precise_upscale；拒绝未知键 |
| kps | cv2.KeyPoint列表；pt为工作图(x,y)浮点，size为直径，angle为[0,360)度，response为响应 |
| desc | float32 (N,128)，第i行与kps[i]一致，有限数值；无特征为空列表和(0,128)，不返回None |
| 无效输入 | 非数组TypeError；空图、位深、通道或非法参数ValueError；不支持SIFT或异常输出RuntimeError |
| 极小图 | 底层最短边<8返回空结果；正式入口最短边≥16，纹理不足时如实返回无特征 |

SIFT四步为尺度极值检测、关键点定位与筛除、方向赋值、4×4×8描述子。OpenCV默认float32描述子包含内部归一化/截断/缩放，不承诺单位L2范数。nfeatures非零时保留高响应实例，临界同分点可能多保留；本机300得到301个，保持API真实结果而不硬裁剪。

## 参数及几何

默认SIFT：nfeatures=0、nOctaveLayers=3、contrastThreshold=0.04、edgeThreshold=10、sigma=1.6、enable_precise_upscale=False。独立改变nfeatures 0/300/800、contrastThreshold 0.04/0.01/0.08、edgeThreshold 5/10/20。相同配置只计算一次，七次唯一提取写成九条按组对照记录。size/方向分布也保存，不能只看点数判断正确率。

edgeThreshold增大意味着边缘状特征筛选变宽松，与contrastThreshold相反。[OpenCV SIFT定义](https://docs.opencv.org/4.x/d7/d60/classcv_1_1SIFT.html)还说明contrastThreshold内部会除以nOctaveLayers；本次比较固定层数。

输入超过max_input_side时INTER_AREA等比缩小，0为保持原尺寸；记录原shape、工作shape及像素中心映射sx*x+(sx−1)/2。缩放后最短边<16会报错，不为了满足下限拉伸图像。原文件到工作图与工作图到各变换图矩阵分别保存，不混淆原始照片坐标和分析坐标。

transform_full_canvas(img,angle,scale)使用源图完整边界计算新尺寸ceil(w|cos|+h|sin|)，调整平移后warpAffine。测试四角边界均落在新画布内，避免原尺寸画布裁切；缩放采用线性插值，边界黑色补边，可能改变边缘特征。

ratio_matches(query,train,threshold)要求float32 N×128，使用全部描述子BF L2 KNN(k=2)，d1<0.75*d2；目标不足两个或查询为空安全返回空。matches排序仅影响绘图选前50，统计不截断。比例分母为源图关键点实例数，多个query可共享train，另记录unique_train_indices。

match_statistics将源关键点通过已知仿射投影，欧氏误差≤3工作像素计为一致；输出匹配数、比例、误差中位数和几何一致比例。没有匹配时一致/匹配用null，不能伪造100%准确。这里不估计H、不做RANSAC，也不把合成变换验证当真实多视角重建。

## 输出、测试与保护

默认18张PNG覆盖尺度/方向、参数数量/空间分布、三种输入变换/关键点/匹配以及两幅描述子玫瑰图和128维对比。无特征时省略描述子示例，不保留上次示例冒充本次结果。JSON保存关键点、全部匹配、参数和来源，NPZ保留float32描述子和float64矩阵；PNG无损回读。

test_lab6.py共40项用例，覆盖类型/空图/配置、描述子行对齐、BGR/BGRA与灰度一致、无输入修改、参数作用、变换完整性、已知正确/错误匹配、350个查询不截断、目标不足两点、无特征、等比缩放、CLI异常及最新结果替换/失败保留。合成纹理有固定seed=6，是单元测试数据，不当作正式个人照片。

一键入口执行全项目pytest，显式--basetemp指向项目.tmp/pytest_lab6，避免使用C盘默认pytest临时目录。该专用目录每次由pytest重建，不能存原图或提交材料；不要并发运行两个使用相同basetemp的测试进程。手动运行命令在统一复现指南中也显式指定D盘临时位置，原pytest.ini保持不变。

LatestRun仅清理项目内指定输出/证据的旧结果，拒绝链接与越界；失败保留前次完整结果。输入目录前后哈希、实验一二三五最新数据、用户此前修改的实验五报告及实拍配置通过集成检查确认保持。实验四本次按用户要求重跑为新实拍结果。

软件工程要求另见lab6_git_workflow.md。API参考：[SIFT](https://docs.opencv.org/4.x/d7/d60/classcv_1_1SIFT.html)、[匹配](https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html)、[pytest临时目录](https://docs.pytest.org/en/stable/how-to/tmp_path.html)。
