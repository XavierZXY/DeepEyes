# 📦 Bbox奖励可选配置使用指南

## 🎯 概述

根据您的要求，我已经将bbox奖励设置为可选的。现在您可以灵活控制是否在奖励计算中包含bbox/grounding相关的奖励。

## 🚀 新功能

### 1. **所有奖励函数都支持可选bbox奖励**

- ✅ `compute_enhanced_score()` - 增强版奖励函数
- ✅ `compute_score()` - 原始奖励函数  
- ✅ `compute_common_reasoning()` - 通用推理奖励函数

### 2. **灵活的配置选项**

- `use_bbox_reward`: 是否启用bbox奖励 (默认: True)
- `bbox_reward_weight`: bbox奖励的权重 (仅限增强版，默认: 0.8)

## 📋 使用方法

### 🔧 **基本用法**

#### 启用bbox奖励 (默认行为)
```python
# 方式1: 使用默认设置
reward = compute_enhanced_score(predict_str, ground_truth, extra_info)

# 方式2: 显式启用
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    use_bbox_reward=True
)

# 方式3: 自定义bbox权重
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    use_bbox_reward=True,
    bbox_reward_weight=0.6  # 降低bbox奖励权重
)
```

#### 禁用bbox奖励
```python
# 完全禁用bbox奖励
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    use_bbox_reward=False
)

# 原始函数禁用bbox奖励
reward = compute_score(
    predict_str, ground_truth, extra_info,
    use_bbox_reward=False
)

# 通用推理函数禁用bbox奖励
reward = compute_common_reasoning(
    predict_str, ground_truth, extra_info,
    use_bbox_reward=False
)
```

### 🎛️ **高级配置**

#### 组合不同策略
```python
# 多层级策略 + 可调bbox权重
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    grounding_strategy="multi_level",
    use_bbox_reward=True,
    bbox_reward_weight=0.5  # 降低grounding的权重
)

# 渐进式训练初期 + 禁用bbox
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    grounding_strategy="progressive",
    training_stage="early",
    use_bbox_reward=False  # 训练初期专注于其他方面
)

# 课程学习 + 动态调整bbox权重
current_step = 5000
if current_step < 2000:
    # 训练初期禁用bbox奖励
    reward = compute_enhanced_score(
        predict_str, ground_truth, extra_info,
        grounding_strategy="curriculum",
        curriculum_step=current_step,
        use_bbox_reward=False
    )
else:
    # 训练中后期启用bbox奖励
    reward = compute_enhanced_score(
        predict_str, ground_truth, extra_info,
        grounding_strategy="curriculum", 
        curriculum_step=current_step,
        use_bbox_reward=True,
        bbox_reward_weight=0.8
    )
```

## 📊 权重分配对比

### 🟢 **启用bbox奖励时** (`use_bbox_reward=True`)

#### compute_enhanced_score:
```python
final_score = (
    0.6 * acc_reward +                    # 答案准确性
    bbox_reward_weight * grounding_reward + # 可配置的grounding奖励
    0.4 * type_acc_reward +               # 类型准确性
    0.8 * tool_reward +                   # 工具使用
    0.2 * format_reward +                 # 格式奖励/惩罚
    0.2 * bbox_format_reward              # Bbox格式奖励
)
```

#### compute_score & compute_common_reasoning:
```python
final_score = (
    0.8 * acc_reward +      # 答案准确性
    0.2 * format_reward +   # 格式奖励/惩罚  
    1.2 * tool_reward +     # 工具使用
    0.6 * bbox_reward +     # Bbox奖励
    0.4 * type_reward       # 类型奖励
)
```

### 🔴 **禁用bbox奖励时** (`use_bbox_reward=False`)

#### compute_enhanced_score:
```python
final_score = (
    0.8 * acc_reward +      # 答案准确性 (增权)
    0.6 * type_acc_reward + # 类型准确性 (增权)
    1.0 * tool_reward +     # 工具使用 (增权)
    0.2 * format_reward     # 格式奖励/惩罚
    # bbox相关奖励全部省略
)
```

#### compute_score & compute_common_reasoning:
```python
final_score = (
    1.0 * acc_reward +      # 答案准确性 (增权)
    0.2 * format_reward +   # 格式奖励/惩罚
    1.4 * tool_reward +     # 工具使用 (增权)  
    0.6 * type_reward       # 类型奖励 (增权)
)
```

## 🎯 应用场景

### 📚 **训练阶段应用**

#### 🌱 **早期训练 (0-30%)**
```python
# 专注于基本的对话和推理能力
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    use_bbox_reward=False  # 先不管定位，专注理解
)
```

#### 🌿 **中期训练 (30-70%)**
```python
# 逐步引入grounding能力
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    grounding_strategy="multi_level",
    use_bbox_reward=True,
    bbox_reward_weight=0.5  # 较低权重
)
```

#### 🌳 **后期训练 (70-100%)**
```python
# 全力训练精确定位
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    grounding_strategy="progressive",
    training_stage="late",
    use_bbox_reward=True,
    bbox_reward_weight=1.0  # 较高权重
)
```

### 🔬 **任务特定应用**

#### 📝 **纯文本对话任务**
```python
# 无需定位能力的对话
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    use_bbox_reward=False
)
```

#### 🎯 **异常检测任务**
```python
# 需要精确定位的检测任务
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    grounding_strategy="multi_level",
    use_bbox_reward=True,
    bbox_reward_weight=1.2  # 高权重
)
```

#### 🔄 **对比实验**
```python
# A/B测试不同配置
configs = [
    {"use_bbox_reward": False},
    {"use_bbox_reward": True, "bbox_reward_weight": 0.5},
    {"use_bbox_reward": True, "bbox_reward_weight": 1.0},
]

for config in configs:
    reward = compute_enhanced_score(
        predict_str, ground_truth, extra_info,
        **config
    )
    # 记录和对比结果
```

## 💡 最佳实践建议

### 🚀 **推荐策略**

1. **🎯 任务导向**:
   - 纯对话任务 → `use_bbox_reward=False`
   - 检测/定位任务 → `use_bbox_reward=True`

2. **📈 渐进训练**:
   - 从`use_bbox_reward=False`开始
   - 逐步增加`bbox_reward_weight`
   - 最终使用完整bbox奖励

3. **⚖️ 权重平衡**:
   - 训练初期: `bbox_reward_weight=0.3-0.5`
   - 训练中期: `bbox_reward_weight=0.5-0.8`
   - 训练后期: `bbox_reward_weight=0.8-1.2`

### 🔧 **调试技巧**

#### 日志分析
```python
# 启用详细日志查看各组件分数
reward = compute_enhanced_score(
    predict_str, ground_truth, extra_info,
    use_bbox_reward=True,  # 或False进行对比
)
# 查看日志中的分数分解
```

#### 分数对比
```python
# 对比有无bbox奖励的分数差异
reward_with_bbox = compute_enhanced_score(
    predict_str, ground_truth, extra_info, use_bbox_reward=True
)
reward_without_bbox = compute_enhanced_score(
    predict_str, ground_truth, extra_info, use_bbox_reward=False
)
print(f"差异: {reward_with_bbox - reward_without_bbox:.3f}")
```

这个可选bbox奖励功能让您能够更灵活地控制训练过程，根据不同阶段和任务需求调整奖励机制！
