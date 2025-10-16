# Baseline Restoration Test - 项目总结

## 项目概述

本项目实现了一个完整的baseline测试框架，用于评估不同修复策略在退化图像修复任务上的性能。

**核心功能：**
1. ✅ 支持随机修复和逆序修复两种策略
2. ✅ 自动识别退化类型并应用相应的修复工具
3. ✅ 计算多种图像质量指标（PSNR、SSIM、LPIPS）
4. ✅ 生成详细的测试报告和统计摘要
5. ✅ 支持批量测试和结果可视化

## 文件结构

```
/app/xiaominl/DeepEyes_v2/tests/baseline/
├── test_baseline_restoration.py    # 主测试脚本 (636行)
├── run_baseline_test.sh            # 运行脚本
├── quick_test.sh                   # 快速测试脚本
├── verify_dataset.py               # 数据集验证脚本
├── README.md                       # 完整文档
├── USAGE_EXAMPLES.md               # 使用示例
├── PROJECT_SUMMARY.md              # 本文件
├── .gitignore                      # Git忽略配置
└── results/                        # 测试结果目录（自动创建）
    ├── results_<timestamp>.json    # 详细结果
    ├── summary_<timestamp>.txt     # 统计摘要
    └── sample_<idx>_<strategy>/    # 样本图像（可选）
        ├── degraded.png
        ├── original.png
        └── restored.png
```

## 核心组件

### 1. test_baseline_restoration.py

**主要功能：**
- 退化类型到工具的映射（`DEGRADATION_TO_TOOLS`）
- 图像质量指标计算（PSNR、SSIM、LPIPS）
- 两种修复策略实现：
  - `random_restoration()` - 随机顺序修复
  - `reverse_restoration()` - 逆序修复
- 完整的测试流程和结果记录

**支持的退化类型：**
- motion blur → RestormerMotionDeblurringToolbox, MPRNetMotionDeblurringToolbox
- defocus blur → RestormerDefocusDeblurringToolbox, DeblurToolbox
- jpeg compression artifact → SwinIRJpegArtifactRemovalToolbox, FBCNNJpegArtifactRemovalToolbox
- noise → SwinIRDenoisingToolbox, MPRNetDenoisingToolbox
- rain → RestormerDerrainingToolbox, MPRNetDeraininingToolbox
- low resolution → SwinIRSrToolbox
- dark → BrighteningToolbox
- haze → DehazeFormerToolbox

### 2. 运行脚本

**run_baseline_test.sh：**
- 设置环境变量
- 解析命令行参数
- 调用主测试脚本
- 提供友好的命令行界面

**quick_test.sh：**
- 快速验证环境配置
- 只测试2个样本
- 适合初次使用和调试

### 3. 数据集验证

**verify_dataset.py：**
- 检查数据集格式
- 验证必需字段
- 显示样本信息
- 检查工具支持情况

## 快速使用指南

### Step 1: 验证数据集

```bash
cd /app/xiaominl/DeepEyes_v2/tests/baseline
python3 verify_dataset.py
```

### Step 2: 快速测试

```bash
./quick_test.sh
```

### Step 3: 完整测试

```bash
# 测试10个样本，使用两种策略
./run_baseline_test.sh --num-samples 10 --strategy both

# 测试20个样本并保存图像
./run_baseline_test.sh --num-samples 20 --strategy both --save-images
```

### Step 4: 查看结果

```bash
# 查看最新的摘要
ls -lt results/summary_*.txt | head -1 | xargs cat

# 查看详细JSON结果
ls -lt results/results_*.json | head -1
```

## 关键设计决策

### 1. 工具选择策略

每种退化类型可能对应多个修复工具，当前实现采用**随机选择**策略：

```python
tools = DEGRADATION_TO_TOOLS[degradation_type]
tool_name, tool_class, default_args = random.choice(tools)
```

**优点：**
- 评估工具的多样性和鲁棒性
- 避免过拟合特定工具

**未来改进：**
- 根据退化程度选择工具
- 使用强化学习选择最佳工具序列

### 2. 修复策略

**随机修复：**
```python
degradations = list(reward_model)
random.shuffle(degradations)
# 按随机顺序应用工具
```

**逆序修复：**
```python
degradations = list(reward_model)
degradations.reverse()
# 按逆序应用工具（模拟撤销退化）
```

**理论基础：**
- 逆序修复理论上应该效果更好（撤销退化的逆过程）
- 实际效果需要实验验证
- 退化之间的交互作用会影响修复顺序的重要性

### 3. 指标计算

**PSNR (峰值信噪比)：**
- 衡量像素级别的差异
- 对噪声敏感
- 计算简单快速

**SSIM (结构相似性)：**
- 衡量结构信息的相似性
- 更符合人类视觉感知
- 对结构变化敏感

**LPIPS (感知相似性)：**
- 基于深度学习的感知指标
- 最接近人类主观评价
- 计算开销较大

## 数据流程

```
数据集 (Parquet)
    ├── images (退化图)
    ├── extra_info
    │   └── original_image (原图)
    └── reward_model (退化信息)
         ├── degradation_type
         └── degradation_level

↓ 加载

退化图像 → 修复策略 → 修复后图像
                ↓
            工具序列
                ↓
         Tool 1 → Tool 2 → ... → Tool N
                ↓
            修复日志

↓ 评估

指标计算:
    - 退化图 vs 原图
    - 修复图 vs 原图
    - 改善程度

↓ 输出

结果文件:
    - results_<timestamp>.json  (详细数据)
    - summary_<timestamp>.txt   (统计摘要)
    - sample_<idx>_<strategy>/  (可视化图像)
```

## 实验结果分析

### 预期结果

**成功的修复应该表现为：**
1. PSNR 提升 2-5 dB
2. SSIM 提升 0.05-0.15
3. LPIPS 降低 0.05-0.15

**策略比较：**
- 逆序修复理论上应该优于随机修复
- 但实际效果取决于：
  - 退化类型的组合
  - 工具的性能
  - 退化程度

### 结果解读示例

```
RANDOM Strategy Results:
Average Improvements:
  PSNR: +3.32
  SSIM: +0.09
  LPIPS: +0.08

REVERSE Strategy Results:
Average Improvements:
  PSNR: +3.67
  SSIM: +0.11
  LPIPS: +0.11
```

**解读：**
- 逆序策略在所有指标上都优于随机策略
- PSNR提升约3.5 dB，表示有明显改善
- SSIM提升0.11，结构信息得到较好恢复
- LPIPS改善0.11，感知质量显著提升

## 扩展方向

### 1. 更多修复策略

```python
def adaptive_restoration(image, reward_model):
    """根据退化程度自适应选择工具"""
    pass

def learned_restoration(image, reward_model):
    """使用RL学习最优修复序列"""
    pass
```

### 2. 更多评估指标

```python
def calculate_all_metrics(img1, img2):
    return {
        'psnr': calculate_psnr(img1, img2),
        'ssim': calculate_ssim(img1, img2),
        'lpips': calculate_lpips(img1, img2),
        'fid': calculate_fid(img1, img2),      # 新增
        'niqe': calculate_niqe(img1),          # 新增：无参考指标
        'brisque': calculate_brisque(img1),    # 新增：无参考指标
    }
```

### 3. 并行化处理

```python
from multiprocessing import Pool

with Pool(processes=8) as pool:
    results = pool.map(process_sample, samples)
```

### 4. 可视化增强

```python
def create_comparison_plot(degraded, restored, original):
    """创建对比图表"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].imshow(degraded)
    axes[0].set_title('Degraded')
    axes[1].imshow(restored)
    axes[1].set_title('Restored')
    axes[2].imshow(original)
    axes[2].set_title('Original')
    return fig
```

## 依赖关系

**Python包：**
```
pandas>=1.3.0
numpy>=1.20.0
pillow>=8.0.0
scikit-image>=0.18.0
opencv-python>=4.5.0
lpips>=0.1.4
torch>=1.10.0
```

**外部服务：**
```
- SwinIR服务：http://<TOOL_SERVICE_IP>:5001
- Restormer服务：http://<TOOL_SERVICE_IP>:5002
- DRBNet服务：http://<TOOL_SERVICE_IP>:5003
- MPRNet服务：http://<TOOL_SERVICE_IP>:5004
- DehazeFormer服务：http://<TOOL_SERVICE_IP>:5005
- FBCNN服务：http://<TOOL_SERVICE_IP>:5006
```

## 性能考虑

**时间复杂度：**
- 单个样本处理时间：~10-30秒（取决于退化数量和工具）
- 10个样本：~2-5分钟
- 100个样本：~20-50分钟

**空间复杂度：**
- JSON结果文件：~1-5 MB/100样本
- 图像文件：~500KB/样本（如果保存）

**优化建议：**
1. 批量处理减少开销
2. 使用GPU加速LPIPS计算
3. 并行处理多个样本
4. 缓存工具模型

## 测试覆盖

✅ 已测试：
- [x] 数据集加载和验证
- [x] 图像格式转换
- [x] 工具调用接口
- [x] 指标计算
- [x] 两种修复策略
- [x] 结果保存和统计

⚠️ 待测试：
- [ ] 大规模数据集（1000+样本）
- [ ] 边界情况（极端退化）
- [ ] 工具失败恢复
- [ ] 内存泄漏检测

## 常见问题

### Q: 为什么有些样本修复后效果变差？

**可能原因：**
1. 工具参数不适合当前退化程度
2. 多重退化的负面交互
3. 修复顺序不当
4. 工具模型的局限性

**解决方案：**
- 调整工具参数
- 尝试不同的修复顺序
- 使用更适合的工具

### Q: 如何添加新的退化类型？

1. 在 `DEGRADATION_TO_TOOLS` 中添加映射
2. 确保工具实现了标准接口
3. 运行 `verify_dataset.py` 验证

### Q: 如何调整工具参数？

编辑 `test_baseline_restoration.py` 中的默认参数：

```python
DEGRADATION_TO_TOOLS = {
    'noise': [
        ('SwinIRDenoisingToolbox', SwinIRDenoisingToolbox, {'noise_level': 30}),
    ],
}
```

## 项目贡献者

本项目由AI助手创建，基于verl框架的图像修复工具体系。

## 版本历史

- v1.0 (2024-10-15): 初始版本
  - 实现随机和逆序两种修复策略
  - 支持8种退化类型
  - 集成多个修复工具
  - 完整的评估指标和报告生成

## 许可证

Copyright 2024 Bytedance Ltd. and/or its affiliates

Licensed under the Apache License, Version 2.0

## 相关文档

- `README.md` - 完整使用文档
- `USAGE_EXAMPLES.md` - 详细使用示例
- `/app/xiaominl/DeepEyes_v2/verl/workers/agent/envs/mm_process_engine/` - 工具实现

## 联系方式

如有问题或建议，请通过项目Issue系统反馈。

