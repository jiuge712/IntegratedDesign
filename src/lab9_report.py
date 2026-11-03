"""Report and executed integration test plan from measured lab-nine data."""
import json


def report_text(info):
    truth=info['known_truth']
    truth_text=('本次无已知相机真值，不报告恢复精度。' if truth is None else
        f'已知生成K仅在求解完成后作独立比较，未传给calibrateCamera。fx/fy相对误差为{truth["focal_relative_errors"]}，主点误差{truth["principal_point_error_px"]:.4f}px；'
        f'畸变系数逐项差值为{truth["distortion_coefficient_errors"]}。高阶k3等存在参数耦合，低RMS不等于每个畸变系数都被唯一精确恢复；应同时看独立图和重投影表现。')
    validation='\n'.join(f'| {v["path"]} | {v["rms"]:.5f} | {v["straightness_before_px"]:.5f} | {v["straightness_after_redetection_px"]:.5f} |' for v in info['validation'])
    return f'''# 实验九 相机标定与去畸变报告

运行时间：{info['time']}。程序{info['program_version']}。姓名、学号、班级、本人实验日期：待本人填写。

## 范围与素材

用户明确授权程序生成本实验棋盘格。当前source_kind={info['source_kind']}，camera_id={info['camera_id']}，物理相机已标定状态={info['physical_camera_calibrated']}。**合成实验验证了代码链路，不是对你的手机或实验七/八照片相机的测量。** 未伪造实拍、摄影者、拍摄时间或真实采集活动。若课程额外限定实拍，按user_tasks.md的条件任务处理；本次已获生成授权，无需为程序运行补图。

输入目录{info['input_directory']}，图像尺寸{info['image_size']}（W,H）；内角点{info['parameters']['cols']}×{info['parameters']['rows']}={info['corners_per_image']}，方格边长{info['parameters']['square_size_mm']}mm。9×7内角点对应10×8格子，不能把格子数当内角点数。合成板的mm只定义模型坐标单位，不代表打印实测尺寸。旧实验五chess.png未修改，不适合直接代替15张多姿态图。

prepare_lab9.py用针孔+5系数畸变模型逆投影绘制20个姿态的棋盘，2倍像素中心采样后缩小，轻微模糊及固定seed=9噪声。另有2张独立验证图，不参与内参拟合；source_manifest.json记录真实K/dist、位姿、63点投影、面积和每文件SHA。素材在data/calib/lab9_synthetic，源文件持久保留，重复生成只校验，内容被改则拒绝覆盖。

## 检测与标定

输入{info['input_count']}张，可用{info['detected_count']}张，检出率{info['detection_rate']:.2%}。每张findChessboardCorners后用cornerSubPix，窗口11×11、40次/0.001终止；未检出/不能解码的原文件只记录排除、不删除。要求可用≥15，同一相机同分辨率；混合尺寸、完全重复图片、规格或生成清单哈希不符会拒绝。OpenCV5可返回(N,2)角点，接口统一成(N,1,2)供存档和后续调用。

calibrateCamera输入只有模型板3D点和从像素实际检测的2D点，K/dist初值为None。K为像素焦距与主点，外参遵循X_camera=R X_board+t。畸变顺序[k1,k2,p1,p2,k3]，不是k1/k2/k3/p1/p2。求解结果：

```text
K = {json.dumps(info['K'],indent=2)}
dist = {json.dumps(info['dist'])}
```

OpenCV全局RMS={info['rms']:.6f}px，独立按sqrt(所有角点二维误差平方和/角点总数)复算={info['recomputed_rms']:.6f}px。每图RMS同一定义，不把平均距离除角点数的另一公式误称RMS。

未调用本次11×11精化时RMS={info['raw_corner_rms']:.6f}px；精化后={info['rms']:.6f}px。这是同一图片集的实际前后对照，不承诺每种数据必然改善，也不因结果不利改数或删图。成像采样、抗锯齿、亚像素窗口及噪声影响残差；实拍还会受虚焦/运动、照明、板不平和姿态不足影响。若真实数据不合格应记录具体问题、改进并重跑，不虚构“已重新拍摄”。

![20张角点检测总览](../data/output/lab9_latest/l9_detection_overview.png)

![每图重投影RMS与所有角点误差分布](../data/output/lab9_latest/l9_reprojection_errors.png)

估计板法线俯仰跨度{info['coverage']['pitch_span_deg']:.3f}°，偏航跨度{info['coverage']['yaw_span_deg']:.3f}°；定义是法线的atan2角，不是相机真实运动记录。棋盘外轮廓投影面积比例最小{min(info['projected_board_fractions']):.2%}，是四边形近似，生成清单另有渲染实际占比。各图坐标/外参/角点保存在NPZ，collection.json记录用图和剔除理由。

{truth_text}

## 去畸变和独立验证

用cv2.undistort(image,K,dist,None,K)保持同尺寸和同一K，黑色边缘保留，不通过裁剪隐藏残余。直线度用棋盘每行/列的正交TLS直线拟合残差RMS，校正前平均{info['straightness_mean_before_px']:.6f}px，undistortPoints校正后平均{info['straightness_mean_after_px']:.6f}px。每个角点同时属于一行和一列，统计定义固定，不能将其称为图像差值PSNR。

独立验证图未参加K/dist优化；固定所求K/dist求每图位姿并计算重投影，再对undistort后的实际像素图重新检测角点，测量直线度：

| 独立图 | 重投影RMS px | 原图直线度 px | 去畸变图重新检测直线度 px |
| --- | --- | --- | --- |
{validation or '| 未提供独立验证图 | 未执行 | 未执行 | 未执行 |'}

![同尺寸去畸变前后](../data/output/lab9_latest/l9_undistort_compare.png)

![姿态与逐图直线度](../data/output/lab9_latest/l9_pose_and_straightness.png)

RMS<0.5px为本实验设定的优秀门槛，不是所有实拍设备的通用保证。直线度要求校正后<0.5px且改善；原本已近似无畸变（<0.1px）允许0.05px数值波动，避免强迫对零畸变数据制造“改善”。

## 验证与交付

全项目{info['pytest']['tests']}项主用例及{info['pytest']['subtests']}项子用例通过；本次{len(info['checks'])}项实际验收，生成{info['png_count']}张PNG。test_plan_l9.md逐条列出测试项、输入/步骤、预期与本次实际，包含数据记录；pytest.log/xml、per_view_metrics.csv、collection.json、corners_and_poses.npz是实测证据，不冒充本人终端截图。

正式结果data/output/lab9_latest，证据evidence/lab9_latest，每次成功只保留最新完整结果，失败保留旧结果与results兼容导出。指导书要求的results/K.npy、results/dist.npy、results/calib_result.json已同步；JSON最后发布并带数组SHA，load_calibration必须核对相机ID、尺寸及文件哈希，拒绝合成K用于其他照片或部分更新。读取NPY/NPZ使用allow_pickle=False。

复现见reproduction.md，素材/换图见image_requirements.md，接口见lab9_design.md。源码包deliverables/lab9_source.zip不含素材、输出、results、证据或环境；先运行生成器即可重建本次源图。本人报告信息、真实截图、课程提交及条件性实拍任务见user_tasks.md，未自动勾选。

依据：[OpenCV标定教程](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html)、[相机模型与标定API](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html)。本机实际库版本见environment.md，非引用网页版本冒充运行版本。
'''


def test_plan_text(info):
    cases={
        '可用棋盘格数量':('标定目录与检测记录','枚举、检测、排除失败项，再计可用数'),
        '每张内角点数':('每图refined角点','检查数组shape并计数'),
        '俯仰覆盖':('标定rvecs','转R并计算板法线俯仰最大值减最小值'),
        '偏航覆盖':('标定rvecs','转R并计算板法线偏航最大值减最小值'),
        '棋盘画面占比':('K/dist、外参与外轮廓','投影四角，算四边形面积/画面面积并取最小'),
        '标定RMS':('全部检测点与calibrateCamera输出','projectPoints复算二维残差RMS并与返回值比较'),
        '去畸变角点直线度':('校正前后角点','逐行列TLS直线拟合并比较平均残差RMS'),
        '未参与拟合的验证图':('独立validation图片','固定K/dist求位姿，去畸变像素图重检角点并计算直线度'),
        '已知合成K独立恢复':('生成清单真值与求解K','仅在拟合后比较焦距相对误差与主点欧氏误差'),
        '全项目测试':('src内全部pytest/unittest','项目D盘临时目录中执行并检查退出码/JUnit'),
        '输入素材未变':('所有标定/独立图','比较运行前后SHA-256'),
        '角点归档回读':('corners_and_poses.npz','allow_pickle=False读取并逐数组比较'),
        '全部PNG可回读':('最新结果目录PNG','逐张解码并检查非空')}
    rows='\n'.join(f'| {r["id"]} | {r["name"]} | {cases[r["name"]][0]} | {cases[r["name"]][1]} | {r["expected"]} | {json.dumps(r["actual"],ensure_ascii=False) if isinstance(r["actual"],(list,dict)) else r["actual"]} | 通过 |' for r in info['checks'])
    collection='\n'.join(f'| {r["path"]} | {r["sha256"]} | {"使用" if r["detected"] else r.get("reason","剔除")} |' for r in info['collection'])
    return f'''# 实验九 集成测试计划与实际执行

版本{info['program_version']}，执行时间{info['time']}，自动技术执行者为代理；不冒充本人/真实同学。范围是角点检测→亚像素→calibrateCamera→重投影评价→undistort→直线度→参数导出；后续L10–L12尚未实现。本次数据为{info['source_kind']}，不宣称物理手机已标定。

## 环境 数据与执行步骤

解释器/依赖见environment.md。输入{info['input_directory']}，{info['input_count']}张，同尺寸{info['image_size']}，内角点{info['corners_per_image']}个/图，方格{info['parameters']['square_size_mm']}mm。生成器固定seed=9，20张拟合图和2张独立图分开；源码ZIP不附图，先prepare_lab9.py再run_lab9.py。真实换图须同相机/焦段/尺寸与完整平面棋盘，配置修改无需源码变更。

所有用例共用步骤：①核验输入/来源；②findChessboardCorners及cornerSubPix，记录失败不删原片；③检查≥15可用图，calibrateCamera不接收真值初值；④复算各图误差和法线角度、板面积；⑤undistort并评价TLS直线度/独立图；⑥检查全部pytest、PNG/原图哈希；⑦LatestRun及results兼容导出。下表给出每个测试项的判定和本次实际；完整数值及逐角点在results.json/NPZ。

## 本次实际验收

| 编号 | 测试项 | 输入 | 步骤 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
{rows}

K/dist的shape、正焦距和有限性在calibrate_views内部校验；导出时load_calibration核验camera_id、尺寸、NPY哈希。results三文件备份/恢复及LatestRun发布回滚有单测，额外失败保留/换图/陈旧清单验证见evidence/lab9_latest/integration_verification.json。没有把文件存在当作所有质量断言通过。

## 数据收集与排除记录

| 输入文件 | SHA-256 | 实际处理 |
| --- | --- | --- |
{collection}

检出率{info['detection_rate']:.2%}，可用{info['detected_count']}张；俯仰跨度{info['coverage']['pitch_span_deg']:.3f}°、偏航{info['coverage']['yaw_span_deg']:.3f}°。角度是模型板法线定义，不是伪造的摄影者记录。生成来源清单含已知位姿、渲染占比、真实K/dist和独立图，但这些不参与内参求解。

## 风险 退出与再执行

不足15、混合分辨率、重复素材、错误规格/清单、角度或占比不足、RMS超限、直线度不合格均非零退出；旧完整结果与兼容导出保留。拒绝把latest输出当持久输入。真正近零畸变时直线度允许明确的小波动，不为满足“改善”编造数据。

本人复现时执行reproduction.md命令并记录真实时间/截图；新增实拍集沿用这些验收步骤，若失败写入真实原因、处理和前后指标，再重新运行，不把合成数据的通过直接复制成实拍通过。个人活动始终见user_tasks.md，未获明确确认仍未完成。
'''
