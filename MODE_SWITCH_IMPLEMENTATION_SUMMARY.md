# Agent对话模式切换功能 - 实现总结

## ✅ 已完成功能

### 1. 环境变量配置系统
- **文件**: `examples/agent/IRv2.sh`
- **新增变量**: `AGENT_CONVERSATION_MODE`
- **支持值**: 
  - `"multi_tool_planning"` - 多工具链式规划（默认）
  - `"single_tool_iterative"` - 单工具迭代（实验性）
- **位置**: 第53行
- **说明**: 包含详细的模式说明和推荐配置

### 2. System Prompt 模板
- **文件**: `verl/workers/agent/envs/mm_process_engine/ConversationModePrompts.py`
- **类**: `ConversationModePrompts`
- **模板**:
  - `MULTI_TOOL_PLANNING_SYSTEM` - 多工具规划模式
  - `MULTI_TOOL_PLANNING_USER_FIRST` - 首轮用户提示
  - `MULTI_TOOL_PLANNING_USER_FEEDBACK` - 反馈提示
  - `SINGLE_TOOL_ITERATIVE_SYSTEM` - 单工具迭代模式
  - `SINGLE_TOOL_ITERATIVE_USER_FIRST` - 首轮用户提示
  - `SINGLE_TOOL_ITERATIVE_USER_FEEDBACK` - 反馈提示

### 3. 核心执行逻辑
- **文件**: `verl/workers/agent/parallel_env.py`
- **修改**:
  - 第4行: 添加 `import os`
  - 第20-33行: 添加 `AGENT_CONVERSATION_MODE` 环境变量读取和验证
  - 第208-221行: 修改 `_create_tools_from_parsed_output` 函数
    - 在单工具迭代模式下，只取第一个工具
    - 添加模式显示日志
    - 工具数量限制逻辑

### 4. 配置说明文档
- **文件**: `examples/agent/IRv2.sh` 第108-141行
- **内容**: 
  - 三种格式检查模式的说明
  - 不同对话模式的推荐配置组合
  - 格式检查优先级说明

### 5. 完整文档
- **CONVERSATION_MODE_GUIDE.md** - 完整指南
  - 两种模式的详细对比
  - 配置方法
  - 对话示例
  - 数据集格式
  - 实现状态
  - 待完成功能清单
  - FAQ

- **QUICK_MODE_SWITCH.md** - 快速开始
  - 快速切换方法
  - 配置示例
  - 验证方法
  - 常见问题

- **MODE_SWITCH_IMPLEMENTATION_SUMMARY.md** - 本文档
  - 实现总结
  - 使用方法

### 6. 切换工具脚本
- **文件**: `switch_conversation_mode.sh`
- **功能**:
  - 快速切换配置
  - 显示推荐参数
  - 可选自动更新 IRv2.sh
  - 参数验证

---

## 🎯 使用方法

### 方法1: 使用切换脚本（最简单）

```bash
# 赋予执行权限（首次）
chmod +x switch_conversation_mode.sh

# 切换到多工具链式规划
./switch_conversation_mode.sh multi

# 切换到单工具迭代
./switch_conversation_mode.sh single
```

### 方法2: 手动修改配置

编辑 `examples/agent/IRv2.sh`:

```bash
# 多工具链式规划（推荐）
export AGENT_CONVERSATION_MODE="multi_tool_planning"
export USE_SINGLE_TURN_FORMAT=True  # 如果 max_turns=1
actor_rollout_ref.rollout.agent.max_turns=1
actor_rollout_ref.rollout.agent.single_response_max_tokens=10240

# 或

# 单工具迭代（实验性）
export AGENT_CONVERSATION_MODE="single_tool_iterative"
export USE_SINGLE_TURN_FORMAT=False
actor_rollout_ref.rollout.agent.max_turns=6
actor_rollout_ref.rollout.agent.single_response_max_tokens=4096
```

### 方法3: 临时环境变量

```bash
export AGENT_CONVERSATION_MODE="multi_tool_planning"
bash examples/agent/IRv2.sh
```

---

## 🔍 验证方法

### 检查模式是否生效

```bash
# 启动训练后，查看日志
grep "AGENT MODE" logs/*.log

# 应该看到
[AGENT MODE] Using conversation mode: multi_tool_planning
```

### 检查工具创建逻辑

```bash
grep "DEBUG CREATE_TOOLS.*模式" logs/*.log

# 应该看到
[DEBUG CREATE_TOOLS] T1-样本0 开始创建工具 (模式: multi_tool_planning)
```

### 检查单工具限制（仅在 single_tool_iterative 模式）

```bash
grep "ITERATIVE MODE" logs/*.log

# 应该看到（如果模型输出了多个工具）
[ITERATIVE MODE] T1-样本0 检测到3个工具，单工具迭代模式只使用第一个
```

---

## 📊 当前实现状态

| 功能模块 | 多工具链式规划 | 单工具迭代 |
|---------|--------------|-----------|
| 环境变量配置 | ✅ 完成 | ✅ 完成 |
| System Prompt | ✅ 完成 | ✅ 完成 |
| 工具数量控制 | ✅ 完成 | ✅ 完成（限制为1个） |
| 工具链式执行 | ✅ 完成 | ✅ 完成 |
| 从原图开始 | ✅ 完成 | N/A |
| 图像状态保持 | N/A | 🚧 需要实现 |
| 格式检查适配 | ✅ 完成 | ✅ 完成（复用多轮格式） |
| 动态User Prompt | N/A | 🚧 需要实现 |
| 数据集生成 | ✅ 已有 | 🚧 需要重新生成 |
| 完整测试 | ✅ 完成 | 🚧 需要测试 |

---

## 🎯 推荐配置

### 当前最佳实践

```bash
# IRv2.sh 配置
export AGENT_CONVERSATION_MODE="multi_tool_planning"
export USE_SINGLE_TURN_FORMAT=True
export USE_ENHANCED_FORMAT=False

# Rollout 配置
actor_rollout_ref.rollout.agent.max_turns=1
actor_rollout_ref.rollout.agent.single_response_max_tokens=10240
```

**原因**:
1. ✅ 多工具链式规划已完全实现和测试
2. ✅ 单轮模式训练效率高
3. ✅ 策略探索能力强
4. ✅ 避免累积误差

---

## 🚧 单工具迭代模式待完成功能

如果需要完整实现单工具迭代模式，需要添加以下功能：

### 1. ParallelEnv 状态管理

**位置**: `verl/workers/agent/parallel_env.py` - `ParallelEnv` 类

```python
class ParallelEnv:
    def __init__(self, ...):
        # 新增：跟踪每个样本的当前图像状态
        self.current_multi_modal_data_list = []
        self.processed_degradations_list = []  # 已处理的降质
        self.remaining_degradations_list = []  # 剩余的降质
    
    def reset(self, ...):
        # 初始化当前图像为原图
        self.current_multi_modal_data_list = deepcopy(self.origin_multi_modal_data_list)
        self.processed_degradations_list = [[] for _ in range(len(prompts))]
        self.remaining_degradations_list = [... for _ in range(len(prompts))]
    
    def step(self, ...):
        # 根据模式选择使用原图还是当前图
        if AGENT_CONVERSATION_MODE == 'single_tool_iterative':
            multi_modal_data = self.current_multi_modal_data_list[idx]
        else:
            multi_modal_data = self.origin_multi_modal_data_list[idx]
        
        # 工具执行后更新当前图像
        if AGENT_CONVERSATION_MODE == 'single_tool_iterative':
            self.current_multi_modal_data_list[idx] = result_image
            self.processed_degradations_list[idx].append(current_degradation)
            self.remaining_degradations_list[idx].remove(current_degradation)
```

### 2. 动态User Prompt生成

**位置**: `verl/workers/agent/parallel_env.py` - `execute_tool_call` 函数

```python
def execute_tool_call(...):
    if AGENT_CONVERSATION_MODE == 'single_tool_iterative':
        # 生成动态反馈prompt
        processed = env.processed_degradations_list[idx]
        remaining = env.remaining_degradations_list[idx]
        
        user_prompt = ConversationModePrompts.SINGLE_TOOL_ITERATIVE_USER_FEEDBACK.format(
            processed_degradations=', '.join(processed),
            remaining_degradations=', '.join(remaining)
        )
    else:
        user_prompt = ConversationModePrompts.MULTI_TOOL_PLANNING_USER_FEEDBACK.format(
            applied_sequence=' → '.join(tool_names)
        )
```

### 3. 格式检查增强

**位置**: `verl/utils/reward_score/image_restoration.py`

```python
def check_single_tool_format(response_str: str, mode: str = "multi_tool_planning"):
    """单工具迭代模式专用格式检查"""
    if mode == "single_tool_iterative":
        # 强制要求只有1个tool_call
        tool_calls = extract_tool_calls(response_str)
        if len(tool_calls) > 1:
            return -1.0  # 违规
    
    # 其他检查...
    return 1.0
```

### 4. 数据集重新生成

创建 `generate_iterative_dataset.py`:

```python
# 生成单工具迭代格式的数据
for sample in dataset:
    turns = []
    
    # Turn 1: 原图 + 所有降质
    turns.append({
        "role": "user",
        "content": f"Image with {degradations}",
        "image": original_image
    })
    
    # Turn 2-N: 逐步处理
    for degradation in optimal_order:
        turns.append({
            "role": "assistant",
            "content": f"<think>...</think><tool_call>[{{tool}}]</tool_call>"
        })
        turns.append({
            "role": "user",
            "content": f"Processed: {processed}, Remaining: {remaining}",
            "image": current_image
        })
    
    # Final: answer
    turns.append({
        "role": "assistant",
        "content": f"<think>...</think><answer>{{restoration_log}}</answer>"
    })
```

---

## 📝 代码修改位置总结

### 已修改
1. `examples/agent/IRv2.sh` - 第53, 108-141行
2. `verl/workers/agent/parallel_env.py` - 第4, 20-33, 208-221行
3. `verl/workers/agent/envs/mm_process_engine/ConversationModePrompts.py` - 新文件

### 新增文件
1. `CONVERSATION_MODE_GUIDE.md` - 完整指南
2. `QUICK_MODE_SWITCH.md` - 快速开始
3. `MODE_SWITCH_IMPLEMENTATION_SUMMARY.md` - 本文档
4. `switch_conversation_mode.sh` - 切换脚本
5. `verl/workers/agent/envs/mm_process_engine/ConversationModePrompts.py` - Prompt模板

### 待修改（单工具迭代完整实现）
1. `verl/workers/agent/parallel_env.py` - `ParallelEnv` 类状态管理
2. `verl/workers/agent/parallel_env.py` - `execute_tool_call` 函数
3. `verl/utils/reward_score/image_restoration.py` - 格式检查函数
4. 数据集生成脚本（新建）

---

## 🎉 成果

### 核心功能
✅ **完全可用的模式切换框架**
- 环境变量配置系统
- 两种模式的完整Prompt模板
- 基础执行逻辑（工具数量控制）
- 完整文档和使用指南
- 便捷切换工具

### 多工具链式规划模式
✅ **生产就绪**
- 完全实现并测试
- 支持单轮/多轮配置
- 从原图重新开始策略
- 格式检查完善

### 单工具迭代模式
🚧 **基础框架就绪**
- 环境变量检测 ✅
- 工具数量限制 ✅
- System Prompt ✅
- 状态管理 🚧
- 数据生成 🚧

---

## 📞 后续支持

如需实现单工具迭代模式的完整功能，可以按以下步骤进行：

1. **实现状态管理** - ParallelEnv 类
2. **动态Prompt生成** - execute_tool_call 函数
3. **数据集重新生成** - 新脚本
4. **充分测试** - 验证逐步传递逻辑

**当前建议**: 继续使用多工具链式规划模式，该模式已经非常成熟且高效。

---

**实现日期**: 2025-10-21
**版本**: v1.0
**状态**: 多工具规划模式完全可用，单工具迭代模式基础框架就绪

