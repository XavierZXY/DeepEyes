# WandB退化类型奖励指标说明

## 🎯 新增指标概述

当启用退化类型奖励（`ENABLE_DEGRADATION_TYPE_REWARD=True`）时，WandB会自动记录以下统计指标：

---

## 📊 完整指标列表

### 训练指标

| 指标名 | 范围 | 说明 |
|-------|------|------|
| `reward/degradation_type_score_mean` | 0.0-1.0 | 有效样本的平均退化类型匹配分数 |
| `reward/degradation_type_score_max` | 0.0-1.0 | 最高分数 |
| `reward/degradation_type_score_min` | 0.0-1.0 | 最低分数（有效样本中） |
| `reward/degradation_type_score_std` | ≥0 | 标准差（反映稳定性） |
| `reward/degradation_type_valid_samples` | 整数 | 有效样本数量 |
| `reward/degradation_type_valid_ratio` | 0.0-1.0 | 有效样本比例 |
| `reward/degradation_type_score_mean_all` | 0.0-1.0 | 所有样本平均（包括0分） |

### 验证指标

所有指标加 `val/` 前缀，如：
- `val/reward/degradation_type_score_mean`
- `val/reward/degradation_type_score_max`
- 等等...

---

## 🔍 指标详解

### 1. degradation_type_score_mean（核心指标）

**含义**: 有效样本的平均退化类型识别准确率

**计算**:
```python
# 只统计分数 > 0.0 的样本
non_zero_scores = [s for s in scores if s > 0.0]
mean = np.mean(non_zero_scores)
```

**范围**: 0.0 ~ 1.0

**期望**: 
- 0.5 ~ 0.7: 早期训练，部分识别
- 0.7 ~ 0.9: 中期训练，良好识别
- 0.9 ~ 1.0: 后期训练，优秀识别

**监控**: 应该随训练逐渐提升

---

### 2. degradation_type_score_max

**含义**: 最好的退化类型识别分数

**用途**: 观察模型的最佳表现

**期望**: 接近1.0

---

### 3. degradation_type_score_min

**含义**: 最差的退化类型识别分数（在有效样本中）

**用途**: 观察模型的最差表现

**注意**: 
- 只统计有效样本（score > 0）
- 0分样本（clean或未启用）不参与

**期望**: 
- 早期: 可能很低（0.3-0.5）
- 后期: 应该提升（> 0.5）

---

### 4. degradation_type_score_std

**含义**: 退化类型分数的标准差

**用途**: 评估模型稳定性

**范围**: 0.0 ~ 0.5

**期望**:
- 高（> 0.3): 不稳定，某些样本好某些差
- 中（0.1-0.3): 正常波动
- 低（< 0.1): 非常稳定

---

### 5. degradation_type_valid_samples

**含义**: 计入统计的有效样本数量

**计算**: 分数 > 0.0 的样本数

**用途**: 
- 验证有多少样本真正计算了退化类型奖励
- 排查是否有过多的clean样本或未启用的样本

**预期**:
- 如果启用了退化类型奖励
- 且batch中非clean样本占比80%
- 则 valid_samples 应该约为 batch_size × 0.8

---

### 6. degradation_type_valid_ratio

**含义**: 有效样本占总样本的比例

**计算**: valid_samples / total_samples

**范围**: 0.0 ~ 1.0

**用途**: 快速判断有效样本比例

**预期**:
- 启用退化类型奖励: > 0.7（大部分是非clean样本）
- 未启用或全clean: 0.0

---

### 7. degradation_type_score_mean_all

**含义**: 所有样本的平均分（包括0分）

**计算**: 直接对所有分数求平均

**对比**:
- `mean`: 只统计有效样本（> 0）
- `mean_all`: 统计所有样本（包括0）

**用途**: 
- 如果 `mean_all` 远低于 `mean`，说明有很多0分样本
- 可以用来判断clean样本比例

---

## 📈 示例数据

### 场景：启用退化类型奖励，batch_size=8

```python
degradation_type_scores = [
    0.0,    # Clean样本
    1.0,    # 完全匹配 (3/3)
    0.667,  # 部分匹配 (2/3)
    0.0,    # Clean样本
    1.0,    # 完全匹配 (2/2)
    0.5,    # 部分匹配 (1/2)
    0.0,    # Clean样本
    1.0,    # 完全匹配 (3/3)
]
```

### 统计结果

```python
# 有效分数（过滤0分）
non_zero = [1.0, 0.667, 1.0, 0.5, 1.0]

# WandB指标
reward/degradation_type_score_mean = 0.833       # 有效样本平均
reward/degradation_type_score_max = 1.0          # 最高分
reward/degradation_type_score_min = 0.5          # 最低分（有效样本中）
reward/degradation_type_score_std = 0.211        # 标准差
reward/degradation_type_valid_samples = 5        # 有效样本数
reward/degradation_type_valid_ratio = 0.625      # 5/8
reward/degradation_type_score_mean_all = 0.521   # 所有样本平均
```

---

## 🎨 在WandB中查看

### 方法1: 搜索框

在WandB页面搜索：
```
degradation_type
```

会显示所有相关指标。

---

### 方法2: 添加到图表

1. 点击 `+ Add panel`
2. 选择 `Line plot`
3. Y轴选择:
   - `reward/degradation_type_score_mean`
   - `reward/degradation_type_score_max`
   - `reward/degradation_type_score_min`
4. X轴: Step

---

### 方法3: 创建对比图

**图表1: 退化类型识别趋势**
```python
X轴: Step
Y轴:
  - reward/degradation_type_score_mean  (平均)
  - reward/degradation_type_score_max   (最好)
  - reward/degradation_type_score_min   (最差)
```

**图表2: 有效样本监控**
```python
X轴: Step  
Y轴:
  - reward/degradation_type_valid_ratio  (有效样本比例)
  - reward/degradation_type_valid_samples (有效样本数)
```

**图表3: 平均分对比**
```python
X轴: Step
Y轴:
  - reward/degradation_type_score_mean      (有效样本)
  - reward/degradation_type_score_mean_all  (所有样本)
```

如果两条线差距很大，说明有很多0分样本（clean或未启用）。

---

## 📊 完整的奖励指标体系

### 现在WandB记录的所有奖励指标

```
# 总奖励
critic/rewards/mean
critic/rewards/max
critic/rewards/min

# 格式奖励
reward/format_correct_ratio        # 正确率
reward/format_violation_ratio      # 违规率
reward/format_score_mean           # 平均分

# 图像质量奖励
reward/quality_score_mean          # 平均分
reward/quality_score_max           # 最高分
reward/quality_score_min           # 最低分
reward/quality_score_std           # 标准差

# 退化类型奖励（⭐ 新增）
reward/degradation_type_score_mean       # 平均分（有效样本）
reward/degradation_type_score_max        # 最高分
reward/degradation_type_score_min        # 最低分
reward/degradation_type_score_std        # 标准差
reward/degradation_type_valid_samples    # 有效样本数
reward/degradation_type_valid_ratio      # 有效样本比例
reward/degradation_type_score_mean_all   # 平均分（所有样本）
```

---

## 🔍 故障排查

### 问题1: 指标未显示

**检查**:
```bash
grep "degradation_type_score" logs/*.log
```

应该看到：
```
[DEBUG degradation_type_match] 完全匹配，奖励=1.0
[DEBUG degradation_type_reward] enabled, degradation_type_score=1.0
```

**如果没有**:
- 检查是否启用: `ENABLE_DEGRADATION_TYPE_REWARD=True`
- 检查日志: `[INFO] Degradation Type Reward Config: enable=True`

---

### 问题2: valid_samples = 0

**原因**: 所有样本都是0分

**可能情况**:
1. 所有样本都是clean样本
2. 退化类型奖励未启用
3. 格式全部错误（格式错误不给退化类型奖励）

**检查**:
```bash
grep "is_clean_sample" logs/*.log
grep "format error" logs/*.log
```

---

### 问题3: mean 和 mean_all 差距很大

**原因**: 有很多0分样本

**正常情况**: 
- 如果batch中有30% clean样本
- `mean_all` 会比 `mean` 低30%左右

**异常情况**:
- 如果 `mean_all` 接近0但 `mean` 很高
- 说明大部分样本都是0分（可能配置有问题）

---

## 💡 使用建议

### 监控指标组合

#### 组合1: 基本监控
```
reward/degradation_type_score_mean  # 平均识别准确率
reward/degradation_type_valid_ratio # 有效样本比例
```

#### 组合2: 详细分析
```
reward/degradation_type_score_mean  # 平均
reward/degradation_type_score_max   # 最好
reward/degradation_type_score_min   # 最差
reward/degradation_type_score_std   # 稳定性
```

#### 组合3: 对比分析
```
reward/degradation_type_score_mean     # 有效样本平均
reward/degradation_type_score_mean_all # 所有样本平均
→ 差距 = clean样本或格式错误的影响
```

---

## 🎯 典型训练曲线

### 早期训练 (Epoch 1-5)
```
degradation_type_score_mean: 0.4 → 0.6
degradation_type_score_std: 0.3 → 0.25
valid_ratio: 0.7 (稳定)
```
**解读**: 识别能力快速提升，开始学习退化类型

---

### 中期训练 (Epoch 5-15)
```
degradation_type_score_mean: 0.6 → 0.85
degradation_type_score_std: 0.25 → 0.15
valid_ratio: 0.7 (稳定)
```
**解读**: 稳步提升，波动减小，识别越来越准确

---

### 后期训练 (Epoch 15-32)
```
degradation_type_score_mean: 0.85 → 0.95
degradation_type_score_std: 0.15 → 0.08
valid_ratio: 0.7 (稳定)
```
**解读**: 接近收敛，大部分样本能完全识别

---

## 📈 与其他指标的关联

### 退化类型 vs 图像质量

**理想情况**:
```python
degradation_type_score ↑  →  quality_score ↑
```

如果模型能正确识别退化类型，应该能更好地恢复图像。

**创建对比图**:
```
X轴: Step
Y轴:
  - reward/degradation_type_score_mean (退化识别)
  - reward/quality_score_mean (图像质量)
```

---

### 退化类型 vs 格式

**预期**:
```python
format_correct_ratio ↑  →  degradation_type_valid_ratio ↑
```

格式正确的样本才会计算退化类型奖励。

---

### 退化类型 vs 总奖励

**预期**:
```python
degradation_type_score ↑  →  critic/rewards/mean ↑
```

退化类型分数提升会直接增加总奖励（因为权重为1.0）。

---

## 🧪 验证示例

### 测试数据
```python
degradation_type_scores = [
    0.0,    # Clean样本
    1.0,    # 完全匹配
    0.667,  # 2/3匹配
    0.0,    # Clean样本
    1.0,    # 完全匹配
    0.5,    # 1/2匹配
    0.0,    # Clean样本
    1.0,    # 完全匹配
]
```

### 统计结果
```python
有效分数: [1.0, 0.667, 1.0, 0.5, 1.0]  # 过滤掉0.0

reward/degradation_type_score_mean = 0.833       # 平均: (1.0+0.667+1.0+0.5+1.0)/5
reward/degradation_type_score_max = 1.0          # 最大值
reward/degradation_type_score_min = 0.5          # 最小值（有效样本中）
reward/degradation_type_score_std = 0.211        # 标准差
reward/degradation_type_valid_samples = 5        # 有效样本数
reward/degradation_type_valid_ratio = 0.625      # 5/8
reward/degradation_type_score_mean_all = 0.521   # 所有样本: 4.167/8
```

---

## ⚙️ 配置影响

### 未启用退化类型奖励
```bash
export ENABLE_DEGRADATION_TYPE_REWARD=False
```

**WandB指标**: 
- 所有 `degradation_type_*` 指标为空或不显示
- 因为所有分数都是0.0，过滤后没有有效样本

---

### 启用退化类型奖励
```bash
export ENABLE_DEGRADATION_TYPE_REWARD=True
export DEGRADATION_TYPE_REWARD_WEIGHT=1.0
```

**WandB指标**:
- 所有7个指标都会显示
- `valid_ratio` 应该接近 (1 - clean_sample_ratio)

---

## 🎨 推荐的WandB Panel配置

### Panel 1: 退化类型识别趋势
```yaml
Panel Type: Line Chart
Title: Degradation Type Recognition
X轴: Step
Y轴:
  - reward/degradation_type_score_mean (主线)
  - reward/degradation_type_score_max (上界)
  - reward/degradation_type_score_min (下界)
  - reward/degradation_type_score_std (右Y轴，标准差)
```

---

### Panel 2: 有效样本监控
```yaml
Panel Type: Line Chart
Title: Valid Samples Ratio
X轴: Step
Y轴:
  - reward/degradation_type_valid_ratio
  - reward/format_correct_ratio (对比)
```

---

### Panel 3: 奖励分解
```yaml
Panel Type: Line Chart
Title: Reward Components
X轴: Step
Y轴:
  - critic/rewards/mean (总奖励)
  - reward/format_score_mean × 0.3 (格式贡献)
  - reward/quality_score_mean × 0.7 (质量贡献)
  - reward/degradation_type_score_mean × 1.0 (退化类型贡献)
```

---

### Panel 4: 平均分对比
```yaml
Panel Type: Line Chart
Title: Mean vs Mean_All
X轴: Step
Y轴:
  - reward/degradation_type_score_mean (有效样本)
  - reward/degradation_type_score_mean_all (所有样本)
Gap = Clean样本或格式错误的影响
```

---

## ✅ 验证清单

训练开始后，检查：

- [ ] 控制台显示启用退化类型奖励的日志
- [ ] WandB中有 `reward/degradation_type_score_mean` 指标
- [ ] `valid_ratio` 不为0（说明有有效样本）
- [ ] `mean` 随训练逐渐提升
- [ ] `std` 逐渐降低（变得更稳定）
- [ ] `mean_all` < `mean`（正常，因为有0分样本）

---

## 🔧 代码位置

### 统计逻辑
**文件**: `verl/trainer/ppo/metric_utils.py`

**函数**: `compute_reward_component_metrics()`

**代码**:
```python
# 退化类型奖励统计
if 'ir_degradation_type_score' in reward_extra_infos_dict:
    degradation_type_scores = reward_extra_infos_dict['ir_degradation_type_score']
    if len(degradation_type_scores) > 0:
        # 过滤0分
        non_zero_scores = [s for s in degradation_type_scores if s > 0.0]
        
        if len(non_zero_scores) > 0:
            metrics['reward/degradation_type_score_mean'] = np.mean(non_zero_scores)
            metrics['reward/degradation_type_score_max'] = np.max(non_zero_scores)
            metrics['reward/degradation_type_score_min'] = np.min(non_zero_scores)
            metrics['reward/degradation_type_score_std'] = np.std(non_zero_scores)
            metrics['reward/degradation_type_valid_samples'] = len(non_zero_scores)
            metrics['reward/degradation_type_valid_ratio'] = len(non_zero_scores) / len(degradation_type_scores)
        
        metrics['reward/degradation_type_score_mean_all'] = np.mean(degradation_type_scores)
```

---

### 数据收集
**文件**: `verl/workers/reward_manager/naive.py`

**收集点**:
```python
# 从score字典中提取
degradation_type_score = score.get("degradation_type_score", 0.0)
reward_extra_info['ir_degradation_type_score'].append(degradation_type_score)
```

---

## 📚 相关文档

- `REWARD_STRUCTURE_EXPLAINED.md` - 奖励结构说明
- `COMPLETE_REWARD_CONFIG_GUIDE.md` - 配置指南
- `DEGRADATION_TYPE_UNORDERED_VERIFICATION.md` - 无序验证
- `docs/WANDB_REWARD_METRICS.md` - 其他奖励指标

---

**新增指标完成** 🎉

现在退化类型奖励的统计指标（mean/min/max/std等）都会自动上传到WandB，方便监控和分析！

