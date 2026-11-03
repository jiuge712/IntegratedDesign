# 实验九 相机标定与去畸变报告

运行时间：2026-11-03T19:55:23+08:00。程序9.0.0。姓名、学号、班级、本人实验日期：待本人填写。

## 范围与素材

用户明确授权程序生成本实验棋盘格。当前source_kind=synthetic，camera_id=lab9_synthetic_v1_seed9，物理相机已标定状态=False。**合成实验验证了代码链路，不是对你的手机或实验七/八照片相机的测量。** 未伪造实拍、摄影者、拍摄时间或真实采集活动。若课程额外限定实拍，按user_tasks.md的条件任务处理；本次已获生成授权，无需为程序运行补图。

输入目录D:\IntegratedDesign\project_i\data\calib\lab9_synthetic，图像尺寸[1280, 960]（W,H）；内角点9×7=63，方格边长25.0mm。9×7内角点对应10×8格子，不能把格子数当内角点数。合成板的mm只定义模型坐标单位，不代表打印实测尺寸。旧实验五chess.png未修改，不适合直接代替15张多姿态图。

prepare_lab9.py用针孔+5系数畸变模型逆投影绘制20个姿态的棋盘，2倍像素中心采样后缩小，轻微模糊及固定seed=9噪声。另有2张独立验证图，不参与内参拟合；source_manifest.json记录真实K/dist、位姿、63点投影、面积和每文件SHA。素材在data/calib/lab9_synthetic，源文件持久保留，重复生成只校验，内容被改则拒绝覆盖。

## 检测与标定

输入20张，可用20张，检出率100.00%。每张findChessboardCorners后用cornerSubPix，窗口11×11、40次/0.001终止；未检出/不能解码的原文件只记录排除、不删除。要求可用≥15，同一相机同分辨率；混合尺寸、完全重复图片、规格或生成清单哈希不符会拒绝。OpenCV5可返回(N,2)角点，接口统一成(N,1,2)供存档和后续调用。

calibrateCamera输入只有模型板3D点和从像素实际检测的2D点，K/dist初值为None。K为像素焦距与主点，外参遵循X_camera=R X_board+t。畸变顺序[k1,k2,p1,p2,k3]，不是k1/k2/k3/p1/p2。求解结果：

```text
K = [
  [
    1099.9573600121341,
    0.0,
    643.182612789891
  ],
  [
    0.0,
    1119.9485567206189,
    476.7308115016081
  ],
  [
    0.0,
    0.0,
    1.0
  ]
]
dist = [-0.17985452172428215, 0.04567116091895118, 0.0010190917034497806, -0.0006991134298371497, -0.0001573718959511382]
```

OpenCV全局RMS=0.046396px，独立按sqrt(所有角点二维误差平方和/角点总数)复算=0.046397px。每图RMS同一定义，不把平均距离除角点数的另一公式误称RMS。

未调用本次11×11精化时RMS=0.079415px；精化后=0.046396px。这是同一图片集的实际前后对照，不承诺每种数据必然改善，也不因结果不利改数或删图。成像采样、抗锯齿、亚像素窗口及噪声影响残差；实拍还会受虚焦/运动、照明、板不平和姿态不足影响。若真实数据不合格应记录具体问题、改进并重跑，不虚构“已重新拍摄”。

![20张角点检测总览](../data/output/lab9_latest/l9_detection_overview.png)

![每图重投影RMS与所有角点误差分布](../data/output/lab9_latest/l9_reprojection_errors.png)

估计板法线俯仰跨度49.101°，偏航跨度57.051°；定义是法线的atan2角，不是相机真实运动记录。棋盘外轮廓投影面积比例最小34.00%，是四边形近似，生成清单另有渲染实际占比。各图坐标/外参/角点保存在NPZ，collection.json记录用图和剔除理由。

已知生成K仅在求解完成后作独立比较，未传给calibrateCamera。fx/fy相对误差为[3.876362533260776e-05, 4.593149944745229e-05]，主点误差0.0354px；畸变系数逐项差值为[0.0001454782757178419, 0.000671160918951183, 1.9091703449780574e-05, 8.865701628502738e-07, -0.005157371895951138]。高阶k3等存在参数耦合，低RMS不等于每个畸变系数都被唯一精确恢复；应同时看独立图和重投影表现。

## 去畸变和独立验证

用cv2.undistort(image,K,dist,None,K)保持同尺寸和同一K，黑色边缘保留，不通过裁剪隐藏残余。直线度用棋盘每行/列的正交TLS直线拟合残差RMS，校正前平均0.718925px，undistortPoints校正后平均0.029302px。每个角点同时属于一行和一列，统计定义固定，不能将其称为图像差值PSNR。

独立验证图未参加K/dist优化；固定所求K/dist求每图位姿并计算重投影，再对undistort后的实际像素图重新检测角点，测量直线度：

| 独立图 | 重投影RMS px | 原图直线度 px | 去畸变图重新检测直线度 px |
| --- | --- | --- | --- |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\validation\validation_01.png | 0.05320 | 0.71304 | 0.03028 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\validation\validation_02.png | 0.03865 | 0.63690 | 0.02467 |

![同尺寸去畸变前后](../data/output/lab9_latest/l9_undistort_compare.png)

![姿态与逐图直线度](../data/output/lab9_latest/l9_pose_and_straightness.png)

RMS<0.5px为本实验设定的优秀门槛，不是所有实拍设备的通用保证。直线度要求校正后<0.5px且改善；原本已近似无畸变（<0.1px）允许0.05px数值波动，避免强迫对零畸变数据制造“改善”。

## 验证与交付

全项目260项主用例及15项子用例通过；本次13项实际验收，生成27张PNG。test_plan_l9.md逐条列出测试项、输入/步骤、预期与本次实际，包含数据记录；pytest.log/xml、per_view_metrics.csv、collection.json、corners_and_poses.npz是实测证据，不冒充本人终端截图。

正式结果data/output/lab9_latest，证据evidence/lab9_latest，每次成功只保留最新完整结果，失败保留旧结果与results兼容导出。指导书要求的results/K.npy、results/dist.npy、results/calib_result.json已同步；JSON最后发布并带数组SHA，load_calibration必须核对相机ID、尺寸及文件哈希，拒绝合成K用于其他照片或部分更新。读取NPY/NPZ使用allow_pickle=False。

复现见reproduction.md，素材/换图见image_requirements.md，接口见lab9_design.md。源码包deliverables/lab9_source.zip不含素材、输出、results、证据或环境；先运行生成器即可重建本次源图。本人报告信息、真实截图、课程提交及条件性实拍任务见user_tasks.md，未自动勾选。

依据：[OpenCV标定教程](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html)、[相机模型与标定API](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)。本机实际库版本见environment.md，非引用网页版本冒充运行版本。
