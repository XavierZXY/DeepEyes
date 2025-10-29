# ⚠️ 重要：下一步操作指南

## 🎯 为什么 WandB 上没有 tool_count_match？

### 答案：**因为这是刚刚添加的新功能！**

你当前看到的 WandB 数据是用**旧代码**训练的结果。

---

## ✅ 要看到新指标，需要这样做：

### 1️⃣ 停止当前训练（如果在运行）

```bash
# 找到训练进程
ps aux | grep main_ppo

# 停止（如果需要）
kill <PID>
```

### 2️⃣ 重新运行训练

```bash
cd /app/xiaominl/DeepEyes_v2
bash examples/agent/IRv2.sh
```

### 3️⃣ 监控日志，确认新功能生效

```bash
# 新开一个终端，实时查看
tail -f logs/debug_for_AIR_multideg_plan_ref_bs32_n4_spv13_lr5e-7_datarand_mi300.log

# 或者在训练日志中搜索
grep "TOOL STATS\|tool_count_match" logs/*.log
```

### 4️⃣ 等待几分钟，查看 WandB

- 打开你的 WandB 项目
- 找到**新的 run**（不是旧的run）
- 搜索 `tool_count_match/`
- 应该能看到14个新指标

---

## 📊 新代码vs旧代码的区别

### 旧代码（修改前）

```python
# 没有以下功能：
- ❌ 双模式对话系统
- ❌ 工具链式传递修复
- ❌ tool_count_match 统计
- ❌ 详细的工具调用日志
```

### 新代码（修改后）

```python
# 新增功能：
- ✅ 双模式对话系统（AGENT_CONVERSATION_MODE）
- ✅ 工具链式传递修复
- ✅ 62个新指标（48个 tool_match + 14个 tool_count_match）
- ✅ 详细的调试日志
```

---

## 🎨 WandB 对比

### 旧 run（修改前训练的）

```
可用指标：
├─ reward/*
├─ agent/tool_call_*
└─ critic/*

缺少：
├─ tool_match/*  ← 可能也没有
└─ tool_count_match/*  ← 肯定没有
```

### 新 run（修改后训练的）

```
可用指标：
├─ reward/*
├─ agent/tool_call_*
├─ critic/*
├─ tool_match/*  ← 48个指标
└─ tool_count_match/*  ← 14个指标（新增）
```

---

## 🔍 验证新代码已就绪

### 检查代码文件

```bash
# 检查关键修改是否存在
grep -n "tool_count_match_stats = {" /app/xiaominl/DeepEyes_v2/verl/workers/agent/parallel_env.py

# 应该输出类似：
# 324:    tool_count_match_stats = {
```

如果有输出，说明代码已更新 ✅

### 检查metric收集

```bash
grep -n "tool_count_match_keys" /app/xiaominl/DeepEyes_v2/verl/trainer/ppo/metric_utils.py

# 应该输出类似：
# 214:    tool_count_match_keys = [key for key in batch.batch.keys() if key.startswith('tool_count_match/')]
```

如果有输出，说明收集逻辑已添加 ✅

---

## 📝 重新训练检查清单

运行新训练后，**必须看到**的日志：

### ✅ 第1个必看日志（启动时）

```
[AGENT MODE] 对话模式: multi_tool_planning
```

**如果没有：** 环境变量没有正确读取

---

### ✅ 第2个必看日志（每个step）

```
[DEBUG STATS] tool_degradation_stats 返回了 62 个指标
[DEBUG STATS] 其中 tool_count_match/ 指标: 14 个
```

**如果没有：** 统计函数没有执行（检查agent是否激活）

---

### ✅ 第3个必看日志（每个step）

```
[TOOL STATS] 工具数量匹配统计（样本调用的工具数 vs 退化数量）:
[TOOL STATS]   2种退化的样本 (共18个):
[TOOL STATS]     刚好: 12/18 = 0.667
```

**如果显示 "共0个"：** 数据集问题，需要扩展统计范围

---

### ✅ 第4个必看日志（每个step）

```
[METRICS] 收集了 48 个工具-退化匹配指标 + 14 个工具数量匹配指标
```

**如果没有：** 指标收集有问题

---

## 🚀 快速行动方案

### 方案A：立即重新训练（推荐）

```bash
# 1. 确认代码已更新
ls -l /app/xiaominl/DeepEyes_v2/docs/TOOL_COUNT_MATCHING_STATS.md
# 如果文件存在，说明代码已更新

# 2. 重新运行训练
cd /app/xiaominl/DeepEyes_v2
bash examples/agent/IRv2.sh 2>&1 | tee logs/new_run_$(date +%Y%m%d_%H%M%S).log

# 3. 实时监控（新终端）
tail -f logs/new_run_*.log | grep "tool_count_match\|TOOL STATS"
```

### 方案B：检查数据集分布

```bash
# 查看你的数据集中退化数量的分布
# 需要用你自己的数据分析脚本
```

如果大部分样本是1种或4种退化，告诉我，我会扩展统计范围。

---

## ⏰ 预期时间线

```
T+0min:  开始运行训练
T+2min:  第一个step完成，应该看到日志
T+5min:  WandB开始显示数据
T+10min: WandB指标稳定显示

如果10分钟后还没有，说明有问题
```

---

## 📞 如果还是看不到

请提供以下信息：

1. **新训练的日志片段**：
   ```bash
   grep -A 20 "TOOL STATS.*工具数量匹配" logs/new_run_*.log
   ```

2. **数据样本示例**：
   ```bash
   grep "真实退化类型" logs/new_run_*.log | head -10
   ```

3. **指标收集日志**：
   ```bash
   grep "METRICS.*收集了" logs/new_run_*.log | head -5
   ```

我会根据这些信息帮你诊断！

---

## ✅ 总结

**当前情况：** 你看的是旧训练的WandB，那个训练用的是旧代码

**解决方法：** 重新运行训练，使用修改后的代码

**验证方法：** 检查日志中的4个关键输出

**预期结果：** 新run的WandB上会有 tool_count_match 指标

🚀 **重新运行训练即可！**

