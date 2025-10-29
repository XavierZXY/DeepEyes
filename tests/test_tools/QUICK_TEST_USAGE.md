# 快速测试单个工具使用说明

## 📋 脚本说明

我们提供了两个快速测试脚本，用于测试单个工具并显示完整的指标（类似 test_results.md 格式）：

| 脚本 | 用途 | 输入数据格式 |
|------|------|------------|
| `quick_test_tool.py` | 测试单个工具（图像文件） | PNG/JPG 图像文件 |
| `quick_test_tool_parquet.py` | 测试单个工具（Parquet 数据集） | Parquet 文件 ⭐ 推荐 |

---

## 🚀 使用方法

### 方法1：使用图像文件测试

```bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 测试 DehazeFormer
python quick_test_tool.py dehazeformer_dehaze \
  /path/to/degraded_image.png \
  /path/to/original_image.png

# 测试 DRBNet
python quick_test_tool.py drbnet_defocus_deblurring \
  /path/to/degraded_image.png \
  /path/to/original_image.png
```

### 方法2：使用 Parquet 数据集测试 ⭐ 推荐

```bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 测试 DehazeFormer（使用第 0 个样本）
python quick_test_tool_parquet.py dehazeformer_dehaze \
  --parquet /app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet \
  --sample-idx 0

# 测试 DRBNet（使用第 5 个样本）
python quick_test_tool_parquet.py drbnet_defocus_deblurring \
  --parquet /app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet \
  --sample-idx 5

# 使用默认 parquet 路径
python quick_test_tool_parquet.py dehazeformer_dehaze --sample-idx 0
```

---

## 📊 输出格式

脚本会输出类似 `test_results.md` 的格式：

```
================================================================================
测试结果（类似 test_results.md 格式）
================================================================================

## 基线指标 (退化图 vs 原图)

| PSNR (dB) | SSIM   | LPIPS  |
|-----------|--------|--------|
| 30.56     | 0.8443 | 0.2066 |

## 工具修复效果

### dehazeformer_dehaze

| PSNR  | SSIM   | LPIPS  | PSNR↑   | SSIM↑  | LPIPS↓ | 状态 |
|-------|--------|--------|---------|--------|--------|------|
| 29.17 | 0.8258 | 0.1911 | -4.5%   | -2.2%  | +7.5%  | ⚠️   |
```

---

## 🎯 测试结果示例

### DehazeFormer 测试结果

**样本 0**：
```
基线: PSNR=30.56, SSIM=0.8443, LPIPS=0.2066
修复: PSNR=29.17, SSIM=0.8258, LPIPS=0.1911
改进: -4.5%, -2.2%, +7.5% ⚠️
```

**分析**：
- 这个样本的退化程度很轻（基线 PSNR=30.56 已经很高）
- DehazeFormer 对轻度退化的处理可能会略微降低 PSNR/SSIM
- 但 LPIPS 有改善（+7.5%），说明感知质量略有提升

### DRBNet 测试结果

**样本 5**：
```
基线: PSNR=30.77, SSIM=0.9259, LPIPS=0.1975
修复: PSNR=33.08, SSIM=0.9668, LPIPS=0.0361
改进: +7.5%, +4.4%, +81.7% ✅
```

**分析**：
- DRBNet 在这个样本上表现很好
- 所有指标都有明显改善，特别是 LPIPS 改善了 81.7%

---

## 🔧 参数说明

### quick_test_tool.py

```
positional arguments:
  tool_name              工具名称
  degraded_image         退化图路径
  original_image         原图路径
```

### quick_test_tool_parquet.py

```
positional arguments:
  tool_name              工具名称

optional arguments:
  --parquet PATH         Parquet 文件路径
                         (默认: /app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet)
  --sample-idx N         样本索引（默认: 0）
```

---

## 📝 支持的工具列表

```
去雾：
  - dehazeformer_dehaze

去模糊：
  - drbnet_defocus_deblurring
  - restormer_motion_deblurring
  - restormer_defocus_deblurring
  - mprnet_motion_deblurring

去噪：
  - swinir_denoising
  - mprnet_denoising
  - scunet_real_denoising_psnr
  - scunet_real_denoising_gan
  - scunet_color_denoising

去雨：
  - restormer_deraining
  - mprnet_deraining

JPEG 伪影：
  - swinir_jpeg_artifact_removal
  - fbcnn_jpeg_artifact_removal

超分辨率：
  - swinir_super_resolution

低光增强：
  - retinexformer_lol_v1
  - retinexformer_lol_v2_real
```

---

## 💡 使用技巧

### 1. 批量测试不同样本

```bash
# 测试样本 0-9
for i in {0..9}; do
  echo "=== 样本 $i ==="
  python quick_test_tool_parquet.py dehazeformer_dehaze --sample-idx $i 2>&1 | tail -15
  echo ""
done
```

### 2. 对比不同工具

```bash
# 对比 DehazeFormer 和 DRBNet
python quick_test_tool_parquet.py dehazeformer_dehaze --sample-idx 0 > dehaze_result.txt
python quick_test_tool_parquet.py drbnet_defocus_deblurring --sample-idx 0 > drbnet_result.txt

# 查看对比
diff -y dehaze_result.txt drbnet_result.txt
```

### 3. 保存结果到文件

```bash
# 保存完整输出
python quick_test_tool_parquet.py dehazeformer_dehaze --sample-idx 0 \
  2>&1 | tee dehaze_test_result.txt

# 只保存表格部分
python quick_test_tool_parquet.py dehazeformer_dehaze --sample-idx 0 \
  2>&1 | grep -A 20 "测试结果"
```

---

## 🐛 故障排查

### 问题1：工具连接失败

```
[ERROR] HTTPConnectionPool: Connection refused
```

**解决**：
1. 检查工具服务是否启动
2. 验证 IP 地址是否正确
3. 检查防火墙设置

```bash
# 检查服务
curl http://10.21.9.6:5002/dehaze -X POST
```

### 问题2：样本索引超出范围

```
[ERROR] 样本索引 100 超出范围（最大: 320）
```

**解决**：
- 检查 parquet 文件的样本数量
- 使用较小的索引值

```bash
# 查看样本数量
python -c "import pandas as pd; print(len(pd.read_parquet('your.parquet')))"
```

### 问题3：改进率为负

这不是错误！说明：
- 退化程度很轻，工具可能过度处理
- 该样本不适合该工具
- 工具参数需要调整

---

## ✅ 验证清单

在测试前，确保：

- [ ] 工具服务已启动（端口 5001-5009）
- [ ] `TOOL_SERVICE_IP` 环境变量已设置（或使用默认 10.21.9.6）
- [ ] Parquet 文件路径正确
- [ ] 样本索引在有效范围内

---

## 🔗 相关文档

- [IP_FIX_DOCUMENTATION.md](./IP_FIX_DOCUMENTATION.md) - IP 地址修复说明
- [UNIFIED_RETURN_FORMAT.md](./UNIFIED_RETURN_FORMAT.md) - 工具统一返回格式
- [WHY_SOME_TOOLS_WORKED.md](./WHY_SOME_TOOLS_WORKED.md) - 为什么有些工具能成功

---

**创建时间**: 2025-10-20  
**版本**: v1.0  
**状态**: ✅ 已验证

