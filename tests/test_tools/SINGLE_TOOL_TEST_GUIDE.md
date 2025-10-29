# 测试单个工具完整指南

## 🎯 脚本功能

`test_single_tool.py` 可以测试单个工具在整个文件夹数据集上的效果（所有级别）。

输出格式与 `test_results.md` 完全一致！

---

## 🚀 使用方法

### 基础用法

\`\`\`bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 测试 DehazeFormer（haze 类型，所有级别）
python test_single_tool.py dehazeformer_dehaze haze

# 测试 DRBNet（defocus_blur 类型，所有级别）
python test_single_tool.py drbnet_defocus_deblurring defocus_blur
\`\`\`

### 限制样本数量

\`\`\`bash
# 每个级别只测试 3 个样本（快速验证）
python test_single_tool.py dehazeformer_dehaze haze --num-samples 3

# 每个级别测试 10 个样本
python test_single_tool.py drbnet_defocus_deblurring defocus_blur --num-samples 10
\`\`\`

### 只测试特定级别

\`\`\`bash
# 只测试 low 和 medium 级别
python test_single_tool.py dehazeformer_dehaze haze --levels low medium

# 只测试 high 级别
python test_single_tool.py drbnet_defocus_deblurring defocus_blur --levels high
\`\`\`

### 自定义数据集路径

\`\`\`bash
python test_single_tool.py dehazeformer_dehaze haze \
  --dataset /path/to/your/dataset \
  --num-samples 5
\`\`\`

---

## 📊 输出结果

### 生成的文件

脚本会在输出目录生成 3 个文件：

1. **Markdown 报告** (`*.md`) - 易读格式
2. **JSON 文件** (`*.json`) - 完整数据
3. **CSV 文件** (`*.csv`) - 表格分析

### Markdown 报告示例

\`\`\`markdown
# DehazeFormer 测试报告

**工具名称**: dehazeformer_dehaze
**退化类型**: haze
**测试时间**: 2025-10-20 11:22:24

## 基线指标 (退化图 vs 原图)

| Level | PSNR (dB) | SSIM | LPIPS |
|-------|-----------|------|-------|
| high | 12.20 | 0.7576 | 0.1860 |
| low | 28.03 | 0.9507 | 0.0155 |
| medium | 17.55 | 0.8536 | 0.0927 |

## 工具修复效果

### DehazeFormer

| Level | PSNR | SSIM | LPIPS | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率 |
|-------|------|------|-------|-------|-------|--------|--------|
| high | 18.72 | 0.8804 | 0.0791 | +53.4% | +16.2% | +57.5% | 100.0% (3/3) |
| low | 20.63 | 0.8960 | 0.0499 | -26.4% | -5.8% | -220.9% | 100.0% (3/3) |
| medium | 20.53 | 0.9056 | 0.0630 | +17.0% | +6.1% | +32.0% | 100.0% (3/3) |
\`\`\`

---

## 💡 完整示例

### 测试所有去雾工具对比

\`\`\`bash
# 只有一个去雾工具，直接测试
python test_single_tool.py dehazeformer_dehaze haze --num-samples 10
\`\`\`

### 测试所有去模糊工具对比

\`\`\`bash
# 测试 Restormer（散焦去模糊）
python test_single_tool.py restormer_defocus_deblurring defocus_blur --num-samples 10

# 测试 DRBNet（散焦去模糊）
python test_single_tool.py drbnet_defocus_deblurring defocus_blur --num-samples 10

# 对比报告
diff -y test_drbnet_single/*.md test_restormer_single/*.md
\`\`\`

### 测试所有去噪工具对比

\`\`\`bash
# SwinIR
python test_single_tool.py swinir_denoising noise --num-samples 10

# MPRNet
python test_single_tool.py mprnet_denoising noise --num-samples 10

# SCUNet-Real-PSNR
python test_single_tool.py scunet_real_denoising_psnr noise --num-samples 10

# SCUNet-Real-GAN
python test_single_tool.py scunet_real_denoising_gan noise --num-samples 10
\`\`\`

---

## 📈 参数说明

\`\`\`
positional arguments:
  tool_name              工具名称（如: dehazeformer_dehaze）
  degradation_type       退化类型（如: haze, noise, rain, defocus_blur）

options:
  --dataset PATH         数据集根目录（默认: /app/xiaominl/datasets/degraded_datasets/degraded_dataset）
  --num-samples N        每个级别的样本数量（默认: 全部）
  --levels LEV1 LEV2     要测试的级别（如: low medium high）
  --output DIR           输出目录（默认: ./single_tool_results）
  --tool-service-ip IP   工具服务IP地址（默认: 10.21.9.6）
\`\`\`

---

## 🔍 支持的工具和退化类型

| 退化类型 | 可用工具 |
|---------|---------|
| **haze** | dehazeformer_dehaze |
| **noise** | swinir_denoising, mprnet_denoising, scunet_real_denoising_psnr, scunet_real_denoising_gan, scunet_color_denoising, scunet_gray_denoising |
| **motion_blur** | restormer_motion_deblurring, mprnet_motion_deblurring, xrestormer_motion_deblurring |
| **defocus_blur** | restormer_defocus_deblurring, drbnet_defocus_deblurring |
| **rain** | restormer_deraining, mprnet_deraining, xrestormer_deraining |
| **jpeg** | swinir_jpeg_artifact_removal, fbcnn_jpeg_artifact_removal |
| **low_resolution** | swinir_super_resolution |
| **dark** | constant_shift, gamma_correction, histogram_equalization, retinexformer_enhance, retinexformer_sdsd_indoor 等 |

---

## ✅ 优势对比

| 特性 | test_restoration_tools.py | test_single_tool.py |
|------|--------------------------|---------------------|
| 测试范围 | 所有工具 | 单个工具 ⭐ |
| 速度 | 慢（测试多个工具） | 快（只测试一个） |
| 适用场景 | 对比多个工具 | 深入评估单个工具 |
| 输出格式 | 完整报告 | 完整报告（相同） |

**推荐使用场景**：
- ✅ 当你只想测试 DehazeFormer 或 DRBNet 其中一个
- ✅ 快速验证单个工具的修复效果
- ✅ 深入分析单个工具在所有级别上的表现

---

**创建时间**: 2025-10-20  
**版本**: v1.0
