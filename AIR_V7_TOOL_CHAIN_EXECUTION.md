# AIR V7 工具链执行逻辑 - 规划-执行-评估模式

## 📋 修改概述

将agent执行逻辑从**逐步执行**模式改为**规划-执行-评估**模式。

### 旧逻辑（逐步执行）
```
模型输出工具1 → 执行工具1 → 返回结果1 → 
模型看到结果1，输出工具2 → 执行工具2 → 返回结果2 → 
模型看到结果2，输出工具3 → ...
```
每次执行都在上一次的结果上继续处理。

### 新逻辑（规划-执行-评估）
```
Turn 1:
  模型输出完整计划A: [工具1, 工具2, 工具3] 
  → 执行工具链: 原图 → 工具1 → 中间结果1 → 工具2 → 中间结果2 → 工具3 → 最终结果A
  → 返回最终结果A给模型

Turn 2:
  模型看到结果A，如果不满意，输出新计划B: [工具4, 工具5]
  → 执行工具链: 原图 → 工具4 → 中间结果3 → 工具5 → 最终结果B
  → 返回最终结果B给模型

Turn 3:
  模型看到结果B，如果满意 → 输出 <answer>
```

**关键特性**:
1. ✅ 模型一次输出完整的工具序列（JSON数组）
2. ✅ 工具链内部按顺序执行，上一个工具的输出是下一个工具的输入
3. ✅ **每次新的turn都从原图开始**，而不是在上一次结果上继续
4. ✅ 只返回最终处理结果，而不是每个中间步骤

## 🔧 代码修改

### 主要修改文件
- `verl/workers/agent/parallel_env.py`
  - 修改了 `execute_tool_call()` 函数（877-1020行）
  - 修改了工具创建逻辑，始终使用原图（1154-1162行）

### 核心实现

#### 1. 工具链执行逻辑（execute_tool_call）

```python
# 获取原图
origin_multi_modal_data = None
for tool in tools:
    if tool is not None and hasattr(tool, 'origin_multi_modal_data'):
        origin_multi_modal_data = tool.origin_multi_modal_data
        break

# 从原图开始执行工具链
current_image_data = origin_multi_modal_data  # 起点：原图

for i, tool in enumerate(tools):
    # 重新初始化工具，使用当前图像数据
    tool.reset(
        multi_modal_data=deepcopy(current_image_data),      # 当前要处理的图像
        origin_multi_modal_data=deepcopy(origin_multi_modal_data),  # 原图（参考）
    )
    
    # 执行工具
    tool_result, reward, done, info = tool.execute(...)
    
    # 更新当前图像为这个工具的输出
    if 'multi_modal_data' in tool_result:
        current_image_data = tool_result['multi_modal_data']  # 传递给下一个工具
    
    executed_tools.append(tool.name)

# 返回最终结果
return {
    "prompt": f"Result image after applying: [{' → '.join(executed_tools)}]",
    "multi_modal_data": current_image_data  # 最终处理结果
}
```

#### 2. 工具创建逻辑

```python
# 每次都从原图开始规划和执行
tools = _create_tools_from_parsed_output(
    parsed_output,
    multi_modal_data=self.origin_multi_modal_data_list[idx],  # 使用原图
    origin_multi_modal_data=self.origin_multi_modal_data_list[idx],
    raw_prompt=self.raw_prompts[idx],
    turn_info=turn_info
)
```

## 📝 模型输出格式

### Turn 1-N: 提出恢复计划

```
<think>
Plan Attempt 1: Given degradations: rain, dark, noise. 
I will first try deraining, then brighten, then denoise.
Plan Sequence:
1. Derain (restormer_deraining)
2. Brighten (retinexformer_sdsd_indoor)
3. Denoise (scunet_real_denoising_gan)
</think>
<tool_call>
[
    {"name": "restormer_deraining", "degradation": "rain", "arguments": {}},
    {"name": "retinexformer_sdsd_indoor", "degradation": "dark", "arguments": {}},
    {"name": "scunet_real_denoising_gan", "degradation": "noise", "arguments": {}}
]
</tool_call>
```

### 最终Turn: 确认完成

```
<think>
The result image from the previous plan looks well-restored. 
All degradations are addressed. Restoration complete.
</think>
<answer>
{
    "restoration_log": [
        "rain",
        "dark", 
        "noise"
    ]
}
</answer>
```

## 🎯 执行流程示例

### 完整示例

**输入图像**: 包含退化类型 [rain, dark, noise]

#### Turn 1: 模型提出计划A
```
模型输出: [restormer_deraining, retinexformer_sdsd_indoor, scunet_real_denoising_gan]
执行过程:
  原图（雨+暗+噪声）
  → restormer_deraining → 中间图1（暗+噪声）
  → retinexformer_sdsd_indoor → 中间图2（亮+噪声）
  → scunet_real_denoising_gan → 最终结果A（清晰但可能不够理想）
返回: 最终结果A + 工具链信息 "restormer_deraining → retinexformer_sdsd_indoor → scunet_real_denoising_gan"
```

#### Turn 2: 模型评估结果A，不满意，提出计划B
```
模型看到: 结果A（质量不够好）
模型输出: [retinexformer_sdsd_indoor, restormer_deraining, scunet_real_denoising_gan]  # 改变顺序
执行过程:
  原图（雨+暗+噪声）  ← 注意：从原图重新开始！
  → retinexformer_sdsd_indoor → 中间图3（亮+雨+噪声）
  → restormer_deraining → 中间图4（亮+噪声）
  → scunet_real_denoising_gan → 最终结果B（清晰且质量更好）
返回: 最终结果B + 工具链信息
```

#### Turn 3: 模型评估结果B，满意，输出答案
```
模型看到: 结果B（质量满意）
模型输出: <answer>{"restoration_log": ["dark", "rain", "noise"]}</answer>
结束: Episode完成
```

## 🔍 关键设计决策

### 1. 为什么每次turn从原图开始？

**理由**: 
- 不同的工具序列和顺序会产生不同的最终结果
- 如果在上一次结果上继续处理，会累积误差
- 从原图开始允许模型探索不同的恢复策略

**类比**: 就像国际象棋，每次模型提出一个完整的"走法序列"，然后看结果如何，如果不满意，回到初始状态尝试新的序列。

### 2. 工具链内部如何传递数据？

**链式传递**:
```
原图 → 工具1 → 工具1输出 → 工具2 → 工具2输出 → ... → 最终结果
```

每个工具处理上一个工具的输出，这是标准的图像处理流程。

### 3. 历史记录的作用

```python
self.multi_modal_data_history_list[idx] = [原图, 结果A, 结果B, ...]
```

- **记录每次turn的最终结果**
- **反馈给模型**：模型需要看到上一次的结果才能决定是否满意
- **不影响执行**：执行时始终从`origin_multi_modal_data`开始

## ✅ 验证要点

### 检查点1: 工具链从原图开始
```bash
# 查看日志
grep "从原图开始" logs/*.log
grep "current_image_data = origin_multi_modal_data" logs/*.log
```

### 检查点2: 工具按序列执行
```bash
# 查看日志
grep "工具链执行完成" logs/*.log
# 应该看到: "工具链执行完成: 工具1 -> 工具2 -> 工具3"
```

### 检查点3: 每次turn重置
```bash
# 查看日志，确认每次turn都输出"开始执行工具链"
grep "开始执行工具链" logs/*.log
```

## 🚀 使用建议

### System Prompt

已更新的system prompt应该强调：
1. **提出完整的恢复计划**（工具序列）
2. **评估返回的结果图像**
3. **如果不满意，提出新的完整计划**（会从原图重新执行）

### 配置参数

```bash
# 在IR.sh中
actor_rollout_ref.rollout.agent.max_turns=4  # 允许多次尝试
```

建议设置较大的`max_turns`，给模型足够的机会尝试不同的恢复策略。

## 📊 预期效果

### 优势
1. ✅ **更灵活的策略探索**: 模型可以尝试不同的工具序列和顺序
2. ✅ **避免累积误差**: 每次从原图开始，不会在错误的结果上继续处理
3. ✅ **更符合规划思维**: 模型提出完整计划，而不是逐步反应
4. ✅ **更高效**: 一次执行完整个工具链，减少模型调用次数

### 潜在挑战
1. ⚠️ **计算成本**: 每次重新从原图处理，如果尝试多次可能耗时
2. ⚠️ **模型规划能力**: 需要模型有能力一次规划完整的恢复序列
3. ⚠️ **评估能力**: 模型需要准确评估结果图像的质量

## 📄 相关文件

- `verl/workers/agent/parallel_env.py` - 核心执行逻辑
- `verl/workers/agent/tool_envs.py` - 工具基类
- `examples/agent/IR.sh` - 训练配置脚本

## 🔄 兼容性

- ✅ 向后兼容：如果模型输出单个工具调用（dict而不是list），会被自动包装为单元素列表
- ✅ 工具接口不变：所有现有工具无需修改
- ✅ 解析逻辑已支持：`_parse_model_output_for_tools`已经支持JSON数组解析

---

**修改时间**: 2025-10-18  
**分支**: air_v7  
**修改人**: AI Assistant

