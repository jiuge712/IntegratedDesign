# 实验九 集成测试计划与实际执行

版本9.0.0，执行时间2026-11-03T19:55:23+08:00，自动技术执行者为代理；不冒充本人/真实同学。范围是角点检测→亚像素→calibrateCamera→重投影评价→undistort→直线度→参数导出；后续L10–L12尚未实现。本次数据为synthetic，不宣称物理手机已标定。

## 环境 数据与执行步骤

解释器/依赖见environment.md。输入D:\IntegratedDesign\project_i\data\calib\lab9_synthetic，20张，同尺寸[1280, 960]，内角点63个/图，方格25.0mm。生成器固定seed=9，20张拟合图和2张独立图分开；源码ZIP不附图，先prepare_lab9.py再run_lab9.py。真实换图须同相机/焦段/尺寸与完整平面棋盘，配置修改无需源码变更。

所有用例共用步骤：①核验输入/来源；②findChessboardCorners及cornerSubPix，记录失败不删原片；③检查≥15可用图，calibrateCamera不接收真值初值；④复算各图误差和法线角度、板面积；⑤undistort并评价TLS直线度/独立图；⑥检查全部pytest、PNG/原图哈希；⑦LatestRun及results兼容导出。下表给出每个测试项的判定和本次实际；完整数值及逐角点在results.json/NPZ。

## 本次实际验收

| 编号 | 测试项 | 输入 | 步骤 | 预期 | 实际 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| IT9-01 | 可用棋盘格数量 | 标定目录与检测记录 | 枚举、检测、排除失败项，再计可用数 | >=15 | 20 | 通过 |
| IT9-02 | 每张内角点数 | 每图refined角点 | 检查数组shape并计数 | cols*rows | 63 | 通过 |
| IT9-03 | 俯仰覆盖 | 标定rvecs | 转R并计算板法线俯仰最大值减最小值 | >=30 deg | 49.10067639600768 | 通过 |
| IT9-04 | 偏航覆盖 | 标定rvecs | 转R并计算板法线偏航最大值减最小值 | >=30 deg | 57.05104407055593 | 通过 |
| IT9-05 | 棋盘画面占比 | K/dist、外参与外轮廓 | 投影四角，算四边形面积/画面面积并取最小 | >=configured fraction | 0.34000159564821736 | 通过 |
| IT9-06 | 标定RMS | 全部检测点与calibrateCamera输出 | projectPoints复算二维残差RMS并与返回值比较 | < configured max_rms | 0.04639619427244997 | 通过 |
| IT9-07 | 去畸变角点直线度 | 校正前后角点 | 逐行列TLS直线拟合并比较平均残差RMS | decreases and <0.5px | 0.02930215799625167 | 通过 |
| IT9-08 | 未参与拟合的验证图 | 独立validation图片 | 固定K/dist求位姿，去畸变像素图重检角点并计算直线度 | RMS<max and redetected lines improve | [{"path": "D:\\IntegratedDesign\\project_i\\data\\calib\\lab9_synthetic\\validation\\validation_01.png", "sha256": "e9005a119bac311c9a10998331d5413d2e21c682782a20bd8b35bc3eee16e595", "not_used_for_fitting": true, "rms": 0.05319805443286896, "straightness_before_px": 0.7130418429296694, "straightness_after_redetection_px": 0.03028073355790215}, {"path": "D:\\IntegratedDesign\\project_i\\data\\calib\\lab9_synthetic\\validation\\validation_02.png", "sha256": "77d33b82e82a70b37976644f48dbbee7db9cd6ca2545307d1db6d52eba6bc0fb", "not_used_for_fitting": true, "rms": 0.038651637732982635, "straightness_before_px": 0.6368996580242295, "straightness_after_redetection_px": 0.024670534595910634}] | 通过 |
| IT9-09 | 已知合成K独立恢复 | 生成清单真值与求解K | 仅在拟合后比较焦距相对误差与主点欧氏误差 | focal errors<2%; principal error<2px | [3.876362533260776e-05, 4.593149944745229e-05] | 通过 |
| IT9-10 | 全项目测试 | src内全部pytest/unittest | 项目D盘临时目录中执行并检查退出码/JUnit | no failures/errors/skips | 260 | 通过 |
| IT9-11 | 输入素材未变 | 所有标定/独立图 | 比较运行前后SHA-256 | all SHA256 unchanged | 22 | 通过 |
| IT9-12 | 角点归档回读 | corners_and_poses.npz | allow_pickle=False读取并逐数组比较 | N*63 observed corners | [20, 63, 1, 2] | 通过 |
| IT9-13 | 全部PNG可回读 | 最新结果目录PNG | 逐张解码并检查非空 | all PNG decoded | 27 | 通过 |

K/dist的shape、正焦距和有限性在calibrate_views内部校验；导出时load_calibration核验camera_id、尺寸、NPY哈希。results三文件备份/恢复及LatestRun发布回滚有单测，额外失败保留/换图/陈旧清单验证见evidence/lab9_latest/integration_verification.json。没有把文件存在当作所有质量断言通过。

## 数据收集与排除记录

| 输入文件 | SHA-256 | 实际处理 |
| --- | --- | --- |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_01.png | bd63785d92f38d02975a7c099e2b6fdb317452b48ab81a0a95a738ac8f6599aa | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_02.png | 4580c7e08cab0106ca54fb92d26dcd4680e5dba2f43147a5f106039973912f64 | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_03.png | 987abee17063a9a624a517c4ac8b3a99260a8ed46a20a86bbbd87e0b449e0ca4 | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_04.png | 25d61aa6ef2d162f389410a76289aa4ad3045823e4d19ebb58e917fafc30fedd | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_05.png | b394282127dd3c64c94d3e77c0edef070a426651e48701eafcbb043f369d4271 | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_06.png | 5433cff2d379747aa04a0bbc0d00027c006d423ccff4ffd7654fac7e064f10e0 | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_07.png | 23e42e2f3733710f463d2296cc681db1d36d451b6585b6be88a68cba5896dbba | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_08.png | 4a8eadb6a73688d687c8c6b43ac441d0b616fb871855d0937370eb2a684fac20 | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_09.png | f386e822abfc5bd3ed6a6418d3502108c9d3f0d7f09efd0458609c645d073cf5 | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_10.png | 657c559a0bbe180642e9f728aa690aa65f44e2976982595e8477f205138876ce | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_11.png | 131095a8838beab1c4ea665c66d890b083571aaede099956e79e2179f7cbc874 | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_12.png | b2c6a1bb85dd92d899d6916a5bdc13bfd675200da830845a9adf43b171160e75 | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_13.png | 777c6fdce786d6146af148e0038fa7ebdb96bf7cbbe8434024ff30864585bae9 | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_14.png | 454ffe2014c98de7d100644e0424d880c77b8a453cf735ddad91071f7b8ead1d | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_15.png | 757610cfd7883409d80b130566d2b47e23b49766527b3c6010f0a52cd2dd1a7a | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_16.png | 24f5766d87b037cf94e906dcbeb51a78700b252119d6de52075c8c8396b83edf | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_17.png | 46d6f9db846b87e74b537a0e048f17326ad3bf5b7bdfcbfaf5c6d9acf3b7bdfe | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_18.png | 48e3736a566bf1ba2dad9fa19ecafe049ccfa22374841ffa7110c7c93fdc9fbe | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_19.png | 955939ad327188c396e59556dce9973efe17e05e2fd4e38eab12edd05f4332b3 | 使用 |
| D:\IntegratedDesign\project_i\data\calib\lab9_synthetic\calib_20.png | 34b9aa97f490455442a8121eb9bc1a06897bdc595d0d5b248dd961cdf66f1796 | 使用 |

检出率100.00%，可用20张；俯仰跨度49.101°、偏航57.051°。角度是模型板法线定义，不是伪造的摄影者记录。生成来源清单含已知位姿、渲染占比、真实K/dist和独立图，但这些不参与内参求解。

## 风险 退出与再执行

不足15、混合分辨率、重复素材、错误规格/清单、角度或占比不足、RMS超限、直线度不合格均非零退出；旧完整结果与兼容导出保留。拒绝把latest输出当持久输入。真正近零畸变时直线度允许明确的小波动，不为满足“改善”编造数据。

本人复现时执行reproduction.md命令并记录真实时间/截图；新增实拍集沿用这些验收步骤，若失败写入真实原因、处理和前后指标，再重新运行，不把合成数据的通过直接复制成实拍通过。个人活动始终见user_tasks.md，未获明确确认仍未完成。
