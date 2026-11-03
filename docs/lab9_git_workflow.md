# 实验九 Git工作流记录

沿用coding_standards.md自实验六起的feature分支、Conventional Commits及真实PR流程。仓库为[jiuge712/IntegratedDesign](https://github.com/jiuge712/IntegratedDesign)，从main的92af0f3创建feature/l9-camera-calibration。功能提交6fd4e86已推送，真实PR为[PR #4 实验九标定与集成测试](https://github.com/jiuge712/IntegratedDesign/pull/4)。最终合并事件可在PR页面核对，实际head、merge SHA和本地/远程状态以evidence/lab9_pr.json、lab9_git_status.json及lab9_latest内证据为准，不把命令示例冒充已执行的合并记录。

只提交源码、配置、文档与忽略规则，不提交生成图、真实原图、results导出、证据、ZIP或环境。用户原有docs/lab5_report.md修改保持原哈希且不纳入本次提交。Git技术流程不等于个人复现、截图或课堂提交已完成。

本次GitHub连接器实际返回403 Resource not accessible by integration，沿用已有本机Git登录调用同一仓库REST接口，认证只在进程内使用、不记录到源码/日志。合并前核对head SHA和base/head分支；拉取后核对main与远程一致，且用户原有报告未变。

```powershell
Set-Location D:\IntegratedDesign\project_i
git log --oneline --graph --all -10
git status --short
```

真实操作人需要的截图/本人提交继续见user_tasks.md，不能用Git操作自动勾选。
