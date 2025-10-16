# Baseline Restoration Test

这个测试脚本用于评估不同修复策略在退化图像修复任务上的性能。

## 功能特点

### 支持的修复策略

1. **随机修复 (random)**
   - 随机打乱退化类型的顺序
   - 依次应用相应的修复工具

2. **逆序修复 (reverse)**
   - 按照`reward_model`中退化类型的逆序
   - 依次应用相应的修复工具
   - 模拟"撤销"退化的过程

### 支持的退化类型和工具

| 退化类型 | 可用工具 |
|---------|---------|
| `motion blur` | RestormerMotionDeblurringToolbox, MPRNetMotionDeblurringToolbox |
| `defocus blur` | RestormerDefocusDeblurringToolbox, DeblurToolbox |
| `jpeg compression artifact` | SwinIRJpegArtifactRemovalToolbox, FBCNNJpegArtifactRemovalToolbox |
| `noise` | SwinIRDenoisingToolbox, MPRNetDenoisingToolbox |
| `rain` | RestormerDerrainingToolbox, MPRNetDeraininingToolbox |
| `low resolution` | SwinIRSrToolbox |
| `dark` | BrighteningToolbox |
| `haze` | DehazeFormerToolbox |

### 评估指标

脚本会计算以下指标：

1. **退化图 vs 原图**
   - PSNR (Peak Signal-to-Noise Ratio)
   - SSIM (Structural Similarity Index)
   - LPIPS (Learned Perceptual Image Patch Similarity)

2. **修复图 vs 原图**
   - PSNR
   - SSIM
   - LPIPS

3. **改善程度**
   - 修复后指标与退化指标的差值
   - 正值表示改善，负值表示恶化

## 使用方法

### 方式1: 使用Shell脚本（推荐）

```bash
# 基本使用
cd /app/xiaominl/DeepEyes_v2/tests/baseline
./run_baseline_test.sh

# 测试5个样本，只使用随机策略
./run_baseline_test.sh --num-samples 5 --strategy random

# 测试20个样本，使用两种策略，保存图像
./run_baseline_test.sh --num-samples 20 --strategy both --save-images

# 指定数据路径
./run_baseline_test.sh --data-path /path/to/your/data.parquet --num-samples 10

# 指定工具服务IP
./run_baseline_test.sh --tool-service-ip 10.21.9.35 --num-samples 10
```

### 方式2: 直接使用Python

```bash
cd /app/xiaominl/DeepEyes_v2

# 基本使用
python3 tests/baseline/test_baseline_restoration.py

# 自定义参数
python3 tests/baseline/test_baseline_restoration.py \
    --data-path /app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet \
    --num-samples 10 \
    --strategy both \
    --save-images

# 只测试随机策略
python3 tests/baseline/test_baseline_restoration.py \
    --strategy random \
    --num-samples 5

# 只测试逆序策略
python3 tests/baseline/test_baseline_restoration.py \
    --strategy reverse \
    --num-samples 5
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|-----|------|--------|
| `--data-path` | Parquet数据文件路径 | `/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet` |
| `--num-samples` | 测试样本数量 | 10 |
| `--strategy` | 修复策略: `random`, `reverse`, 或 `both` | `both` |
| `--output-dir` | 结果输出目录 | `/app/xiaominl/DeepEyes_v2/tests/baseline/results` |
| `--seed` | 随机种子 | 42 |
| `--save-images` | 保存图像（退化图、修复图、原图） | False |

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `TOOL_SERVICE_IP` | 工具服务的IP地址 | `10.21.9.34` |

## 输出结果

### 1. JSON结果文件

保存在 `results/results_<timestamp>.json`，包含每个样本的详细结果：

```json
[
  {
    "sample_idx": 0,
    "strategy": "random",
    "degraded_metrics": {
      "psnr": 25.34,
      "ssim": 0.78,
      "lpips": 0.23
    },
    "restored_metrics": {
      "psnr": 28.45,
      "ssim": 0.85,
      "lpips": 0.15
    },
    "improvements": {
      "psnr": 3.11,
      "ssim": 0.07,
      "lpips": 0.08
    },
    "restoration_log": [...],
    "degradation_types": ["motion blur", "noise"]
  }
]
```

### 2. 统计摘要文件

保存在 `results/summary_<timestamp>.txt`，包含所有样本的平均指标：

```
BASELINE RESTORATION TEST SUMMARY
================================================================================

Test Time: 20251015_123456
Data Path: /app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet
Samples Tested: 10
Strategies: random, reverse

RANDOM Strategy Results:
--------------------------------------------------------------------------------

Average Degraded Metrics:
  PSNR: 24.5678
  SSIM: 0.7543
  LPIPS: 0.2456

Average Restored Metrics:
  PSNR: 27.8901
  SSIM: 0.8234
  LPIPS: 0.1789

Average Improvements:
  PSNR: +3.3223
  SSIM: +0.0691
  LPIPS: +0.0667
```

### 3. 图像文件（可选）

如果使用 `--save-images` 参数，会在 `results/sample_<idx>_<strategy>/` 目录下保存：
- `degraded.png` - 退化图像
- `original.png` - 原始图像
- `restored.png` - 修复后图像

## 数据格式

脚本期望的Parquet数据格式：

```python
{
    'images': [PIL.Image or bytes],  # 退化图像
    'extra_info': {
        'original_image': PIL.Image or bytes,  # 原始图像（ground truth）
        'index': int,
        'split': str,
        ...
    },
    'reward_model': [
        {
            'degradation_type': str,  # 退化类型
            'degradation_level': str,  # 退化程度: 'low', 'medium', 'high'
            'has_original': bool
        },
        ...
    ]
}
```

## 工作原理

### 随机修复策略流程

1. 读取样本的`reward_model`，获取所有退化类型
2. 随机打乱退化类型的顺序
3. 对每个退化类型：
   - 随机选择一个对应的修复工具
   - 应用工具到当前图像
   - 记录修复日志
4. 计算最终修复图与原图的指标

### 逆序修复策略流程

1. 读取样本的`reward_model`，获取所有退化类型
2. 将退化类型**逆序**排列（模拟撤销退化）
3. 对每个退化类型：
   - 随机选择一个对应的修复工具
   - 应用工具到当前图像
   - 记录修复日志
4. 计算最终修复图与原图的指标

### 工具调用机制

每个工具都实现了以下接口：
- `reset()`: 重置工具状态
- `execute(action_string)`: 执行工具操作
  - 输入：包含工具名称和参数的JSON字符串
  - 输出：(observation, reward, done, info)

示例工具调用：
```python
tool = SwinIRDenoisingToolbox(_name="", _desc="", _params={})
tool.multi_modal_data = {'image': [image]}
action_string = '<tool_call>{"name":"swinir_denoising","arguments":{"noise_level":25}}</tool_call>'
obs, reward, done, info = tool.execute(action_string)
processed_image = tool.multi_modal_data['image'][0]
```

## 依赖要求

```bash
# Python包
pip install pandas numpy pillow scikit-image opencv-python lpips torch

# 工具服务
# 需要确保以下服务在运行：
# - SwinIR服务 (端口 5001)
# - Restormer服务 (端口 5002)
# - DRBNet服务 (端口 5003)
# - MPRNet服务 (端口 5004)
# - 其他工具服务...
```

## 故障排查

### 问题1: 工具服务连接失败

```
ConnectionError: Failed to connect to SwinIR API
```

**解决方案：**
- 检查 `TOOL_SERVICE_IP` 环境变量是否正确
- 确保相应的工具服务正在运行
- 检查网络连接和防火墙设置

### 问题2: LPIPS计算失败

```
[WARNING] LPIPS calculation failed
```

**解决方案：**
- 确保安装了 `lpips` 包：`pip install lpips`
- 如果没有GPU，LPIPS会使用CPU，速度较慢

### 问题3: 图像尺寸不匹配

脚本会自动调整图像尺寸到较小的尺寸进行比较，不需要手动处理。

### 问题4: 内存不足

**解决方案：**
- 减少 `--num-samples` 参数
- 不使用 `--save-images` 参数
- 在测试大量样本时分批运行

## 扩展和定制

### 添加新的修复工具

在 `DEGRADATION_TO_TOOLS` 字典中添加新工具：

```python
DEGRADATION_TO_TOOLS = {
    'your_degradation_type': [
        ('YourToolboxName', YourToolboxClass, {'param1': value1}),
    ],
}
```

### 添加新的修复策略

实现新的策略函数：

```python
def your_custom_strategy(image: Image.Image, reward_model: List[Dict]) -> Tuple[Image.Image, List[Dict]]:
    # 实现你的策略逻辑
    # ...
    return restored_image, restoration_log
```

然后在 `test_single_sample()` 函数中添加对应的分支。

### 自定义评估指标

在 `calculate_all_metrics()` 函数中添加新指标：

```python
def calculate_all_metrics(img1: Image.Image, img2: Image.Image) -> Dict[str, float]:
    return {
        'psnr': calculate_psnr(img1, img2),
        'ssim': calculate_ssim(img1, img2),
        'lpips': calculate_lpips(img1, img2),
        'your_metric': calculate_your_metric(img1, img2),  # 新增
    }
```

## 示例使用场景

### 场景1: 快速验证工具效果

```bash
./run_baseline_test.sh --num-samples 5 --strategy both
```

### 场景2: 完整评估并保存结果

```bash
./run_baseline_test.sh --num-samples 50 --strategy both --save-images
```

### 场景3: 比较随机和逆序策略

```bash
./run_baseline_test.sh --num-samples 20 --strategy both
# 查看results/summary_*.txt文件比较两种策略的平均改善
```

### 场景4: 测试特定数据集

```bash
./run_baseline_test.sh \
    --data-path /path/to/your/custom_dataset.parquet \
    --num-samples 10 \
    --strategy reverse
```

## 性能优化建议

1. **使用GPU加速**：确保LPIPS计算使用GPU
2. **批量处理**：增加样本数量可以更好地评估平均性能
3. **并行处理**：可以修改脚本使用多进程处理多个样本
4. **缓存工具模型**：工具类会自动缓存模型，避免重复加载

## 许可证

Copyright 2024 Bytedance Ltd. and/or its affiliates

## 联系方式

如有问题或建议，请联系项目维护者。


