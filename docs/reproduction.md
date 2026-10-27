# 各实验统一复现指南

本文件是固定的复现入口，目前覆盖实验一至七。后续每完成一个实验，都增加对应指导，并同步更新 image_requirements.md。维护规则已写入项目 AGENTS.md，两个入口沿用原文件名。需要你本人参与的任务见 user_tasks.md；未明确告知已完成的任务继续保持未完成。实验七人工误配率待真实标签补齐，不将程序完成等同课堂活动完成。

图片由你提供；格式、尺寸、亮度、Alpha 和噪声派生版本记录来源与参数。实验五棋盘已获你明确授权由程序绘制，作为正式素材并记录来源。每个实验的个人输出与证据只保留最新一次完整运行，原始输入保留。

## 共同环境与安装

```powershell
Set-Location D:\IntegratedDesign\project_i
py -0p
```

当前已有 .venv，直接使用解释器即可，不必激活。首次复现或换机器时：

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -X utf8 src/version_check.py
```

本次实测 Windows 11 AMD64、Python 3.14.7，具体库版本见 environment.md 与 requirements.txt。依赖为 OpenCV、NumPy、Matplotlib，实验三新增scikit-image，实验五新增pytest 9.1.1及传递依赖。旧环境也应执行 pip install -r requirements.txt。不要复制其他机器的 .venv；WindowsApps 占位 python 不能启动时使用 py 或真实解释器路径。

普通复现保留锁定版本。主动升级依赖才用 version_check.py --freeze requirements.txt 更新记录。离线安装可先在同平台同 Python 联网机器下载 wheels，再复制到离线机：

```powershell
.\.venv\Scripts\python.exe -m pip download -r requirements.txt -d wheels
.\.venv\Scripts\python.exe -m pip install --no-index --find-links wheels -r requirements.txt
```

## 已完成实验入口

| 实验 | 配置 | 一键执行 | 报告 | 个人最新输出 |
| --- | --- | --- | --- | --- |
| 一 读取与灰度基线 | config/images.json | src/run_tests.py | docs/test_report.md、docs/lab_report.md | data/output/lab1_latest |
| 二 基本运算与均衡化 | config/lab2_images.json | src/run_lab2.py | docs/lab2_report.md | data/output/lab2_latest |
| 三 空间滤波与增强 | config/lab3_images.json | src/run_lab3.py | docs/lab3_report.md | data/output/lab3_latest |
| 四 边缘与阈值分割 | config/lab4_images.json | src/run_lab4.py | docs/lab4_report.md | data/output/lab4_latest |
| 五 角点与尺度空间 | config/lab5_images.json | src/run_lab5.py | docs/lab5_report.md | data/output/lab5_latest |
| 六 SIFT提取与描述 | config/lab6_images.json | src/run_lab6.py | docs/lab6_report.md | data/output/lab6_latest |
| 七 特征匹配与误配分析 | config/lab7_images.json | src/run_lab7.py | docs/lab7_report.md | data/output/lab7_latest |

对应证据为 evidence/labN_latest。图片放在 data/input，不能放入 data/output、docs 或 evidence。JSON和一键二至七的图片覆盖相对路径按project_i根目录解释。实验一单张工具按当前工作目录解释，建议始终先Set-Location。人工持久CSV放data/annotations，避免latest替换清理。

## 实验一复现

完整图片条件见 image_requirements.md。现有八类素材已准备好，直接执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/run_tests.py
$LASTEXITCODE
```

17 项正式用例应通过。异常用例预期 ERROR/非零退出码，符合预期时测试仍标记 PASS。输出为同尺寸单通道 PNG；灰度像素保持，彩色转灰度，Alpha 舍弃。实验一支持 uint8/uint16。

只提供新彩色源图时，沿用已有黑白图，先准备素材：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/prepare_inputs.py --source "data/input/新原图.jpg"
.\.venv\Scripts\python.exe -X utf8 src/run_tests.py
```

黑白图改名时增加 --black/--white 实际路径。准备脚本只在新建 prepared_ 目录创建格式/灰度/Alpha/尺寸版本，更新 config/images.json 和来源记录，不修改原图。自行准备全套素材时直接改配置。

单张运行示例，读取当前配置避免写死派生路径：

```powershell
$labImages = Get-Content config/images.json -Raw | ConvertFrom-Json
.\.venv\Scripts\python.exe -X utf8 src/baseline_pipeline.py --input $labImages.color --output data/output/lab1_latest/manual_color_gray.png --record evidence/lab1_latest/manual_run.jsonl
.\.venv\Scripts\python.exe -X utf8 src/baseline_pipeline.py --input $labImages.gray --output data/output/lab1_latest/manual_gray_copy.png
```

日志打印 shape/dtype/ndim/channels、状态、耗时和哈希，并回读输出验证。输出必须 PNG，不能覆盖原图或写入输入目录。无个人素材时运行 run_tests.py --self-test，21 项临时数组自检单独保存，不代替正式结果。

## 实验二复现

normal 是正常亮度图，dark 是偏暗图，low_contrast 是低对比度图，均为 uint8。已同意从同一插画派生；dark/low_contrast=null 时分别按 0.45*gray、0.3*gray+80 生成，填写路径则使用个人独立图片。

```powershell
.\.venv\Scripts\python.exe -X utf8 src/test_lab2.py
.\.venv\Scripts\python.exe -X utf8 src/run_lab2.py
$LASTEXITCODE
.\.venv\Scripts\python.exe -X utf8 src/package_lab2.py
```

22 项数值/边界自检与 13 项正式检查应通过。生成线性、gamma=2.2/0.5、回绕/饱和加法、混合、减法与乘除、三类直方图及手写/API均衡化。伽马公式为 255*(r/255)^(1/gamma)，2.2 提亮、0.5 压暗。均衡化以 int16 差值记录最大误差和差异像素。

换图可改配置，也可覆盖：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/run_lab2.py --normal "data/input/新原图.jpg"
.\.venv\Scripts\python.exe -X utf8 src/run_lab2.py --normal "data/input/正常图.jpg" --dark "data/input/暗图.jpg"
```

两图运算要求同尺寸，不隐式拉伸。主要图为 l2_transform_compare.png、l2_arith_compare.png、l2_hist_compare.png、l2_eq_compare.png。完整直方图/CDF/LUT见 evidence/lab2_latest/histograms.json。API调研和技术评审见 api_notes.md、mvp_review.md；真实课堂互评由参与者补充。

## 实验三复现

提供一张清晰、纹理与边缘丰富的 uint8 参考图，宽高至少 7，建议 640×480 至 1920×1080。本次继续使用你的插画；含噪图按要求生成，无需另提供噪声图片。

```powershell
.\.venv\Scripts\python.exe -X utf8 src/test_lab3.py
.\.venv\Scripts\python.exe -X utf8 src/run_lab3.py
$LASTEXITCODE
.\.venv\Scripts\python.exe -X utf8 src/package_lab3.py
```

22 项自检、9 项正式检查应通过，生成 27 张图像/对比图及评分表。参考图 PSNR=∞、SSIM=1；JSON以 psnr_db=null、psnr_infinite=true 表示无穷。评分比较相同尺寸的参考图和处理图。

lab3_images.json 的 input 为参考路径。seed 默认 0，高斯标准差 25；椒盐使用 seed+1，总概率 0.10（黑白各 0.05）。均值/中值核 5，高斯 sigma=1.5 自动核，拉普拉斯系数 0.8，USM 系数 0.6、sigma=2.0。也保存双边滤波加分对比。

换图或改配置后再次运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/run_lab3.py --input "data/input/新参考图.jpg"
```

相同输入、种子、参数和库版本下，含噪和算法结果可重复；记录时间和耗时会变化。不要把真实未知噪声图当作无噪声真值。参考 JPEG 原有压缩痕迹属于固定参考信号，评分只评价额外加入的噪声。

主要图为 l3_gaussian_compare.png、l3_salt_pepper_compare.png、l3_sharpen_compare.png、l3_detail_compare.png、l3_architecture.png。评分见 evidence/lab3_latest/quality.csv；参数、种子、版本、哈希见 results.json。架构和接口见 architecture.md、interface_agreement.md。

preprocess(img_bgr,cfg) 接收 uint8 BGR，输出同尺寸 BGR，不修改输入。一键实验已真实调用，其原图、含噪输入和输出三张彩色图以 l3_interface_ 开头。灰度/BGRA需在加载边界转换，不能直接冒充 BGR。

## 实验四复现

需要一张清晰纹理图和一张光照不均图，uint8，主入口宽高至少为5，建议宽高均≥31且640×480至1920×1080。当前texture使用你的插画；你于2026年10月20日明确告知已换实拍，uneven现为data/input/uneven_real.jpg（4096×3072、BGR uint8），原尺寸用于本实验。若以后设uneven=null，才从同图生成横向增益0.35→1.0的模拟版本，报告会区分来源。

```powershell
.\.venv\Scripts\python.exe -X utf8 src/test_lab4.py
.\.venv\Scripts\python.exe -X utf8 src/run_lab4.py
$LASTEXITCODE
.\.venv\Scripts\python.exe -X utf8 src/package_lab4.py
```

28项自检与12项正式检查应通过。当前真实uneven输入生成26张图像/对比图：Sobel核3/5的Gx/Gy/幅值，Canny三组50/150、100/200、150/250，固定128与Otsu，光照不均图的自适应Gaussian阈值，以及手写NMS/八邻域连接加分对比。只有模拟输入时另导出增益图，共27张。

Sobel梯度保持float64，显示图分别归一化，恒定图显示全黑。Canny先显式Gaussian sigma=1.0，apertureSize=3、L2gradient=True，手写分支也用同一设置。low/high需有限且0≤low<high；调整canny_pairs保留三组。阈值在原始梯度尺度上使用，不是显示幅值图的灰度。

Otsu实际阈值打印在控制台并写入报告。自适应blockSize默认31、C=5，窗口为≥3奇整数。实验结果显示白色区域比例和左右比例，不当作有人工标签的分割准确率。清晰图本次Otsu=128，恰与固定128相同；新实拍图2026年10月20日简单验证Otsu=66，12项正式检查通过。此前模拟图的110属于旧运行，不沿用到实拍图。简单验证记录见evidence/lab4_latest/real_input_verification.json。

替换个人图片：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/run_lab4.py --texture "data/input/新纹理图.jpg"
.\.venv\Scripts\python.exe -X utf8 src/run_lab4.py --texture "data/input/纹理图.jpg" --uneven "data/input/实拍光照不均.jpg"
```

若希望固定使用自己的光照不均图片，修改lab4_images.json的uneven字段；两个图分别分析，无双图运算，不要求同尺寸。不提供该字段时沿用已说明的受控派生。

主要对比图为l4_sobel_compare.png、l4_canny_compare.png、l4_threshold_compare.png、l4_adaptive_compare.png、l4_manual_compare.png。统计在evidence/lab4_latest/metrics.csv，参数/来源/哈希在results.json。raw_gradients.npz保存原始Gx/Gy/幅值/弧度、NMS及派生时的增益；读取时使用np.load(...,allow_pickle=False)。

detailed_design.md覆盖L3/L4函数设计，coding_standards.md为技术编码规范，design_walkthrough.md有已验证的技术意见及真实两两走查空位。按user_tasks.md亲自完成课堂交换走查、组内规范确认；若要求实拍或截图再补对应材料。完成真实记录后重新package_lab4.py，避免ZIP中还是旧文档。

## 实验五复现

本次已授权的棋盘为data/input/chess.png，8×8格、每格40像素、320×320、灰度uint8，49个内部交点；不是实拍照片。texture沿用你的photo.jpg做补充检测器对照。源码ZIP不带输入；在新机器上可重新生成已授权棋盘，再放入自己的纹理图片，或将配置texture设为null：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/prepare_chess.py
.\.venv\Scripts\python.exe -X utf8 -m pytest -v src/test_feature.py src/test_lab5_scale.py
.\.venv\Scripts\python.exe -X utf8 src/run_lab5.py
$LASTEXITCODE
.\.venv\Scripts\python.exe -X utf8 src/package_lab5.py
```

prepare_chess.py只新建棋盘；已有不同内容会拒绝覆盖，防止改掉你的替换素材。默认棋盘相同则复用，来源写入evidence/chess_source.json。已经有自己的棋盘时跳过该准备命令。

实验五独立35项pytest用例应通过。主入口自动执行全项目pytest：实验五原完成时107项主用例及15项子用例通过（JUnit tests=122含子用例）；新增实验六后全项目变为147项主用例及15项子用例，其中二至四72、五35、六40。应以各次日志为准，不能将JUnit含子用例总数当成主用例数。正式运行14项检查，默认27张PNG；texture=null时省略纹理对照，26张。日志和JUnit保存在evidence/lab5_latest，程序生成的图片/文本不冒充真实终端截图。

Harris的k固定对比0.04/0.06/0.1，block_size=2、sobel_ksize=3；quality_level=0.01是相对各自最大正R的阈值，min_distance=10为当前图像像素，max_harris_corners=500。Shi-Tomasi最多100个，FAST阈值20并启用非极大值抑制。可改质量阈值、间距、上限和核等字段；正式配置保留指导书三组k与四层金字塔。不接受未知键。

当前三组Harris和Shi-Tomasi各49点；FAST在理想二值棋盘为0，在个人插画为1635点，属于检测条件差异。本例三组相对阈值下角点数相同，应保留真实结果。响应R、λ1/λ2及手写/API差异见报告；坐标为(x,y)整数、数组访问[y,x]。手写/API相关系数本次1.0；恒定图用null表示相关系数无定义。

四层尺寸320×320、160×160、80×80、40×40，奇数尺寸使用ceil(n/2)。相邻层先把粗层float32放大到细层，再计算coarse_up−fine：保留负值，不使用uint8饱和减法。候选是|DoG|空间局部峰，质量0.1、间距6、最多max_dog_candidates=150；达到上限时不是实际极值总数。raw_arrays.npz保存带符号值，PNG只是显示。

另有同尺寸Gaussian DoG补充：初始sigma=1.6、scale_ratio=2^(1/3)，6个sigma形成5层差分；中间3层与26邻点严格比较，contrast_threshold=2，排除边界和等值平台。未实现完整SIFT，不据此证明尺度不变性。详细数学、接口和测试见lab5_design.md。

更换棋盘或补充纹理图，无需改源码：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/run_lab5.py --chess "data/input/我的棋盘.png"
.\.venv\Scripts\python.exe -X utf8 src/run_lab5.py --chess "data/input/我的棋盘.jpg" --texture "data/input/新纹理图.jpg"
```

或修改config/lab5_images.json的chess/texture；设置texture=null可单独做棋盘必做项。每次按新文件哈希确认来源，不会把换后的图仍写为生成的8×8棋盘。原始输入保持不变；全套校验后才替换lab5_latest，失败保留前次完整结果。重复运行也会替换该证据目录中的手工截图，应在最后一次运行后补截图并备份提交材料。

主要图：l5_harris_compare.png、l5_detector_compare.png、l5_lambda_plane.png、l5_manual_compare.png、l5_pyramid_compare.png、l5_dog_compare.png及l5_gaussian_dog_compare.png。检测坐标/尺度候选在coordinates.json，统计metrics.csv，原始数组raw_arrays.npz（np.load(...,allow_pickle=False)），输入与参数results.json，图像哈希manifest.json。

Git流程、目标远程及真实提交/推送记录见lab5_git_workflow.md与evidence/lab5_git.log；本机使用已补齐HTTPS助手的便携MinGit，命令见Git文档，其他机器可安装完整Git for Windows。按user_tasks.md亲自复现、截取pytest成功画面、核对远程提交/个人推送证据并最终提交。修改课堂记录后重新package_lab5.py，ZIP包含pytest.ini、源码/配置/全部Markdown，图片和证据另交。

本次代理已实际推送main及feature/l5-corner并核验远程SHA；9项集成检查验证换图、中文/空格路径、奇数尺寸、texture=null清除旧输出、失败保留、原图/其他实验不变，记录为evidence/lab5_latest/replacement_verification.json。个人复现/截图/提交状态仍须你明确告知后更新。

## 实验六复现

默认输入为你已提供的建筑夜景实拍data/input/uneven_real.jpg。配置config/lab6_images.json的max_input_side=1600将4096×3072等比缩为1600×1200，仅在分析时生成工作图，不修改原照片。设0可保持原尺寸；换图后记录实际尺寸和哈希，不强制拉伸。缩小后最短边不足16会报错，应提高上限或设0。

```powershell
Set-Location D:\IntegratedDesign\project_i
.\.venv\Scripts\python.exe -X utf8 -m pytest -v src/test_lab6.py --basetemp=.tmp/pytest_lab6_manual
.\.venv\Scripts\python.exe -X utf8 src/run_lab6.py
$LASTEXITCODE
.\.venv\Scripts\python.exe -X utf8 src/package_lab6.py
```

实验六40项独立用例通过。实验六完成时全项目147项主用例与15项子用例，新增七后重跑全套会变为187项主用例与15项子用例；各实验独立数量不变。六正式12项检查、默认18张PNG，工作图2455个关键点、描述子shape=(2455,128)、float32。无特征图可安全运行，但没有有效纹理观察结果，会省略描述子示例图；不要把此情况当作完成有效不变性验证。

本次手动命令的pytest临时目录为项目.tmp/pytest_lab6_manual；run_lab6.py自动测试显式使用.tmp/pytest_lab6。因此本实验这些入口无需写入C盘pytest-of-jiuge。原pytest.ini未改，其他直接pytest命令若不加--basetemp仍使用系统默认。pytest会在会话开始时清空指定basetemp，只使用专用临时目录，不放原图、报告或截图，也不要并发使用同一basetemp。

默认SIFT参数为nfeatures=0、nOctaveLayers=3、contrastThreshold=0.04、edgeThreshold=10、sigma=1.6、enable_precise_upscale=False。参数实验独立改变nfeatures 0/300/800、contrastThreshold 0.04/0.01/0.08、edgeThreshold 5/10/20。相同配置复用提取，九条对照记录对应七次唯一配置。nfeatures=300本次实际返回301，是临界同响应点一并保留，不强行改成300；数量以parameters.csv为准。edgeThreshold越大过滤的边缘状点越少，不能照指导书排错段将其理解为“调大可排掉更多边缘点”。

生成30°旋转、0.6倍缩放及两者组合，使用足够大的完整画布，目标尺寸分别1986×1840、960×720、1192×1104。SIFT重新提取后对全部描述子做BF L2 KNN(k=2)，d1<0.75*d2。匹配比例分母为原图2455个关键点实例，不用截断描述子数。前50条只用于绘图。

本次旋转/缩放/组合ratio通过数1636/843/884，比例66.64%/34.34%/36.01%；已知变换下≤3工作像素的几何一致数1602/771/827。ratio通过可能包括重复窗格误配，不能直接当全部正确。本次只验证已知受控变换，不做实验七完整匹配或实验八RANSAC/拼接。

换图无需改源码：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/run_lab6.py --input "data/input/我的纹理照片.jpg"
.\.venv\Scripts\python.exe -X utf8 src/run_lab6.py --input "data/input/photo.jpg"
```

也可改lab6_images.json的input，或复制该配置修改max_input_side和其他参数后以--config指定。JSON相对路径以project_i为根，支持中文/空格路径；图像需uint8，灰度/BGR/BGRA明确转换。配置拒绝未知字段。extract_sift(img,cfg=None)在src/features.py，N个KeyPoint与float32 N×128描述子逐行对齐，无特征为(0,128)。与实验五src/feature.py不是同一文件。

主要图为l6_keypoints.png、l6_distributions.png、l6_parameter_counts.png、l6_contrast_keypoints.png、l6_transform_compare.png、l6_matches_combined.png及l6_descriptor_1/2.png。圆圈表示尺度范围（size是直径），短线表示主方向；两幅4×4网格、每格8方向的玫瑰图共用半径尺度，角度在主方向对齐坐标中，不把存储值当原始梯度计数或单位向量。

证据位置evidence/lab6_latest：results.json记录输入/工作尺寸、实际参数和矩阵；parameters.csv及invariance.csv保存数量/比例；keypoints.json、matches.json保存全部点及匹配误差；features.npz保存全部float32描述子和float64矩阵（np.load(...,allow_pickle=False)）。pytest.log、pytest.xml为实际测试证据，不能冒充终端截图。换图/空图/失败保留等九项集成检查在integration_verification.json。

Git功能分支和真实PR链接/状态见lab6_git_workflow.md及evidence/lab6_git.log。原始个人图片不推送Git。按user_tasks.md亲自复现、补Git提交历史截图/个人信息、核对PR并提交；修改文档后再次package_lab6.py，源码ZIP不含输入、结果、截图或.git历史。

## 实验七复现

读取你提供的data/input/seven-1.jpg和seven-2.jpg，两张4096×3072、BGR uint8的图书馆实拍，场景有大面积重叠，含视角/反射/行人变化。无需派生或下载照片；不要求同尺寸，不做像素相减或强行拉伸。

```powershell
Set-Location D:\IntegratedDesign\project_i
.\.venv\Scripts\python.exe -X utf8 -m pytest -v src/test_lab7.py --basetemp=.tmp/pytest_lab7_manual
.\.venv\Scripts\python.exe -X utf8 src/run_lab7.py
$LASTEXITCODE
.\.venv\Scripts\python.exe -X utf8 src/package_lab7.py
```

实验七40项独立用例、全项目187项主用例及15项子用例、14项正式检查通过。默认24张PNG（包含15张人工样本页），加annotate.html和labels_template.csv。无特征/少匹配时输出数量会减少；导入明确标签后可增加最多3张绿/红人工标签连线图。pytest临时目录自动为D盘项目.tmp/pytest_lab7，手动命令也显式给出专用目录；pytest会清空该目录，勿放原图/标注/截图，不并发使用相同basetemp。

正式max_input_side=0保持原始分辨率，SIFT实例33057/29086、float32 N×128。试运行发现长边1600时严格0.6档最终仅24对，2400时43对，故正式保留原图细节，三档最终58/175/1148，均可抽50。改成缩图可以减小运行和输出开销，但对应数量/样本总体会改变，旧标签不可沿用，不应把缩图不足50时伪装成已抽50。

BF用NORM_L2、crossCheck=False，双向KNN(k=2)覆盖全部描述子；单向ratio数量83/344/4102，前向ratio+互为最近邻81/284/2281，双向ratio58/175/1148。双向ratio是指导书示例实际实现的更严格集合，不与“仅互为最近邻”混名。严格d1<threshold*d2，d2=0拒绝；无第二邻点不做ratio。max_distance=null默认不加绝对阈值；distance_thresholds为补充L2对照，不把L2数值当ratio。

FLANN加分对比为KD-tree algorithm=1、trees=5、checks=50，先预热再计三次双向构建+KNN中位耗时；当前原尺寸实测FLANN比BF快，但首邻结果和最终配对有差异，具体时延/一致率以本次results.json为准，不保证其他机器或参数仍然更快。

### 人工误匹配率 必须由真实标注补齐

正式三档均随机无放回抽50对，seed=7；跨组共137个唯一配对，同一对只标一次，样本固定在annotation_manifest.json。当前未标注，误率为null，表格显示“待人工标注”，不是0%或正确率100%。

1. 用浏览器打开data/output/lab7_latest/annotate.html，填写真实标注者，切换0.6/0.75/0.9三组。
2. 核对左右紫色十字是否同一实际物理点；可调局部半径、全图定位并打开原工作图，Y/N/U分别记正确/错误/不确定。重复窗格、反射、移动人物要结合上下文，不能根据ratio自动判定。
3. 导出CSV，保存到data/annotations/。导出文件名为lab7_labels_数据ID前16位.csv，按实际文件名使用下列命令；若愿意统一命名为lab7_labels.csv也可以。页面本地缓存不是文件备份，重跑前先导出；也支持导入既有CSV继续标注。
4. 用实际CSV重新运行。程序只读取标签，复制使用副本到证据，不改原CSV；全组明确判断后计算误率与Wilson区间。uncertain不会被计为错误/正确，未完成的组仍为空；不足50会标记课程50对条件未完成。

```powershell
.\.venv\Scripts\python.exe -X utf8 src/run_lab7.py --labels "data/annotations/lab7_labels.csv"
.\.venv\Scripts\python.exe -X utf8 src/package_lab7.py
```

CSV表头固定dataset_id,pair_id,query_index,train_index,label,reviewer,note。label为correct/incorrect/uncertain或空；非空标签需填真实reviewer。数据ID绑定照片/尺寸/提取配置/关键点/描述子，旧来源、索引错位和重复行均报错并保留前次完整结果。标注文件不要留在data/output或evidence目录作为持久源，那里重跑会替换。

每组误配率=incorrect/(correct+incorrect)，总体是该组“双向ratio最终匹配集合”。用真实样本估计数量与正确性权衡后再下最终阈值结论；默认0.75不是人工验证最优阈值。程序不使用RANSAC/单应性/互查来伪造人工真值，实验八未执行。

### 换图、输出与评审

```powershell
.\.venv\Scripts\python.exe -X utf8 src/run_lab7.py --image1 "data/input/新场景1.jpg" --image2 "data/input/新场景2.jpg"
```

也可修改config/lab7_images.json。labels默认null，换图时先不带旧--labels并使用新模板。两张可不同尺寸，uint8灰度/BGR/BGRA明确转灰度，原始输入禁止覆盖。保留max_input_side=0可完整分析，设上限时等比缩小并记录坐标映射。更改提取和工作尺寸后重新抽样，不能复用旧索引标签。

主要图：l7_before_after.png、l7_matches_raw/ratio/symmetric.png、l7_threshold_counts.png、l7_ratio_distribution.png及sample_阈值_页号.png。灰/蓝连线仅区分处理阶段，紫色十字仅定位；绿/红只在导入人类标签后表示正确/错误。原始完整匹配和距离在matches.json，关键点keypoints.json，描述子descriptors.npz（allow_pickle=False），统计metrics.csv/results.json。browser_qa.json记录实际离线页面检查，integration_verification.json记录11项换图/空图/CSV/失败保留及原数据保护检查。

指导书要求真实同学结对交换L5–L7代码，至少5条意见。lab7_code_review.md已提供清单、8条明确标为技术自走查的意见和真实结对空位；docs/defects.md区分设计防护、实际观察、已处理和人工待办，需真实参与者继续填写，不把代理自评当同学活动。按user_tasks.md完成实际标注/评审/修复记录和提交。Git分支/PR实际状态见lab7_git_workflow.md。个人文件变更后重新package_lab7.py，源码ZIP不带原图、输出、标签、证据和.git。

## 同一新图片用于各实验

七个配置独立。prepare_inputs.py **只更新images.json，不自动替换其他实验**。使用同一新源图时，准备实验一角色，再分别用二--normal、三--input、四--texture、五--texture、六--input或同步改JSON；七需要两个有重叠场景的图片，用--image1/--image2。四的真实光照不均图用--uneven，五的棋盘用--chess。单张纹理图不能自动代替棋盘或真实双视角对。无需改源码。

JSON绝对路径推荐 D:/MyImages/photo.jpg；反斜杠要转义。命令含空格、中文路径用双引号。保持对应角色的格式、通道和尺寸要求即可重复替换。

## 输出保留、排错与提交

各实验只留lab1_latest至lab7_latest的最新完整个人结果和证据。新运行在临时目录完成校验后替换旧结果，失败保留此前完整结果；原图、派生输入及data/annotations中的人工CSV保留，其他实验最新结果不受影响。自动数组自检独立记录。

| 现象 | 处理 |
| --- | --- |
| cv2/skimage 导入失败 | 在 .venv 安装 requirements.txt，检查解释器 |
| 图片不存在或损坏 | 按错误路径检查文件与真实编码 |
| 二的尺寸不同 | 显式对齐或用同图派生，不隐式 resize |
| 三的 SSIM 输入过小 | 宽高至少 7，避免临时放大伪造有效评分 |
| 16位在二至四报错 | 提供uint8，一的支持不代表后续API均支持 |
| 四的全局阈值与Otsu图相同 | 检查返回阈值，本次确实同为128，不是程序异常 |
| 四的自适应图纹理较多/大面积白色 | 调整blockSize/C，结合局部细节观察；没有真值标签不报告准确率 |
| 五的FAST在理想棋盘为0 | 属于圆周比较的条件差异，查看个人纹理对照，不强造角点 |
| pytest导入失败或找不到feature | 安装requirements.txt；从project_i根目录用python -m pytest，保留pytest.ini |
| 生成棋盘提示文件已存在且不同 | 不覆盖你的素材；跳过prepare_chess.py，直接指定你的棋盘运行 |
| 六的SIFT没有关键点 | 检查纹理/清晰度与参数；空描述子为(0,128)，不伪造匹配 |
| 六的nfeatures=300得到301 | 本机临界同响应点可能并保留，以实际数量为准 |
| 六的缩放后最短边不足16 | 提高max_input_side或设0，保持比例，不强拉伸 |
| 七的误匹配率显示待人工标注 | 按标注页实际判断、导出到持久目录后--labels导入，未填/不确定不当真值 |
| 七的CSV提示来源不匹配 | 图/工作尺寸/提取已变化，保留旧CSV并使用当前新模板，不改ID硬套 |
| 七的严格档不足50对 | 按实际数量报告；当前原尺寸58对可抽50，缩图可能减少可匹配细节 |
| 核/sigma 不合法 | 核≥3奇整数，sigma 有限正数 |
| 锐化过冲/黑边 | 降低系数，结合局部图观察 |
| 运行锁存在 | 确认无同实验进程；中断残留时才移除对应 .labN_running.lock |

源码ZIP排除环境、个人图片和输出；另提交输入、最新图像与证据。源码/文档更新后重新执行对应 package_labN.py。截图应真实截取命令、状态和结果，不将程序绘图冒充系统截图。Linux/macOS解释器路径为 .venv/bin/python，本次只实测Windows。

后续实验结束时更新本文件入口表、环境变化、命令、配置、验证、换图及结果路径，并同步在 image_requirements.md 增加该实验素材条件，检查旧实验指导仍能使用。
