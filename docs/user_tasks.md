# 需要你完成的任务

更新日期：2026年10月14日。当前实验一至四的代码、个人图片运行、日志和技术文档已完成。以下只列需要你本人或真实同学参与的事情，不能用程序自检、技术自评代替课堂活动；尚未完成的项目保持未勾选。

## 实验四的课堂活动

- [ ] **与一位同学完成两两设计走查。** 将 `detailed_design.md` 和 `coding_standards.md` 交给同学检查，你也检查对方设计。实际记录参与者、日期和至少三条意见，每条包含问题位置、建议、处理情况和验证方式，填写到 `design_walkthrough.md` 的“真实两两走查记录”部分。已有四条技术自走查是参考，不是同学互查记录。
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

## 已完成 不需要重复提供

代码28项自检和个人运行12项正式检查已通过；Sobel/Canny/阈值/自适应及手写NMS/滞后连接、最新结果管理、技术设计、编码规范和技术自走查均已有材料。原始插画和已有黑白图保留，不需要你重做代码或提供实验五的素材。

此清单随后续实验更新。完成后由真实执行者勾选、注明日期；未发生的活动不预先标为完成。
