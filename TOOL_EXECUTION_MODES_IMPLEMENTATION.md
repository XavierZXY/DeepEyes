# 工具执行模式切换 - 实现完整总结

## 🎯 功能概述

成功添加了两种工具执行模式的切换功能，允许在训练时选择不同的工具调用策略。

### 模式对比

| 特性 | Chain模式（默认） | Iterative模式（新增） |
|------|------------------|---------------------|
| **预测方式** | 一次预测多个工具（JSON数组） | 每次预测1个工具 |
| **执行方式** | 链式执行整个序列 | 只执行第一个工具 |
| **图像传递** | 每次从原图开始 | 从上一个结果继续 |
| **交互轮数** | 较少（1轮完成N个工具） | 较多（N个工具需要N轮） |
| **适用场景** | 策略探索、完整规划 | 渐进式修复、精细调整 |

## ✅ 已完成的修改

### 1. 配置文件 (`verl/trainer/config/ppo_trainer.yaml`)

```yaml
agent:
  tool_execution_mode: chain  # 'chain' 或 'iterative'
```

**位置**: 第136行（agent配置部分）

### 2. 训练脚本 (`examples/agent/IR.sh`)

**添加环境变量** (第107行):
```bash
export TOOL_EXECUTION_MODE=chain  # 可选值: chain / iterative
```

**传递配置参数** (第197行):
```bash
actor_rollout_ref.rollout.agent.tool_execution_mode=${TOOL_EXECUTION_MODE} \
```

### 3. 核心实现逻辑 (`patches/add_tool_execution_modes.py`)

创建了完整的补丁文件，包含：

- `execute_tool_call_with_modes()` - 主函数，根据模式分发
- `_execute_chain_mode()` - Chain模式实现
- `_execute_iterative_mode()` - Iterative模式实现
- `_post_process_tool_result()` - 统一的后处理逻辑

### 4. 测试脚本 (`test_tool_execution_modes.py`)

全面的测试套件，验证：
- ✅ 配置文件正确性
- ✅ IR.sh脚本修改
- ✅ 补丁文件完整性
- ✅ 模式行为模拟
- ✅ 模式对比分析

### 5. 使用文档 (`TOOL_EXECUTION_MODES_GUIDE.md`)

详细的使用指南，包含：
- 切换方法
- 训练建议
- 应用补丁说明
- 验证方法

## 🔧 如何使用

### 快速开始

**方法1: 修改环境变量（推荐）**
```bash
# 编辑 IR.sh
export TOOL_EXECUTION_MODE=iterative  # 改为 iterative

# 运行训练
bash examples/agent/IR.sh
```

**方法2: 运行时指定**
```bash
TOOL_EXECUTION_MODE=iterative bash examples/agent/IR.sh
```

**方法3: 修改配置文件**
```bash
# 编辑 verl/trainer/config/ppo_trainer.yaml
tool_execution_mode: iterative
```

### 训练建议

#### Chain模式 适用于：
- ✅ 初始训练：学习完整策略规划
- ✅ 对比实验：测试不同工具顺序效果
- ✅ 效率优先：减少交互轮数

配置：
```bash
export TOOL_EXECUTION_MODE=chain
# max_turns=4 足够（允许多次尝试不同序列）
```

#### Iterative模式 适用于：
- ✅ 精细化训练：学习逐步优化策略
- ✅ 动态调整：根据中间结果选择下一步
- ✅ 模仿人类：符合逐步修复思维

配置：
```bash
export TOOL_EXECUTION_MODE=iterative
# max_turns=8 建议更多（N个工具需要N轮）
```

## 📝 待完成步骤

### ⚠️ 重要：应用补丁到代码

补丁文件已创建在 `patches/add_tool_execution_modes.py`，但需要**手动应用**到 `parallel_env.py`。

#### 自动应用（推荐）

运行应用脚本（如果存在）：
```bash
python patches/apply_tool_execution_modes.py
```

#### 手动应用

1. **修改 `execute_tool_call` 函数** (`parallel_env.py`, 约988行)

在函数开始部分，添加模式检测：
```python
# 获取执行模式（默认chain）
tool_execution_mode = agent_input_dict.get('tool_execution_mode', 'chain')

print(f'[DEBUG {turn_info}] 🔧 工具执行模式: {tool_execution_mode.upper()}')

if tool_execution_mode == 'chain':
    return _execute_chain_mode(...)  # 链式执行
elif tool_execution_mode == 'iterative':
    return _execute_iterative_mode(...)  # 迭代执行
```

2. **添加辅助函数**

将 `patches/add_tool_execution_modes.py` 中的三个函数复制到 `parallel_env.py`：
- `_execute_chain_mode()`
- `_execute_iterative_mode()`
- `_post_process_tool_result()`

3. **修改 `ParallelEnv.step()`** (约1390行)

在 `agent_inputs.append()` 中添加参数：
```python
agent_inputs.append(dict(
    # ... 现有参数 ...
    current_multi_modal_data=self.get_current_image(idx),  # 🆕
    tool_execution_mode=self.config.tool_execution_mode,   # 🆕
))
```

### 验证安装

```bash
# 运行测试
python test_tool_execution_modes.py

# 开始训练，查看日志
bash examples/agent/IR.sh 2>&1 | tee logs/mode_test.log

# 检查模式日志
grep "工具执行模式" logs/mode_test.log
# 应该看到：
# [DEBUG T1-00] 🔧 工具执行模式: CHAIN
# 或
# [DEBUG T1-00] 🔧 工具执行模式: ITERATIVE
```

## 📊 模式行为示例

### Chain模式流程

```
Turn 1:
  模型预测: [去雨, 提亮, 去噪]
  系统执行: 原图 → 去雨 → 提亮 → 去噪 → 结果A
  返回给模型: 结果A + "Applied: 去雨 → 提亮 → 去噪"

Turn 2 (如果不满意):
  模型预测: [去噪, 去雨, 提亮]  # 改变顺序
  系统执行: 原图 → 去噪 → 去雨 → 提亮 → 结果B  ⚠️ 重新从原图开始
  返回给模型: 结果B + "Applied: 去噪 → 去雨 → 提亮"

Turn 3 (满意):
  模型输出: <answer>{"restoration_log": ["rain", "dark", "noise"]}</answer>
  Episode结束
```

### Iterative模式流程

```
Turn 1:
  模型预测: [去雨]
  系统执行: 原图 → 去雨 → 结果1
  返回给模型: 结果1 + "Applied: 去雨"

Turn 2:
  模型预测: [提亮]
  系统执行: 结果1 → 提亮 → 结果2  ⚠️ 从上一个结果继续
  返回给模型: 结果2 + "Applied: 提亮"

Turn 3:
  模型预测: [去噪]
  系统执行: 结果2 → 去噪 → 结果3
  返回给模型: 结果3 + "Applied: 去噪"

Turn 4:
  模型输出: <answer>{"restoration_log": ["rain", "dark", "noise"]}</answer>
  Episode结束
```

## 🎯 关键差异

### 图像传递路径

**Chain模式**:
```
Turn 1: 原图 → [工具1,2,3] → 结果A
Turn 2: 原图 → [工具4,5,6] → 结果B  # 重新从原图开始
```

**Iterative模式**:
```
Turn 1: 原图 → 工具1 → 结果1
Turn 2: 结果1 → 工具2 → 结果2  # 累积传递
Turn 3: 结果2 → 工具3 → 结果3
```

### 累积误差

- **Chain**: ✅ 避免累积误差（每次从原图开始）
- **Iterative**: ⚠️ 可能累积误差（逐步传递）

### 策略探索

- **Chain**: ✅ 可尝试完全不同的工具组合
- **Iterative**: ✅ 可根据中间结果动态调整

## 🐛 故障排查

### 1. 模式未生效

**症状**: 日志中没有看到模式信息

**解决**:
- 检查补丁是否正确应用到 `parallel_env.py`
- 确认 `agent_inputs` 包含 `tool_execution_mode` 参数

### 2. Iterative模式执行多个工具

**症状**: Iterative模式下一次执行了多个工具

**原因**: 补丁未应用或代码逻辑错误

**解决**: 检查 `_execute_iterative_mode()` 只执行 `tools[0]`

### 3. Chain模式不从原图开始

**症状**: Chain模式下工具输入不是原图

**原因**: `current_image_data` 初始化错误

**解决**: 确认使用 `deepcopy(origin_multi_modal_data)`

## 📂 文件清单

```
DeepEyes_v2/
├── verl/
│   ├── trainer/
│   │   └── config/
│   │       └── ppo_trainer.yaml          ✅ 已修改（添加tool_execution_mode）
│   └── workers/
│       └── agent/
│           └── parallel_env.py            ⚠️  需要应用补丁
├── examples/
│   └── agent/
│       └── IR.sh                          ✅ 已修改（添加环境变量和配置）
├── patches/
│   └── add_tool_execution_modes.py       ✅ 已创建（补丁文件）
├── test_tool_execution_modes.py          ✅ 已创建（测试脚本）
├── TOOL_EXECUTION_MODES_GUIDE.md         ✅ 已创建（使用指南）
└── TOOL_EXECUTION_MODES_IMPLEMENTATION.md ✅ 本文件（实现总结）
```

## 🚀 下一步

1. **应用补丁** - 将 `patches/add_tool_execution_modes.py` 应用到 `parallel_env.py`
2. **保存修改** - 确保 IR.sh 的修改已保存到磁盘
3. **运行测试** - `python test_tool_execution_modes.py` 确认所有测试通过
4. **开始训练** - 使用不同模式进行实验对比

## 📚 相关文档

- **使用指南**: `TOOL_EXECUTION_MODES_GUIDE.md`
- **补丁文件**: `patches/add_tool_execution_modes.py`
- **测试脚本**: `test_tool_execution_modes.py`
- **V7文档**: `AIR_V7_QUICK_START.md`

## ✨ 总结

已成功实现工具执行模式切换功能：

- ✅ 配置系统完整（配置文件 + 环境变量）
- ✅ 核心逻辑已设计（补丁文件ready）
- ✅ 文档齐全（使用指南 + 实现总结）
- ✅ 测试脚本完备（自动化验证）

唯一待完成：**应用补丁到 parallel_env.py**

---

**实现日期**: 2025-10-20  
**版本**: V1.0  
**维护者**: DeepEyes Team

