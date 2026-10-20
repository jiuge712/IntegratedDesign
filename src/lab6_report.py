"""Render the SIFT report from measured counts and known-transform errors."""


def report_text(info):
    cfg,source = info['parameters'],info['source']
    original = info['original_features']
    tests = info['pytest']
    lines = ['# 实验六 SIFT特征提取与描述', '',
             f"运行时间：{info['time']}；版本{info['program_version']}。", '',
             '依据实验六_SIFT特征提取与描述.docx，完成SIFT提取、三个参数的控制变量实验、旋转/缩放匹配验证、features.py封装及描述子玫瑰图。Git功能分支、Conventional Commits和PR/MR流程见lab6_git_workflow.md；实际状态以该文档及Git证据为准。', '',
             f"全项目pytest {tests['tests']}项主用例与{tests['subtests']}项子用例，失败{tests['failures']}、错误{tests['errors']}、跳过{tests['skipped']}；正式检查{len(info['checks'])}项通过，生成{info['png_count']}张PNG。", '',
             '## 输入与来源', '',
             f"实际文件：`{source['path']}`。SHA-256：`{source['sha256']}`。", '',
             f"原始shape={source['original_shape']}；工作shape={source['working_shape']}。max_input_side={cfg['max_input_side']}，只在超过上限时使用INTER_AREA等比缩小；原文件不修改。所有角点、尺度和几何误差以工作图像素为单位，原文件到工作图的像素中心矩阵保存在results.json。", '',
             '当前默认沿用用户2026年10月20日明确提供的建筑夜景实拍图uneven_real.jpg；该文件也用于实验四。若替换输入，以上实际路径、尺寸和哈希为本次来源依据，不根据旧文件名推断新图片拍摄属性。旋转/缩放图是受控派生，不是其他视角的独立拍摄照片。', '',
             '## SIFT原理与接口', '',
             'SIFT依次进行DoG尺度空间极值检测、亚像素关键点定位/低对比度及边缘响应剔除、梯度主方向赋值、描述子生成。描述子将旋转对齐邻域分成4×4空间网格，每格8个方向bin，故维度为128。同一物理位置可能有多个主方向，关键点数统计包含这些实例。', '',
             '接口为src/features.py的extract_sift(img,cfg=None) -> (kps,desc)。接受非空uint8灰度/BGR/BGRA，显式转灰度、舍弃Alpha，不修改输入；cfg使用OpenCV参数名。无特征统一返回[]与float32的(0,128)，避免对None调用shape。', '',
             f"本次关键点数={original['count']}，描述子shape={original['descriptor_shape']}，dtype={original['descriptor_dtype']}。尺度size最小/中位/最大={original['size_min']} / {original['size_median']} / {original['size_max']}。", '',
             '![尺度和主方向关键点](../data/output/lab6_latest/l6_keypoints.png)', '',
             'Rich Keypoints圆圈表示关键点尺度范围，KeyPoint.size为直径；短线表示主方向。angle单位度、范围[0,360)，不是弧度。', '',
             '![尺度方向分布](../data/output/lab6_latest/l6_distributions.png)', '',
             '## 参数实验', '',
             f"基准配置：{cfg['sift']}。每组仅改变一个参数，其余保持基准；重复的相同配置复用同一次提取，共{info['unique_parameter_extractions']}次唯一参数提取。计时包含提取包装，不是多次性能基准。", '',
             '| 变化参数 | 值 | 关键点数 | size中位数 | 提取ms |', '| --- | --- | --- | --- | --- |']
    lines += [f"| {row['group']} | {row['value']} | {row['count']} | {row['size_median']} | {row['elapsed_ms']} |" for row in info['parameter_experiments']]
    lines += ['', '![参数数量对比](../data/output/lab6_latest/l6_parameter_counts.png)', '',
              'nfeatures=0表示不限制，非零时优先保留高响应特征；临界响应相同的特征在部分OpenCV实现中可能一同保留，数量以实际结果为准。提高contrastThreshold会过滤更多低对比度点；该阈值在内部还会除以nOctaveLayers，跨配置比较时需固定层数。', '',
              'edgeThreshold的方向与contrastThreshold不同：提高edgeThreshold会减少对边缘状点的过滤，通常保留更多点。指导书常见问题中建议用更高edgeThreshold去除边缘点的说法与官方API定义相反，这里以API定义和实际对照为准；减少数量不直接代表更准确。', '',
              '![对比度阈值与空间分布](../data/output/lab6_latest/l6_contrast_keypoints.png)', '',
              '## 旋转与缩放的受控验证', '',
              f"使用{cfg['rotation_degrees']}°旋转、{cfg['scale_factor']}倍缩放及两者组合。每次由完整源矩形计算新画布，用ceil避免截掉角部，再warpAffine；矩阵、目标尺寸和描述子均归档。黑色补边及插值仍可能影响边界附近的检测，不宣称所有关键点都保持。", '',
              '![变换输入](../data/output/lab6_latest/l6_transform_compare.png)', '',
              f"对全部描述子用BFMatcher(NORM_L2).knnMatch(k=2)，采用d1 < {cfg['ratio_threshold']}×d2筛选，不截断des[:300]。匹配比例=通过ratio的查询点数/原图关键点数；每个查询最多一条结果，但不同查询可能指向相同目标，所以同时记录唯一目标数。仅绘图时选距离较小的前{cfg['max_draw_matches']}对。", '',
              '| 变换 | 目标关键点 | ratio通过 | 通过/原图点数 | 几何一致 | 一致/通过 | 误差中位数px | 唯一目标点 |',
              '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in info['transforms']:
        precision = f"{row['geometry_consistent_per_match']:.2%}" if row['geometry_consistent_per_match'] is not None else '无匹配'
        lines.append(f"| {row['name']} | {row['target_keypoints']} | {row['ratio_passed']} | {row['ratio_passed_per_source']:.2%} | {row['geometry_consistent']} | {precision} | {row['median_reprojection_error_px']} | {row['unique_train_indices']} |")
    lines += ['',
              f"已知生成矩阵提供位置真值：将原关键点投影到目标，欧氏误差≤{cfg['geometry_tolerance_px']}工作像素计为几何一致。ratio筛选通过不等于真实对应，建筑重复窗格尤其可能形成误配；此处的误差验证仅依赖已知合成变换，不是估计相机位姿或RANSAC。", '']
    for row in info['transforms']:
        lines += [f"![{row['name']}匹配示意](../data/output/lab6_latest/l6_matches_{row['name']}.png)", '']
    combined = next(row for row in info['transforms'] if row['name']=='combined')
    lines += [f"本次组合变换匹配比例为{combined['ratio_passed_per_source']:.2%}。指导书的通常超过30%是经验观察，不是对任何图片的保证；本次按实际值报告。尺度空间、方向对齐与描述子归一化提供鲁棒性，仍受采样、插值、重复纹理、阈值和原图质量影响，不能将一次受控实验推广为任意场景绝对不变。", '',
              '## 加分项 描述子玫瑰图', '',
              '选取一个高响应关键点及一个空间分离、描述子差异较大的点；按行优先将128维数组reshape为4×4×8。每幅16格玫瑰图共用同一半径尺度，角度相对关键点主方向，不代表固定世界方向。图中是OpenCV已归一化、截断及缩放后的存储值，不是直接的原始梯度计数，也不能把默认float32描述子当作单位范数向量。', '']
    for example in info['descriptor_examples']:
        lines += [f"样例{example['example']}：描述子行{example['keypoint_index']}，位置({example['x']:.2f},{example['y']:.2f})，size={example['size']:.3f}，angle={example['angle']:.3f}。", '',
                  f"![描述子样例{example['example']}](../data/output/lab6_latest/l6_descriptor_{example['example']}.png)", '']
    if info['descriptor_examples']:
        lines += ['![128维向量对比](../data/output/lab6_latest/l6_descriptor_compare.png)', '']
    else:
        lines += ['本次图像没有关键点，未伪造描述子样例；请更换有纹理的个人图片。', '']
    lines += ['## 验证与复现', '', '| 检查 | 结果 |', '| --- | --- |']
    lines += [f"| {check['name']} | PASS |" for check in info['checks']]
    lines += ['',
              'features.npz保存原图/变换图/参数对照描述子和矩阵；keypoints.json包含浮点坐标、尺度、角度、响应及packed octave；matches.json含全部ratio匹配的索引、距离和已知变换误差；parameters.csv和invariance.csv便于复查。', '',
              'pytest.log/pytest.xml为真实测试文本，临时目录显式设到项目.tmp/pytest_lab6；程序图像不是终端截图。最新结果位于data/output/lab6_latest及evidence/lab6_latest，完整校验后替换，失败保留前次结果，其他实验和原始输入保持。', '',
              '统一reproduction.md、image_requirements.md覆盖实验一至六；user_tasks.md记录真实个人复现、Git截图/PR核对、报告信息及提交。未明确确认的用户事项保持未完成。实验七至十四未执行；本次只做指导书要求的不变性简单匹配。', '',
              '官方依据：[SIFT参数](https://docs.opencv.org/4.x/d7/d60/classcv_1_1SIFT.html)、[BF/KNN匹配](https://docs.opencv.org/4.x/dc/dc3/tutorial_py_matcher.html)。本机实际版本见environment.md与results.json。', '']
    return '\n'.join(lines)
