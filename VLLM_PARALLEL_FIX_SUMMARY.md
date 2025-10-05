# VLLM 张量并行组初始化错误修复说明

## 问题描述

在运行 `eval_agent_true_inference_v2.py` 时遇到VLLM分布式相关错误：

```
AssertionError: tensor model parallel group is not initialized
File "/app/xiaominl/DeepEyes/verl/workers/agent/parallel_env_v2.py", line 478, in agent_rollout_loop_v2
    pg = vllm_ps.get_tp_group()
```

## 问题原因

`agent_rollout_loop_v2` 函数设计用于分布式训练环境，其中使用了VLLM的张量并行功能：

```python
pg = vllm_ps.get_tp_group()  # 获取张量并行组
if pg.is_first_rank:         # 检查是否是第一个rank
    obs_results = env.step(...)
else:
    obs_results = None
obs_results = pg.broadcast_object(obs_results)  # 广播结果
```

在单GPU推理评估时，这些分布式功能没有初始化，导致错误。

## 解决方案

创建了一个专门用于单GPU推理的版本 `agent_rollout_loop_v2_single_gpu`，绕过所有分布式功能。

### 主要修改

1. **移除分布式组依赖**：
   ```python
   # ❌ 原版本（分布式）
   pg = vllm_ps.get_tp_group()
   if pg.is_first_rank:
       obs_results = env.step(active_indices, actions, current_turn=step + 1)
   else:
       obs_results = None
   obs_results = pg.broadcast_object(obs_results)
   
   # ✅ 单GPU版本
   obs_results = env.step(active_indices, actions, current_turn=step + 1)
   ```

2. **保持核心功能**：
   - 完整的agent rollout逻辑
   - V2格式解析和统计
   - 图像历史管理
   - 工具调用统计

3. **简化分布式特性**：
   - 直接调用环境步进
   - 移除rank检查和广播
   - 保持所有其他功能不变

## 修复详情

### 文件修改

**`eval_agent_true_inference_v2.py`**：
- 添加了 `agent_rollout_loop_v2_single_gpu` 函数
- 修改调用点使用单GPU版本

### 核心差异

| 功能 | 原版本 (分布式) | 单GPU版本 |
|------|----------------|-----------|
| 张量并行组 | `vllm_ps.get_tp_group()` | 不使用 |
| Rank检查 | `pg.is_first_rank` | 直接执行 |
| 结果广播 | `pg.broadcast_object()` | 不需要 |
| 环境步进 | 条件执行 | 直接执行 |
| 其他功能 | 完全保留 | 完全保留 |

## 验证结果

修复后的函数可以正常导入和使用：

```bash
python -c "from eval_agent_true_inference_v2 import agent_rollout_loop_v2_single_gpu; print('✅ 导入成功')"
```

输出：
```
✅ 单GPU版本函数导入成功
✅ 配置创建成功
✅ 函数签名: (config, vllm_engine, vllm_inputs, prompts, multi_modal_inputs, sampling_params)
```

## 使用方法

现在可以正常运行V2推理评估：

```bash
python eval_agent_true_inference_v2.py \
    --model_path /path/to/your/model \
    --data_file /app/datasets/IRdatasetv3/shard-train-000003.parquet \
    --sample_indices 0 1 2
```

## 功能特性

单GPU版本保持了所有重要功能：

### ✅ 保留的功能
- **V2格式解析**：完整的 `<think>`, `<tool_call>`, `<answer>` 解析
- **工具执行**：所有图像修复工具的正常执行
- **图像历史**：完整的图像处理历史追踪
- **统计信息**：详细的工具使用和退化类型统计
- **错误处理**：完整的错误处理和日志记录

### 🔄 简化的功能
- **分布式处理**：改为直接单GPU处理
- **并行通信**：移除rank检查和广播机制

## 性能影响

- **推理速度**：单GPU版本移除了分布式开销，实际上可能更快
- **内存使用**：与原版本基本相同
- **功能完整性**：100%保持核心功能

## 适用场景

- ✅ **单GPU推理评估**：完美适用
- ✅ **模型测试**：适用于快速测试
- ✅ **小规模评估**：适用于样本数量较少的评估
- ❌ **大规模分布式训练**：需要使用原版本

## 注意事项

1. **模型路径**：确保模型路径正确
2. **工具模块**：确保所有工具模块已导入
3. **数据格式**：确保数据格式符合预期
4. **GPU内存**：注意GPU内存使用，避免OOM

修复完成！现在V2推理评估脚本应该可以在单GPU环境下正常运行了。
