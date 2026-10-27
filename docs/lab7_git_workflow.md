# 实验七 Git与PR记录

沿用实验六起的feature分支、Conventional Commits和PR流程。仓库为[jiuge712/IntegratedDesign](https://github.com/jiuge712/IntegratedDesign)，从本地及远程main（实验六合并bc1eabf）创建feature/l7-matching。功能提交00dda1f已推送，真实PR为[PR #2 实验七匹配与人工标注工作流](https://github.com/jiuge712/IntegratedDesign/pull/2)。最终合并事件可在PR页核对，发布核验状态与完整SHA记录于evidence/lab7_pr.json、lab7_git.log和lab7_git_status.json。

代码评审的技术自走查见lab7_code_review.md，真实结对≥5条仍需本人/同学完成；GitHub PR合并不能冒充同学交换代码或签字。

本次只提交实验七源码、配置、统一文档与缺陷/评审材料，保留工作区原有docs/lab5_report.md修改，不混入本次提交。照片、输出、人工CSV、证据、.venv和源码ZIP由.gitignore排除，个人照片及标注不上传Git。

本机便携Git与HTTPS助手沿用已有安装：

```powershell
Set-Location D:\IntegratedDesign\project_i
git log --oneline --graph --all -10
git status --short
& 'D:\IntegratedDesign\.tools\mingit\cmd\git.exe' --exec-path='D:/IntegratedDesign/.tools/mingit/ucrt64/bin' push -u origin feature/l7-matching
```

若已连接GitHub集成的PR接口仍无权限，使用本机Git现有登录调用同一仓库REST接口；认证只在进程内，不把凭据写入源码/日志。PR合并须核对head SHA，再拉取main快进本地并验证原有用户报告未变。实际成功/失败以证据与PR页面为准，不把本文示例当执行记录。
