# 中间图像质量奖励功能

## 📋 功能概述

为训练系统添加了**中间图像质量奖励**，用于评估多步处理过程中每一步的图像质量，鼓励模型在逐步处理中保持质量，防止中间步骤降低图像质量。

## 🎯 设计动机

### 问题背景

在单工具迭代模式（`single_tool_iterative`）中：
- 模型需要多轮逐步处理图像（如：去噪 → 去模糊 → 提亮）
- 原有奖励只评估**最终结果**
- 中间步骤可能降低图像质量，但只要最终结果好就能得分
- 这可能导致模型采用"破坏-修复"策略

### 解决方案

新增中间图像质量奖励：
- ✅ 评估**每个中间步骤**的图像质量
- ✅ 鼓励模型保持**逐步改善**的处理路径
- ✅ 惩罚中间步骤降低质量的行为
- ✅ 促进更稳定、可靠的多步处理策略

## 🔧 配置方法

### 环境变量配置

在训练脚本（如`IRv2.sh`）中：

```bash
# 启用中间图像质量奖励
export ENABLE_INTERMEDIATE_REWARD=True        # 是否启用（默认False）
export INTERMEDIATE_REWARD_WEIGHT=0.5         # 权重系数（默认0.5）

# 配合使用的其他配置
export FORMAT_REWARD_WEIGHT=0.3               # 格式奖励权重
export QUALITY_REWARD_WEIGHT=0.7              # 最终质量奖励权重
export AGENT_CONVERSATION_MODE="single_tool_iterative"  # 单工具迭代模式
```

### 奖励结构

**启用后的总奖励公式**：
```python
总奖励 = 0.3 × 格式奖励 + 0.7 × 最终质量奖励 + 0.5 × 中间质量奖励
```

**注意**：总权重 = 0.3 + 0.7 + 0.5 = 1.5（允许超过1.0，鼓励全面优化）

## 📊 计算逻辑

### 图像历史结构

```python
image_history = [
    原始退化图,        # index 0 - 不计入评估
    工具1处理结果,      # index 1 - 中间图像
    工具2处理结果,      # index 2 - 中间图像
    工具3处理结果,      # index 3 - 最终结果（主质量奖励）
]
```

### 中间奖励计算步骤

1. **提取中间图像**
   ```python
   # 排除原始图（index 0）和最终结果（index -1）
   intermediate_images = image_history[1:-1]
   ```

2. **计算每个中间图像的质量**
   ```python
   # 使用无参考指标
   for img in intermediate_images:
       score = compute_no_reference_metrics(img)
       # NIQE + BRISQUE + CPBD + CLIP-IQA + Hyper-IQA
   ```

3. **归一化求平均**
   ```python
   intermediate_reward = sum(scores) / len(scores)
   # 范围: [0, 1]
   ```

4. **加入总奖励**
   ```python
   total_reward += 0.5 × intermediate_reward
   ```

## 🎨 实际示例

### 示例1：3个工具处理（标准情况）

**处理流程**：
```
原始图（退化） 
  ↓ 工具1：去噪
图像1（中间）
  ↓ 工具2：去模糊
图像2（中间）
  ↓ 工具3：提亮
图像3（最终）
```

**奖励计算**：
```python
# 中间图像评估
intermediate_images = [图像1, 图像2]
intermediate_score_1 = 0.75  # 图像1的无参考质量
intermediate_score_2 = 0.82  # 图像2的无参考质量
intermediate_reward = (0.75 + 0.82) / 2 = 0.785

# 最终图像评估
final_quality = 0.88  # 图像3的质量（SSIM/LPIPS/PSNR）

# 总奖励
format_score = 1.0
total_reward = 0.3 × 1.0 + 0.7 × 0.88 + 0.5 × 0.785
            = 0.3 + 0.616 + 0.393
            = 1.309 ✅
```

---

### 示例2：1个工具处理（特殊情况）

**处理流程**：
```
原始图（退化）
  ↓ 工具1：去噪
图像1（既是中间也是最终）
```

**奖励计算**：
```python
# 特殊处理：只有1个工具时，该图像既算主奖励也算中间奖励
image_history = [原始图, 图像1]

# 中间图像评估（包含图像1）
intermediate_images = [图像1]
intermediate_reward = 0.80

# 最终图像评估（也是图像1）
final_quality = 0.85

# 总奖励（图像1被评估两次，但使用不同指标）
total_reward = 0.3 × 1.0 + 0.7 × 0.85 + 0.5 × 0.80
            = 0.3 + 0.595 + 0.40
            = 1.295 ✅
```

**设计理由**：
- 只有1个工具时，无法单独评估"中间过程"
- 但仍然需要鼓励该工具的输出质量
- 所以既算主奖励（与GT对比）也算中间奖励（无参考评估）
- 两种评估角度不同，互为补充

---

### 示例3：对比启用前后的效果

**场景**：模型使用3个工具处理图像

#### 不启用中间奖励（原始系统）

| 步骤 | 质量分数 | 获得奖励 |
|------|---------|---------|
| 原始图 | 0.30 | - |
| 工具1处理 | 0.40 | 无 ❌ |
| 工具2处理 | 0.45 | 无 ❌ |
| 工具3处理 | 0.90 | ✅ 0.3×1.0 + 0.7×0.90 = 0.93 |

**问题**：只看最终结果，中间步骤可以随意

#### 启用中间奖励（新系统）

| 步骤 | 质量分数 | 获得奖励 |
|------|---------|---------|
| 原始图 | 0.30 | - |
| 工具1处理 | 0.40 | ✅ 计入中间奖励 |
| 工具2处理 | 0.45 | ✅ 计入中间奖励 |
| 工具3处理 | 0.90 | ✅ 最终奖励 + 中间奖励 |

**总奖励**：
```python
intermediate_reward = (0.40 + 0.45) / 2 = 0.425
total = 0.3×1.0 + 0.7×0.90 + 0.5×0.425
     = 0.3 + 0.63 + 0.213
     = 1.143 ✅
```

**效果**：鼓励逐步改善，每一步都有质量要求

---

### 示例4：惩罚中间质量下降

**场景A：中间质量下降**
```
原始图: 0.30
工具1: 0.20  ❌ 质量下降
工具2: 0.25  ❌ 质量仍低
工具3: 0.85  ✅ 最终恢复
```

**奖励计算**：
```python
intermediate_reward = (0.20 + 0.25) / 2 = 0.225  # 低
total = 0.3×1.0 + 0.7×0.85 + 0.5×0.225
     = 0.3 + 0.595 + 0.113
     = 1.008
```

**场景B：中间质量稳定提升**
```
原始图: 0.30
工具1: 0.50  ✅ 质量提升
工具2: 0.65  ✅ 继续提升
工具3: 0.85  ✅ 最终结果相同
```

**奖励计算**：
```python
intermediate_reward = (0.50 + 0.65) / 2 = 0.575  # 高
total = 0.3×1.0 + 0.7×0.85 + 0.5×0.575
     = 0.3 + 0.595 + 0.288
     = 1.183  ✅ 更高！
```

**对比**：
- 场景A：总奖励 = 1.008
- 场景B：总奖励 = 1.183（高17%）
- **结论**：鼓励逐步改善的策略

## 🔍 技术实现

### 核心函数

```python
def compute_intermediate_image_quality_reward(
    image_history: List, 
    include_last: bool = False
) -> float:
    """
    计算中间被工具处理的图片的无参考质量奖励
    
    Args:
        image_history: 图像历史列表
        include_last: 是否包含最后一张（默认False）
    
    Returns:
        归一化的中间图像质量奖励 [0, 1]
    """
    # 1. 确定评估范围
    start_idx = 1  # 跳过原始图
    if include_last:
        end_idx = len(image_history)
    else:
        end_idx = len(image_history) - 1
    
    # 2. 特殊处理：只有1个工具
    if len(image_history) == 2:
        end_idx = len(image_history)
    
    intermediate_images = image_history[start_idx:end_idx]
    
    # 3. 计算每个中间图像的无参考质量
    scores = []
    for img_data in intermediate_images:
        img = extract_image(img_data)
        score = compute_no_reference_metrics(img)
        scores.append(score)
    
    # 4. 归一化
    return sum(scores) / len(scores)
```

### 无参考指标

使用5个无参考质量指标（均等权重0.2）：

| 指标 | 范围 | 方向 | 含义 |
|------|------|------|------|
| NIQE | [2, 15] | 越小越好 | 自然场景统计特征 |
| BRISQUE | [0, 100] | 越小越好 | 亮度结构信息 |
| CPBD | [0, 1] | 越大越好 | 清晰度评估 |
| CLIP-IQA | [0, 1] | 越大越好 | 语义质量 |
| Hyper-IQA | [0, 1] | 越大越好 | 局部失真检测 |

**计算公式**：
```python
reward = 0.2 × norm_niqe 
       + 0.2 × norm_brisque 
       + 0.2 × norm_cpbd 
       + 0.2 × norm_clip_iqa 
       + 0.2 × norm_hyper_iqa
```

### 与主质量奖励的区别

| 维度 | 主质量奖励 | 中间质量奖励 |
|------|-----------|-------------|
| **评估对象** | 最终图像 | 中间图像 |
| **指标类型** | 有参考（SSIM/LPIPS/PSNR）| 无参考（NIQE/BRISQUE等）|
| **需要GT** | 是（当前配置） | 否 |
| **数量** | 1个图像 | N-1个图像 |
| **聚合方式** | 直接使用 | 求平均 |

## 💡 最佳实践

### 适用场景

| 场景 | 是否推荐 |
|------|---------|
| 单工具迭代模式 | ✅ 强烈推荐 |
| 多步逐一处理 | ✅ 推荐 |
| 多工具链式执行 | ⚠️ 可选 |
| 单轮单工具 | ⚠️ 意义不大 |

### 权重调整建议

| 场景 | 推荐权重 | 理由 |
|------|---------|------|
| 重视最终质量 | 中间=0.3 | 辅助引导 |
| 平衡中间和最终 | 中间=0.5 | 当前默认 |
| 严格要求中间质量 | 中间=0.7 | 强制逐步改善 |

### 配置组合

**推荐配置1：单工具迭代 + 中间奖励**
```bash
export AGENT_CONVERSATION_MODE="single_tool_iterative"
export ENABLE_INTERMEDIATE_REWARD=True
export INTERMEDIATE_REWARD_WEIGHT=0.5
export FORMAT_REWARD_WEIGHT=0.3
export QUALITY_REWARD_WEIGHT=0.7
actor_rollout_ref.rollout.agent.max_turns=4
```

**推荐配置2：严格中间质量控制**
```bash
export ENABLE_INTERMEDIATE_REWARD=True
export INTERMEDIATE_REWARD_WEIGHT=0.7  # 提高权重
export FORMAT_REWARD_WEIGHT=0.3
export QUALITY_REWARD_WEIGHT=0.7
```

## 📈 预期效果

### 训练效果

1. **更稳定的处理路径**
   - 每一步都有质量约束
   - 减少"破坏-修复"行为

2. **更好的泛化能力**
   - 学会逐步改善策略
   - 不依赖最后一步的"救场"

3. **更高的中间图像质量**
   - 每个中间结果都可用
   - 支持早停机制

### 监控指标

新增监控字段：
```python
{
    "intermediate_quality_score": 0.785,  # 中间图像平均质量
    "quality_score": 0.88,                # 最终图像质量
    "score": 1.309                        # 总奖励
}
```

## 🔧 调试和监控

### 日志输出

```
[DEBUG INTERMEDIATE] 评估中间图像: 总历史长度=4, 评估范围=[1:3], 数量=2
[DEBUG INTERMEDIATE] 第1/2个中间图像质量=0.7500
[DEBUG INTERMEDIATE] 第2/2个中间图像质量=0.8200
[DEBUG INTERMEDIATE] 中间图像奖励: 总分=1.5700, 平均分=0.7850 (评估了2/2张)
[DEBUG intermediate_reward] enabled, intermediate_quality_score=0.785, weight=0.5, contribution=0.393
[DEBUG intermediate_reward] new total_score=1.309 (包含中间图像质量奖励)
```

### 特殊情况日志

**只有1个工具**：
```
[DEBUG INTERMEDIATE] 只有一个工具，结果图既算主奖励也算中间奖励
```

**图像历史不足**：
```
[DEBUG intermediate_reward] 图像历史不足，跳过中间奖励计算 (history_len=1)
```

**Clean样本**：
```
[DEBUG intermediate_reward] clean样本跳过中间奖励计算
```

## ⚠️ 注意事项

1. **计算开销**
   - 每个中间图像都需要计算5个无参考指标
   - 建议在GPU上运行

2. **只在格式正确时计算**
   - 格式违规：跳过中间奖励
   - 防止无效计算

3. **非Clean样本限定**
   - Clean样本跳过中间奖励
   - 因为没有工具处理

4. **特殊情况处理**
   - 只有1个工具：既算主奖励也算中间奖励
   - 设计合理，鼓励该工具输出质量

## 📝 文件修改

1. ✅ `verl/utils/reward_score/image_restoration.py`
   - 新增 `compute_intermediate_image_quality_reward()` 函数
   - `compute_score_v2()` 添加中间奖励计算

2. ✅ `verl/utils/reward_score/__init__.py`
   - 读取环境变量配置
   - 传递参数到计算函数

3. ✅ `examples/agent/IRv2.sh`
   - 添加配置选项
   - 更新说明文档

## 🎯 总结

### 核心价值

1. ✅ **鼓励逐步改善**：每一步都有质量要求
2. ✅ **防止质量下降**：中间步骤不能降低质量
3. ✅ **提高稳定性**：减少"破坏-修复"策略
4. ✅ **增强泛化**：学会可靠的多步处理

### 快速启用

```bash
# 在 IRv2.sh 中添加
export ENABLE_INTERMEDIATE_REWARD=True
export INTERMEDIATE_REWARD_WEIGHT=0.5
```

### 关键公式

```
总奖励 = 0.3 × 格式 + 0.7 × 最终质量 + 0.5 × 中间质量
```

---

**版本**: v1.0  
**创建日期**: 2025-10-31  
**适用版本**: AIR v9  
**状态**: ✅ 已实现并测试

