# 实验八 设计与接口

8.0.0复用features.py的SIFT与matching.py的BF L2 KNN/双向ratio，新增homography.py实现右→左单应估计和二维拼接。run_lab8.py负责配置、图片IO、三档对比、真实回归、证据/报告与latest发布；demo_m1.py为同一链路的一键演示，package_lab8.py沿用现有排除个人数据的打包器。未实现相机K/R/t或三维重建，不把二维H当成三维位姿。

## 数值接口

| 接口 | 输入 | 输出与约定 |
| --- | --- | --- |
| match_and_estimate(image1,image2,ratio=.75,sift=None,threshold=5.,confidence=.995,max_iters=10000,seed=8) | 两幅uint8灰度/BGR/BGRA图 | 特征/描述子、全部双向ratio配对、右→左H、bool内点及误差；索引引用原特征 |
| estimate_homography(right,left,threshold=5.,confidence=.995,max_iters=10000,seed=8) | 数量一致的有限N×2 float坐标 | H float64 3×3、bool N掩码、N维正向误差；至少4对非退化点 |
| canvas_geometry(shape1,shape2,H,max_pixels=20000000) | 尺寸与右→左H | 完整画布size=(W,H)、原点和T、右图变换角点；负坐标保留 |
| stitch_pair(image1,image2,H,max_pixels=20000000) | 非空uint8 BGR、右→左H | hard/feather/50%overlay、warped_right、有效掩码、overlap、alpha和geometry；不修改输入 |

数组索引img[y,x]，点为(x,y)；KeyPoint的size是直径、angle是度，描述子float32 N×128。加载沿用lab7_artifacts.load_photo，灰度扩为BGR，BGRA舍弃Alpha；uint16/float不隐式缩放，最短边至少16。默认工作长边2400，0表示保留原尺寸。所有路径在配置/CLI传入，JSON相对项目根；更换两图无需改源码。

右→左重投影误差为||H p_right - p_left||的欧氏距离，阈值5工作像素；OpenCV掩码保持原样。原图H=inv(S_left) H_work S_right，S包含源→工作尺寸像素中心平移。完整画布用两图四个像素中心角点取并集，floor(min)、ceil(max)+1；因此与使用边界w/h角点的预检可能相差1像素。左用T、右用TH，不以w+200裁图。

## 羽化与边界

投影全白掩码定义有效区，不能用图像像素>0判定有效性。掩码外补一圈0后求distanceTransform；重叠区alpha=d_left/(d_left+d_right)，独占区复制原值，无效区黑色。按128行分块计算浮点加权，限制临时内存。实际黑色像素参与融合；输出uint8，rint后无损PNG保存/回读。

H拒绝非3×3、非有限、奇异/病态；点拒绝不足4、重复退化或共线。投影无穷远线穿右图、画布单边≥32767、像素数超过max_canvas_pixels或无有效重叠均在正式发布前报错。默认20百万像素上限用于资源保护，不代表拼接质量门槛。正式运行另需≥30配对、实际内点率>50%，数量通过不替代视觉检查。

LatestRun('lab8')锁定同实验，先在stage完成全部pytest、图像回读及13项正式检查，再替换输出/证据。发布第二目录失败时两者回滚；输入、其他实验和data/annotations不清理。报告同时留于证据内，发布后写统一docs报告。失败输出ERROR/非零，旧完整结果保留。pytest临时目录显式为项目.tmp/pytest_lab8，不使用系统默认C盘pytest目录。

## 测试与现实限制

test_pipeline.py的三个必做断言和已知透视精度测试，跑固定种子的真实SIFT→匹配→RANSAC；夹具只用于自检，不冒充个人照片。test_lab8.py涵盖已知H与25%外点、退化、无穷远、资源、黑像素、独占区、输入不变、换图入口和发布失败回滚；合计37项新测试。实际输入另外检查13项，证据不靠测试夹具替代。

单H不普遍对齐任意三维场景，水面/浮冰/移动物体或反射会有局部差异；羽化主要减少亮度接缝。每次换图需看共同静态区域。未标定照片不能证明精确≥30°；图片提供者不自动等于拍摄者。真实M1参与者、评分、截图和个人提交见user_tasks.md，不由技术运行完成。
