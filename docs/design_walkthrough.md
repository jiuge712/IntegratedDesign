# 实验四设计走查记录

技术自走查日期：2026年10月14日。下表是根据代码与实际测试完成的技术自检查，不伪装成两名同学交换设计的课堂记录。

| 编号 | 可改进点 | 已落实的处理 | 验证证据 |
| --- | --- | --- | --- |
| TW-01 | 恒定图幅值最大值为0，直接归一化会除零 | unit_gray遇peak=0返回全黑 | test_constant_sobel_zero_without_division |
| TW-02 | Sobel负响应直接转uint8会破坏导数 | 保留CV_64F原值，显示用abs/hypot，浮点NPZ归档 | test_signed_negative_gradient_preserved及正式归档回读 |
| TW-03 | 手写NMS的45°邻点容易混淆图像y方向 | 图像坐标下使用NW/SE，一侧严格比较打破平台 | test_nms_45_degrees_uses_image_row_coordinates、test_nms_breaks_equal_plateau |
| TW-04 | 模拟光照可能被误称为实拍，边缘IoU可能被误称准确率 | 记录输入来源/uneven_is_derived，一致性指标明确无真值含义 | results.json及报告来源和限制 |
| TW-05 | 重跑可能累积输出或失败时丢失有效结果 | lab4_latest校验后替换，失败保留旧结果 | test_latest_lab4_replacement_and_failure及实际失败保留验证 |

其他经验：显式高斯平滑、原始梯度阈值和L2度量统一；固定128与Otsu阈值偶尔相同应如实记录，不为了显得有对比而改动结果。

## 真实两两走查记录 待参与者填写

指导书要求两两交换设计文档、至少三条真实意见。具体步骤见user_tasks.md。请在活动发生后填写，不复制上表作为假定的同学评论。

- 日期与地点：待填写。
- 设计作者、检查者及对方文档：待填写。
- 交换文档：detailed_design.md、coding_standards.md。

| 意见 | 提出者 | 函数/文档位置 | 发现的问题与建议 | 处理决定与验证 |
| --- | --- | --- | --- | --- |
| 1 | 待填写 | 待填写 | 待真实走查 | 待填写 |
| 2 | 待填写 | 待填写 | 待真实走查 | 待填写 |
| 3 | 待填写 | 待填写 | 待真实走查 | 待填写 |

完成后按用户任务清单核对并重新生成源码ZIP，保证提交包包含最新记录。
