# 工具执行模式切换指南


## 🚀 如何切换模式

### 方法1: 修改 IR.sh 脚本

打开 `examples/agent/IR.sh`，找到：

```bash
export TOOL_EXECUTION_MODE=chain  # 可选值: chain / iterative
```

修改为：
- `chain`     - 链式执行模式（默认，V7模式）
- `iterative` - 迭代执行模式（新增）

### 方法2: 运行时指定

```bash
TOOL_EXECUTION_MODE=iterative bash examples/agent/IR.sh
```

### 方法3: 直接修改配置文件

编辑 `verl/trainer/config/ppo_trainer.yaml`:

```yaml
actor_rollout_ref:
  rollout:
    agent:
      tool_execution_mode: iterative  # 或 chain
```

## 📊 训练建议

### Chain 模式 (推荐用于)
- 初始训练阶段：让模型学习完整策略规划
- 对比实验：测试不同工具顺序的效果
- 效率优先：减少交互轮数，加快训练

配置建议：
```bash
export TOOL_EXECUTION_MODE=chain
actor_rollout_ref.rollout.agent.max_turns=4  # 允许多次尝试不同序列
```

### Iterative 模式 (推荐用于)
- 精细化训练：学习逐步优化策略
- 动态调整：根据中间结果选择下一步
- 模仿人类：符合人类逐步修复思维

配置建议：
```bash
export TOOL_EXECUTION_MODE=iterative
actor_rollout_ref.rollout.agent.max_turns=8  # 需要更多轮数完成任务
```

## 🔧 应用补丁

补丁文件位于: `patches/add_tool_execution_modes.py`

**重要**: 需要手动将补丁应用到 `verl/workers/agent/parallel_env.py`

1. 打开 `parallel_env.py`
2. 找到 `execute_tool_call` 函数（约988行）
3. 按照补丁文件中的说明添加代码
4. 在 `ParallelEnv.step()` 中添加模式参数传递

或者运行自动应用脚本（如果有）。

## ✅ 验证安装

运行测试脚本：
```bash
python test_tool_execution_modes.py
```

查看日志确认模式：
```bash
# 训练时应该看到
[DEBUG T1-00] 🔧 工具执行模式: CHAIN
# 或
[DEBUG T1-00] 🔧 工具执行模式: ITERATIVE
```
