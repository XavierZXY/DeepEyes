# 图像修复工具性能测试指南

## 📋 概述

`test_all_tools_metrics.py` 是一个全面的工具性能评估脚本，用于：

1. ✅ 测试所有图像修复工具的性能
2. ✅ 计算每个工具的 PSNR/SSIM/LPIPS 指标
3. ✅ 对比退化图和修复图相对原图的质量
4. ✅ 生成详细的性能报告

## 🚀 快速开始

### 基本用法

```bash
# 测试所有工具（使用完整数据集）
python3 tests/test_all_tools_metrics.py \
    --parquet /app/xiaominl/datasets/air_d1_sp9_up2_bs128_n8_balanced/shard-test-000000.parquet \
    --output_dir ./test_results

# 快速测试（只测试前10个样本）
python3 tests/test_all_tools_metrics.py \
    --parquet /app/xiaominl/datasets/air_d1_sp9_up2_bs128_n8_balanced/shard-test-000000.parquet \
    --output_dir ./test_results_quick \
    --max_samples 10

# 只测试特定工具
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/data.parquet \
    --output_dir ./test_results \
    --tools swinir_denoising restormer_motion_deblurring

# 不保存图像（节省磁盘空间）
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/data.parquet \
    --output_dir ./test_results \
    --no_save_images
```

## 📊 输出说明

测试完成后，会在输出目录生成以下文件：

```
test_results/
├── detailed_results.csv        # 详细结果（每个工具×每个样本）
├── summary_report.txt          # 汇总报告（人类可读）
└── images/                     # 图像文件
    ├── sample_0/
    │   ├── original.png                    # 原图（GT）
    │   ├── degraded.png                    # 退化图
    │   ├── swinir_denoising.png           # 工具修复结果
    │   ├── restormer_motion_deblurring.png
    │   └── ...
    └── sample_1/
        └── ...
```

### 详细结果 (detailed_results.csv)

包含每个测试的完整数据：

| 列名 | 说明 |
|------|------|
| `sample_id` | 样本标识符 |
| `degradation_types` | 退化类型（如 "noise, blur"） |
| `degradation_levels` | 退化等级（如 "high, medium"） |
| `tool_name` | 工具名称 |
| `success` | 是否成功（True/False） |
| `baseline_psnr` | 退化图 vs 原图的 PSNR |
| `baseline_ssim` | 退化图 vs 原图的 SSIM |
| `baseline_lpips` | 退化图 vs 原图的 LPIPS |
| `restored_psnr` | 修复图 vs 原图的 PSNR |
| `restored_ssim` | 修复图 vs 原图的 SSIM |
| `restored_lpips` | 修复图 vs 原图的 LPIPS |
| `psnr_improvement` | PSNR 改进量 |
| `ssim_improvement` | SSIM 改进量 |
| `lpips_improvement` | LPIPS 改进量（正数表示改进） |

### 汇总报告 (summary_report.txt)

人类可读的文本报告，包含：

1. **工具性能汇总**: 每个工具的平均性能
2. **按退化类型的工具性能**: 针对特定退化的最佳工具
3. **推荐工具**: 按PSNR改进排序的前10名工具

## 🔧 可用工具列表

脚本支持测试以下15个工具：

### SwinIR 系列（端口 5001）
- `swinir_denoising` - 去噪
- `swinir_jpeg_artifact_removal` - JPEG伪影去除
- `swinir_super_resolution` - 超分辨率

### Restormer 系列（端口 5006）
- `restormer_motion_deblurring` - 运动去模糊
- `restormer_defocus_deblurring` - 散焦去模糊
- `restormer_deraining` - 去雨

### XRestormer 系列（端口 5007）
- `xrestormer_motion_deblurring` - 运动去模糊
- `xrestormer_deraining` - 去雨

### MPRNet 系列（端口 5004）
- `mprnet_denoising` - 去噪
- `mprnet_motion_deblurring` - 运动去模糊
- `mprnet_deraining` - 去雨

### 其他工具
- `fbcnn_jpeg_artifact_removal` - FBCNN JPEG伪影去除（端口 5005）
- `drbnet_defocus_deblurring` - DRBNet散焦去模糊（端口 5003）
- `dehazeformer_dehaze` - DehazeFormer去雾（端口 5002）

## 📝 指标说明

### PSNR (Peak Signal-to-Noise Ratio)
- **范围**: 0-100 dB（理论上无上限）
- **越高越好**
- **典型值**: 20-40 dB
- **说明**: 峰值信噪比，衡量图像质量的客观指标

### SSIM (Structural Similarity Index)
- **范围**: 0-1
- **越高越好**
- **典型值**: 0.7-0.95
- **说明**: 结构相似性指数，衡量图像结构的保持程度

### LPIPS (Learned Perceptual Image Patch Similarity)
- **范围**: 0-1
- **越低越好**（注意与前两者相反）
- **典型值**: 0.1-0.5
- **说明**: 感知损失，基于深度学习的感知相似度

## 🔍 结果分析示例

假设某个样本的测试结果：

```
样本: sample_42
退化类型: noise, jpeg compression artifact
退化等级: high, medium

基线指标（退化图 vs 原图）:
  PSNR: 22.45 dB
  SSIM: 0.6543
  LPIPS: 0.3821

工具: swinir_denoising
  修复后 PSNR: 28.32 dB (+5.87 dB) ✅ 改进明显
  修复后 SSIM: 0.8123 (+0.1580) ✅ 结构改善
  修复后 LPIPS: 0.2145 (-0.1676) ✅ 感知质量提升

工具: restormer_motion_deblurring
  修复后 PSNR: 21.89 dB (-0.56 dB) ❌ 反而下降
  修复后 SSIM: 0.6234 (-0.0309) ❌ 结构损失
  修复后 LPIPS: 0.4012 (+0.0191) ❌ 感知质量下降
```

**分析**:
- `swinir_denoising` 对噪声退化效果显著（PSNR提升5.87 dB）
- `restormer_motion_deblurring` 不适合这种退化，反而导致质量下降

## ⚙️ 环境配置

### 必需的环境变量

```bash
# 设置工具服务IP（所有工具共用）
export TOOL_SERVICE_IP=10.21.9.6

# 确保GPU可用（LPIPS需要）
nvidia-smi  # 或 rocm-smi（AMD GPU）
```

### 依赖项

脚本会自动使用以下模块：
- `pandas` - 数据处理
- `PIL (Pillow)` - 图像处理
- `requests` - API调用
- `verl.utils.reward_score.image_quality_metrics` - 指标计算（PSNR/SSIM/LPIPS）

这些依赖已包含在项目的 `requirements.txt` 中。

## 🎯 典型使用场景

### 场景1: 评估所有工具的整体性能

```bash
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/test_data.parquet \
    --output_dir ./results_all_tools
```

查看 `summary_report.txt` 中的"推荐工具"部分。

### 场景2: 找出针对特定退化的最佳工具

```bash
# 测试完整数据集
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/test_data.parquet \
    --output_dir ./results_by_degradation

# 在报告中查看"按退化类型的工具性能"部分
cat ./results_by_degradation/summary_report.txt
```

### 场景3: 对比两个工具的性能

```bash
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/test_data.parquet \
    --output_dir ./results_comparison \
    --tools swinir_denoising mprnet_denoising

# 在Excel中打开CSV对比
libreoffice ./results_comparison/detailed_results.csv
```

### 场景4: 快速验证工具是否正常工作

```bash
# 只测试1个样本
python3 tests/test_all_tools_metrics.py \
    --parquet /path/to/test_data.parquet \
    --output_dir ./sanity_check \
    --max_samples 1 \
    --tools swinir_denoising

# 检查是否有成功的结果
grep "success" ./sanity_check/detailed_results.csv
```

## 🐛 故障排除

### 问题1: 连接错误

```
[API] ❌ 连接错误: Connection refused
```

**解决方法**:
1. 检查工具服务是否启动
2. 检查 `TOOL_SERVICE_IP` 环境变量是否正确
3. 检查防火墙设置

### 问题2: GPU内存不足

```
[API] ❌ API返回错误: CUDA out of memory
```

**解决方法**:
1. 减少并发测试的样本数（使用 `--max_samples`）
2. 重启工具服务释放GPU内存
3. 使用更小的图像尺寸

### 问题3: 图像尺寸不一致

```
[警告] 图像尺寸不一致: (1024, 768) vs (512, 512)，调整为相同尺寸
```

**说明**: 脚本会自动调整图像尺寸，这不是错误。

### 问题4: parquet文件格式不兼容

```
[警告] 样本 X 缺少原图，跳过
```

**解决方法**:
1. 确认parquet文件包含 `extra_info` 字段
2. 确认 `extra_info['original_image']` 存在
3. 检查数据格式是否符合训练数据的格式

## 📈 性能优化

### LPIPS GPU加速

脚本自动使用GPU加速的LPIPS计算（50倍加速），无需额外配置。

如果看到以下日志，说明GPU加速已启用：

```
[INFO] LPIPS model initialized on GPU: cuda:0
```

### 批量测试技巧

```bash
# 分批测试（避免单次运行时间过长）
for i in {0..3}; do
    python3 tests/test_all_tools_metrics.py \
        --parquet /path/to/shard-test-00000$i.parquet \
        --output_dir ./results_shard_$i
done

# 合并结果
cat results_shard_*/detailed_results.csv > combined_results.csv
```

## 📚 进阶用法

### 导出数据用于绘图

```python
import pandas as pd
import matplotlib.pyplot as plt

# 读取结果
df = pd.read_csv('test_results/detailed_results.csv')

# 绘制PSNR改进分布
df.boxplot(column='psnr_improvement', by='tool_name', figsize=(15, 6))
plt.xticks(rotation=45)
plt.title('PSNR Improvement by Tool')
plt.savefig('psnr_improvement.png')

# 绘制成功率
success_rate = df.groupby('tool_name')['success'].mean().sort_values()
success_rate.plot(kind='barh', figsize=(10, 8))
plt.title('Tool Success Rate')
plt.xlabel('Success Rate')
plt.savefig('success_rate.png')
```

### 过滤特定退化类型

```python
import pandas as pd

df = pd.read_csv('test_results/detailed_results.csv')

# 只看噪声退化
noise_df = df[df['degradation_types'].str.contains('noise')]

# 找出最佳去噪工具
best_denoising = noise_df.groupby('tool_name')['psnr_improvement'].mean().sort_values(ascending=False)
print(best_denoising.head())
```

## 📞 支持

如有问题，请检查：
1. 日志输出（包含详细的错误信息）
2. `detailed_results.csv`（查看哪些测试失败）
3. 工具服务日志（服务端错误）

---

**版本**: v1.0  
**创建日期**: 2025-10-13  
**作者**: AI Assistant

