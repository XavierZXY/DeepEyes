# Baseline测试使用示例

## 快速开始

### 1. 验证数据集格式

在运行测试之前，先验证数据集格式是否正确：

```bash
cd /app/xiaominl/DeepEyes_v2/tests/baseline

# 验证默认测试数据集
python3 verify_dataset.py

# 验证自定义数据集
python3 verify_dataset.py \
    --data-path /path/to/your/dataset.parquet \
    --num-samples 10
```

**输出示例：**
```
================================================================================
Verifying Dataset: /app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet
================================================================================

✅ Successfully loaded parquet file
   Total samples: 1000
   Columns: ['data_source', 'prompt', 'images', 'ability', 'env_name', 'reward_model', 'extra_info']

✅ All required columns present: ['images', 'extra_info', 'reward_model']

================================================================================
Checking Sample Data (first 5 samples)
================================================================================

--- Sample 0 ---
✅ Degraded image: (512, 512) RGB
✅ Original image: (512, 512) RGB
✅ Reward model: 2 degradation(s)
   [1] motion blur (level: low)
   [2] jpeg compression artifact (level: medium)

...

✅ Dataset verification PASSED
```

### 2. 运行快速测试（2个样本）

```bash
cd /app/xiaominl/DeepEyes_v2/tests/baseline

# 快速验证环境配置
./quick_test.sh
```

### 3. 运行完整测试

```bash
cd /app/xiaominl/DeepEyes_v2/tests/baseline

# 测试10个样本，使用两种策略
./run_baseline_test.sh --num-samples 10 --strategy both

# 测试20个样本并保存图像
./run_baseline_test.sh --num-samples 20 --strategy both --save-images
```

## 详细使用场景

### 场景1: 比较随机vs逆序策略

测试两种策略在相同数据上的表现：

```bash
# 运行测试
./run_baseline_test.sh --num-samples 20 --strategy both

# 查看结果摘要
cat results/summary_*.txt
```

**预期输出：**
```
RANDOM Strategy Results:
Average Degraded Metrics:
  PSNR: 23.45
  SSIM: 0.72
  LPIPS: 0.28

Average Restored Metrics:
  PSNR: 26.78
  SSIM: 0.81
  LPIPS: 0.19

Average Improvements:
  PSNR: +3.33
  SSIM: +0.09
  LPIPS: +0.09

REVERSE Strategy Results:
Average Degraded Metrics:
  PSNR: 23.45
  SSIM: 0.72
  LPIPS: 0.28

Average Restored Metrics:
  PSNR: 27.12
  SSIM: 0.83
  LPIPS: 0.17

Average Improvements:
  PSNR: +3.67
  SSIM: +0.11
  LPIPS: +0.11
```

**分析：**
- 如果逆序策略的改善更大，说明按照退化的逆序修复效果更好
- 比较PSNR、SSIM、LPIPS的改善值来评估策略优劣

### 场景2: 测试特定策略

只测试随机策略：

```bash
./run_baseline_test.sh --num-samples 15 --strategy random
```

只测试逆序策略：

```bash
./run_baseline_test.sh --num-samples 15 --strategy reverse
```

### 场景3: 保存可视化结果

保存每个样本的原图、退化图和修复图：

```bash
./run_baseline_test.sh --num-samples 10 --strategy both --save-images

# 查看保存的图像
ls results/sample_0_random/
# 输出: degraded.png  original.png  restored.png

ls results/sample_0_reverse/
# 输出: degraded.png  original.png  restored.png
```

### 场景4: 大规模评估

测试大量样本以获得稳定的统计结果：

```bash
# 测试100个样本（不保存图像以节省空间）
./run_baseline_test.sh --num-samples 100 --strategy both

# 或者分批运行
for i in {0..9}; do
    echo "Batch $i"
    ./run_baseline_test.sh --num-samples 10 --strategy both
done
```

### 场景5: 使用自定义数据集

```bash
# 设置数据路径环境变量
export DATA_PATH="/path/to/your/custom_dataset.parquet"

# 运行测试
./run_baseline_test.sh --num-samples 20

# 或者直接指定
./run_baseline_test.sh \
    --data-path /path/to/your/custom_dataset.parquet \
    --num-samples 20 \
    --strategy both
```

### 场景6: 配置工具服务IP

如果工具服务部署在不同的服务器上：

```bash
# 方式1: 使用环境变量
export TOOL_SERVICE_IP="10.21.9.35"
./run_baseline_test.sh --num-samples 10

# 方式2: 使用命令行参数
./run_baseline_test.sh --tool-service-ip 10.21.9.35 --num-samples 10
```

## 结果分析

### 1. 查看JSON结果

```bash
# 查看最新的结果文件
ls -lt results/results_*.json | head -1

# 使用jq查看格式化的JSON
cat results/results_20251015_123456.json | jq '.[0]'
```

**示例输出：**
```json
{
  "sample_idx": 0,
  "strategy": "random",
  "degraded_metrics": {
    "psnr": 24.567,
    "ssim": 0.7543,
    "lpips": 0.2456
  },
  "restored_metrics": {
    "psnr": 27.890,
    "ssim": 0.8234,
    "lpips": 0.1789
  },
  "improvements": {
    "psnr": 3.323,
    "ssim": 0.0691,
    "lpips": 0.0667
  },
  "restoration_log": [
    {
      "step": 1,
      "degradation": "noise",
      "level": "medium",
      "tool": "SwinIRDenoisingToolbox",
      "tool_args": {"noise_level": 25},
      "success": true,
      "error": null
    },
    {
      "step": 2,
      "degradation": "motion blur",
      "level": "low",
      "tool": "RestormerMotionDeblurringToolbox",
      "tool_args": {},
      "success": true,
      "error": null
    }
  ],
  "degradation_types": ["motion blur", "noise"]
}
```

### 2. 提取特定指标

使用Python分析结果：

```python
import json
import numpy as np

# 加载结果
with open('results/results_20251015_123456.json') as f:
    results = json.load(f)

# 按策略分组
random_results = [r for r in results if r['strategy'] == 'random']
reverse_results = [r for r in results if r['strategy'] == 'reverse']

# 计算平均改善
random_avg_psnr_improvement = np.mean([r['improvements']['psnr'] for r in random_results])
reverse_avg_psnr_improvement = np.mean([r['improvements']['psnr'] for r in reverse_results])

print(f"Random strategy average PSNR improvement: {random_avg_psnr_improvement:.2f}")
print(f"Reverse strategy average PSNR improvement: {reverse_avg_psnr_improvement:.2f}")

# 找出改善最大的样本
best_sample = max(results, key=lambda r: r['improvements']['psnr'])
print(f"\nBest improvement: Sample {best_sample['sample_idx']} with PSNR +{best_sample['improvements']['psnr']:.2f}")
```

### 3. 可视化对比

创建简单的对比图表：

```python
import matplotlib.pyplot as plt
import json

with open('results/results_20251015_123456.json') as f:
    results = json.load(f)

# 提取数据
strategies = ['random', 'reverse']
metrics = ['psnr', 'ssim', 'lpips']

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for i, metric in enumerate(metrics):
    random_vals = [r['improvements'][metric] for r in results if r['strategy'] == 'random']
    reverse_vals = [r['improvements'][metric] for r in results if r['strategy'] == 'reverse']
    
    axes[i].boxplot([random_vals, reverse_vals], labels=strategies)
    axes[i].set_title(f'{metric.upper()} Improvements')
    axes[i].set_ylabel('Improvement')
    axes[i].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('results/comparison.png')
print("Saved comparison plot to results/comparison.png")
```

## 常见问题

### Q1: 如何解读指标改善？

**PSNR (Peak Signal-to-Noise Ratio):**
- 越高越好（通常20-40 dB）
- 正值表示修复后质量提升
- +3 dB 以上通常表示明显改善

**SSIM (Structural Similarity Index):**
- 范围 0-1，越高越好
- +0.05 以上表示有明显改善
- 接近1表示与原图非常相似

**LPIPS (Learned Perceptual Image Patch Similarity):**
- 越低越好（通常0-1）
- 正值表示修复后感知质量提升
- +0.05 以上表示有明显改善

### Q2: 为什么有些样本修复效果不好？

可能的原因：
1. 退化类型识别错误
2. 工具参数不适合
3. 多重退化的交互作用
4. 工具模型的局限性

查看详细日志：
```python
import json
with open('results/results_*.json') as f:
    results = json.load(f)

# 找出效果不好的样本
poor_samples = [r for r in results if r['improvements']['psnr'] < 0]
for sample in poor_samples:
    print(f"Sample {sample['sample_idx']}:")
    print(f"  Degradations: {sample['degradation_types']}")
    print(f"  PSNR change: {sample['improvements']['psnr']:.2f}")
    print(f"  Restoration log: {sample['restoration_log']}")
```

### Q3: 如何调整工具参数？

编辑 `test_baseline_restoration.py` 中的 `DEGRADATION_TO_TOOLS`：

```python
DEGRADATION_TO_TOOLS = {
    'noise': [
        ('SwinIRDenoisingToolbox', SwinIRDenoisingToolbox, {'noise_level': 15}),  # 降低噪声等级
    ],
    'jpeg compression artifact': [
        ('SwinIRJpegArtifactRemovalToolbox', SwinIRJpegArtifactRemovalToolbox, {'quality_factor': 5}),  # 更激进的修复
    ],
}
```

### Q4: 如何添加新的修复工具？

1. 确保工具实现了标准接口
2. 在 `DEGRADATION_TO_TOOLS` 中添加映射
3. 运行测试验证

```python
from your_module import YourNewToolbox

DEGRADATION_TO_TOOLS = {
    'your_degradation_type': [
        ('YourNewToolbox', YourNewToolbox, {'param': value}),
    ],
}
```

## 性能优化

### 并行处理多个样本

可以修改脚本使用多进程：

```python
from multiprocessing import Pool

def process_sample_wrapper(args):
    return test_single_sample(*args)

# 在main函数中
with Pool(processes=4) as pool:
    results = pool.map(process_sample_wrapper, sample_args)
```

### 减少内存使用

```bash
# 不保存图像
./run_baseline_test.sh --num-samples 100

# 分批处理
for i in {0..9}; do
    ./run_baseline_test.sh --num-samples 10 --strategy random
done
```

## 下一步

1. **分析结果**：查看哪种策略效果更好
2. **调优参数**：根据结果调整工具参数
3. **扩展工具**：添加新的修复工具
4. **集成训练**：将最佳策略集成到RL训练中

## 支持

遇到问题？
1. 检查 `verify_dataset.py` 输出
2. 查看工具服务日志
3. 检查网络连接和GPU状态
4. 参考 `README.md` 的故障排查部分

