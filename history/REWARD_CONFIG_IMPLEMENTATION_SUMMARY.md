# 图像质量奖励参数化配置 - 实现总结

## 🎯 实现目标

✅ **在训练脚本中通过环境变量控制图像质量奖励的计算方式**
- 无需修改代码
- 灵活切换有参考/无参考模式
- 可配置离散化等级

---

## 📝 修改的文件

### 1. 核心奖励函数 (verl/utils/reward_score/__init__.py)

**修改内容**：
```python
# 添加 os 导入
import os

# 修改 image_restoration_v2 分支
elif data_source in ["image_restoration_v2"]:
    from . import image_restoration
    
    # 从环境变量读取配置
    use_no_reference = os.environ.get('IMAGE_QUALITY_USE_NO_REFERENCE', 'True').lower() == 'true'
    discretize_levels = int(os.environ.get('IMAGE_QUALITY_DISCRETIZE_LEVELS', '0'))
    
    print(f"[INFO] Image Quality Reward Config: use_no_reference={use_no_reference}, discretize_levels={discretize_levels}")
    
    res = image_restoration.compute_score_v2(
        solution_str, 
        ground_truth, 
        extra_info,
        discretize_levels=discretize_levels,
        use_no_reference=use_no_reference,
    )
```

**关键变化**：
- ✅ 添加环境变量读取逻辑
- ✅ 支持 `IMAGE_QUALITY_USE_NO_REFERENCE` (默认: True)
- ✅ 支持 `IMAGE_QUALITY_DISCRETIZE_LEVELS` (默认: 0)
- ✅ 添加配置日志输出

---

### 2. 训练脚本 (examples/agent/IR.sh)

**修改内容**：
在脚本开头添加配置区域：

```bash
# ========== Image Quality Reward Configuration ==========
# 控制图像质量奖励的计算方式
export IMAGE_QUALITY_USE_NO_REFERENCE=True  # True=无参考指标, False=有参考指标
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0    # 离散化等级: 0=连续, 10=每10%, 20=每5%

# 推荐配置：
# - 训练阶段: use_no_reference=True, discretize_levels=0
# - 早期训练: use_no_reference=True, discretize_levels=10
# - 如果有GT: use_no_reference=False
# ========================================================
```

**位置**：在 `export WANDB_API_KEY` 之后

---

### 3. 测试脚本 (test_reward_config.py) - 新增

**功能**：
- ✅ 验证环境变量配置是否正确读取
- ✅ 显示当前配置和解释
- ✅ 测试奖励函数调用
- ✅ 提供使用建议

**使用方法**：
```bash
# 测试默认配置
python test_reward_config.py

# 测试自定义配置
IMAGE_QUALITY_USE_NO_REFERENCE=False \
IMAGE_QUALITY_DISCRETIZE_LEVELS=10 \
python test_reward_config.py
```

---

### 4. 配置文档 (docs/IMAGE_QUALITY_REWARD_CONFIG.md) - 新增

**内容**：
- 📖 参数详细说明
- 🎯 使用场景和推荐配置
- 📊 两种模式对比表
- 🔍 调试和验证方法
- ❓ 常见问题解答

---

### 5. 快速参考 (REWARD_CONFIG_QUICK_START.md) - 新增

**内容**：
- ⚡ 一分钟配置指南
- 🎨 常用配置表格
- 📝 快速测试命令

---

## 🎛️ 配置参数详解

### IMAGE_QUALITY_USE_NO_REFERENCE

**类型**: 布尔值 (True/False)  
**默认值**: `True`

| 值 | 模式 | 指标 | 公式 |
|---|------|------|------|
| `True` | 无参考 | NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA | 均等权重 (0.2×5) |
| `False` | 有参考 | SSIM, LPIPS, PSNR | 0.35×SSIM + 0.50×LPIPS + 0.15×PSNR |

**选择依据**：
- ✅ `True`: 数据集无GT，适用所有样本
- ✅ `False`: 数据集有GT，评估更准确

---

### IMAGE_QUALITY_DISCRETIZE_LEVELS

**类型**: 整数 (≥0)  
**默认值**: `0`

| 值 | 效果 | 奖励值 |
|---|------|--------|
| `0` | 连续奖励 | [0.0, 1.0] 任意浮点数 |
| `10` | 每10%一档 | {0.0, 0.1, 0.2, ..., 1.0} |
| `20` | 每5%一档 | {0.0, 0.05, 0.10, ..., 1.0} |

**选择依据**：
- ✅ `0`: 精细区分，训练稳定时使用
- ✅ `10`: 平滑信号，训练初期使用
- ✅ `20`: 更细档位，微调阶段使用

---

## 📊 使用场景

### 场景1: 标准训练（最常用）⭐

```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
```

**适用于**：
- 大部分训练场景
- 数据集没有ground truth
- 希望所有样本都参与训练

**优势**：
- 无需GT，适用性最强
- Batch长度一致
- 训练稳定

---

### 场景2: 训练早期（稳定优先）

```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=True
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10
```

**适用于**：
- 训练初期策略不稳定
- 奖励信号波动大
- 需要快速收敛

**优势**：
- 离散化减少波动
- 策略更新更平滑
- 后期可切换回连续

---

### 场景3: 有GT数据集

```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False
export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
```

**适用于**：
- 数据集包含original_image
- 需要准确质量评估
- 样本都会执行工具

**注意**：
- ⚠️ 必须有original_image字段
- ⚠️ 未执行工具的样本返回0.0

---

### 场景4: 精细调优

```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False
export IMAGE_QUALITY_DISCRETIZE_LEVELS=20
```

**适用于**：
- 训练后期微调
- 高质量GT数据
- 对比不同策略

**优势**：
- 有参考指标最准确
- 20档位精细区分
- 适合策略评估

---

## ✅ 测试验证

### 验证步骤

1. **修改配置**：编辑 `IR.sh` 中的环境变量

2. **运行测试**：
```bash
python test_reward_config.py
```

3. **查看输出**：
```
[INFO] Image Quality Reward Config: use_no_reference=True, discretize_levels=0
```

4. **训练验证**：启动训练，检查日志中是否出现配置信息

---

## 🔍 调试技巧

### 查看配置是否生效

```bash
# 方法1: 运行测试脚本
python test_reward_config.py

# 方法2: 训练日志搜索
bash examples/agent/IR.sh 2>&1 | grep "Image Quality Reward Config"

# 方法3: Python交互式测试
python -c "from verl.utils.reward_score import _default_compute_score; \
           _default_compute_score('image_restoration_v2', '', {}, {})"
```

### 常见问题排查

**问题1**: 配置未生效
```bash
# 检查环境变量是否设置
echo $IMAGE_QUALITY_USE_NO_REFERENCE
echo $IMAGE_QUALITY_DISCRETIZE_LEVELS

# 确保在脚本中export了
grep "IMAGE_QUALITY" examples/agent/IR.sh
```

**问题2**: 有参考模式报错
```bash
# 检查数据集是否有original_image
python -c "import pandas as pd; \
           df = pd.read_parquet('path/to/data.parquet'); \
           print('original_image' in df.columns)"
```

---

## 📚 相关文件

- **核心修改**: `verl/utils/reward_score/__init__.py`
- **训练配置**: `examples/agent/IR.sh`
- **测试脚本**: `test_reward_config.py`
- **详细文档**: `docs/IMAGE_QUALITY_REWARD_CONFIG.md`
- **快速参考**: `REWARD_CONFIG_QUICK_START.md`

---

## 🎉 功能总结

### 实现的功能

✅ **环境变量配置** - 通过两个环境变量控制奖励计算  
✅ **无需修改代码** - 训练脚本直接配置  
✅ **实时日志** - 显示当前使用的配置  
✅ **完整测试** - 提供测试脚本验证  
✅ **详细文档** - 使用指南和场景推荐  

### 向前兼容

- ✅ 未设置环境变量时使用默认值 (True, 0)
- ✅ 不影响其他data_source的奖励计算
- ✅ Wandb展示不受影响（仍会按需计算有参考指标）

---

## 💡 使用建议

### 推荐工作流

1. **训练初期** (Epoch 0-10)
   ```bash
   export IMAGE_QUALITY_USE_NO_REFERENCE=True
   export IMAGE_QUALITY_DISCRETIZE_LEVELS=10
   ```

2. **训练中期** (Epoch 10-25)
   ```bash
   export IMAGE_QUALITY_USE_NO_REFERENCE=True
   export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
   ```

3. **微调阶段** (可选，如果有GT)
   ```bash
   export IMAGE_QUALITY_USE_NO_REFERENCE=False
   export IMAGE_QUALITY_DISCRETIZE_LEVELS=0
   ```

### 监控指标

在Wandb中关注：
- `reward/quality_score_mean` - 质量分数趋势
- `reward/quality_score_std` - 稳定性指标
- `val/ssim_mean`, `val/lpips_mean` - 验证集质量

---

## 🚀 快速开始

```bash
# 1. 编辑训练脚本（已完成）
vim examples/agent/IR.sh

# 2. 测试配置
python test_reward_config.py

# 3. 启动训练
bash examples/agent/IR.sh

# 4. 监控日志
tail -f logs/debug_for_TIR_IR_bs8_air_mi300.log | grep "Image Quality"
```

---

**实现完成时间**: 2025-10-11  
**版本**: v1.0  
**状态**: ✅ 测试通过，可以使用

祝训练顺利！🎊

