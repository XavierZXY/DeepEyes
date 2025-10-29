# 工具-退化匹配统计 - 快速参考

## 📊 统计指标总览

### 48个新指标（8个退化类型 × 6个指标）

```
tool_match/
├─ rain_repeat_ratio          # 重复统计：调用次数/退化次数
├─ rain_repeat_count          # 对应工具调用总次数
├─ rain_total_count           # rain退化出现总次数
├─ rain_unique_ratio          # 不重复统计：匹配样本/总样本
├─ rain_unique_matched        # 调用过对应工具的样本数
├─ rain_unique_total          # 有rain的样本总数
├─ haze_repeat_ratio
├─ haze_repeat_count
├─ ... (共48个)
```

---

## ✅ 统计逻辑（核心）

### 原则1：只统计真实存在的退化

```python
样本A: 真实退化=['rain', 'haze']
→ 统计 rain 和 haze 的指标

样本B: 真实退化=['noise']
→ 统计 noise 的指标

样本C: 真实退化=[] 或 'clean'
→ 跳过，不参与任何统计
```

### 原则2：从 reward_model/env_name 获取

```python
# 优先
reward_model = [
    {'degradation_type': 'rain', ...},
    {'degradation_type': 'haze', ...}
]

# 备用
env_name = "noise, haze, rain"  # 逆序
→ ['rain', 'haze', 'noise']  # 反转后
```

### 原则3：只计对应工具

```python
样本: 退化=['rain']
调用: ['mprnet_deraining', 'swinir_denoising']

匹配:
- mprnet_deraining ✓ (在去雨工具列表中)
- swinir_denoising ✗ (不在去雨工具列表中)

→ rain_repeat_count += 1
```

---

## 🔀 模式差异

### 单轮多工具（multi_tool_planning）

```
第1轮: [tool1, tool2, tool3]
第2轮: [tool4]  ← 只统计这一轮

原因: 最后一轮是最终决策
```

### 多轮单工具（single_tool_iterative）

```
第1轮: [tool1]
第2轮: [tool2]  
第3轮: [tool3]  ← 统计所有轮次

原因: 每轮都有意义
```

---

## 📈 指标解读

### 理想值

```
unique_ratio ≈ 1.0    # 所有样本都识别并调用了
repeat_ratio ≈ 1.0    # 每个退化平均调用1次
```

### 问题诊断

| unique | repeat | 问题 | 建议 |
|--------|--------|------|------|
| 低 | 低 | 识别能力差 | 增加训练数据 |
| 低 | 正常 | 部分样本漏检 | 调整奖励权重 |
| 高 | 高 | 重复调用 | 正常（单工具模式） |

---

## 🎨 WandB 可视化建议

### 图表1：匹配率趋势

```python
Y轴: tool_match/rain_unique_ratio
     tool_match/haze_unique_ratio
     tool_match/noise_unique_ratio
     ...
X轴: training_step
```

### 图表2：覆盖率对比

```python
退化类型 | Unique Ratio | Repeat Ratio
---------|-------------|-------------
rain     | 0.95        | 1.05
haze     | 0.88        | 0.92
...
```

---

## 🚀 使用方法

### 1. 运行训练

```bash
bash examples/agent/IRv2.sh
```

### 2. 查看日志

```bash
[TOOL STATS] === 工具-退化匹配统计 ===
[TOOL STATS]   rain: 28/30 = 0.933
[METRICS] 收集了 48 个工具-退化匹配指标
```

### 3. 查看 WandB

- 搜索 `tool_match/`
- 创建自定义图表
- 分析匹配率趋势

---

## 🔧 工具映射配置

如需修改，编辑 `parallel_env.py` 第298-311行：

```python
DEGRADATION_TO_TOOLS = {
    'rain': ['mprnet_deraining', 'restormer_deraining', ...],
    'haze': ['dehazeformer_dehaze'],
    # ... 添加或修改映射
}
```

---

## ✅ 完成确认

- ✅ 只统计真实退化（从reward_model/env_name）
- ✅ 只计对应工具（严格映射检查）
- ✅ 重复+不重复统计
- ✅ 单轮多工具只看最后一轮
- ✅ WandB 独立panel
- ✅ 代码无语法错误

**可以直接使用！** 🎉

