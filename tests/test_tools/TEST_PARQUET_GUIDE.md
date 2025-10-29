# 测试整个 Parquet 数据集指南

## 🚀 快速开始

### 测试单个工具（10个样本）

\`\`\`bash
cd /app/xiaominl/DeepEyes_v2/tests/test_tools

# 测试 DehazeFormer（10个样本）
python test_tool_on_parquet.py dehazeformer_dehaze --num-samples 10

# 测试 DRBNet（10个样本）
python test_tool_on_parquet.py drbnet_defocus_deblurring --num-samples 10
\`\`\`

### 测试整个数据集（全部样本）

\`\`\`bash
# 测试所有样本（321个）
python test_tool_on_parquet.py dehazeformer_dehaze

# 指定输出目录
python test_tool_on_parquet.py dehazeformer_dehaze \
  --output ./results_dehaze_full
\`\`\`

### 使用自定义 Parquet 文件

\`\`\`bash
python test_tool_on_parquet.py dehazeformer_dehaze \
  --parquet /path/to/your/data.parquet \
  --num-samples 50
\`\`\`

---

## 📊 输出结果

脚本会生成 3 个文件：

### 1. Markdown 报告（可读性强）

\`\`\`markdown
## 测试工具: dehazeformer_dehaze

### 基线指标 (退化图 vs 原图)
| 指标      | 平均值 | 标准差 |
|-----------|--------|--------|
| PSNR (dB) | 28.55  | ±4.14 |
| SSIM      | 0.7587 | ±0.2332 |
| LPIPS     | 0.3375 | ±0.2961 |

### 修复后指标 (修复图 vs 原图)
| 指标      | 平均值 | 标准差 |
|-----------|--------|--------|
| PSNR (dB) | 19.32  | ±4.97 |
| SSIM      | 0.6511 | ±0.2317 |
| LPIPS     | 0.4011 | ±0.3260 |

### 改进率
| 指标   | 平均改进 | 标准差 | 状态 |
|--------|---------|--------|------|
| PSNR↑  | -31.5%  | ±16.8% | ⚠️ |
| SSIM↑  | -14.2%  | ±13.8% | ⚠️ |
| LPIPS↓ | -28.8% | ±33.6% | ⚠️ |

### 详细结果（每个样本）
| 样本 | 基线PSNR | 修复PSNR | PSNR↑ | ... |
|------|---------|---------|-------|-----|
|  0   | 30.56   | 29.03   | -5.0% | ... |
|  1   | 30.54   | 30.52   | -0.1% | ... |
...
\`\`\`

### 2. JSON 文件（完整数据）

包含所有统计信息和每个样本的详细结果。

### 3. CSV 文件（Excel 分析）

可以用 Excel/Pandas 进一步分析。

---

## 💡 实用命令

### 对比两个工具

\`\`\`bash
# 测试两个工具
python test_tool_on_parquet.py dehazeformer_dehaze --num-samples 20
python test_tool_on_parquet.py drbnet_defocus_deblurring --num-samples 20

# 对比 Markdown 报告
diff -y test_dehaze_parquet/*.md test_drbnet_parquet/*.md | less
\`\`\`

### 查看详细结果

\`\`\`bash
# 查看 Markdown 报告
cat ./parquet_test_results/*.md

# 查看 CSV（用 column 命令格式化）
column -t -s, ./parquet_test_results/*.csv | less -S

# 分析 JSON（用 jq）
cat ./parquet_test_results/*.json | jq '.statistics'
\`\`\`

### 批量测试多个工具

\`\`\`bash
#!/bin/bash
# 创建批量测试脚本

TOOLS=(
    "dehazeformer_dehaze"
    "drbnet_defocus_deblurring"
    "restormer_motion_deblurring"
    "swinir_denoising"
)

for tool in "\${TOOLS[@]}"; do
    echo "测试 \$tool..."
    python test_tool_on_parquet.py \$tool \
        --num-samples 20 \
        --output ./results_\$tool
done

echo "所有测试完成！"
\`\`\`

---

## 📈 测试结果示例

### DehazeFormer（10个样本）

\`\`\`
基线指标: PSNR=28.55±4.14, SSIM=0.7587±0.2332, LPIPS=0.3375±0.2961
修复指标: PSNR=19.32±4.97, SSIM=0.6511±0.2317, LPIPS=0.4011±0.3260
改进率: -31.5%±16.8%, -14.2%±13.8%, -28.8%±33.6% ⚠️
成功率: 100.0%
\`\`\`

### DRBNet（10个样本）

\`\`\`
基线指标: PSNR=28.55±4.14, SSIM=0.7587±0.2332, LPIPS=0.3375±0.2961
修复指标: PSNR=28.58±3.41, SSIM=0.7856±0.1975, LPIPS=0.2989±0.2830
改进率: +0.7%±5.8%, +10.0%±23.3%, +13.7%±33.6% ✅
成功率: 100.0%
\`\`\`

---

## 🎯 参数说明

\`\`\`
positional arguments:
  tool_name             工具名称

optional arguments:
  --parquet PATH        Parquet 文件路径
                        (默认: /app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet)
  --num-samples N       测试的样本数量（默认: 全部 321 个）
  --output DIR          输出目录（默认: ./parquet_test_results）
\`\`\`

---

## ✅ 总结

现在你有 3 个工具可用：

| 脚本 | 用途 | 适用场景 |
|------|------|---------|
| \`quick_test_tool_parquet.py\` | 测试单个样本 | 快速调试单个工具 |
| \`test_tool_on_parquet.py\` | 测试整个数据集 | **完整评估工具性能** ⭐ |
| \`test_restoration_tools.py\` | 测试所有工具 | 对比多个工具 |

**推荐使用** \`test_tool_on_parquet.py\` 来全面评估单个工具的性能！

---

**创建时间**: 2025-10-20  
**版本**: v1.0
