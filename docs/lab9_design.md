# 实验九 设计与接口

本实验增加标定分支，程序9.0.0，核心文件calibration.py，生成器prepare_lab9.py，正式入口run_lab9.py，指导书兼容入口lab9_calib.py。合成K只适用于该虚拟相机/分辨率，不被当成实验七八照片的内参。后续L10–L12尚未实现，导出是受来源约束的数据契约，不代表对极几何或三维重建已完成。

## 输入和合成来源

用户明确授权生成棋盘。data/calib/lab9_synthetic/calib_01.png至calib_20.png为拟合输入，validation/validation_01/02.png独立保留，board_template.png为模板，source_manifest.json记录seed=9、生成版本1、每文件SHA、已知K/dist、位姿、板占比与63个真实投影点。生成图片是带畸变的数学渲染，不称实拍。旧实验五7×7内角点棋盘不被改写。

1280×960虚拟相机，9×7内角点/10×8格、25mm方格。对每个输出像素反求无畸变相机射线，与R/t定义的板平面相交并采样棋盘纹理；2倍像素中心采样后INTER_AREA缩小，模糊sigma.45像素与固定种子噪声sigma.4灰度级。姿态覆盖四个俯仰层和五个偏航层，棋盘完整入画且渲染占比≥30%。真实K/dist只进入渲染和拟合后的独立误差评价，不传入calibrateCamera；同模型合成验证不能证明真实镜头的其他误差都已建模。

生成器只允许data/calib内独立子目录，先stage再发布；已有源图只在参数/全部哈希匹配时复用，未知/修改内容拒绝覆盖。生成图和模板持久保留，输出清理不涉及它们。源码ZIP与Git排除data/calib，复制源码后先执行生成器即可复现；不下载素材。

## 接口

| 函数 | 输入 | 输出与边界 |
| --- | --- | --- |
| board_points(cols=9,rows=7,square_size=25.) | 内角点数、毫米格长 | N×3 float32，Z=0，x列/y行；不是外部格子数 |
| detect_board(image,cols=9,rows=7) | uint8灰度/BGR/BGRA | raw/refined各(N,1,2) float32，失败None，不修改输入 |
| calibrate_views(corners,image_size,...,min_views=15) | 同尺寸(W,H)、观察角点列表 | K float64 3×3、5系数dist、各图rvec/tvec、全局/逐图/逐点误差 |
| pose_coverage(rvecs) | 板→相机旋转向量 | 板法线的pitch/yaw及跨度，不冒充摄影者测量 |
| straightness(points,cols,rows) | 同序角点 | 各行列TLS正交距离的合并RMS，单位像素 |
| undistort_image(image,K,dist) | 同一相机同尺寸图 | 用同一K去畸变，保留原大小/黑边，不改输入 |
| load_calibration(folder,expected_camera_id,expected_size) | 三文件和来源/尺寸 | 验camera_id、分辨率、K/dist文件SHA后allow_pickle=False读取，返回K/dist/元数据 |

OpenCV5返回角点(N,2)的实际差异已归一化，也兼容4.x的(N,1,2)。每张使用findChessboardCorners的自适应阈值/归一化标志和cornerSubPix(11,11)、40次/.001。可解码但没检出者记录排除；损坏文件记录cannot_decode；原片不删除。混合分辨率、完全重复图片、少于15成功图、生成规格/清单陈旧等明确失败，不自动缩放或重复计数凑足。

## 几何与验收

X_camera=R X_board+t，t单位与square_size一致（本次虚拟mm）；K单位像素。dist顺序[k1,k2,p1,p2,k3]，不能将k3放到第三项。RMS=sqrt(sum二维残差平方/总角点数)，与OpenCV返回值独立复算；每图同定义，保存所有观察点而非只保存真值。

板法线n为R第三列并取nz≥0，pitch=atan2(-ny,hypot(nx,nz))，yaw=atan2(nx,nz)。外轮廓由扩展到10×8格的四角投影近似面积，生成清单另有实际渲染mask面积。默认验收可用≥15、俯仰/偏航跨度各≥30°、画面占比≥30%、RMS<0.5px；配置可收严，RMS最多放至1px可用门槛，角度/面积不得调低以伪通过。

去畸变角点TLS直线度需<0.5px并改善；原已近零(<.1px)允许+.05px，避免硬逼无畸变图“改善”。另2张独立图不参加K/dist优化，固定内参求位姿算RMS，再对去畸变后的像素图重新检测测直线度；已知K只在最后比对，强调高阶畸变参数耦合和可辨识性限制。

## 发布与结果契约

LatestRun('lab9')校验后替换data/output/lab9_latest与evidence/lab9_latest，只保留最新完整运行。输出含27张PNG、K.npy/dist.npy/calib_result.json；NPZ、CSV、采集记录和测试日志在证据。正式输入禁止位于results、data/output、docs或evidence；原图、其他实验结果和持久标签不清理。

指导书兼容导出固定results/K.npy、results/dist.npy、results/calib_result.json，JSON最后写入并带数组哈希。读者需调用load_calibration核对来源/尺寸/SHA，拒绝更新中间态和用于其他相机；不可只见到K.npy就套用。导出备份旧三文件，任何写入或canonical发布失败都恢复；外层LatestRun也回滚两目录，相关失败注入有单测。跨三个文件的瞬时读取不保证一起替换，JSON提交标志与哈希校验是完整性边界。

已有results目录其他文件不清理，K/dist路径若为链接/目录拒绝写入。pytest显式使用项目.tmp/pytest_lab9和.tmp/pytest_lab9_cache，不依赖C盘默认临时目录。结果中源类型synthetic、physical_camera_calibrated=false、camera_id和image_size必须保留，不能抹去元数据把合成结果改称实拍。

## 现实活动

36项新增测试、260项全项目主用例+15子用例、13项实际验收和9项换图/失败保留集成检查由代理执行，不是本人已复现。用户任务状态、条件性实拍、真实截图、个人信息和课程提交见user_tasks.md，未自动完成。集成计划见test_plan_l9.md，报告含亚像素前后RMS及高阶系数限制，Git真实状态见lab9_git_workflow.md。
