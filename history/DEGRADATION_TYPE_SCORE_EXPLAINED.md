# Degradation Type Score 指标详解

## 🎯 核心问题

**为什么 `reward/degradation_type_score_mean` 一直是 1.0？**

这是**正常现象**，不是bug！

---

## 📊 两个指标的关键区别

### `reward/degradation_type_score_mean` (过滤版本)

```python
# verl/trainer/ppo/metric_utils.py 第273-278行
degradation_type_scores = reward_extra_infos_dict['ir_degradation_type_score']
non_zero_scores = [s for s in degradation_type_scores if s > 0.0]  # ← 过滤！

if len(non_zero_scores) > 0:
    metrics['reward/degradation_type_score_mean'] = np.mean(non_zero_scores)
```

**特点**:
- ✅ 只统计分数 **> 0.0** 的样本
- ❌ 排除了所有 0.0 分样本（clean样本、部分匹配、格式错误等）
- 📊 **反映**: 在成功识别的样本中，准确度如何

---

### `reward/degradation_type_score_mean_all` (完整版本)

```python
# verl/trainer/ppo/metric_utils.py 第286行
metrics['reward/degradation_type_score_mean_all'] = np.mean(degradation_type_scores)
```

**特点**:
- ✅ 统计**所有样本**，包括 0.0 分
- 📊 **反映**: 整个 batch 的真实平均分数

---

## 🔍 为什么会一直是 1.0？

### 原因1: 评分规则严格

```python
# verl/utils/reward_score/image_restoration.py 第1166-1177行
def check_degradation_type_match_v2(predicted_log, reward_model_order):
    predicted_set = set(predicted_log)
    expected_set = set(reward_model_order)
    
    if predicted_set == expected_set:
        return 1.0  # ✅ 完全匹配
    elif len(predicted_set) > 0:
        return len(predicted_set) / len(expected_set)  # ⚠️ 部分匹配
    else:
        return 0.0  # ❌ 无匹配
```

**关键**: 只有**完全匹配**才会得分 > 0！

### 示例

| Ground Truth | 模型预测 | 分数 | 是否计入 mean |
|-------------|---------|------|-------------|
| `["noise", "blur"]` | `["noise", "blur"]` | 1.0 | ✅ 是 |
| `["noise", "blur"]` | `["noise"]` | 0.5 | ❌ **否** (< 1.0视为失败，记0) |
| `["noise", "blur"]` | `["noise", "haze"]` | 0.0 | ❌ 否（预测了无效类型） |
| `["noise"]` | `[]` | 0.0 | ❌ 否 |

**实际效果**: 
- 只有完全匹配的样本（1.0分）会被统计
- 部分匹配（如0.5分）会被视为失败，记为0.0
- 因此 `degradation_type_score_mean` 只能是 1.0（或不显示）

---

### 原因2: 大部分样本被过滤

假设一个 batch 有 100 个样本：

```python
样本分布:
- 30个 clean样本 → score = 0.0 (跳过)
- 10个 格式错误 → score = 0.0 (跳过)
- 50个 部分匹配 → score = 0.5 → 按0.0处理 (跳过)
- 5个  完全错误 → score = 0.0 (跳过)
- 5个  完全匹配 → score = 1.0 (统计！)

计算:
degradation_type_score_mean = mean([1.0, 1.0, 1.0, 1.0, 1.0]) 
                            = 1.0 ✅

degradation_type_score_mean_all = mean([0.0×95, 1.0×5]) 
                                 = 0.05 ← 真实情况！

degradation_type_valid_samples = 5  ← 只有5个样本被统计
```

---

## 🎯 正确的监控姿势

### ❌ 错误做法
只看 `reward/degradation_type_score_mean = 1.0` → "模型表现完美！"

### ✅ 正确做法
同时监控三个指标：

1. **`reward/degradation_type_score_mean`**: 1.0
   - 说明：成功识别的样本都是完全匹配

2. **`reward/degradation_type_valid_samples`**: 5
   - 说明：只有 5 个样本成功识别（很少！）

3. **`reward/degradation_type_score_mean_all`**: 0.05
   - 说明：整体只有 5% 的准确率（真实情况很差！）

---

## 📈 实际案例分析

### 案例1: 早期训练

```
degradation_type_score_mean = 1.0
degradation_type_valid_samples = 3
degradation_type_score_mean_all = 0.03

解读: 100个样本中只有3个完全匹配，其余97个都失败了
结论: 模型刚开始学习，识别能力很弱
```

### 案例2: 训练中期

```
degradation_type_score_mean = 1.0
degradation_type_valid_samples = 35
degradation_type_score_mean_all = 0.35

解读: 100个样本中有35个完全匹配
结论: 模型识别能力在提升
```

### 案例3: 训练后期

```
degradation_type_score_mean = 1.0
degradation_type_valid_samples = 85
degradation_type_score_mean_all = 0.85

解读: 100个样本中有85个完全匹配
结论: 模型识别能力很强！
```

---

## 🛠️ 调试步骤

### 1. 检查功能是否启用

```bash
grep "ENABLE_DEGRADATION_TYPE_REWARD" examples/agent/IR.sh
# 输出: export ENABLE_DEGRADATION_TYPE_REWARD=False  ← 默认关闭

# 如果是 False，所有分数都是 0.0
# degradation_type_score_mean 不会显示
# degradation_type_score_mean_all = 0.0
```

### 2. 查看日志详情

```bash
grep "degradation_type_match" logs/*.log | tail -20

# 输出示例:
# [DEBUG degradation_type_match] 预测集合: {'noise'}
# [DEBUG degradation_type_match] 期望集合: {'noise', 'motion blur'}
# [DEBUG degradation_type_match] 部分匹配: 1/2, 奖励=0.5 → 按0.0处理
```

### 3. 在 WandB 中对比指标

```python
# 创建自定义图表，同时显示:
- reward/degradation_type_score_mean (可能是1.0)
- reward/degradation_type_score_mean_all (真实均值)
- reward/degradation_type_valid_samples (样本数量)

# 看三条线的趋势:
# - mean 一直是1.0 → 正常（只统计完全匹配的）
# - mean_all 上升 → 整体识别能力在提升 ✅
# - valid_samples 增加 → 更多样本完全匹配 ✅
```

### 4. 检查表格数据

在 WandB 表格中查看 `Prediction_Match` 列：
- ✅ 完全正确: 这些样本的 score = 1.0
- ⚠️ 部分正确: 这些样本的 score = 0.0（被过滤）
- ❌ 完全错误: 这些样本的 score = 0.0（被过滤）

---

## 💡 关键要点总结

1. **`degradation_type_score_mean = 1.0` 是正常的**
   - 因为它只统计完全匹配的样本
   - 部分匹配的样本被视为失败（0.0分）

2. **重点关注 `degradation_type_score_mean_all`**
   - 这个才反映真实的识别准确度
   - 包含了所有样本（包括失败的）

3. **`valid_samples` 很重要**
   - 告诉你有多少样本成功识别
   - 如果很小，说明大部分样本都失败了

4. **监控组合**
   ```
   mean = 1.0 + valid_samples 小 + mean_all 小 = 识别能力弱
   mean = 1.0 + valid_samples 大 + mean_all 大 = 识别能力强
   ```

---

## 🔗 相关文档

- 完整指标说明: `WANDB_METRICS_GUIDE.md`
- 代码位置: `verl/trainer/ppo/metric_utils.py` 第269-287行
- 评分函数: `verl/utils/reward_score/image_restoration.py` 第1111-1179行

---

**最后更新**: 2025-01-XX

