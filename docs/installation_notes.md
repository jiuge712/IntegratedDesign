# 实验一安装与故障记录

安装日期：2026 年 10 月 13 日，北京时间。独立环境路径：`D:\IntegratedDesign\project_i\.venv`。所有依赖只安装到这个环境，没有向系统 Python 安装包。

## 实际安装过程

1. 检查发现 `python` 指向 WindowsApps 占位程序，不能启动。`py -0p` 找到 `D:\Python\python.exe`，版本为 3.14.7，改用 `py -3.14` 创建环境。
2. 沙箱内初次创建环境的 ensurepip 在临时目录写入时发生 PermissionError。获得环境创建授权后，在项目目录成功建立虚拟环境。
3. 沙箱内初次 pip 下载被网络连接权限限制，出现 WinError 10013。获得依赖安装授权后，在同一个项目虚拟环境成功安装 `opencv-python numpy matplotlib`。
4. 用 `src/version_check.py --freeze requirements.txt` 记录真实版本及传递依赖；用 `pip check` 确认依赖没有冲突。
5. 首次实际运行 `src/run_tests.py --self-test`，21 项代码验证通过。当时尚缺个人图片，默认正式测试能明确报告缺少的文件并返回 1。
6. 用户提供源图及黑白图后，使用新增的素材准备脚本导出实验版本并更新配置，正式执行 17 项个人图片测试，全部通过。原图、已有黑白图及测试输入哈希均保持不变。
7. 实验三新增 scikit-image 用于 SSIM。沙箱内首次安装受访问限制，授权后在同一虚拟环境安装 scikit-image 0.26.0 及其传递依赖；更新 requirements.txt 并通过 pip check。实验三22项自检、9项个人运行检查通过。
8. 实验五新增pytest 9.1.1及colorama/iniconfig/pluggy/pygments；沙箱内首次下载失败，获得安装授权后在同一.venv安装。requirements.txt及environment.md已更新。全项目107项pytest用例及15项unittest子用例通过，实验五14项正式检查通过。

## 本机提示

实验一早期解释器曾在stderr打印`Failed to find real location of D:\Python\python.exe`；当时版本检查、依赖导入和处理仍成功，提示保留在原日志中。实验五当前实测命令没有再出现该提示。跨机器根据实际环境处理，不隐藏或伪造运行结果。

其他机器复现时应按 reproduction.md 重新创建环境，环境或网络异常按实际情况处理，不把本机沙箱现象当作所有 Windows 环境必然发生的问题。
