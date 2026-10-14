# 实验二图片要求与复现指南

本次使用你已提供的插画。你已确认以同一素材派生偏暗与低对比度版本；原图不修改。实验二只接受 uint8 图像，彩色会先转单通道灰度。其他位深明确报错，不自动缩放。

## 安装和运行

实验二核心复用OpenCV、NumPy、Matplotlib。项目如今还包含实验三的scikit-image依赖；新机器按统一 reproduction.md 创建环境并安装当前requirements.txt。该统一文档覆盖各个已完成实验。

```powershell
Set-Location D:\IntegratedDesign\project_i
.\.venv\Scripts\python.exe -X utf8 src/version_check.py
.\.venv\Scripts\python.exe -X utf8 src/test_lab2.py
.\.venv\Scripts\python.exe -X utf8 src/run_lab2.py
$LASTEXITCODE
.\.venv\Scripts\python.exe -X utf8 src/package_lab2.py
```

22 项数值及边界自检通过后，一键入口生成个人图片结果并执行 13 项输出与算法检查。主命令成功返回 0，失败返回 1，缺失参数由 argparse 处理。实验一仍使用 `src/run_tests.py`。

## 图片配置与替换

`config/lab2_images.json` 的 normal 为正常亮度图路径；dark 和 low_contrast 可填写其他个人图片路径。值为 null 时由 normal 派生：偏暗为 `0.45*gray`，低对比度为 `0.3*gray+80`。派生文件属于本次输出，在 `data/output/lab2_latest/inputs`，不会写入 data/input。报告记录来源和参数。

若提供两张独立图片，建议内容相近、均为静态 PNG/JPEG、8 位每通道；暗图应有可辨识的暗部细节，正常图避免大面积纯黑/纯白。代数运算要求 dark 与 normal 的像素尺寸相同，程序不会偷偷拉伸第二张图片。低对比度图用于直方图形态对比，可以单独指定或按已约定的公式派生。

把新原图放入 data/input，修改 normal 路径即可再运行，或使用命令行覆盖：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/run_lab2.py --normal "data/input/新插画.jpg"
.\.venv\Scripts\python.exe -X utf8 src/run_lab2.py --normal "data/input/正常图.jpg" --dark "data/input/暗图.jpg"
```

JSON 相对路径按 project_i 根目录解释，绝对路径建议使用正斜杠。含空格的命令路径要加引号。config 中 alpha/beta 控制线性变换，gamma_bright/gamma_dark 作为 1/gamma 的分母，blend_weight 为 A 的混合权重，B 权重为 1-weight。

## 查看输出

- `data/output/lab2_latest/`：本次实际图像及并排图。
- `docs/lab2_report.md`：带对比图、属性表和差值统计的正式报告。
- `evidence/lab2_latest/results.json`：输入哈希、环境、参数、每张输出属性和 13 项检查结论。
- `evidence/lab2_latest/histograms.json`：完整直方图、概率、CDF 及手写 LUT。
- `evidence/lab2_latest/run.log`：实际命令和检查状态。
- `docs/api_notes.md`、`docs/mvp_review.md`：官方 API 调研及需求技术自评。
- `deliverables/lab2_source.zip`：本次源码与配套配置、依赖及说明的提交包。

源码 ZIP 不包含个人图片、实验输出或虚拟环境。提交结果时一并提交 lab2_latest 图像和证据；新机器复现时放入自己的图片并修改配置即可。修改源码或文档后再次执行 package_lab2.py，用相同文件名更新提交包。

对比图文件：l2_transform_compare.png、l2_gamma_compare.png、l2_arith_compare.png、l2_hist_compare.png、l2_eq_compare.png。灰度图使用统一 vmin=0/vmax=255，避免各子图自动归一化造成错误的亮度判断。

## 最新结果保留规则

实验一批量个人运行固定为 `data/output/lab1_latest` 和 `evidence/lab1_latest`；实验二固定为 lab2_latest。新结果在临时目录生成，通过检查后替换旧结果；随后移除旧目录。参数或输入错误不会删除上次完整结果。原图、准备好的输入素材与代码自检记录保留。实验一迁移时会移除旧 personal_ 批次目录。

单张处理工具按指定文件名替换对应结果；若要每个实验只有一套完整结果，使用上述批量主入口。专门模块可单独运行到指定目录以调试，指定目录不会触发主入口的批次管理：

```powershell
.\.venv\Scripts\python.exe -X utf8 src/lab2_transform.py --input data/input/gray.png --output-dir .tmp/lab2_debug_transform
.\.venv\Scripts\python.exe -X utf8 src/lab2_arith.py --a data/input/gray.png --b data/input/gray.png --output-dir .tmp/lab2_debug_arith
.\.venv\Scripts\python.exe -X utf8 src/lab2_hist.py --input data/input/gray.png --output-dir .tmp/lab2_debug_hist
```

## 错误排查与提交

出现不同尺寸提示时先在图片软件或素材准备阶段显式对齐；出现 dtype 提示时提供 8 位图。中文路径支持，损坏图明确报错。伽马必须为正的有限值；混合权重必须在 [0,1]。分母为零的除法输出 0；恒定图均衡化保持原值。

提交实验报告、最新图像与证据、源码 ZIP、API 调研及 MVP 评审文档。课堂互评必须由实际参与同学完成，本次文档仅记录技术自评。若课程要求截图，实际截取终端命令、SUCCESS/ERROR、输出文件与图像对照，不将程序绘图冒充系统截图。
