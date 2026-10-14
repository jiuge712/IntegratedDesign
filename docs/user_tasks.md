# 需要你完成的任务

更新日期：2026年10月14日。当前实验一至五的代码、技术运行、日志和技术文档已完成。以下只列需要你本人或真实同学参与的事情，不能用程序自检、技术自评代替课堂活动。

**状态规则：你未明确告知已完成的任务，一律默认未完成。** 本清单保留此前所有未勾选任务；图片存在、程序通过、ZIP生成、本地Git提交或日期变化都不代表你已完成个人任务。只有你明确确认对应事项后才更新为已完成；条件不适用也需你告知后记录，不自行勾选。

## 实验五的个人任务

- [ ] **亲自复现实验五并核对结果。** 按reproduction.md实验五章节执行pytest和run_lab5.py，查看Harris三组k、Shi-Tomasi/FAST、四层金字塔与DoG区域。当前棋盘Harris/ Shi各49点，FAST为0；插画FAST为1635。全套107项用例及15项子用例通过是代理执行的技术验证，不代表你本人已运行。用自己的观察补充参数/尺度分析。
- [ ] **截取真实pytest通过画面。** 指导书要求单元测试截图；从project_i根目录实际运行`.\.venv\Scripts\python.exe -X utf8 -m pytest -v src/test_feature.py src/test_lab5_scale.py`，截取命令、35项通过及退出情况，保存到evidence/lab5_latest。已有pytest.log和pytest.xml是真实文本证据，不能代替终端截图。先完成最后一次run_lab5.py，再放入截图；重跑会替换此目录。
- [ ] **核对真实Git远程提交，补齐个人推送证据。** 你已提供https://github.com/jiuge712/IntegratedDesign作为目标仓库；本地分支开发、提交、合并及远程操作由代理执行，真实状态见lab5_git_workflow.md/evidence/lab5_git.log。你仍需亲自检查main及feature/l5-corner远程提交，按课程要求保存推送成功截图/仓库链接；新增个人修改后再次推送。代理执行和提供地址都不自动勾选本项，不提交密码或令牌。
- [ ] **核对指导书所需Git证据和报告个人信息。** 查看真实git log/分支合并记录，按教师要求补姓名、学号、班级、实验日期及仓库链接。不要把示例命令写成已执行记录。
- [ ] **若教师要求实拍棋盘，补充自己的棋盘图片并重跑。** 当前你已授权程序绘制标准棋盘作为正式素材，来源已标注，不需要为本次代码运行额外供图。若课程额外限定实拍，按image_requirements.md提供清晰棋盘，通过--chess或配置替换；不得把生成图改称照片。你未明确告知教师允许情况前，此条件任务保持未完成。

## 实验五最终提交

- [ ] 完成个人报告/截图/远程记录后运行`src/package_lab5.py`刷新deliverables/lab5_source.zip，核对ZIP包含pytest.ini、源码、配置与更新后的文档。
- [ ] 按课程平台提交docs/lab5_report.md、单元测试/源代码、deliverables/lab5_source.zip、所用棋盘及个人纹理图、data/output/lab5_latest、evidence/lab5_latest和课程要求的Git链接/截图。ZIP不含原图、输出、证据或.git历史，需单独提交相应材料。

## 实验四的课堂活动

- [ ] **与一位同学完成两两设计走查。** 将 `detailed_design.md` 和 `coding_standards.md` 交给同学检查，你也检查对方设计。实际记录参与者、日期和至少三条意见，每条包含问题位置、建议、处理情况和验证方式，填写到 `design_walkthrough.md` 的“真实两两走查记录”部分。已有技术自走查是参考，不是同学互查记录。
- [ ] **与小组确认编码规范。** 阅读 `coding_standards.md`，确认命名、注释语言、文件职责、参数/错误约定和格式习惯。把真实讨论的日期、参与者、修改意见及最终确认写入该文档末尾。现有文件是可使用的技术规范，未伪造小组批准。
- [ ] **亲自复现实验四并核对观察。** 按 `reproduction.md` 的实验四章节运行 test_lab4.py、run_lab4.py，查看 Sobel 3/5、三组 Canny 以及光照不均图的分割结果。确认报告中的阈值、密度和现象与自己的运行一致，使用自己的表达补充课堂要求的参数经验。

## 图片与截图 条件性任务

- [ ] **若教师要求两张独立拍摄的素材，补充真实光照不均图片。** 当前清晰图来自你的插画，光照不均图是从它生成的受控阴影版本，已明确标注。可拍摄窗边、室内阴影或明暗区域共存的场景，保存为 `data/input/uneven_real.jpg`。uint8，建议宽高均≥31，含轮廓与局部细节；与纹理图不必同尺寸。运行：

```powershell
Set-Location D:\IntegratedDesign\project_i
.\.venv\Scripts\python.exe -X utf8 src/run_lab4.py --uneven "data/input/uneven_real.jpg"
.\.venv\Scripts\python.exe -X utf8 src/package_lab4.py
```

  若希望以后默认读取该图片，把 `config/lab4_images.json` 的 uneven 改为 `data/input/uneven_real.jpg`。如教师允许同图派生的受控实验，可在本清单注明允许情况，此项无需另拍；不要把模拟图改称实拍。

- [ ] **若课程要求真实终端/操作截图，补充截图。** 截取实际命令、SUCCESS、Otsu返回阈值、三组密度及输出文件画面，保存到 `evidence/lab4_latest`。现有PNG是程序生成的对比图，不冒充系统截图。新一次完整运行会替换该证据目录，因此先完成最后一次运行，再补截图。
- [ ] **若课程有统一封面或个人信息格式，填写真实信息。** 按教师要求补姓名、学号、班级、课程、实验日期及小组成员，不填虚构参与者。

## 若同时提交此前实验

- [ ] 实验二：完成课堂需求互评，至少三条真实意见补入 `mvp_review.md`，注明参与者、日期和采纳情况。已有技术评审意见可以作为检查线索。
- [ ] 实验三：与小组确认 `architecture.md` 和 `interface_agreement.md` 中的函数签名、BGR/dtype/坐标约定，记录真实确认和变更。代码已有接口演示及输入不变验证。

## 最终提交

- [ ] 完成上述需要的课堂记录后，运行 `src/package_lab4.py` 更新源码ZIP，避免提交的文档还是修改前版本。
- [ ] 按课程平台要求提交 `docs/lab4_report.md`、`detailed_design.md`、`coding_standards.md`、`design_walkthrough.md`、`deliverables/lab4_source.zip`、个人输入及 `data/output/lab4_latest`/`evidence/lab4_latest`。源码ZIP不含原图、环境或输出，图片与证据需要单独提交或另行打包。

## 代理已完成的技术材料 不代表个人任务完成

实验四28项自检和12项正式检查、实验五35项独立pytest用例/全项目回归及14项正式检查已通过。Sobel/Canny/分割、Harris/Shi/FAST、金字塔/DoG、手写加分分支、最新结果管理及技术文档均已提供。原始插画和已有黑白图保留；经你明确授权的程序棋盘已经准备好，通常无需另供实验五素材。上述只说明代理完成的技术范围，不勾选你本人尚未明确确认的任何任务。

代理已实际推送实验五main和feature/l5-corner至你指定的GitHub仓库，远程分支SHA核验通过；你本人核对/保存课程所需截图和仓库链接的任务仍未完成，不因代理操作自动勾选。

此清单随后续实验更新。你明确告知对应事项完成后再勾选、注明真实日期；此前未告知的任务始终保持未完成。
