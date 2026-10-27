"""Measured matching counts; human estimates remain pending until labels exist."""
def percent(value):
    return '待人工标注' if value is None else f'{value:.2%}'


def report_text(info):
    cfg=info['parameters']
    tests=info['pytest']
    lines=['# 实验七 特征匹配与误匹配分析','',f"运行时间：{info['time']}；版本{info['program_version']}。",'',
           '依据实验七_特征匹配与误匹配分析.docx，完成SIFT、BF/KNN、ratio三档、最近邻互查、双向ratio、距离阈值补充、FLANN速度对比、随机抽样及人工标注工具。真实结对评审和人工误配标签由本人/同学提供；技术自走查不冒充结对活动。','',
           f"自动验证：{tests['tests']}项主用例、{tests['subtests']}项子用例，失败{tests['failures']}、错误{tests['errors']}、跳过{tests['skipped']}；正式检查{len(info['checks'])}项通过。",'',
           '## 个人照片与SIFT','', '| 角色 | 实际路径 | 原始shape | 工作shape | SIFT实例 |','| --- | --- | --- | --- | --- |']
    lines += [f"| {name} | {src['path']} | {src['original_shape']} | {src['working_shape']} | {info['feature_counts'][name]} |" for name,src in info['sources'].items()]
    lines += ['',
              f"两张图分别使用用户提供的seven-1.jpg、seven-2.jpg，SHA-256在results.json；max_input_side={cfg['max_input_side']}，0为保留原尺寸，非0仅在超出上限时等比缩小，不改原文件。均为图书馆场景，有大面积共同建筑；人物、反射和遮挡不同，不能将其当作已知仿射派生图。未用匹配数捏造精确重叠率。",'',
              f"SIFT配置：{cfg['sift']}。描述子为float32 N×128，原关键点与描述子不截断，坐标在各自工作图上；矩阵记录原照片到工作图像素中心的映射。",'',
              '![输入和特征](../data/output/lab7_latest/l7_inputs_keypoints.png)','',
              '## KNN与提纯','',
              f"BFMatcher使用NORM_L2、crossCheck=False，双向knnMatch(k=2)。前向最近邻候选{info['raw']['nearest_count']}条，具有完整两邻点的查询{info['raw']['complete_pairs']}个；只有完整两邻点且d2>0时才做d1<阈值×d2。重复的零距离两邻点视为歧义，避免除零；目标只有一个描述子时仍保留最近邻信息，但不伪造ratio。",'',
              '| ratio阈值 | 单向ratio（保留率） | 互为最近邻且前向ratio | 双向ratio（最终） | 最终/原始候选 | 人工样本明确数/抽取数 | 样本误匹配率 |','| --- | --- | --- | --- | --- | --- | --- |']
    for row in info['thresholds']:
        human=row['human']
        ratio_fraction=f"{row['ratio_count']/info['raw']['nearest_count']:.2%}" if info['raw']['nearest_count'] else '无候选'
        lines.append(f"| {row['threshold']} | {row['ratio_count']}（{ratio_fraction}） | {row['mutual_nearest_count']} | {row['symmetric_ratio_count']} | {row['retained_fraction']:.2%} | {human['decisive_count']}/{human['sample_count']} | {percent(human['error_rate'])} |")
    lines += ['',
              '“互为最近邻”要求A→B和B→A首邻点互指；“双向ratio”还要求两边都过同一ratio阈值，后者是指导书步骤3示例的实际行为，更严格。不能在BFMatcher(crossCheck=True)上直接做k=2；本实现显式反向匹配。上表人工误匹配率的总体为各阈值“双向ratio最终集合”，不是原始KNN或单向ratio集合。','',
              f"默认展示阈值{cfg['display_threshold']}，绝对L2距离上限max_distance={cfg['max_distance']}。候选、ratio与最终三张图都以固定seed均匀抽取最多{cfg['max_draw_matches']}条展示，全部匹配数见表/JSON；图中灰色/蓝色表示处理阶段，不能将蓝色直接解释为人工确认正确。",'',
              '![提纯前后比较](../data/output/lab7_latest/l7_before_after.png)','',
              '![阈值数量对比](../data/output/lab7_latest/l7_threshold_counts.png)','',
              '![最近邻距离比](../data/output/lab7_latest/l7_ratio_distribution.png)','',
              '比值越低表示最近邻比次近邻更独特，是区分度指标；建筑重复窗格、反射和移动人物仍可能导致误配。宽阈值通常保留更多匹配，也接受更多歧义；降低阈值与互查可能减少误配，同时也丢失真实对应。没有人工标签时不据数量宣布“准确率显著上升”。','',
              '## 绝对距离补充','', '| L2上限 | 默认ratio最终集合保留数 |','| --- | --- |']
    lines += [f"| {row['max_distance']} | {row['count']} |" for row in info['distance_experiment']]
    lines += ['', '距离阈值基于OpenCV实际缩放的SIFT L2值，不假定单位范数，也不把它与ratio阈值混为一谈。绝对距离筛选不能提供正确标签。','',
              '## BF与FLANN加分对比','', '| 后端 | 双向构建+KNN中位ms | 最小ms | 重复次数 |','| --- | --- | --- | --- |']
    lines += [f"| {row['backend']} | {row['median_ms']:.4f} | {row['min_ms']:.4f} | {row['repeats']} |" for row in info['benchmark']]
    agreement=info['backend_agreement']
    lines += ['',
              f"先分别预热，再测双向匹配，包含构造和FLANN索引时间；不包括SIFT提取/绘图/人工标注。FLANN KD-tree trees={cfg['flann_trees']}、checks={cfg['flann_checks']}、随机seed={cfg['sample_seed']}。",'',
              f"FLANN与BF在可比较查询上的首邻点索引一致率{percent(agreement['nearest_index_agreement']) if agreement['nearest_index_agreement'] is not None else '无可比较查询'}；默认阈值最终配对Jaccard={agreement['symmetric_pair_jaccard']:.4f}。FLANN近似搜索可能改变第一/第二邻点和ratio，不能只比较速度宣称结果完全一致；本机时延不代表其他机器性能。",'',
              '## 人工误匹配率与操作方法','',
              f"每个阈值最终集合均匀无放回抽{cfg['sample_size']}对，随机seed={cfg['sample_seed']}，不足则全取；不同组重复抽中的同一配对共用标签。共需查看{info['annotation_unique_pairs']}个唯一配对。固定配对ID绑定输入哈希、工作尺寸、SIFT配置、OpenCV版本、关键点及描述子；换图/提取变化后旧标签拒绝使用。",'',
              '打开data/output/lab7_latest/annotate.html，可调局部观察半径或全图定位，在紫色十字处核对是否为同一物理点。填写真实标注者，按正确/错误/不确定逐对记录；导出CSV放入data/annotations，按reproduction.md用--labels重跑。每组另有5张sample_阈值_页号.png样本页和labels_template.csv。','',
              '只在该组所有抽取样本都明确标为correct/incorrect后输出误配率=incorrect/(correct+incorrect)，并给出Wilson 95%区间；uncertain不当作错误或正确，未完成时率为null/“待人工标注”。不足50的样本会明确说明未满足50对要求；不合并不同阈值样本伪装成每组50对。','']
    for row in info['thresholds']:
        h=row['human']
        lines.append(f"阈值{row['threshold']}：correct={h['correct']}，incorrect={h['incorrect']}，uncertain={h['uncertain']}，未标={h['unlabeled']}，误匹配率={percent(h['error_rate'])}，95%区间={h['wilson_95_interval']}；50对条件完成={h['course_50_pairs_complete']}。")
    lines += ['',
              '当前没有人工标签的组不提供虚构误配率，也不把互查、ratio、RANSAC或单应性内点当人工真值。人工完成后才基于数量与抽样误配率作最终阈值选择；0.75只是本次默认工作点。实验八的RANSAC与图像拼接未执行。','',
              '## 代码评审与缺陷','',
              'lab7_code_review.md提供正确性/边界/性能/可读性清单、至少5条明确标为技术自走查的意见及防护验证，并保留真实结对记录。defects.md登记编号、日期、位置、严重度、状态、处理者和验证；真实结对意见、修复人和日期由参与者填写，不伪造同学评审。个人待办见user_tasks.md。','',
              '## 自动检查与复现','', '| 检查 | 结果 |','| --- | --- |']
    lines += [f"| {row['name']} | PASS |" for row in info['checks']]
    lines += ['',
              '所有处理图PNG无损回读；descriptors.npz保留全部描述子，keypoints.json及matches.json保留关键点和各阶段完整索引/距离；annotation_manifest.json固定抽样列表，parameters/metrics以results.json与metrics.csv为准。标签源文件和输入前后哈希不变。','',
              '一键入口测试临时文件显式放在D盘项目.tmp/pytest_lab7。输出与证据分别只保留lab7_latest，失败保留此前完整结果；永久人工CSV放data/annotations，避免被重跑清理。源码包deliverables/lab7_source.zip排除照片/输出/证据/标签与环境。统一复现及图片要求覆盖实验一至七。','',
              'Git功能分支与PR实际状态见lab7_git_workflow.md及Git证据。程序结果、技术自审与代理操作不代表个人标注、结对评审或课程提交已经完成。','',
              '官方依据：[OpenCV匹配教程](https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html)、[BFMatcher](https://docs.opencv.org/4.x/d3/da1/classcv_1_1BFMatcher.html)。','']
    return '\n'.join(lines)
