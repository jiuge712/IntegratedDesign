# 图像处理实验项目

本项目已完成实验一至五的技术实现：读取与灰度、基本运算与均衡化、空间滤波与锐化、边缘检测与阈值分割，以及角点与尺度空间。图片由你提供，实验五标准棋盘经你授权由程序绘制；替换配置即可重跑。

固定入口为 [各实验统一复现指南](docs/reproduction.md) 和 [各实验个人图片要求](docs/image_requirements.md)，涵盖全部已完成实验。后续每个实验结束都更新这两个入口，规则已写入项目 AGENTS.md。

需要你亲自参与的任务见 [用户任务清单](docs/user_tasks.md)。实验四的 [报告](docs/lab4_report.md)、[详细设计](docs/detailed_design.md)、[编码规范](docs/coding_standards.md) 和 [走查记录](docs/design_walkthrough.md) 已提供技术材料，真实小组活动仍由参与者完成。

实验五入口为src/run_lab5.py；[实验五报告](docs/lab5_report.md)、[算法与API设计](docs/lab5_design.md)、[Git工作流](docs/lab5_git_workflow.md)已提供。Harris三组k、Shi-Tomasi、FAST、四层金字塔、浮点DoG及手写Harris均有结果。Git采用feature/l5-corner分支合并main，目标远程[IntegratedDesign](https://github.com/jiuge712/IntegratedDesign)，实际记录见Git文档及证据。用户未明确告知已完成的任务默认继续未完成。

代理已完成main及feature/l5-corner实际推送和远程SHA核对，图片/输出/证据保留在本地；9项换图与保留机制集成检查通过。源码包deliverables/lab5_source.zip可重新生成，个人截图和课堂提交仍见任务清单。

实验三执行 `src/run_lab3.py`，报告见 [实验三报告](docs/lab3_report.md)，架构和接口见 [SFM架构](docs/architecture.md)、[接口约定](docs/interface_agreement.md)。

实验二入口为 `src/run_lab2.py`，完整流程见 [实验二复现指南](docs/lab2_reproduction.md)，结果见 [实验二报告](docs/lab2_report.md)。需求评审见 [MVP范围](docs/mvp_review.md)，官方 API 调研见 [API说明](docs/api_notes.md)。

当前代码自检与图片实验分开记录。一正式17项，二自检22项/正式13项，三自检22项/正式9项，四自检28项/正式12项通过。五独立35项pytest用例、全项目107项用例及15项子用例/正式14项通过，默认27张图。输出与证据各实验只留最新一次，原图保留，同图派生和程序棋盘明确标注。

## 从哪里开始

1. 按 [图片要求](docs/image_requirements.md) 准备图片并修改对应实验的配置。
2. 按 [复现实验指南](docs/reproduction.md) 安装、单张运行、批量测试和查看结果。
3. 查看 [需求规格](docs/requirements.md)、[实验报告](docs/lab_report.md) 及实际测试报告。

## Windows 快速运行

在 PowerShell 中进入本目录。当前机器已建立 `.venv`；直接使用虚拟环境里的解释器，无需激活，也不受 PowerShell 脚本执行策略影响。

```powershell
Set-Location D:\IntegratedDesign\project_i
.\.venv\Scripts\python.exe -X utf8 src/version_check.py
$labImages = Get-Content config/images.json -Raw | ConvertFrom-Json
.\.venv\Scripts\python.exe -X utf8 src/baseline_pipeline.py --input $labImages.color --output data/output/lab1_latest/manual_color_gray.png --record evidence/lab1_latest/manual_run.jsonl
.\.venv\Scripts\python.exe -X utf8 src/run_tests.py
.\.venv\Scripts\python.exe -X utf8 src/run_lab2.py
.\.venv\Scripts\python.exe -X utf8 src/run_lab3.py
.\.venv\Scripts\python.exe -X utf8 src/run_lab4.py
.\.venv\Scripts\python.exe -X utf8 src/prepare_chess.py
.\.venv\Scripts\python.exe -X utf8 src/run_lab5.py
```

图片处理命令使用当前配置中的彩色图；本次八类素材已准备齐全。以后只需提供新的原图并执行下面命令，即可建立新素材批次、更新配置，再运行正式测试：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/prepare_inputs.py --source "data/input/新的原图.jpg"
.\.venv\Scripts\python.exe -X utf8 src/run_tests.py
```

素材准备脚本只向新建的派生目录创建文件，保留原图和已有黑白图；实验处理程序仍禁止向输入目录写入。尚无个人图片时可运行代码自检：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/run_tests.py --self-test
```

在其他机器上重新建立虚拟环境并安装 `requirements.txt`，完整命令见复现指南。不要复制 `.venv` 到另一台机器。

## 项目目录

```text
project_i/
  README.md
  requirements.txt              实际安装版本及传递依赖
  .gitignore
  config/images.json            可替换的图片路径
  src/common.py                 路径保护、哈希与原子写入
  src/version_check.py          环境记录和依赖导出
  src/baseline_pipeline.py      参数化最小处理链
  src/run_tests.py              实际命令行测试及报告生成
  src/prepare_inputs.py         按授权从个人源图导出新素材批次
  src/lab2_transform.py         线性与固定伽马
  src/lab2_arith.py             加减乘除与混合
  src/lab2_hist.py              直方图与手写均衡化
  src/run_lab2.py               实验二一键执行及报告
  src/test_lab2.py              数值与最新结果替换自检
  src/latest_runs.py            各实验最新结果管理
  src/lab3_filter.py            空间滤波、锐化与BGR接口
  src/lab3_metrics.py           手写PSNR与skimage SSIM
  src/run_lab3.py               实验三一键运行和报告
  src/test_lab3.py              噪声、数值、接口和保留自检
  src/package_lab3.py           实验三源码提交包
  src/lab4_edges.py             Sobel Canny及手写NMS/滞后连接
  src/lab4_segment.py           固定/Otsu/自适应阈值
  src/run_lab4.py               实验四一键运行及证据报告
  src/test_lab4.py              实验四数值和边界自检
  src/package_lab4.py           实验四源码提交包
  src/feature.py                Harris/Shi-Tomasi/FAST及手写Harris
  src/lab5_scale.py             四层金字塔/带符号DoG/尺度极值
  src/prepare_chess.py          按明确授权准备标准棋盘，拒绝覆盖异图
  src/run_lab5.py               实验五一键执行、pytest和报告
  src/test_feature.py           角点数学与类型/坐标pytest
  src/test_lab5_scale.py        DoG/边界/命令行/最新结果pytest
  src/package_lab5.py           实验五源码提交包
  config/lab5_images.json       棋盘及纹理路径/参数
  pytest.ini                    模块搜索与测试发现
  data/input/                   你提供的原始图片，程序不写入
  data/output/                  各实验最新图像与对比图
  docs/                         需求、环境、报告及两个操作指南
  evidence/                     命令、状态、属性、耗时和哈希
```

## 图像与接口约定

- 数组采用 `img[y, x]` 索引。`shape=(H,W)` 为灰度，`(H,W,3)` 为 BGR，`(H,W,4)` 为 BGRA；H 是行，W 是列。
- 连续场景采样形成像素网格，像素量化为数值；OpenCV 解码后返回 NumPy 数组。`dtype` 指像素分量类型，`ndim` 指数组维数。
- 实验一接受uint8/uint16；二至五使用uint8，灰度用于算法/分析，三的接口单独严格使用BGR。四原始梯度为float64，五原始响应/DoG为float32，保存显示图时才归一化。
- 实验一基线中灰度输入保持原像素，彩色使用COLOR_BGR2GRAY；Alpha舍弃，透明区域隐藏颜色参与灰度计算。二、三再按各自任务运算，三的BGR接口保留三通道输出。
- 输入建议单张静态PNG/JPEG，实验输出保存无损PNG；基线保持空间尺寸，素材准备单独导出尺寸版本，二/三的算法与评分见对应报告。
- 中文和带空格的路径受支持；命令中带空格的路径要加双引号。解码采用 `Path.read_bytes + cv2.imdecode`，编码采用 `cv2.imencode + 文件写入`。
- 主程序成功退出码为 0，打印 `SUCCESS`；可处理的输入、转换或保存错误退出码为 1，打印 `ERROR`；参数缺失由 argparse 返回 2。
- 输出目录自动创建。输出文件若已存在会被替换；原始输入路径和整个 `data/input` 目录受到写入保护，日志也不能写入这些位置。
- 完整结果固定为data/output/lab1_latest至lab5_latest，对应证据为evidence中同名目录。新结果校验后替换旧结果，失败保留前次完整结果。配置图片路径按项目根目录解释，单张基线路径按当前目录解释。
- Matplotlib 显示彩色图前使用 `cv2.cvtColor(img, cv2.COLOR_BGR2RGB)`；灰度使用 `cmap='gray'` 并按位深设置 `vmin/vmax`。

本实验的解码和通道顺序依据 [OpenCV 图像读写文档](https://docs.opencv.org/4.x/d4/da8/group__imgcodecs.html)，灰度转换依据 [OpenCV 颜色转换文档](https://docs.opencv.org/4.x/de/d25/imgproc_color_conversions.html)。
