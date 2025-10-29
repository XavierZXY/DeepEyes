# AIR V7 修改总结

## ✅ 修改完成

已成功将agent执行逻辑从**逐步执行**改为**规划-执行-评估**模式。

## 📝 修改内容

### 1. 核心逻辑修改

**文件**: `verl/workers/agent/parallel_env.py`

#### 修改点1: `execute_tool_call` 函数（877-1020行）

**改动**:
- 从"逐个执行工具"改为"执行完整工具链"
- 每次从原图开始，工具链内部按顺序传递结果
- 只返回最终处理结果，而不是每个中间步骤

**关键代码**:
```python
# 从原图开始
current_image_data = origin_multi_modal_data

# 逐个执行工具链
for i, tool in enumerate(tools):
    # 重置工具，使用当前图像
    tool.reset(
        multi_modal_data=deepcopy(current_image_data),
        origin_multi_modal_data=deepcopy(origin_multi_modal_data),
    )
    
    # 执行工具
    tool_result, reward, done, info = tool.execute(...)
    
    # 更新当前图像为这个工具的输出
    if 'multi_modal_data' in tool_result:
        current_image_data = tool_result['multi_modal_data']
```

#### 修改点2: 工具创建逻辑（1154-1162行）

**改动**:
- 工具创建时直接使用`origin_multi_modal_data`（原图）
- 不再使用`multi_modal_data_history_list[-1]`（上一次结果）

**原因**: 确保每次turn都从原图开始规划和执行

## 🎯 执行流程

### 旧逻辑（逐步执行）
```
Turn 1: 模型 → 工具1 → 结果1
Turn 2: 模型看到结果1 → 工具2 → 结果2（在结果1上处理）
Turn 3: 模型看到结果2 → 工具3 → 结果3（在结果2上处理）
```

### 新逻辑（规划-执行-评估）
```
Turn 1: 
  模型输出 [工具1, 工具2, 工具3]
  → 原图 → 工具1 → 中间1 → 工具2 → 中间2 → 工具3 → 结果A
  → 返回结果A

Turn 2:
  模型看到结果A，输出 [工具4, 工具5]
  → 原图 → 工具4 → 中间3 → 工具5 → 结果B  ← 从原图重新开始
  → 返回结果B

Turn 3:
  模型看到结果B满意 → 输出 <answer>
```

## 🔧 技术细节

### 1. 解析支持

`_parse_model_output_for_tools` 函数已支持JSON数组：
```python
tool_calls_json = json.loads(tool_call_content)
if isinstance(tool_calls_json, list):
    result['tool_calls'] = tool_calls_json  # 数组
else:
    result['tool_calls'] = [tool_calls_json]  # 单个转为数组
```

### 2. 向后兼容

✅ 单个工具调用（dict）会自动转换为单元素列表  
✅ 所有现有工具无需修改  
✅ 旧的训练数据格式仍然支持

### 3. 数据流

```
ParallelEnv
├── origin_multi_modal_data_list: 保存原图（每个样本一个）
├── multi_modal_data_history_list: 保存历史结果（用于反馈给模型）
└── execute_tool_call:
    ├── 从origin开始执行工具链
    ├── 工具链内部链式传递
    └── 返回最终结果
```

## 📊 测试验证

### 测试脚本

运行 `test_tool_chain_logic.py`:
```bash
python test_tool_chain_logic.py
```

### 测试结果

✅ **解析测试**: JSON数组和单个dict都能正确解析  
✅ **执行测试**: 工具链按顺序执行，从原图开始  
✅ **兼容性测试**: 向后兼容旧格式  

### 示例输出

```
Turn 1: 模型提出计划A
起点: Image(原图(雨+暗+噪声))
  → restormer_deraining → Image(...去雨)
  → retinexformer_sdsd_indoor → Image(...去雨 -> 提亮)
  → scunet_real_denoising_gan → Image(...去雨 -> 提亮 -> 去噪)
最终结果A: Image(原图(雨+暗+噪声) -> 去雨 -> 提亮 -> 去噪)

Turn 2: 从原图重新开始（改变顺序）
起点: Image(原图(雨+暗+噪声))  ← 注意：重新从原图开始！
  → retinexformer_sdsd_indoor → Image(...提亮)
  → restormer_deraining → Image(...提亮 -> 去雨)
  → scunet_real_denoising_gan → Image(...提亮 -> 去雨 -> 去噪)
最终结果B: Image(原图(雨+暗+噪声) -> 提亮 -> 去雨 -> 去噪)
```

## 📝 模型输出格式

### 提出计划（Turn 1-N）

```json
<think>
Plan Attempt 1: Given degradations: rain, dark, noise.
I will try: derain → brighten → denoise.
</think>
<tool_call>
[
    {"name": "restormer_deraining", "degradation": "rain", "arguments": {}},
    {"name": "retinexformer_sdsd_indoor", "degradation": "dark", "arguments": {}},
    {"name": "scunet_real_denoising_gan", "degradation": "noise", "arguments": {}}
]
</tool_call>
```

### 完成答案（最后一个Turn）

```json
<think>
The result image looks well-restored. All degradations are addressed.
</think>
<answer>
{
    "restoration_log": ["rain", "dark", "noise"]
}
</answer>
```

## 🚀 使用方法

### 1. System Prompt

已提供的system prompt已经正确描述了新的交互模式。关键要点：
- 模型需要**一次输出完整的工具序列**
- 用户会执行整个序列并返回**最终结果**
- 如果不满意，模型提出**新的完整序列**，从原图重新执行

### 2. 训练配置

在 `IR.sh` 或其他训练脚本中：
```bash
actor_rollout_ref.rollout.agent.max_turns=4  # 允许多次尝试
actor_rollout_ref.rollout.agent.single_response_max_tokens=10240  # 足够输出工具列表
```

### 3. 监控日志

训练时查看关键日志：
```bash
# 查看工具链执行
grep "开始执行工具链" logs/*.log
grep "工具链执行完成" logs/*.log

# 查看工具执行顺序
grep "工具.*执行成功" logs/*.log

# 查看从原图开始
grep "从原图开始" logs/*.log
```

## 🎯 预期效果

### 优势

1. **更灵活**: 模型可以尝试不同的工具组合和顺序
2. **避免累积误差**: 每次从原图开始，不会在错误结果上继续
3. **更符合规划思维**: 完整计划 → 执行 → 评估，而不是逐步反应
4. **更高效**: 减少模型调用次数，一次完成整个处理链

### 潜在挑战

1. **计算成本**: 每次重新处理可能增加计算量
2. **模型能力要求**: 需要模型有良好的规划和评估能力

## 📄 相关文档

- `AIR_V7_TOOL_CHAIN_EXECUTION.md` - 详细的技术文档
- `test_tool_chain_logic.py` - 测试脚本
- `verl/workers/agent/parallel_env.py` - 核心实现

## ✅ 完成清单

- [x] 修改 `execute_tool_call` 函数实现工具链执行
- [x] 修改工具创建逻辑，使用原图
- [x] 验证解析逻辑支持JSON数组
- [x] 编写测试脚本并验证
- [x] 创建技术文档
- [x] 确保向后兼容性
- [x] 无语法或lint错误

## 🔄 下一步

1. **运行实际训练**: 使用 `IR.sh` 或其他训练脚本
2. **监控日志**: 确认工具链正确执行
3. **评估效果**: 观察模型是否能有效利用规划-执行-评估模式
4. **调整参数**: 根据实际效果调整 `max_turns` 等参数

## 📞 问题排查

### 如果工具没有从原图开始

检查日志：
```bash
grep "origin_multi_modal_data" logs/*.log
```

### 如果解析失败

检查模型输出格式：
```bash
grep "<tool_call>" logs/*.log
```

确保输出是有效的JSON数组。

### 如果工具执行顺序错误

检查执行日志：
```bash
grep "工具.*执行成功" logs/*.log
```

---

**修改完成时间**: 2025-10-18  
**分支**: air_v7  
**测试状态**: ✅ 全部通过  
**准备状态**: ✅ 可以开始训练

