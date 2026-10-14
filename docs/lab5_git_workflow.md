# 实验五 Git 工作流

本项目此前未初始化Git。本次在project_i创建main，以实验一至四源码和文档为基线提交，再从main切换到feature/l5-corner开发实验五。完成测试和文档后提交该分支，以--no-ff合并回main，保留分支工作流。真实提交图/状态保存在evidence/lab5_git.log，不把命令示例当作执行证据。

## 本地完成范围

基线提交说明为`chore: record experiments 1-4 baseline`；功能提交说明为`feat: complete lab5 corners and scale space`；合并提交说明为`merge: integrate lab5 corner experiment`。使用机器已有Git作者配置，不代填虚构成员。feature/l5-corner分支保留供检查，最终工作分支为main。

.gitignore排除.venv、缓存、个人输入、图像输出、证据和deliverables，避免把大图/环境混入源码历史。源码和实验报告受版本管理。数据应单独备份/提交，源代码ZIP不含.git历史。

查看本地记录：

```powershell
Set-Location D:\IntegratedDesign\project_i
git branch --show-current
git log --oneline --graph --all -8
git status --short
git remote -v
```

## 远程仓库与推送核验

用户已指定[jiuge712/IntegratedDesign](https://github.com/jiuge712/IntegratedDesign)。首次检查确认空仓库、当前账号有push权限；origin使用该地址。具体推送结果以evidence/lab5_git.log与远程分支实际SHA为准。更换仓库时先确认地址和既有历史，不用force覆盖。

```powershell
git remote add origin "https://github.com/jiuge712/IntegratedDesign.git"
git push -u origin main
git push -u origin feature/l5-corner
git ls-remote --heads origin
```

本机origin已配置时不要重复remote add，直接检查和push；其他机器未配置才执行add。若origin已经存在，先git remote -v检查实际地址；只在你确认需要修改时使用git remote set-url origin。按课程要求保存真实push成功画面/远程提交链接；认证使用Git自身配置，不在报告或命令截图泄露密码/令牌。

本机Codex内置Git缺少HTTPS传输组件，已下载官方便携MinGit 2.56.0.windows.2到D:/IntegratedDesign/.tools/mingit；官方来源/下载哈希在同级mingit_source.json。工具不放入源码ZIP，其他机器可安装完整Git for Windows。本机推送时指定实际HTTPS助手目录：

```powershell
& 'D:\IntegratedDesign\.tools\mingit\cmd\git.exe' --exec-path='D:/IntegratedDesign/.tools/mingit/ucrt64/bin' push -u origin main
& 'D:\IntegratedDesign\.tools\mingit\cmd\git.exe' --exec-path='D:/IntegratedDesign/.tools/mingit/ucrt64/bin' push -u origin feature/l5-corner
& 'D:\IntegratedDesign\.tools\mingit\cmd\git.exe' --exec-path='D:/IntegratedDesign/.tools/mingit/ucrt64/bin' ls-remote --heads origin
```

官方工具来源：[Git for Windows发布页](https://github.com/git-for-windows/git/releases/latest)。机器使用的包版本以mingit_source.json为准，未来版本的助手目录可能不同，应查看实际安装目录。

未来在其他机器从源码ZIP解压后不包含这次.git历史，若需要保留分支/提交，请从真实仓库clone或另备份本地仓库。user_tasks.md中的个人核对、截图和课程提交仍保持未完成；代理执行Git操作不自动代表用户完成这些个人任务。
