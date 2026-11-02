# 实验八 M1演示与需求追溯

技术演示脚本、测试与追溯已准备；真实课堂5分钟演示和评审尚未发生，下面参与者、分数和结论均待填写。不得用本技术自检或Git PR代替真实课堂活动。

## 一键与5分钟安排

```powershell
Set-Location D:\IntegratedDesign\project_i
.\.venv\Scripts\python.exe -X utf8 src/demo_m1.py
```

支持与run_lab8.py相同的--config/--image1/--image2。默认配置全部为data/相对路径，解析按项目根，代码没有个人D盘路径。运行真实SIFT→匹配→RANSAC→拼接/羽化和全项目pytest，并打印追溯提示。pytest/程序图像是自动技术证据，不冒充本人终端截图。

| 时间 | 演示内容 | 可展示证据 |
| --- | --- | --- |
| 0:00–0:40 | 输入、来源/视角条件、工作尺寸与原图保护 | 配置、results.json来源哈希 |
| 0:40–1:30 | 实验五角点概念、六SIFT和七匹配如何沿用 | features.py/matching.py与数量；不宣称Harris是SIFT输入 |
| 1:30–2:30 | 右→左3×3 H，4对最小集，内点比例、绿/红 | 1740/1944、H、内外点对照 |
| 2:30–3:30 | 完整画布、负坐标、独立掩码和羽化 | hard/feather/valid_masks |
| 3:30–4:30 | 核心3个测试、完整回归、逐条追溯 | pytest.log/xml、下表 |
| 4:30–5:00 | 水面局部变化、H限制、回答提问 | 诊断叠加图与报告限制 |

换图后数量以本次results.json为准，不背诵旧数值冒充新结果。

## 需求追溯

需求定义在requirements.md的“实验八增量需求”。指导书F3只是例子，本项目原FR-03是灰度转换，不将它改名冒充特征匹配。

| 需求 | 模块 | 验证 | 运行证据 |
| --- | --- | --- | --- |
| L8-FR-01 特征与匹配 | features.py/matching.py | test_match_count_positive，实际≥30 | keypoints.json、matches.csv |
| L8-FR-02 H和RANSAC统计 | homography.py | test_homography_shape/test_inlier_ratio_over_half/已知H外点测试 | results.json H、掩码、误差，geometry.npz |
| L8-FR-03 内外点显示 | run_lab8.py | bool分组互斥、索引/计数检查 | l8_inliers.png、l8_outliers.png、l8_inlier_outlier_compare.png、展示索引 |
| L8-FR-04 完整拼接与羽化 | homography.py | 负平移画布、黑色有效像素、独占区 | l8_stitch_hard.png、l8_stitch_feather.png、l8_valid_masks.png |
| L8-FR-05 链路单测与M1材料 | test_pipeline.py/demo_m1.py | 37项新增、全项目224主+15子，无跳过 | pytest.log/xml、本表；真实课堂记录仍待补 |
| L8-FR-06 换图与结果保留 | run_lab8.py/latest_runs.py | 配置入口、发布失败回滚、换图集成验证 | results.json来源/配置、integration_verification.json |
| 既有FR-01/FR-07 读取与可换图 | lab7_artifacts.py/CLI | 图片解码、覆盖路径 | 两图工作图/来源哈希 |
| 既有NFR-04/NFR-05 原图保护/最新结果 | common.py/latest_runs.py | 输入前后SHA、失败保留 | 正式检查、integration_verification.json |

上述为技术映射，不把自动数字检验冒称所有像素准确；尤其≥30°拍摄条件需本人确认。二维H不等于相机K/R/t或点云。

## 真实M1评审记录 待参与者填写

日期/地点：待填写。演示者、评审者及小组：待填写。真实照片来源、角度依据：待填写。

| 评分项 | 满分（按教师评分表） | 实际得分 | 评语/问题 |
| --- | --- | --- | --- |
| 链路运行和RANSAC解释 | 待确认 | 待评 | 待填 |
| 拼接效果与限制分析 | 待确认 | 待评 | 待填 |
| 需求追溯 | 待确认 | 待评 | 待填 |
| 单测与证据 | 待确认 | 待评 | 待填 |
| 总分/结论 | 待确认 | 待评 | 待填 |

本表是记录空位，不是假定教师评分权重；若教师提供统一表，改用真实评分表。真实提问、回答、意见、处理人和复核日期：待填写。需修复的问题登记defects.md，完成后关联实际验证。不得填虚构评审者、分数或“已通过”课堂结论。
