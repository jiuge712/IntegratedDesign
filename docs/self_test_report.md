# 实验一程序自检报告

输入为程序生成的临时测试数组，用于验证代码；这些数据没有放入 data/input，也不代表用户个人图片实验结果。个人图片正式实验仍待提供素材后运行。

运行时间：2026-10-13T20:02:28+08:00。

执行 21 个测试，通过 21 个，失败 0 个。
原始输入 SHA-256 校验：全部保持不变。

| 用例 | 输入条件 | 预期状态 | 实际状态 | 退出码 | 结论 | 处理耗时 ms |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | 彩色 PNG | SUCCESS | SUCCESS | 0 | PASS | 7.772 |
| T02 | 彩色 JPEG | SUCCESS | SUCCESS | 0 | PASS | 7.998 |
| T03 | 不存在路径 | ERROR | ERROR | 1 | PASS | — |
| T04 | 单通道灰度 PNG | SUCCESS | SUCCESS | 0 | PASS | 6.713 |
| T05 | 四通道 RGBA PNG，舍弃 Alpha | SUCCESS | SUCCESS | 0 | PASS | 7.2 |
| T06 | 中文输入和输出路径 | SUCCESS | SUCCESS | 0 | PASS | 15.492 |
| T07 | 损坏图片 | ERROR | ERROR | 1 | PASS | — |
| T08 | 输出目录不存在 | SUCCESS | SUCCESS | 0 | PASS | 9.065 |
| T09a | 全黑图 | SUCCESS | SUCCESS | 0 | PASS | 6.25 |
| T09b | 全白图 | SUCCESS | SUCCESS | 0 | PASS | 6.144 |
| T10 | 较大图像及耗时 | SUCCESS | SUCCESS | 0 | PASS | 40.068 |
| T11 | 不同尺寸图像 | SUCCESS | SUCCESS | 0 | PASS | 7.029 |
| T12 | 输出路径为目录 | ERROR | ERROR | 1 | PASS | — |
| T13 | 输出与输入相同 | ERROR | ERROR | 1 | PASS | — |
| T14 | 不支持的输出扩展名 | ERROR | ERROR | 1 | PASS | — |
| T15 | 写入原始输入目录 | ERROR | ERROR | 1 | PASS | — |
| T17 | 日志与图片路径冲突 | ERROR | ERROR | 1 | PASS | — |
| T16 | 16 位彩色 PNG 保留位深 | SUCCESS | SUCCESS | 0 | PASS | 6.99 |
| T20 | 已知蓝绿红白黑像素的灰度权重 | SUCCESS | SUCCESS | 0 | PASS | 6.463 |
| T18 | 拒绝 float32 数组 | ERROR | ERROR | 函数检查 | PASS | — |
| T19 | 拒绝两通道数组 | ERROR | ERROR | 函数检查 | PASS | — |

## 运行证据

日志与结构化数据：`evidence/self_test_2026-10-13T20-02-24+08-00_496cb4`。
灰度结果：`data/output/self_test_2026-10-13T20-02-24+08-00_496cb4`。

命令行用例的 .log 包含实际命令、退出码、标准输出和错误输出；数组校验用例记录函数、输入属性和异常。results.json 保存全部输出属性、版本、输入输出哈希和耗时。
异常用例预期 ERROR；明确报错且退出码为非零时，测试结论为 PASS。

## 性能记录

T10 输入 [1080, 1920, 3]，处理耗时 40.068 ms。
≤ 2 s 的性能参考：满足。该项为平台相关参考指标，不改变功能测试结论。
计时覆盖读取、检查、转换、编码和保存，不包含 Python 启动、保存后回读或哈希计算。

## 结果分析与限制

通过项说明正常输入、灰度分支、透明通道策略、中文路径、异常反馈及输入保护满足接口约定。
预期异常来自不存在路径、损坏文件或无效输出条件；它们不是已通过测试中的程序缺陷。
范围为单张静态图像的基线处理；不执行实验二至五的算法。下一实验可继承命令行路径、BGR/BGRA/GRAY、uint8/uint16、PNG输出及状态证据约定。

如需截图，请真实截取运行终端与输出文件属性；截图方法见 reproduction.md。

## 失败详情

本次没有非预期失败。
