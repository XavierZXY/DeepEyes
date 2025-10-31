# 总工具调用数上限约束功能

## 📋 功能概述

为单工具迭代模式（`single_tool_iterative`）添加了**总工具调用数上限检查**，防止模型过度调用工具。

**核心约束**：多轮对话中，所有轮次的工具调用总数 ≤ 退化数量 + 1

## 🎯 使用场景

### 适用场景
- ✅ **单工具迭代模式**（`AGENT_CONVERSATION_MODE=single_tool_iterative`）
- ✅ 需要防止模型过度调用工具
- ✅ 希望模型精准识别退化类型并合理使用工具

### 不适用场景
- ❌ 多工具规划模式（`multi_tool_planning`）- 一轮内可能需要多个工具链式执行
- ❌ 允许模型自由探索工具组合的训练阶段

## 🔧 配置方法

### 环境变量配置

在训练脚本（如`IRv2.sh`）中添加：

```bash
export USE_ENHANCED_FORMAT=True                  # 必须启用增强格式检查
export ENABLE_TOTAL_TOOLS_UPPER_LIMIT=True       # 启用总工具数上限检查
export MAX_TOOLS_PER_TURN=1                      # 单轮最多1个工具（单工具迭代模式）

# 配套设置
AGENT_CONVERSATION_MODE="single_tool_iterative"  # 对话模式
actor_rollout_ref.rollout.agent.max_turns=4      # 最大轮数
```

### 配置说明

| 环境变量 | 值 | 说明 |
|---------|-----|------|
| `USE_ENHANCED_FORMAT` | `True` | 必须启用，否则此约束不生效 |
| `ENABLE_TOTAL_TOOLS_UPPER_LIMIT` | `True` | 启用总工具数上限检查 |
| `MAX_TOOLS_PER_TURN` | `1` | 单工具迭代模式建议设为1 |

## 📊 约束规则

### 计算公式

```
允许的最大工具数 = 退化数量 + 1
```

### 验证逻辑

```python
if enable_total_tools_upper_limit and not is_clean_sample and degradation_count > 0:
    max_allowed_tools = degradation_count + 1
    if total_tool_calls > max_allowed_tools:
        # 格式违规：-1.0
        return -1.0
```

### 示例场景

#### 场景1：双退化图像，正常调用（✅ 通过）

**图像信息**：
- 退化类型：`["noise", "blur"]`
- 退化数量：2
- 允许最大工具数：2 + 1 = 3

**模型响应**：
```
轮次1: <think>...</think> <tool_call>[{"name": "scunet_real_denoising_gan", ...}]</tool_call>
轮次2: <think>...</think> <tool_call>[{"name": "nafnet_single_image_defocus_deblurring", ...}]</tool_call>
轮次3: <think>...</think> <answer>{"restoration_log": ["noise", "blur"]}</answer>
```

**结果**：
- 总工具数：2
- 2 ≤ 3 ✅
- **格式分数：+1.0**

---

#### 场景2：双退化图像，适度探索（✅ 通过）

**图像信息**：
- 退化类型：`["noise", "blur"]`
- 退化数量：2
- 允许最大工具数：2 + 1 = 3

**模型响应**：
```
轮次1: <think>...</think> <tool_call>[{"name": "scunet_real_denoising_gan", ...}]</tool_call>
轮次2: <think>...</think> <tool_call>[{"name": "nafnet_single_image_defocus_deblurring", ...}]</tool_call>
轮次3: <think>...</think> <tool_call>[{"name": "swinir_super_resolution", ...}]</tool_call>  # 额外增强
轮次4: <think>...</think> <answer>{"restoration_log": ["noise", "blur"]}</answer>
```

**结果**：
- 总工具数：3
- 3 ≤ 3 ✅
- **格式分数：+1.0**
- 允许1个额外工具用于质量增强

---

#### 场景3：双退化图像，过度调用（❌ 违规）

**图像信息**：
- 退化类型：`["noise", "blur"]`
- 退化数量：2
- 允许最大工具数：2 + 1 = 3

**模型响应**：
```
轮次1: <think>...</think> <tool_call>[{"name": "scunet_real_denoising_gan", ...}]</tool_call>
轮次2: <think>...</think> <tool_call>[{"name": "nafnet_single_image_defocus_deblurring", ...}]</tool_call>
轮次3: <think>...</think> <tool_call>[{"name": "swinir_super_resolution", ...}]</tool_call>
轮次4: <think>...</think> <tool_call>[{"name": "retinexformer_sdsd_indoor", ...}]</tool_call>  # 超出限制
```

**结果**：
- 总工具数：4
- 4 > 3 ❌
- **格式分数：-1.0**
- **错误提示**：`Tool_call数量超过上限: 4 > 3（退化数量2+1）`

---

#### 场景4：三退化图像，正常调用（✅ 通过）

**图像信息**：
- 退化类型：`["noise", "blur", "dark"]`
- 退化数量：3
- 允许最大工具数：3 + 1 = 4

**模型响应**：
```
轮次1: <think>...</think> <tool_call>[{"name": "scunet_real_denoising_gan", ...}]</tool_call>
轮次2: <think>...</think> <tool_call>[{"name": "nafnet_single_image_defocus_deblurring", ...}]</tool_call>
轮次3: <think>...</think> <tool_call>[{"name": "retinexformer_sdsd_indoor", ...}]</tool_call>
轮次4: <think>...</think> <answer>{"restoration_log": ["noise", "blur", "dark"]}</answer>
```

**结果**：
- 总工具数：3
- 3 ≤ 4 ✅
- **格式分数：+1.0**

---

#### 场景5：Clean样本（⭕ 不检查）

**图像信息**：
- 退化类型：`[]` (clean)
- is_clean_sample：True

**模型响应**：
```
轮次1: <think>...</think> <answer>{"restoration_log": ["clean"]}</answer>
```

**结果**：
- **不进行上限检查**（clean样本跳过）
- **格式分数：+1.0**

## 🔄 与其他约束的关系

### 完整的格式约束（增强模式）

当 `USE_ENHANCED_FORMAT=True` 时，格式检查包括：

| 约束 | 说明 | 适用条件 |
|------|------|---------|
| 1. 每轮有`<think>` | 内容>=10字符 | 所有轮次 |
| 2. 每轮有`<tool_call>`或`<answer>` | 二选一必须存在 | 所有轮次 |
| 3. 不能同时有两者 | `<tool_call>`和`<answer>`互斥 | 所有轮次 |
| 4. Answer在最后一轮 | 如果有answer，必须在最后 | 全局 |
| 5. 工具数下限 | 总工具数 >= 1 | 非clean样本 |
| 6. 单轮工具数上限 | 每轮 <= `MAX_TOOLS_PER_TURN` | 如果设置>0 |
| 7. **总工具数上限** | **总工具数 <= 退化数+1** | **启用此功能时** |

### 约束优先级

```
格式检查流程：
1. ✅ 基础格式正确（think、tool_call/answer等）
2. ✅ Answer位置正确（最后一轮）
3. ✅ 单轮工具数限制（如果MAX_TOOLS_PER_TURN>0）
4. ✅ 总工具数下限（至少1个）
5. ✅ 总工具数上限（如果ENABLE_TOTAL_TOOLS_UPPER_LIMIT=True）
```

**任何一项不通过 → 格式分数 = -1.0**

## 💡 设计思想

### 为什么是"退化数量+1"？

1. **基本处理**：每个退化类型至少需要1个工具 → 退化数量个工具
2. **适度探索**：允许1个额外工具用于：
   - 质量增强（如超分辨率）
   - 尝试不同工具
   - 处理复杂情况
3. **防止过度**：限制总数，避免模型盲目调用工具

### 为什么只在单工具迭代模式启用？

| 模式 | 工具调用方式 | 是否启用上限 | 原因 |
|------|-------------|-------------|------|
| `multi_tool_planning` | 一轮规划多个工具链式执行 | ❌ 否 | 可能需要多个工具组合探索 |
| `single_tool_iterative` | 每轮一个工具，逐步处理 | ✅ 是 | 需要精准判断，避免冗余 |

## 📝 代码修改

### 修改的文件

1. ✅ `verl/utils/reward_score/image_restoration.py`
   - 修改 `check_multiturn_format_v3_enhanced()` 函数（第225-391行）
   - 添加 `enable_total_tools_upper_limit` 参数
   - 添加上限验证逻辑（第373-380行）
   - 修改 `compute_score_v2()` 函数签名（第1405-1414行）
   - 传递参数到格式检查函数（第1519-1525行）

2. ✅ `verl/utils/reward_score/__init__.py`
   - 读取环境变量 `ENABLE_TOTAL_TOOLS_UPPER_LIMIT`（第106行）
   - 传递参数到 `compute_score_v2()`（第127行）
   - 添加日志输出（第113行）

3. ✅ `examples/agent/IRv2.sh`
   - 添加环境变量配置（第94行）
   - 更新格式检查说明（第136-142行）
   - 更新推荐配置（第159-164行）

## 🚀 使用示例

### 推荐配置：单工具迭代模式

```bash
# IRv2.sh 配置
export AGENT_CONVERSATION_MODE="single_tool_iterative"
export USE_ENHANCED_FORMAT=True
export MAX_TOOLS_PER_TURN=1
export ENABLE_TOTAL_TOOLS_UPPER_LIMIT=True

# 训练参数
actor_rollout_ref.rollout.agent.max_turns=4  # 允许最多4轮
```

### 日志输出示例

**启用时**：
```
[INFO] Enhanced Format Check: enabled=True
[INFO] Max Tools Per Turn: 1
[INFO] Total Tools Upper Limit: enabled (degradation_count+1)
...
[ENHANCED FORMAT] Tool_call数量下限验证通过: 2 >= 1
[ENHANCED FORMAT] Tool_call数量上限验证通过: 2 <= 3（退化数量2+1）
[ENHANCED FORMAT] 所有检查通过: 轮次=3, tool_calls=2, answer_turns=[3]
```

**违规时**：
```
[ENHANCED FORMAT] Tool_call数量超过上限: 4 > 3（退化数量2+1）
```

## 🎯 预期效果

### 训练效果

1. **减少冗余调用**：模型学会精准识别退化类型
2. **提高效率**：避免不必要的工具调用
3. **保持探索性**：允许+1个工具用于质量增强

### 与其他奖励的配合

```
总奖励 = 格式奖励(30%) × 格式分数 + 质量奖励(70%) × 质量分数

- 格式正确且工具数合理 → 格式分数 = +1.0
- 工具数超限 → 格式分数 = -1.0，总奖励变负
- 即使图像质量高，格式违规也会导致负奖励
```

## ⚠️ 注意事项

1. **必须启用增强格式检查**：`USE_ENHANCED_FORMAT=True`
2. **只对非clean样本生效**：clean样本不检查工具数量
3. **需要准确的退化数量**：从ground_truth的`degradation_addition_order`获取
4. **与MAX_TOOLS_PER_TURN配合**：建议单工具模式设为1
5. **不影响图像质量奖励**：工具执行仍正常进行，只影响格式分数

## 📊 完整的格式规则总结

### 单工具迭代模式 + 增强格式检查 + 上限约束

```
每轮要求：
1. ✅ 必须有 <think> (>=10字符)
2. ✅ 必须有 <tool_call> 或 <answer> (二选一)
3. ✅ 不能同时有两者
4. ✅ 单轮最多1个工具（MAX_TOOLS_PER_TURN=1）

全局要求：
5. ✅ Answer必须在最后一轮（如果有）
6. ✅ 非clean样本至少1个工具
7. ✅ 非clean样本最多 退化数量+1 个工具 ← 新增

任何一项不满足 → 格式分数 = -1.0
```

## ✅ 功能完成

- ✅ 代码实现完成
- ✅ 环境变量配置添加
- ✅ 文档更新完成
- ✅ 日志输出完善
- ✅ 推荐配置提供

**此功能已完整集成到训练框架中，可直接使用！**

