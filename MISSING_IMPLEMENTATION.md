# 单工具迭代模式 - 缺失实现清单

## 📋 当前状态

### ✅ 已有功能
1. **单次 Turn 内的工具链式传递**（第1078-1174行）
   - 工具1 → 工具2 → 工具3（图像逐步传递）
   
2. **多 Turn 场景**（但每次从原图开始）
   - Turn 1: [工具1, 工具2] 从原图
   - Turn 2: [工具3] 从原图（重新开始）

3. **配置开关**（我增加的）
   - 环境变量检测
   - 强制只取第一个工具
   - Prompt 模板

### ❌ 缺失功能（多轮单工具迭代）

需要实现：**Turn 之间的图像状态保持**

- Turn 1: [工具1] 从原图 → 结果1
- Turn 2: [工具2] 从**结果1** → 结果2  ❌ 当前会从原图
- Turn 3: [工具3] 从**结果2** → 结果3  ❌ 当前会从原图

---

## 🔧 需要修改的代码

### 1. ParallelEnv 类状态管理

**位置**: `verl/workers/agent/parallel_env.py` Line 1313+

```python
class ParallelEnv:
    def __init__(self, env_config, tokenizer, processor, **kwargs):
        self.config = env_config
        self.tokenizer = tokenizer
        self.processor = processor
        self.tools = []
        
        # ✅ 新增：跟踪每个样本的当前图像状态
        self.current_multi_modal_data_list = []  # 当前图像
        self.processed_degradations_list = []    # 已处理的降质
        self.remaining_degradations_list = []    # 剩余的降质
```

### 2. Reset 方法初始化

**位置**: `verl/workers/agent/parallel_env.py` Line 1518+

```python
def reset(self, prompts, vllm_inputs, n=1, **kwargs):
    self.tools = []
    self.raw_prompts = []
    self.multi_modal_data_history_list = []
    self.origin_multi_modal_data_list = []
    
    # ✅ 新增：初始化当前图像为原图
    self.current_multi_modal_data_list = []
    self.processed_degradations_list = []
    self.remaining_degradations_list = []
    
    # ... 现有代码 ...
    
    for i in range(len(prompts)):
        # ... 处理 prompt 和 multi_modal_data ...
        
        # ✅ 新增：初始化状态
        self.current_multi_modal_data_list.append(deepcopy(multi_modal_data))
        self.processed_degradations_list.append([])
        
        # 从 extra_info 中提取降质列表
        degradations = prompts.batch.get('degradations', [[]])[i]
        self.remaining_degradations_list.append(list(degradations))
```

### 3. Step 方法选择图像源

**位置**: `verl/workers/agent/parallel_env.py` Line 1389+

```python
def step(self, active_indices, actions, current_turn=1):
    # ... 现有代码 ...
    
    for i, idx, action in zip(real_indices, valid_indices, valid_actions):
        # ... 解析工具 ...
        
        tools = _create_tools_from_parsed_output(
            parsed_output,
            # ✅ 修改：根据模式选择图像源
            multi_modal_data=(
                self.current_multi_modal_data_list[idx]  # 单工具迭代：用当前图
                if AGENT_CONVERSATION_MODE == 'single_tool_iterative'
                else self.origin_multi_modal_data_list[idx]  # 多工具规划：用原图
            ),
            origin_multi_modal_data=self.origin_multi_modal_data_list[idx],
            raw_prompt=self.raw_prompts[idx],
            turn_info=turn_info
        )
        
        agent_inputs.append(dict(
            idx=i,
            valid_idx=idx,
            action=action,
            tools=tools,
            parsed_output=parsed_output,
            turn_info=turn_info,
            # ✅ 修改：传递当前图像
            origin_multi_modal_data=(
                self.current_multi_modal_data_list[idx]
                if AGENT_CONVERSATION_MODE == 'single_tool_iterative'
                else self.origin_multi_modal_data_list[idx]
            ),
            raw_prompt=self.raw_prompts[idx],
        ))
```

### 4. 工具执行后更新状态

**位置**: `verl/workers/agent/parallel_env.py` execute_tool_call 函数返回后

在 `step` 方法中，工具执行完成后：

```python
def step(self, active_indices, actions, current_turn=1):
    # ... 工具执行 ...
    
    for idx, (obs, reward, done, info) in enumerate(zip(observations, rewards, dones, infos)):
        valid_idx = valid_indices[idx]
        
        # ✅ 新增：单工具迭代模式下更新状态
        if AGENT_CONVERSATION_MODE == 'single_tool_iterative':
            # 更新当前图像
            if isinstance(obs, dict) and 'multi_modal_data' in obs:
                self.current_multi_modal_data_list[valid_idx] = obs['multi_modal_data']
            
            # 更新降质追踪
            if info.get('status') == 'success':
                executed_tools = info.get('executed_tools', [])
                for tool_name in executed_tools:
                    # 从工具名推断降质类型
                    degradation = infer_degradation_from_tool(tool_name)
                    if degradation in self.remaining_degradations_list[valid_idx]:
                        self.processed_degradations_list[valid_idx].append(degradation)
                        self.remaining_degradations_list[valid_idx].remove(degradation)
        
        obs_list[idx] = obs
        reward_list[idx] = reward
        # ...
```

### 5. execute_tool_call 函数修改

**位置**: `verl/workers/agent/parallel_env.py` Line 1078

```python
def execute_tool_call(...):
    # ✅ 修改：根据模式选择起始图像
    if AGENT_CONVERSATION_MODE == 'single_tool_iterative':
        # 单工具迭代：使用当前图像（不是原图）
        current_image_data = multi_modal_data  # 传入的就是当前状态
        print(f'[DEBUG {turn_info}] 🔄 单工具迭代模式：使用上一轮结果图像')
    else:
        # 多工具规划：使用原图
        current_image_data = origin_multi_modal_data
        print(f'[DEBUG {turn_info}] 🔄 多工具规划模式：从原图开始')
    
    # ... 其余代码不变 ...
```

### 6. 动态 User Prompt 生成

**位置**: `verl/workers/agent/parallel_env.py` 构建 observation 时

```python
def step(self, active_indices, actions, current_turn=1):
    # ... 工具执行完成后 ...
    
    # ✅ 新增：根据模式生成不同的 user prompt
    if AGENT_CONVERSATION_MODE == 'single_tool_iterative':
        from verl.workers.agent.envs.mm_process_engine.ConversationModePrompts import ConversationModePrompts
        
        processed = self.processed_degradations_list[valid_idx]
        remaining = self.remaining_degradations_list[valid_idx]
        
        user_prompt = ConversationModePrompts.SINGLE_TOOL_ITERATIVE_USER_FEEDBACK.format(
            processed_degradations=', '.join(processed) if processed else 'none',
            remaining_degradations=', '.join(remaining) if remaining else 'none'
        )
    else:
        user_prompt = ConversationModePrompts.MULTI_TOOL_PLANNING_USER_FEEDBACK.format(
            applied_sequence=' → '.join(info.get('executed_tools', []))
        )
    
    # 构建 observation 使用 user_prompt
```

---

## 🎯 总结

### 我做的（只是开关）：
```python
# 只是检测和限制
if AGENT_CONVERSATION_MODE == 'single_tool_iterative' and len(tool_calls) > 1:
    tool_calls = tool_calls[:1]
```

### 真正需要的（状态管理）：
```python
# Turn 之间保持图像状态
Turn 1: 原图 → 工具1 → 结果1 (保存到 current_multi_modal_data_list[idx])
Turn 2: 结果1 → 工具2 → 结果2 (保存到 current_multi_modal_data_list[idx])
Turn 3: 结果2 → 工具3 → 结果3 (保存到 current_multi_modal_data_list[idx])
```

---

## 📝 实现优先级

1. **高优先级**（核心功能）
   - [ ] ParallelEnv 状态管理（current_multi_modal_data_list）
   - [ ] Step 方法选择正确的图像源
   - [ ] execute_tool_call 使用传入的图像而非原图

2. **中优先级**（用户体验）
   - [ ] 动态 User Prompt 生成
   - [ ] 降质追踪（processed/remaining）

3. **低优先级**（锦上添花）
   - [ ] 工具名到降质类型的映射
   - [ ] 详细的日志输出

---

## ⚠️ 重要说明

**单轮单工具之前就能用**：
```python
# 如果模型只输出1个工具
max_turns=1
model output: [{"name": "tool1"}]
# 系统会执行这1个工具，没问题！
```

**我增加的只是检测**：
```python
# 如果模型在单工具迭代模式下输出了多个工具，强制只取1个
if mode == "single_tool_iterative" and len(tools) > 1:
    tools = tools[:1]
```

**真正新功能是多轮单工具迭代**：
```python
# 需要实现图像在 turn 之间传递
Turn 1: 从原图开始
Turn 2: 从 Turn 1 结果开始  ← 这个需要新代码
Turn 3: 从 Turn 2 结果开始  ← 这个需要新代码
```

---

**结论**: 你的理解完全正确！我主要增加了配置框架和检测，但核心的"多轮单工具迭代"状态管理还没实现。

