# 实验八 Git工作流记录

沿用coding_standards.md从实验六开始的feature分支、Conventional Commits和实际PR合并流程。目标仓库为[jiuge712/IntegratedDesign](https://github.com/jiuge712/IntegratedDesign)。从main的0915410创建feature/l8-ransac-stitch，功能提交5983428已推送；真实PR为[PR #3 实验八RANSAC拼接与M1演示](https://github.com/jiuge712/IntegratedDesign/pull/3)。最终合并事件可在PR页面核对，实际head、merge SHA和本地/远程核验记录保存于evidence/lab8_pr.json、lab8_git_status.json及lab8_latest对应证据，不把本文示例命令当作已执行的合并证据。

只提交实验八源码、配置、更新文档与环境版本记录，保留用户原有docs/lab5_report.md修改。照片、输出、证据、人工CSV、ZIP、.tmp和环境不上传Git。真实M1评审和本人历史截图仍待本人，不以PR合并替代课堂活动。

本次GitHub连接器创建PR实际返回403 Resource not accessible by integration，沿用已有本机Git登录调用该仓库REST接口，认证只在进程内，不写入源码/日志。PR合并前校验head SHA与base/head分支，拉取后校验本地main与远程相同；用户原有报告须保持原哈希。

```powershell
Set-Location D:\IntegratedDesign\project_i
git log --oneline --graph --all -10
git status --short
```

代码技术测试/走查和真实M1分别记录，所有来源、角度、截图和个人提交待办继续见user_tasks.md。
