# 🐛 工具链执行Bug修复

## 问题描述

**症状**: 工具创建成功，但工具链不执行，最终状态显示 `❌`

**日志表现**:
```
✅ 工具创建成功：
  [DEBUG TOOL] tool_name: fbcnn_jpeg_artifact_removal
  FBCNNToolbox initialized
  [RESET] fbcnn_jpeg_artifact_removal reset with new image

✅ 工具链开始：
  [DEBUG T1-样本28] 🔧 开始执行工具链，共3个工具

❌ 但没有看到工具执行日志！

❌ 最终状态失败：
  [DEBUG step 1-31] 执行: ❌ reward=0.000, done=False
```

## 🔍 根本原因

### 问题1: 缺少原图数据传递

**位置**: `verl/workers/agent/parallel_env.py` 第1236-1245行（修复前）

```python
# 旧代码：构建agent_inputs时缺少关键数据
agent_inputs.append(dict(
    idx=i,
    valid_idx=idx,
    action=action,
    tools=tools,
    parsed_output=parsed_output,
    turn_info=turn_info,
    # ❌ 缺少 origin_multi_modal_data
    # ❌ 缺少 raw_prompt
))
```

### 问题2: 从错误的地方获取数据

**位置**: `execute_tool_call` 函数第931-949行（修复前）

```python
# 旧代码：试图从工具实例获取数据
origin_multi_modal_data = None
raw_prompt = None
for tool in tools:
    if tool is not None and hasattr(tool, 'origin_multi_modal_data'):
        origin_multi_modal_data = tool.origin_multi_modal_data  # ❌ 工具没有这个属性！
        break

if origin_multi_modal_data is None:
    # ❌ 这里会提前返回，status='failed'
    return error_obs, 0.0, False, {"error": "...", "status": "failed"}
```

**为什么工具没有这个属性？**

工具的 `reset` 方法没有保存 `origin_multi_modal_data`：

```python
# 工具的reset方法（例如SCUNetToolbox）
def reset(self, raw_prompt, multi_modal_data, origin_multi_modal_data=None, **kwargs):
    self.chatml_history = raw_prompt
    self.multi_modal_data = multi_modal_data
    # ❌ 没有保存：self.origin_multi_modal_data = origin_multi_modal_data
    # ❌ 没有保存：self.raw_prompt = raw_prompt
```

---

## ✅ 解决方案

### 修复1: 在agent_inputs中传递原图数据

```python
# 新代码（第1236-1245行）
agent_inputs.append(dict(
    idx=i,
    valid_idx=idx,
    action=action,
    tools=tools,
    parsed_output=parsed_output,
    turn_info=turn_info,
    origin_multi_modal_data=self.origin_multi_modal_data_list[idx],  # ✅ 添加
    raw_prompt=self.raw_prompts[idx],  # ✅ 添加
))
```

### 修复2: 从sample中获取数据

```python
# 新代码（第904-905行）
def execute_tool_call(sample, tokenizer=None, processor=None, pbar=None):
    ...
    origin_multi_modal_data = sample.get('origin_multi_modal_data', None)  # ✅ 从sample获取
    raw_prompt = sample.get('raw_prompt', None)  # ✅ 从sample获取
```

### 修复3: 添加调试日志

```python
# 新代码（第931-933行）
print(f'[DEBUG {turn_info}] 🔧 开始执行工具链，共{len(tools)}个工具')
print(f'[DEBUG {turn_info}] 📋 origin_multi_modal_data: {origin_multi_modal_data is not None}')
print(f'[DEBUG {turn_info}] 📋 raw_prompt: {raw_prompt is not None}')
```

### 修复4: 工具结果后处理异常捕获

```python
# 新代码（第1058-1131行）
try:
    # post-process the final tool result
    ...
    return tool_result_info, total_reward, final_done, final_info
    
except Exception as post_process_error:
    print(f'[ERROR {turn_info}] ❌ 工具结果后处理失败: {str(post_process_error)}')
    traceback.print_exc()
    return error_obs, total_reward, False, {"error": error_msg, "status": "failed", "executed_tools": executed_tools}
```

---

## 📊 修复后的完整数据流

```python
1. ParallelEnv.step 构建 agent_inputs:
   agent_inputs = [
       {
           'tools': [tool1, tool2, tool3],
           'origin_multi_modal_data': 原图,  ← ✅ 现在包含了
           'raw_prompt': 原始prompt,        ← ✅ 现在包含了
           ...
       }
   ]

2. execute_tool_call 获取数据:
   origin_multi_modal_data = sample.get('origin_multi_modal_data')  ← ✅ 成功获取
   raw_prompt = sample.get('raw_prompt')  ← ✅ 成功获取

3. 检查通过，开始执行工具链:
   current_image_data = origin_multi_modal_data  ← ✅ 有数据
   
4. 执行工具链:
   for tool in tools:
       tool.reset(
           multi_modal_data=current_image_data,
           origin_multi_modal_data=origin_multi_modal_data  ← ✅ 正确传递
       )
       tool_result, ... = tool.execute(...)
       current_image_data = tool_result['multi_modal_data']  ← 链式传递
   
5. 返回结果:
   return ..., final_info={'status': 'success', 'executed_tools': [...]}  ← ✅ 正确
```

---

## 🎯 新增的调试日志

运行训练后会看到：

### 1. 开始执行

```
[DEBUG T1-00] 🔧 开始执行工具链，共3个工具
[DEBUG T1-00] 📋 origin_multi_modal_data: True  ← 检查是否有数据
[DEBUG T1-00] 📋 raw_prompt: True
[DEBUG T1-00] 📋 工具列表: ['restormer_deraining', 'retinexformer_sdsd_indoor', 'scunet_real_denoising_gan']
[DEBUG T1-00] 📋 有效工具数: 3/3
```

### 2. 工具执行详情

```
[DEBUG T1-00] 🔍 处理工具1/3
[DEBUG T1-00] 📝 工具1类型: RestormerDerrainingToolbox, 名称: restormer_deraining
[DEBUG T1-00] 📝 工具1 tool_call: {'name': 'restormer_deraining', 'arguments': {}}
[DEBUG T1-00] 🔄 工具1/3: restormer_deraining (输入: 原图)
[DEBUG T1-00] ✅ 工具1 reset成功
[DEBUG T1-00] 🚀 开始执行工具1: restormer_deraining
[DEBUG T1-00] ✅ 工具1执行返回: type=<class 'dict'>, reward=0.000, done=False, info_status=success
[DEBUG T1-00] 📷 更新当前图像数据
```

### 3. 工具链完成

```
[DEBUG T1-00] 🎉 工具链执行完成: restormer_deraining -> retinexformer_sdsd_indoor -> scunet_real_denoising_gan
[DEBUG T1-00] 🔄 预处理multi_modal输入...
[DEBUG T1-00] ✅ 预处理完成
[DEBUG T1-00] 🎁 最终返回: tool_result_info keys=['prompt_token_ids_vllm', 'prompt_token_ids_model', 'multi_modal_data'], final_info={'status': 'success', 'executed_tools': [...]}
```

### 4. 统计计数

```
[DEBUG TOOL CNT] ✅ 样本0 轮次1: 工具链成功执行 [restormer_deraining → retinexformer_sdsd_indoor → scunet_real_denoising_gan], 计数 = 1
```

---

## ✅ 验证修复

运行训练后检查：

```bash
# 1. 检查是否有origin_multi_modal_data
grep "📋 origin_multi_modal_data:" logs/*.log | head -10

# 2. 检查工具链是否执行
grep "🔍 处理工具" logs/*.log | head -10

# 3. 检查工具是否成功执行
grep "✅ 工具.*执行返回" logs/*.log | head -10

# 4. 检查最终状态
grep "DEBUG step.*执行:" logs/*.log | grep "✅" | head -10
```

---

## 🎉 修复总结

| 修复项 | 位置 | 修复内容 |
|--------|------|---------|
| 1. 数据传递 | 第1243-1244行 | 在agent_inputs中添加origin_multi_modal_data和raw_prompt |
| 2. 数据获取 | 第904-905行 | 从sample中获取，而不是从tools中获取 |
| 3. 错误处理 | 第1058-1131行 | 添加try-except捕获后处理异常 |
| 4. 调试日志 | 多处 | 添加详细的执行日志 |

---

## 🚀 测试

修改后立即可以运行训练：

```bash
bash examples/agent/IRv2.sh
```

应该能看到完整的工具链执行过程！

---

**修复时间**: 2025-10-18  
**分支**: air_v7  
**严重程度**: 🔴 Critical (导致工具完全无法执行)  
**状态**: ✅ 已修复

