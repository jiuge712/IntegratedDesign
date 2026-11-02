"""Generate the lab-eight report from the current run, without fictional reviews."""
import json


def report_text(info):
    sources=info['sources'];cfg=info['parameters']
    table='\n'.join(f'| {r["ratio"]} | {r["matches"]} | {r.get("inliers","—")} | {r.get("inlier_ratio",0):.2%} |'
                    for r in info['trials'] if 'error' not in r)
    return f'''# 实验八 RANSAC与图像拼接报告

运行时间：{info['time']}。程序版本：{info['program_version']}。姓名、学号、班级和本人实验日期：待本人填写。

## 完成范围与输入

已完成特征→匹配→RANSAC→完整画布透视拼接与距离羽化、内外点可视化、三档阈值对比及链路测试。M1一键演示和追溯材料已准备，真实5分钟现场演示、评分和评审记录仍待参与者完成，不预填分数。

输入由用户提供，不推断是本人实拍或已获出版授权；来源与≥30°拍摄条件待本人据实际记录核对。两张图可以不同尺寸，路径/配置可替换，无需改源码。

| 输入 | 路径 | 原尺寸shape | 工作shape | SHA-256 |
| --- | --- | --- | --- | --- |
| 左图 | {sources['image1']['path']} | {sources['image1']['original_shape']} | {sources['image1']['working_shape']} | {sources['image1']['sha256']} |
| 右图 | {sources['image2']['path']} | {sources['image2']['original_shape']} | {sources['image2']['working_shape']} | {sources['image2']['sha256']} |

max_input_side={cfg['max_input_side']}，只在内存INTER_AREA等比缩小超限图片；原文件保持。SIFT为{info['feature_counts'][0]}/{info['feature_counts'][1]}个实例，描述子float32 N×128，匹配用实验七BF L2 KNN与双向ratio，默认{cfg['ratio_threshold']}。实验五角点概念、六SIFT和七匹配模块在同一工程保留；不将Harris输出冒称为SIFT输入。

## RANSAC与数据分析

单应矩阵H为3×3，至少需4对非共线匹配。随机取最小集→拟合→按重投影误差统计内点→迭代选择并重估；足够迭代次数的近似关系为N=log(1-p)/log(1-w^4)，依赖真实内点率和采样假设，不能把输出掩码比例视为已知真值。

cv2.findHomography(右点,左点,cv2.RANSAC,{cfg['ransac_threshold']})，maxIters={cfg['max_iters']}、confidence={cfg['confidence']}、seed={cfg['seed']}。阈值和误差均为工作图像素。保留OpenCV原始掩码，不为提高内点率事后删点。

默认{info['match_count']}对匹配，内点{info['inliers']}、外点{info['outliers']}，内点比例{info['inlier_ratio']:.2%}。内点中位误差{info['inlier_median_error_working_px']:.3f} px，95分位{info['inlier_p95_error_working_px']:.3f} px。

| ratio | 双向ratio配对 | RANSAC内点 | 内点比例 |
| --- | --- | --- | --- |
{table}

匹配接受数和内点比例描述当前模型的一致性，不是实验七人工误配真值；没有以“经验通常>70%”冒充所有图片的必要条件。比例增大也不能单独证明几何质量更好。绿色表示几何内点、红色表示外点，每图最多均匀无放回展示{cfg['max_draw_matches']}条，全部匹配、索引、坐标、掩码与误差保存在matches.csv，展示索引另存JSON。

![内外点对照](../data/output/lab8_latest/l8_inlier_outlier_compare.png)

![三档统计](../data/output/lab8_latest/l8_thresholds.png)

工作坐标右→左H：

```text
{json.dumps(info['H_working_right_to_left'],indent=2)}
```

原图H=inv(S_left) H_work S_right，S含缩放的像素中心平移。原图H、完整工作H、平移T和所有float坐标均存JSON/NPZ，不混用缩图与原图坐标。

## 拼接与加分融合

变换右图四个像素中心角点，与左图范围取并集，向下/向上取整生成完整画布；平移T补偿负坐标，右图使用T H，左图使用T，避免固定w+200导致裁切。画布{info['canvas']['size']}，工作原点{info['canvas']['origin_xy']}。拒绝投影无穷远线穿图、奇异H、无重叠及超过{cfg['max_canvas_pixels']}像素的画布，失败保留前次完整结果。

有效区域来自单独投影的全白掩码，原图真正黑色像素仍有效。独占区域直接复制，重叠区域用到各自掩码边界的距离归一化加权；掩码外补零后算距离，防止全有效图的距离异常。50%混合图单独用于观察错位，直接覆盖与羽化成品同时保留。有效重叠{info['overlap_pixels']}像素，约占投影后左图{info['overlap_fraction_of_left']:.2%}，此比例依赖当前H。

![直接覆盖](../data/output/lab8_latest/l8_stitch_hard.png)

![距离羽化融合](../data/output/lab8_latest/l8_stitch_feather.png)

新图运行后应查看共同区域的静态轮廓和接缝。单个H适合近似平面或相机纯旋转；水面、浮冰、移动物体及反射可能仍有局部差异，羽化主要减轻亮度接缝，不保证修复视差或动态重影。数值检查不能替代视觉复核，也不能从未标定照片证明准确拍摄角度。

## 软件工程与验证

本次全项目{info['pytest']['tests']}项主用例、{info['pytest']['subtests']}项子用例通过，无失败/跳过；{len(info['checks'])}项正式检查通过，生成{info['png_count']}张PNG。test_pipeline.py包含要求的3个核心断言，使用固定种子受控透视图跑真实SIFT→匹配→RANSAC，不依赖交付包以外的个人照片。test_lab8.py另测已知H与外点、负坐标完整画布、真实黑色像素、羽化独占区、退化/无穷远/资源保护及结果替换回滚。正式运行另对当前实际输入检查匹配≥30、H形状和内点比例>50%，不是仅靠人工夹具通过。

复现入口见reproduction.md实验八章节；demo_m1.py运行同一链路并展示追溯说明。lab8_m1_review.md含5分钟演示安排、真实评审空表及追溯表；lab8_design.md记录接口/限制。真实参与者、评分、提问与课堂结论均待填写。user_tasks.md中的个人状态不因代理执行自动完成。

证据在evidence/lab8_latest：results.json、pytest.log/xml、matches.csv、keypoints.json、geometry.npz（allow_pickle=False）、PNG哈希清单及本报告副本。每次完整成功仅保留最新结果，失败保留旧批次。原始输入/其他实验/持久标签不清理。源码包deliverables/lab8_source.zip排除个人原图、输出、证据、标签和环境，课程所需这些材料应另行提交。
'''
