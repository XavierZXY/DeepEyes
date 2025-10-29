# 修复 low resolution 指标为0的问题

## 🔍 问题诊断

### 发现

你的日志显示：
```
[TOOL STATS] 不重复统计（样本级别）:  ← 旧版本文本
[TOOL STATS] === 统计完成 ===
```

但新代码的输出应该是：
```
[TOOL STATS] 不重复统计（只要调用了对应工具就算，样本级别）:  ← 新版本文本
[TOOL STATS]   rain: 28/30 = 0.933
[TOOL STATS]   low resolution: 8/8 = 1.000  ← 应该有这行
```

## ❌ 根本原因

**你运行的训练还在使用旧代码！**

---

## ✅ 解决方案

### 步骤1: 确认代码已更新

```bash
# 检查关键新增代码
grep -n "只要调用了对应工具就算" /app/xiaominl/DeepEyes_v2/verl/workers/agent/parallel_env.py

# 应该输出：
# 425:    print(f"[TOOL STATS] 不重复统计（只要调用了对应工具就算，样本级别）:")
```

✅ 如果有输出 → 代码已更新
❌ 如果没有输出 → 代码文件有问题

---

### 步骤2: 停止旧训练

```bash
# 找到正在运行的训练进程
ps aux | grep "main_ppo\|python.*verl" | grep -v grep

# 停止旧进程
kill <PID>
```

---

### 步骤3: 清理 Python 缓存

**重要！** Python 可能缓存了旧的 .pyc 文件

```bash
cd /app/xiaominl/DeepEyes_v2

# 清理所有 .pyc 和 __pycache__
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo "缓存已清理"
```

---

### 步骤4: 重新运行训练

```bash
cd /app/xiaominl/DeepEyes_v2
bash examples/agent/IRv2.sh 2>&1 | tee logs/new_metrics_test_$(date +%Y%m%d_%H%M%S).log
```

---

### 步骤5: 验证新代码生效

在日志中搜索：

```bash
# 验证1: 新文本出现
grep "只要调用了对应工具就算" logs/new_metrics_test_*.log

# 验证2: 有 low resolution 统计
grep "low resolution:" logs/new_metrics_test_*.log | head -10

# 验证3: 有 tool_count_match 指标
grep "tool_count_match/ 指标:" logs/new_metrics_test_*.log
```

**必须看到：**
```
[TOOL STATS] 不重复统计（只要调用了对应工具就算，样本级别）:  ← 新文本
[TOOL STATS]   low resolution: 8/8 = 1.000  ← 有统计
[DEBUG STATS] 其中 tool_count_match/ 指标: 14 个  ← 有新指标
```

---

## 🐛 为什么会用旧代码？

### 可能原因1: Python 缓存

Python 会缓存编译后的 .pyc 文件，即使你修改了 .py 文件：

```bash
# 旧的 .pyc 文件可能还在
ls -la verl/workers/agent/__pycache__/parallel_env.*.pyc
```

**解决：** 清理缓存（见步骤3）

---

### 可能原因2: Ray 使用了旧的 worker

如果使用 Ray，worker 可能还在运行旧代码：

```bash
# 查看 Ray 状态
ray status

# 停止所有 Ray 进程
ray stop

# 清理 Ray 临时文件
rm -rf /tmp/ray/* 2>/dev/null
rm -rf $RAY_TMPDIR/* 2>/dev/null
```

**解决：** 重启 Ray

---

### 可能原因3: 代码文件没有保存

检查文件修改时间：

```bash
ls -l /app/xiaominl/DeepEyes_v2/verl/workers/agent/parallel_env.py
ls -l /app/xiaominl/DeepEyes_v2/verl/trainer/ppo/metric_utils.py
```

应该显示最近的修改时间（今天）。

---

## 🎯 完整的重启方案

```bash
#!/bin/bash

echo "=== 步骤1: 停止所有训练 ==="
pkill -f "main_ppo"
pkill -f "verl.trainer"
sleep 2

echo "=== 步骤2: 停止 Ray ==="
ray stop
sleep 2

echo "=== 步骤3: 清理缓存 ==="
cd /app/xiaominl/DeepEyes_v2
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
rm -rf /tmp/ray/* 2>/dev/null

echo "=== 步骤4: 验证代码版本 ==="
grep -n "只要调用了对应工具就算" verl/workers/agent/parallel_env.py
grep -n "tool_count_match_keys" verl/trainer/ppo/metric_utils.py

echo "=== 步骤5: 重新运行训练 ==="
bash examples/agent/IRv2.sh 2>&1 | tee logs/clean_restart_$(date +%Y%m%d_%H%M%S).log
```

保存为 `restart_training.sh` 并运行：

```bash
chmod +x restart_training.sh
./restart_training.sh
```

---

## 🔍 验证清单

新训练开始后，检查日志：

### ✅ 第1步: 检查代码版本标识

```bash
grep "只要调用了对应工具就算" logs/clean_restart_*.log
```

**必须有输出！** 如果没有，说明还是旧代码。

---

### ✅ 第2步: 检查统计输出

```bash
grep -A 20 "不重复统计.*只要调用了对应工具就算" logs/clean_restart_*.log | head -30
```

**必须看到：**
```
[TOOL STATS] 不重复统计（只要调用了对应工具就算，样本级别）:
[TOOL STATS]   rain: X/X = X.XXX
[TOOL STATS]   haze: X/X = X.XXX
[TOOL STATS]   low resolution: X/X = X.XXX  ← 必须有！
...
```

---

### ✅ 第3步: 检查新指标

```bash
grep "tool_count_match/ 指标" logs/clean_restart_*.log
```

**必须看到：**
```
[DEBUG STATS] 其中 tool_count_match/ 指标: 14 个
```

---

## 📊 预期的完整日志（新代码）

```bash
[AGENT MODE] 对话模式: multi_tool_planning

[TOOL STATS] 样本0: 真实退化类型 ['low resolution', 'jpeg compression artifact']
[TOOL STATS] 样本0 轮次1: 调用工具 ['swinir_super_resolution', 'fbcnn_jpeg_artifact_removal']

[TOOL STATS] === 工具-退化匹配统计（批次级别）===

[TOOL STATS] 不重复统计（只要调用了对应工具就算，样本级别）:  ← 新文本！
[TOOL STATS]   defocus blur: 8/8 = 1.000
[TOOL STATS]   noise: 4/4 = 1.000
[TOOL STATS]   low resolution: 16/16 = 1.000  ← 应该有！
[TOOL STATS]   jpeg compression artifact: 8/8 = 1.000

[TOOL STATS] 重复统计（样本中任何工具被调用≥2次）:
[TOOL STATS]   low resolution: 8/16 = 0.500

[TOOL STATS] 工具数量匹配统计（样本调用的工具数 vs 退化数量）:
[TOOL STATS]   2种退化的样本 (共16个):  ← 新功能！
[TOOL STATS]     刚好: 12/16 = 0.750

[DEBUG STATS] tool_degradation_stats 返回了 62 个指标  ← 新日志！
[DEBUG STATS] 其中 tool_count_match/ 指标: 14 个  ← 新日志！

[METRICS] 收集了 48 个工具-退化匹配指标 + 14 个工具数量匹配指标  ← 新日志！
```

---

## ✅ 总结

### 问题根源

你的训练还在运行**旧代码**（可能是 Python 缓存或 Ray worker 的问题）

### 解决方案

1. 停止所有训练和 Ray
2. 清理 Python 缓存
3. 重新运行训练
4. 验证日志中有新的输出格式

### 关键验证点

看到这行就说明新代码生效了：
```
[TOOL STATS] 不重复统计（只要调用了对应工具就算，样本级别）:
```

注意"**只要调用了对应工具就算**"这几个字，旧代码没有这个！

---

## 🚀 立即行动

```bash
# 一键清理并重启
ray stop
find /app/xiaominl/DeepEyes_v2 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
bash /app/xiaominl/DeepEyes_v2/examples/agent/IRv2.sh
```

然后检查新日志！🎯


