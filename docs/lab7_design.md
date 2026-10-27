# 实验七 特征匹配设计

实现指导书的BF/KNN、ratio、交叉检查、误匹配抽样与FLANN补充。正式输入为用户提供的seven-1.jpg与seven-2.jpg，不把真实视角变化当作实验六已知仿射；人工误配率需要真实标签，结对评审需要真实参与者。

## 模块与数据流

features.py复用实验六extract_sift，输出KeyPoint与float32 N×128描述子。matching.py提供纯数组匹配/筛选和测时；lab7_annotations.py生成稳定数据ID/均匀抽样、校验CSV并计算误率；lab7_artifacts.py负责只读图片、PNG/CSV及离线标注页；run_lab7.py串联参数/pytest/证据/LatestRun；lab7_report.py只依据本次数据写报告。

| 函数 | 输入输出与约束 |
| --- | --- |
| knn_matches(query,train,backend,trees,checks,seed) | 有限float32 N×128；bf用L2，flann用KD-tree；每查询0/1/2个DMatch，输入不截断 |
| filter_ratio(raw,threshold,max_distance) | 0<threshold<1；完整两邻点且d2>0，严格d1<threshold*d2；可再限制绝对L2距离 |
| mutual_nearest(forward,reverse_raw) | 接受前向候选列表，B→A首邻点反转为(A索引,B索引)，两侧互为首邻点才留 |
| symmetric_ratio(forward_raw,reverse_raw,threshold,max_distance) | 前向和反向都过ratio，并且互指；比单向ratio加最近邻互查更严格 |
| match_records(raw) | 记录完整原始索引/距离；d2缺失或为0时ratio=null，严格JSON不产生NaN/Infinity |
| benchmark_matchers(...) | 两种后端分别预热，再测双向构建+KNN；默认3次，以中位/最小ms及逐次值记录 |
| random_sample(matches,threshold,size,seed) | 先按query/train稳定排序，再按seed和阈值派生独立流，无放回均匀抽样；不挑前50或最好50 |
| read_labels(path,dataset_id,...) | 严格CSV表头、数据来源、配对ID、索引、标签/真实标注者及重复行验证；只读、不覆盖原CSV |
| error_estimate(samples,...) | correct/incorrect全覆盖后才给误配率；不确定/未填不算真值；附Wilson区间及是否满50对 |

输入为空/位深或描述子维度错误明确报错；无特征、目标只有0/1描述子安全返回，不把缺少次近邻当ratio=0。crossCheck=True不与k=2混用，严格保留原始索引，不把排序后的行号当原特征索引。

## 坐标和分辨率

正式配置max_input_side=0，保留两张4096×3072原图进行特征分析，原文件只读。参数可指定上限等比缩小，记录像素中心矩阵，不隐式拉伸，不要求两图同尺寸。坐标指各自工作图，标签页/CSV和原始关键点使用同一批次。

实际试运行：长边1600时0.6/0.75/0.9最终双向ratio为24/64/361；长边2400为43/99/550；完整原尺寸为58/175/1148。低分辨率严格阈值不足50对，因此正式保留原图细节；没有修改阈值凑数，也没有改动任何真值。这个选择改变统计总体，所有正式数量和人工标签都绑定最终分辨率，不能跨分辨率复用。原始照片有移动人物、遮挡、反射和重复窗格，大面积场景重叠不等于每个关键点可对应。

## 人工抽样和标签持久化

默认每阈值最终双向ratio集合抽50对，三组共150次抽取、137个唯一配对；同一对共享标签。数据ID绑定两个源文件的路径/哈希/工作尺寸、SIFT配置、OpenCV版本、关键点和完整描述子；采样seed=7，列表固定到annotation_manifest.json。标签CSV保存在data/annotations，不随latest替换删除，源码ZIP和Git不收集私人标签。

标注页annotate.html完全离线，读取同目录两个工作PNG，以画布显示局部放大/全图十字定位，Y/N/U标正确/错误/不确定；可导出/导入UTF8 CSV并尝试浏览器本地保存。未改用户全局浏览器配置。当前页面操作不能自行写入项目文件，需要用户把下载CSV保存至持久目录并用--labels导入。页面导入校验表头、数据ID、原索引、标签、标注者及重复；使用textContent展示文本，内嵌JSON转义<，不把用户备注当HTML。

Python再次校验外部CSV，不信任页面校验替代后端检查。标签格式字段为dataset_id,pair_id,query_index,train_index,label,reviewer,note；label允许空/correct/incorrect/uncertain。只有每组全部样本明确后给出incorrect/明确样本数；不足50会明确标记。所有测试夹具标签都位于临时测试路径并标明非真实人工，正式结果没有混入测试标签。

## 数量、效率与结论边界

原始两图SIFT数33057/29086，默认ratio=0.75单向344、互为最近邻284、双向ratio175。完整描述子参与双向KNN，仅图示最多抽50条。图中灰/蓝色区分处理阶段；绿/红仅用于外部CSV真实标签，未标注时不输出“正确/错误”的伪着色。

FLANN algorithm=1、trees=5、checks=50、seed=7，近似首邻点和次邻点可能不同。测时包含各自构造及索引，不含提取/绘图，先预热再报告3次中位；同时提供BF/FLANN首邻点一致率和默认最终集合Jaccard。近似速度优势不是正确性保证，参数会改变近似质量。

没有已知真实几何矩阵或人工标签时，不把ratio、互查或RANSAC内点当作真值。RANSAC和拼接是实验八，本次未执行。0.75只作为默认，最终数量/误率权衡等用户完成抽样后再作实证结论。

## 验证、评审和发布

test_lab7.py共40项主用例，覆盖已知最近/次近邻、空/单目标、类型/阈值、等号/零距离、反向索引、两种互查差异、350查询不截断、均匀抽样、标签陈旧/重复/未知/未标/不确定/完整、Wilson分母、HTML转义、CLI错误及latest替换/失败保留。全项目187项主用例及15项子用例通过。pytest临时目录显式放项目.tmp/pytest_lab7。

浏览器实际核验图片/布局/点击/导航/全图/CSV导出转义及错误表头导入；临时浏览器profile的测试标签不产生正式人工标签。额外集成测试覆盖换图/空图、CSV闭环、过期来源拒绝、失败保留、原图/实验一至六/用户已有实验五报告不变。真实结果与测试夹具分开记录。

lab7_code_review.md的技术自走查至少5条，defects.md区分实际发现问题与设计期预防风险；真实结对互查记录和小组签名仍待本人/同学填写。user_tasks.md旧状态保持。代码通过feature/l7-matching与真实PR流程管理，实际状态另见lab7_git_workflow.md。每次成功后只保留lab7_latest，输入和持久CSV不删，失败保留旧完整结果。

参考：[OpenCV匹配](https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html)、[BFMatcher](https://docs.opencv.org/4.x/d3/da1/classcv_1_1BFMatcher.html)、[pytest临时路径](https://docs.pytest.org/en/stable/how-to/tmp_path.html)。
