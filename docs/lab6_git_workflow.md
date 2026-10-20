# 实验六 Git分支与PR流程

指导书要求从main创建feature/l6-sift，按Conventional Commits提交，通过PR/MR合并。目标仓库为[jiuge712/IntegratedDesign](https://github.com/jiuge712/IntegratedDesign)。开始时本地与远程main均为a1ab80e，已创建feature/l6-sift；程序、测试、文档先在该分支完成并验证，再创建PR。

实际PR链接、合并状态和最终SHA将在发布核验时记录；原始Git命令/远程核验见evidence/lab6_git.log及evidence/lab6_git_status.json。不能把本文命令示例或本地提交直接当作已完成PR合并的证据。

## 提交与范围

按功能、测试、文档职责使用feat:/test:/docs:/fix:前缀；本次功能与对应测试一并以feat提交，后续PR链接/核验文档用docs。保留feature分支，PR使用merge方式合并，留下可查看的合并记录，不直接以一次本地merge代替PR流程。

本次纳入实验六实现和统一文档、用户确认的实验四实拍配置及重跑报告。工作区原有docs/lab5_report.md是用户复现产生的修改，保持原样且不混入本次提交。原图、输出、证据、.venv与ZIP按.gitignore排除，不上传个人实拍照片。

查看历史和状态：

```powershell
Set-Location D:\IntegratedDesign\project_i
git log --oneline --graph --all -10
git branch -vv
git diff -- docs/lab5_report.md
```

用户原有实验五报告可能仍显示本地修改，这是保留用户工作，不等于实验六有未提交代码。

## 本机网络工具

本机使用之前已授权安装的便携Git D:/IntegratedDesign/.tools/mingit/cmd/git.exe。HTTPS助手位于ucrt64/bin，推送/拉取时显式指定；其他机器使用完整Git即可。示例：

```powershell
& 'D:\IntegratedDesign\.tools\mingit\cmd\git.exe' --exec-path='D:/IntegratedDesign/.tools/mingit/ucrt64/bin' push -u origin feature/l6-sift
& 'D:\IntegratedDesign\.tools\mingit\cmd\git.exe' --exec-path='D:/IntegratedDesign/.tools/mingit/ucrt64/bin' fetch origin main
git switch main
git merge --ff-only origin/main
```

PR创建/合并采用已连接GitHub工具，校验待合并head SHA，避免合并期间分支变动；实际动作和结果记录到证据，不冒充真实同学的代码批准。个人Git历史截图、PR核对与课程提交仍由用户完成，见user_tasks.md；代理执行这些Git动作不会自动勾选用户任务。
