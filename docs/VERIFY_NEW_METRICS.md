# 验证新指标是否正常工作

## 🎯 重要说明

**如果你看不到 `tool_count_match` 指标，是因为这是新代码！**

你需要**重新运行训练**才能看到这些新指标。

---

## ✅ 验证步骤

### 步骤1: 重新运行训练

```bash
cd /app/xiaominl/DeepEyes_v2
bash examples/agent/IRv2.sh
```

### 步骤2: 实时监控日志

在另一个终端：

```bash
# 方法1：实时查看日志
tail -f logs/your_experiment.log

# 方法2：grep 关键信息
tail -f logs/your_experiment.log | grep "TOOL STATS\|METRICS"
```

### 步骤3: 查找关键日志

训练开始后几分钟，应该看到：

#### ✅ 必须出现的日志

```bash
# 1. 模式确认
[AGENT MODE] 对话模式: multi_tool_planning

# 2. 退化类型提取
[TOOL STATS] 开始提取真实退化类型...
[TOOL STATS] 样本0: 真实退化类型 ['rain', 'haze'] (来源: reward_model)
[TOOL STATS] 样本1: 真实退化类型 ['noise', 'dark'] (来源: reward_model)

# 3. 工具调用收集
[TOOL STATS] 样本0 轮次1: 调用工具 ['mprnet_deraining', 'dehazeformer_dehaze']

# 4. 统计计算
[DEBUG STATS] tool_degradation_stats 返回了 62 个指标  ← 必须有！
[DEBUG STATS] 其中 tool_count_match/ 指标: 14 个  ← 必须有！
[DEBUG STATS] tool_count_match 指标示例: ['tool_count_match/deg2_less_ratio', ...]

# 5. 工具数量匹配详情
[TOOL STATS] 工具数量匹配统计（样本调用的工具数 vs 退化数量）:
[TOOL STATS]   2种退化的样本 (共45个):  ← 如果是0，说明数据集问题
[TOOL STATS]     少调用: 12/45 = 0.267
[TOOL STATS]     刚好: 28/45 = 0.622
[TOOL STATS]     多调用: 5/45 = 0.111

# 6. 指标收集确认
[METRICS] 收集了 48 个工具-退化匹配指标 + 14 个工具数量匹配指标  ← 必须有！
```

---

## 🔍 常见问题

### Q1: 看到 "2种退化的样本 (共0个)"

**原因：** 当前batch没有2种退化的样本

**检查：**
```bash
grep "真实退化类型" logs/*.log | awk '{print NF-3}' | sort | uniq -c
```

这会显示退化数量的分布。

**解决方案A：** 如果大部分是1种或4种退化，扩展统计范围

修改 `parallel_env.py` 第324-327行：
```python
tool_count_match_stats = {
    'deg1': {'less': 0, 'exact': 0, 'more': 0, 'total': 0},
    'deg2': {'less': 0, 'exact': 0, 'more': 0, 'total': 0},
    'deg3': {'less': 0, 'exact': 0, 'more': 0, 'total': 0},
    'deg4': {'less': 0, 'exact': 0, 'more': 0, 'total': 0},
}
```

并在第376行附近添加对应的统计逻辑。

**解决方案B：** 等待更多batches，可能后续batch会有

---

### Q2: 日志中没有 "[DEBUG STATS]" 输出

**原因：** 代码没有被执行

**检查：**
1. 确认你使用的是修改后的代码
2. 确认 `activate_agent=True`
3. 检查是否有Python异常

**验证代码版本：**
```bash
grep -n "tool_count_match_stats = {" /app/xiaominl/DeepEyes_v2/verl/workers/agent/parallel_env.py
```

应该显示行号（如果有，说明代码已更新）

---

### Q3: 指标在日志中有，但WandB上没有

**原因：** 可能是WandB同步延迟

**检查：**
1. 等待几分钟，WandB有时会延迟
2. 刷新WandB页面
3. 检查WandB run是否在运行（没有crashed）

**验证：**
- 在WandB搜索栏输入：`tool_count_match/`
- 检查其他指标是否正常（如 `tool_match/`）
- 查看 Console Logs 是否有错误

---

## 🧪 简单测试方法

### 最小化测试

运行一个很小的测试：

```bash
# 修改 IRv2.sh
data.train_batch_size=8        # 减小batch
trainer.total_epochs=1         # 只跑1个epoch
trainer.save_freq=-1           # 不保存
trainer.test_freq=-1           # 不测试

# 运行
bash examples/agent/IRv2.sh 2>&1 | tee test_metrics.log

# 立即检查
grep "tool_count_match" test_metrics.log
```

---

## 📊 预期的完整日志流程

```bash
# === Step 1: Rollout ===
[AGENT MODE] 对话模式: multi_tool_planning
[TOOL STATS] 样本0 轮次1: 调用工具 ['mprnet_deraining', 'dehazeformer_dehaze']
...

# === Step 2: 统计计算 ===
[TOOL STATS] 开始提取真实退化类型...
[TOOL STATS] 样本0: 真实退化类型 ['rain', 'haze'] (来源: reward_model)
...
[TOOL STATS] 开始计算工具-退化匹配统计...
[TOOL STATS] 统计模式: multi_tool_planning
[TOOL STATS] 样本数量: 32

# === Step 3: 统计结果 ===
[TOOL STATS] === 工具-退化匹配统计（批次级别）===
[TOOL STATS] 不重复统计（只要调用了对应工具就算，样本级别）:
[TOOL STATS]   rain: 28/30 = 0.933
...

[TOOL STATS] 重复统计（样本中任何工具被调用≥2次）:
[TOOL STATS]   rain: 15/30 = 0.500
...

[TOOL STATS] 工具数量匹配统计（样本调用的工具数 vs 退化数量）:
[TOOL STATS]   2种退化的样本 (共18个):  ← 关键！
[TOOL STATS]     少调用: 5/18 = 0.278
[TOOL STATS]     刚好: 12/18 = 0.667
[TOOL STATS]     多调用: 1/18 = 0.056
[TOOL STATS]   3种退化的样本 (共10个):  ← 关键！
[TOOL STATS]     少调用: 4/10 = 0.400
[TOOL STATS]     刚好: 5/10 = 0.500
[TOOL STATS]     多调用: 1/10 = 0.100

# === Step 4: 转换为tensor ===
[DEBUG STATS] tool_degradation_stats 返回了 62 个指标  ← 关键！
[DEBUG STATS] 其中 tool_count_match/ 指标: 14 个  ← 关键！
[DEBUG STATS] tool_count_match 指标示例: ['tool_count_match/deg2_less_ratio', 'tool_count_match/deg2_exact_ratio', ...]

# === Step 5: 收集指标 ===
[METRICS] 收集了 48 个工具-退化匹配指标 + 14 个工具数量匹配指标  ← 关键！

# === Step 6: 上传到WandB ===
(WandB自动上传，无特殊日志)
```

---

## 🎯 确认清单

运行新训练后，检查以下内容：

- [ ] 日志中有 `[DEBUG STATS] 其中 tool_count_match/ 指标: 14 个`
- [ ] 日志中有 `2种退化的样本 (共X个)` 且 X > 0
- [ ] 日志中有 `[METRICS] 收集了 ... + 14 个工具数量匹配指标`
- [ ] WandB中可以搜索到 `tool_count_match/deg2_exact_ratio`

如果前3个都有，但WandB上没有，那是WandB同步问题（等待或刷新）。

如果前3个都没有，说明代码没有运行到（检查异常或配置）。

---

## 💡 总结

**你看不到指标的原因很可能是：**

1. **代码刚修改，还没重新运行训练** ← 最可能
2. **数据集中没有2种或3种退化的样本** ← 次可能
3. **WandB同步延迟** ← 不太可能

**建议：**

重新运行训练，然后：
1. 检查日志是否有上述关键输出
2. 如果有，等待WandB同步（1-5分钟）
3. 如果日志中显示 "共0个"，扩展统计范围支持更多退化数量

---

## 📞 需要帮助？

如果重新运行后还是看不到，请提供：
1. 最新的训练日志（grep "TOOL STATS" 的输出）
2. 数据集的退化分布情况
3. WandB run的URL

我会帮你进一步诊断！

