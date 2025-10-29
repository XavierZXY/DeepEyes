# AIR V7 快速开始 - 规划-执行-评估模式

## ✅ 修改完成

已成功实现规划-执行-评估模式！模型现在可以：
1. 一次输出完整的工具序列
2. 系统按顺序执行所有工具（链式传递）
3. 每次新的尝试都从原图重新开始
4. 模型评估结果，决定是否满意

## 🚀 立即开始

### 1. 验证修改（可选）

```bash
# 运行测试脚本
python test_tool_chain_logic.py

# 预期输出：✅ 所有测试通过
```

### 2. 开始训练

使用您现有的训练脚本（如 `IR.sh`）：
```bash
bash examples/agent/IR.sh
```

**不需要修改任何配置！** 代码已经向后兼容。

### 3. 监控训练

打开新终端，实时查看日志：
```bash
# 查看工具链执行
tail -f logs/*.log | grep "工具链执行完成"

# 查看工具执行详情
tail -f logs/*.log | grep "工具.*执行成功"

# 查看从原图开始
tail -f logs/*.log | grep "从原图开始"
```

## 📝 模型需要输出的格式

### 提出恢复计划（Turn 1-N）

```json
<think>
Plan Attempt 1: Given degradations: rain, dark, noise.
Strategy: First address rain, then brighten, finally denoise.
Reasoning:
1. Derain first to remove rain streaks
2. Brighten to recover occluded details
3. Denoise to remove remaining noise
</think>
<tool_call>
[
    {"name": "restormer_deraining", "degradation": "rain", "arguments": {}},
    {"name": "retinexformer_sdsd_indoor", "degradation": "dark", "arguments": {}},
    {"name": "scunet_real_denoising_gan", "degradation": "noise", "arguments": {}}
]
</tool_call>
```

**关键点**:
- `<tool_call>` 标签内是 **JSON数组** `[...]`
- 每个元素是一个工具调用 `{"name": "...", "degradation": "...", "arguments": {...}}`
- 系统会按顺序执行：原图 → 工具1 → 工具2 → 工具3 → 最终结果

### 完成恢复（最后一个Turn）

```json
<think>
The result image from the previous plan looks excellent.
All degradations have been successfully addressed.
The image is clear and well-restored.
</think>
<answer>
{
    "restoration_log": ["rain", "dark", "noise"]
}
</answer>
```

## 🎯 训练场景示例

### 场景：图像包含 [rain, dark, noise]

**Turn 1**: 模型提出计划A
```
模型输出: [derain, brighten, denoise]
系统执行: 原图 → 去雨 → 提亮 → 去噪 → 结果A
返回: 结果A + "applied: derain → brighten → denoise"
```

**Turn 2**: 模型评估结果A（不满意）
```
模型看到: 结果A（质量不够好）
模型输出: [brighten, derain, denoise]  # 改变顺序
系统执行: 原图 → 提亮 → 去雨 → 去噪 → 结果B  ← 从原图重新开始！
返回: 结果B + "applied: brighten → derain → denoise"
```

**Turn 3**: 模型评估结果B（满意）
```
模型看到: 结果B（质量很好）
模型输出: <answer>{"restoration_log": ["dark", "rain", "noise"]}</answer>
系统: Episode完成 ✅
```

## 🔍 关键改进

### 对比旧逻辑

| 维度 | 旧逻辑（逐步） | 新逻辑（规划-执行-评估） |
|------|--------------|----------------------|
| 工具输出 | 单个工具 | **完整工具列表** |
| 执行方式 | 逐步执行 | **一次执行整个链** |
| 起点 | 上一次结果 | **始终从原图** |
| 灵活性 | 受限于顺序 | **可任意规划** |
| 模型角色 | 逐步反应 | **策略规划者** |

### 优势

1. ✅ **更强的策略探索能力**: 模型可以尝试不同的工具组合和顺序
2. ✅ **避免累积误差**: 每次从原图开始，不会在错误结果上继续
3. ✅ **符合人类思维**: 先规划，再执行，再评估
4. ✅ **减少交互次数**: 一次完成整个处理流程

## ⚙️ 配置建议

在训练脚本中（如 `IR.sh`）：

```bash
# 允许多次尝试不同的恢复计划
actor_rollout_ref.rollout.agent.max_turns=4

# 足够的token让模型输出工具列表
actor_rollout_ref.rollout.agent.single_response_max_tokens=10240

# 并发执行工具（加速）
actor_rollout_ref.rollout.agent.concurrent_workers=2
```

## 📊 监控指标

训练时注意观察：

### 日志输出
```bash
# 应该看到这样的日志：
[DEBUG T1-00] 🔧 开始执行工具链，共3个工具
[DEBUG T1-00] 🔄 工具1/3: restormer_deraining (输入: 原图)
[DEBUG T1-00] ✅ 工具1执行成功: reward=0.000, done=False
[DEBUG T1-00] 📷 更新当前图像数据
[DEBUG T1-00] 🔄 工具2/3: retinexformer_sdsd_indoor (输入: 工具1结果)
[DEBUG T1-00] ✅ 工具2执行成功: reward=0.000, done=False
[DEBUG T1-00] 📷 更新当前图像数据
[DEBUG T1-00] 🔄 工具3/3: scunet_real_denoising_gan (输入: 工具2结果)
[DEBUG T1-00] ✅ 工具3执行成功: reward=0.000, done=False
[DEBUG T1-00] 🎉 工具链执行完成: restormer_deraining -> retinexformer_sdsd_indoor -> scunet_real_denoising_gan
```

### 关键指标
- **工具序列长度**: 平均每次提出几个工具？
- **尝试次数**: 平均需要几次turn才完成？
- **成功率**: 最终输出answer的比例
- **工具顺序变化**: 模型是否在探索不同的顺序？

## 🐛 问题排查

### 问题1: 工具没有从原图开始

**检查**: 
```bash
grep "使用当前图像数据" logs/*.log
```

**原因**: 代码已确保每次从原图开始，不应该出现此问题。

### 问题2: 解析失败

**现象**: 日志显示"Failed to parse valid tool calls"

**检查**: 
```bash
grep "<tool_call>" logs/*.log | head -20
```

**原因**: 模型输出格式不正确。确保：
- `<tool_call>` 内是有效的JSON
- 使用JSON数组格式 `[{...}, {...}]`

**解决**: 调整system prompt，强调JSON格式

### 问题3: 工具执行顺序错误

**检查**:
```bash
grep "工具.*执行成功" logs/*.log
```

**原因**: 应该按照模型输出的顺序执行。检查日志中的顺序是否正确。

## 📚 详细文档

- `AIR_V7_TOOL_CHAIN_EXECUTION.md` - 完整技术文档
- `AIR_V7_MODIFICATION_SUMMARY.md` - 修改总结
- `test_tool_chain_logic.py` - 测试脚本

## 🎉 Ready to Go!

一切准备就绪！执行：
```bash
bash examples/agent/IR.sh
```

训练将自动使用新的规划-执行-评估模式。

---

**版本**: AIR V7  
**状态**: ✅ 就绪  
**测试**: ✅ 通过  
**向后兼容**: ✅ 支持

祝训练顺利！🚀

