# 图像修复工具测试脚本

## 📋 功能说明

该脚本用于测试各种图像修复工具的效果，通过对比原图、退化图和修复图来计算质量指标。

### 支持的指标
- **PSNR** (Peak Signal-to-Noise Ratio): 峰值信噪比，越高越好
- **SSIM** (Structural Similarity Index): 结构相似性，越高越好
- **LPIPS** (Learned Perceptual Image Patch Similarity): 感知相似度，越低越好

### 支持的退化类型和工具

| 退化类型 | 工具 |
|---------|------|
| **haze** | DehazeFormer |
| **noise** | SwinIR, MPRNet |
| **motion_blur** | Restormer, MPRNet, XRestormer |
| **defocus_blur** | Restormer, DRBNet |
| **rain** | Restormer, MPRNet, XRestormer |
| **jpeg** | SwinIR, FBCNN |
| **low_resolution** | SwinIR |
| **dark** | Constant Shift, Gamma Correction, Histogram Equalization |

---

## 📁 数据集结构

```
dataset/
├── original/              # 原图（ground truth）
│   ├── 000001.png
│   ├── 000002.png
│   └── ...
├── haze/                  # 雾霾退化
│   ├── low/               # 低级别
│   │   ├── 000001_level1.png
│   │   └── 000002_level1.png
│   ├── medium/            # 中级别
│   └── high/              # 高级别
├── rain/                  # 雨滴退化
├── noise/                 # 噪声退化
└── ...
```

**注意**: 
- `original/000001.png` 和 `haze/low/000001_level1.png` 是同一个样本的原图和退化图
- 每个退化类型可以有多个级别（low, medium, high等）
- 级别目录下的图像命名格式: `{sample_id}_level{n}.png`

---

## 🚀 使用方法

### 基础用法

```bash
# 测试所有退化类型，使用所有样本
python test_restoration_tools.py --dataset /path/to/dataset --output ./results

# 测试所有类型，每个级别只测试10个样本
python test_restoration_tools.py --dataset /path/to/dataset --num-samples 10 --output ./results
```

### 选择性测试

```bash
# 只测试雾霾和噪声
python test_restoration_tools.py \
    --dataset /path/to/dataset \
    --types haze noise \
    --output ./haze_noise_results

# 排除某些类型
python test_restoration_tools.py \
    --dataset /path/to/dataset \
    --exclude-types dark low_resolution \
    --output ./results

# 只测试低和中等级别
python test_restoration_tools.py \
    --dataset /path/to/dataset \
    --levels low medium \
    --output ./results
```

### 指定工具服务IP

```bash
# 如果工具运行在其他机器上
python test_restoration_tools.py \
    --dataset /path/to/dataset \
    --tool-service-ip 10.21.9.34 \
    --output ./results
```

---

## 📊 输出结果

测试完成后会在输出目录生成以下文件：

### 1. `test_results.json`
完整的JSON格式结果，包含所有详细数据

```json
{
  "haze": {
    "degradation_type": "haze",
    "baseline": {
      "low": {"psnr": 15.23, "ssim": 0.6521, "lpips": 0.3421},
      "medium": {...},
      "high": {...}
    },
    "tools": {
      "dehazeformer_dehaze": {
        "display_name": "DehazeFormer",
        "levels": {
          "low": {
            "metrics": {"psnr": 28.45, "ssim": 0.8921, "lpips": 0.1234},
            "improvement": {"psnr": 86.7, "ssim": 36.8, "lpips": 63.9},
            "success_rate": 1.0
          }
        }
      }
    }
  }
}
```

### 2. `test_results.csv`
表格格式，方便在Excel中分析

| Degradation_Type | Level | Tool | PSNR | SSIM | LPIPS | Improve_PSNR% | ... |
|------------------|-------|------|------|------|-------|---------------|-----|
| haze | low | DehazeFormer | 28.45 | 0.8921 | 0.1234 | +86.7% | ... |

### 3. `test_results.md`
Markdown格式报告，可读性强

```markdown
## haze

### 基线指标 (退化图 vs 原图)
| Level | PSNR (dB) | SSIM | LPIPS |
|-------|-----------|------|-------|
| low   | 15.23     | 0.6521 | 0.3421 |

### 工具修复效果
#### DehazeFormer
| Level | PSNR | SSIM | LPIPS | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率 |
|-------|------|------|-------|-------|-------|--------|--------|
| low   | 28.45 | 0.8921 | 0.1234 | +86.7% | +36.8% | +63.9% | 100.0% |
```

---

## 🔧 参数说明

| 参数 | 必需 | 说明 | 默认值 |
|-----|------|------|--------|
| `--dataset` | ✅ | 数据集根目录 | - |
| `--output` | ❌ | 结果输出目录 | `./test_results` |
| `--num-samples` | ❌ | 每个级别的样本数量 | 全部 |
| `--types` | ❌ | 要测试的退化类型列表 | 全部 |
| `--exclude-types` | ❌ | 要排除的退化类型 | 无 |
| `--levels` | ❌ | 要测试的级别 | 全部 |
| `--tool-service-ip` | ❌ | 工具服务IP地址 | 环境变量 |

---

## 📈 指标解读

### PSNR (峰值信噪比)
- **范围**: 0~∞ dB (通常10-50 dB)
- **越高越好**: 值越大表示图像质量越好
- **改进计算**: `(restored_psnr - baseline_psnr) / baseline_psnr × 100%`
- **参考值**: 
  - >40 dB: 优秀
  - 30-40 dB: 良好
  - 20-30 dB: 可接受
  - <20 dB: 较差

### SSIM (结构相似性)
- **范围**: 0~1
- **越高越好**: 1表示完全相同
- **改进计算**: `(restored_ssim - baseline_ssim) / baseline_ssim × 100%`
- **参考值**:
  - >0.9: 优秀
  - 0.8-0.9: 良好
  - 0.7-0.8: 可接受
  - <0.7: 较差

### LPIPS (感知相似度)
- **范围**: 0~1
- **越低越好**: 0表示感知上完全相同
- **改进计算**: `(baseline_lpips - restored_lpips) / baseline_lpips × 100%` (注意顺序相反)
- **参考值**:
  - <0.1: 优秀
  - 0.1-0.2: 良好
  - 0.2-0.3: 可接受
  - >0.3: 较差

---

## 🔍 示例场景

### 场景1: 快速测试单个类型
```bash
# 测试去雾工具，只用5个样本快速验证
python test_restoration_tools.py \
    --dataset /data/restoration_dataset \
    --types haze \
    --num-samples 5 \
    --output ./quick_test
```

### 场景2: 完整评估
```bash
# 评估所有工具，使用完整数据集
python test_restoration_tools.py \
    --dataset /data/restoration_dataset \
    --output ./full_evaluation
```

### 场景3: 对比实验
```bash
# 只对比不同的去模糊工具
python test_restoration_tools.py \
    --dataset /data/restoration_dataset \
    --types motion_blur defocus_blur \
    --output ./deblur_comparison
```

---

## ⚠️ 注意事项

1. **工具服务**: 确保相关的工具API服务已启动
   - DehazeFormer: port 5002
   - SwinIR: port 5001
   - MPRNet: port 5004
   - Restormer: port 5006
   - 等...

2. **环境变量**: 设置工具服务IP
   ```bash
   export TOOL_SERVICE_IP=10.21.9.34
   ```

3. **内存占用**: 
   - 处理大量高分辨率图像时注意内存使用
   - 可以通过`--num-samples`限制样本数量

4. **GPU使用**: 
   - LPIPS计算会使用GPU（如果可用）
   - 工具API调用也会使用GPU

---

## 🐛 故障排查

### 问题1: 工具调用失败
```
[ERROR] Tool dehazeformer_dehaze execution failed: Connection refused
```
**解决**: 检查工具API服务是否运行，IP和端口是否正确

### 问题2: 找不到样本
```
[WARNING] No levels found for haze
```
**解决**: 检查数据集目录结构是否正确

### 问题3: 内存不足
```
CUDA out of memory
```
**解决**: 减少`--num-samples`数量，或使用CPU模式

---

## 📝 TODO

- [ ] 支持保存修复后的图像
- [ ] 支持批量可视化对比
- [ ] 支持更多无参考质量指标
- [ ] 支持多GPU并行测试
- [ ] 生成HTML可视化报告

---

**创建时间**: 2025-10-14  
**版本**: v1.0  
**维护**: DeepEyes Team

