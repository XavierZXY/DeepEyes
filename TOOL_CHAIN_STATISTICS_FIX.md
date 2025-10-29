# 工具链统计逻辑修复

## 📊 问题背景

在 AIR V7 的规划-执行-评估模式下，工具调用统计逻辑存在问题。

### 旧逻辑（有问题）

```python
if parsed_action.get('tool_calls'):
    # 只要模型输出<tool_call>就计数 +1
    tool_call_cnt_list[idx] += 1
```

**问题**:
1. ❌ 只检查模型是否输出 `<tool_call>`
2. ❌ 不管工具是否成功执行
3. ❌ 不区分工具链执行结果

### 问题场景

```python
场景1: 工具链部分成功
  模型输出: [tool1, tool2, tool3]
  执行: tool1✅ → tool2✅ → tool3❌
  旧统计: +1  ← 错误！应该算成功还是失败？
  
场景2: 工具链全部成功
  模型输出: [tool1, tool2]
  执行: tool1✅ → tool2✅
  旧统计: +1  ← 正确
  
场景3: 解析失败，无工具执行
  模型输出: 格式错误的JSON
  执行: 无工具执行
  旧统计: +1  ← 错误！没有成功执行任何工具
  
场景4: 所有工具失败
  模型输出: [tool1, tool2]
  执行: tool1❌ → tool2❌
  旧统计: +1  ← 错误！工具链完全失败
```

---

## ✅ 新逻辑（已修复）

### 修改内容

**文件**: `verl/workers/agent/parallel_env.py`

#### 1. env.step 返回工具执行info (第1254行)

```python
# 构造info_list，按照obs_list的顺序
info_list = [info_dict.get(i, {}) for i in range(len(obs_list))]

return obs_list, reward_list, done_list, info_list  # ← 新增info_list
```

**info包含的信息**:
```python
{
    'status': 'success',  # 或 'failed'
    'executed_tools': ['tool1', 'tool2', 'tool3'],  # 成功执行的工具列表
    'tool_chain': 'tool1 → tool2 → tool3'  # 工具链摘要
}
```

#### 2. 统计逻辑修改 (第572-590行)

```python
# 🔥 新逻辑：只有工具链成功执行才计数
# 检查：1. 模型输出了tool_call  2. 工具链成功执行（至少有一个工具执行成功）
if parsed_action.get('tool_calls'):
    # 模型输出了<tool_call>，检查工具链是否成功执行
    executed_tools = info.get('executed_tools', [])
    if len(executed_tools) > 0:
        # 工具链成功执行（至少执行了一个工具）
        tool_call_cnt_list[idx] += 1
        tools_summary = info.get('tool_chain', ' → '.join(executed_tools))
        print(f"[DEBUG TOOL CNT] ✅ 样本{idx} 轮次{step + 1}: 工具链成功执行 [{tools_summary}], 计数 = {tool_call_cnt_list[idx]}")
    else:
        # 模型输出了tool_call，但工具链执行失败（所有工具都失败）
        print(f"[DEBUG TOOL CNT] ❌ 样本{idx} 轮次{step + 1}: 工具链执行失败，不计数")
elif parsed_action.get('is_done', False):
    # Model generated <answer> block, no tool call
    print(f"[DEBUG TOOL CNT] 样本{idx} 轮次{step + 1}: 给出answer，无工具调用")
else:
    # Model only generated <think> or invalid format
    print(f"[DEBUG TOOL CNT] 样本{idx} 轮次{step + 1}: 仅思考或格式错误，无工具调用")
```

---

## 📈 新逻辑行为

### 正确处理各种场景

```python
场景1: 工具链部分成功
  模型输出: [tool1, tool2, tool3]
  执行: tool1✅ → tool2✅ → tool3❌
  executed_tools: ['tool1', 'tool2']  ← 有成功的工具
  新统计: +1  ✅ 正确：至少有工具成功执行
  
场景2: 工具链全部成功
  模型输出: [tool1, tool2]
  执行: tool1✅ → tool2✅
  executed_tools: ['tool1', 'tool2']
  新统计: +1  ✅ 正确
  
场景3: 解析失败，无工具执行
  模型输出: 格式错误的JSON
  执行: 无工具创建
  executed_tools: []
  新统计: 0  ✅ 正确：没有成功执行任何工具
  
场景4: 所有工具失败
  模型输出: [tool1, tool2]
  执行: tool1❌ → tool2❌
  executed_tools: []
  新统计: 0  ✅ 正确：工具链完全失败
  
场景5: 单个工具成功
  模型输出: [tool1]
  执行: tool1✅
  executed_tools: ['tool1']
  新统计: +1  ✅ 正确
```

---

## 🎯 统计指标含义

### `agent/tool_call_mean`

**定义**: 平均每个样本成功执行工具链的次数

**含义**:
- **旧逻辑**: 平均每个样本输出 `<tool_call>` 的次数（不管是否成功）
- **新逻辑**: 平均每个样本**成功执行工具链**的次数

**示例**:
```python
样本1: 输出3次tool_call，成功执行2次 → 计数 = 2
样本2: 输出2次tool_call，成功执行2次 → 计数 = 2
样本3: 输出1次tool_call，失败0次 → 计数 = 0

tool_call_mean = (2 + 2 + 0) / 3 = 1.33
```

### 合理范围

- **0 < mean < max_turns**: 正常范围
- **mean ≈ 0**: 警告！几乎所有工具链都执行失败
- **mean > max_turns**: 不可能（已被max_turns限制）

---

## 🔍 调试日志

训练时会看到这样的日志：

### 成功执行

```
[DEBUG TOOL CNT] ✅ 样本0 轮次1: 工具链成功执行 [restormer_deraining → retinexformer_sdsd_indoor → scunet_real_denoising_gan], 计数 = 1
[DEBUG TOOL CNT] ✅ 样本0 轮次2: 工具链成功执行 [retinexformer_sdsd_indoor → restormer_deraining], 计数 = 2
```

### 失败情况

```
[DEBUG TOOL CNT] ❌ 样本5 轮次1: 工具链执行失败，不计数
```

### 其他情况

```
[DEBUG TOOL CNT] 样本3 轮次3: 给出answer，无工具调用
[DEBUG TOOL CNT] 样本7 轮次1: 仅思考或格式错误，无工具调用
```

---

## 🎉 修复效果

### 更准确的统计

1. **反映实际工具执行成功率**: 不只是看模型输出，而是看实际执行结果
2. **区分失败情况**: 能识别工具链完全失败的情况
3. **更好的监控**: 帮助发现工具执行问题

### 训练监控

```bash
# 查看工具链统计
grep "DEBUG TOOL CNT" logs/*.log

# 统计成功率
grep "✅.*工具链成功执行" logs/*.log | wc -l
grep "❌.*工具链执行失败" logs/*.log | wc -l

# 查看哪些工具被成功执行
grep "工具链成功执行" logs/*.log | grep -oP '\[.*?\]'
```

### WandB监控

在 WandB 界面查看：
- `agent/tool_call_mean`: 平均成功工具链数
- `agent/tool_call_max`: 最大成功工具链数
- `agent/tool_call_min`: 最小成功工具链数

**健康指标**:
- `mean > 0.5`: 大部分样本至少成功执行一次
- `max ≈ max_turns`: 有样本充分利用了多次尝试
- `min = 0`: 有样本完全失败（需要关注）

---

## 📝 注意事项

### 什么算"成功执行"？

**当前标准**: 工具链中**至少有一个工具**成功执行

**理由**:
- 即使某个工具失败，其他工具的成功执行也有价值
- 完全失败（所有工具都失败）才不计数
- 这样统计更能反映模型的实际能力

### 可选的更严格标准

如果想要更严格（所有工具都成功才计数），可以修改为：

```python
# 严格模式：所有工具都成功才计数
expected_tool_count = len(parsed_action.get('tool_calls', []))
if len(executed_tools) == expected_tool_count and expected_tool_count > 0:
    tool_call_cnt_list[idx] += 1
else:
    # 工具链部分失败或完全失败，不计数
    print(f"[DEBUG TOOL CNT] ❌ 样本{idx}: 工具链部分失败 ({len(executed_tools)}/{expected_tool_count})")
```

---

## ✅ 验证清单

训练后检查：

```bash
# 1. 检查是否有工具链成功执行的日志
grep "✅.*工具链成功执行" logs/*.log | head -20

# 2. 检查是否有失败的日志
grep "❌.*工具链执行失败" logs/*.log | head -10

# 3. 查看统计指标是否合理
# 在WandB中查看 agent/tool_call_mean
# 应该 > 0 且 <= max_turns
```

---

**修改时间**: 2025-10-18  
**分支**: air_v7  
**状态**: ✅ 已修复并测试通过  
**向后兼容**: ✅ 是（新增字段，不影响旧逻辑）

