# 实验一素材准备记录

准备时间：2026-10-13T20:40:44+08:00。

源图：`data/input/DreamEnding_swing_dusk.jpg`，1192×671，三通道 uint8。源图及用户黑白图前后 SHA-256 均一致。

本次根据用户指示由其提供的原图导出实验素材。派生文件位于独立的新建目录，正式测试仍禁止向输入目录写入。

| 角色 | 文件 | 宽×高 | 通道 | 转换与来源 |
| --- | --- | --- | --- | --- |
| color | `data/input/prepared_2026-10-13T20-40-44+08-00_8e9074/color.png` | 1192×671 | 3 | 原 JPEG 解码像素无损保存为三通道 PNG |
| gray | `data/input/prepared_2026-10-13T20-40-44+08-00_8e9074/gray.png` | 1192×671 | 1 | OpenCV COLOR_BGR2GRAY，真正的单通道 PNG |
| rgba | `data/input/prepared_2026-10-13T20-40-44+08-00_8e9074/rgba.png` | 1192×671 | 4 | 保留原 RGB；左侧 149 列 Alpha=0，随后 149 列 Alpha=128，其余 Alpha=255；为透明度测试遮罩 |
| different_size | `data/input/prepared_2026-10-13T20-40-44+08-00_8e9074/different_size.png` | 320×180 | 3 | 按比例缩放至 320×180 |
| large | `data/input/prepared_2026-10-13T20-40-44+08-00_8e9074/large.png` | 1920×1080 | 3 | 等比例调整至 1919×1080，居中置于 1920×1080 黑色画布；缩放图片用于尺寸及性能测试，不增加原始细节 |
| jpeg | `data/input/prepared_2026-10-13T20-40-44+08-00_8e9074/photo.jpg` | 1192×671 | 3 | JPEG 原文件逐字节复制，未重新压缩 |
| black | `data/input/black.png` | 320×240 | 3 | 沿用用户提供的原文件 |
| white | `data/input/white.png` | 320×240 | 3 | 沿用用户提供的原文件 |

详细哈希和属性：`evidence/prepared_2026-10-13T20-40-44+08-00_8e9074/preparation.json`。

配置文件 config/images.json 已更新，运行 run_tests.py 即采用本批素材。

更换原图后重新运行 prepare_inputs.py，再运行 run_tests.py；之前的派生素材和证据保留。
