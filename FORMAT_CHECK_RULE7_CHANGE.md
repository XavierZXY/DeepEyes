# 📝 格式检查规则7修改说明

## 🔄 修改内容

### **原规则（已注释保留）**
```python
# 总工具数必须 >= 退化数量（对于非clean样本）
if not is_clean_sample and degradation_count > 0:
    if total_tool_calls < degradation_count:
        return -1.0  # 违规
```

**问题**：
- ❌ 过于严格：强制要求工具数量≥退化数量
- ❌ 限制探索：模型可能想尝试少量工具的组合
- ❌ 不够灵活：某些工具可能可以处理多种退化

---

### **新规则（当前使用）**
```python
# 总工具数必须 >= 1（对于非clean样本）
if not is_clean_sample:
    if total_tool_calls < 1:
        return -1.0  # 违规
```

**优点**：
- ✅ 更灵活：只要求至少尝试1个工具
- ✅ 鼓励探索：模型可以尝试不同的工具组合
- ✅ 合理约束：防止模型直接输出answer而不处理
- ✅ 适应多功能工具：一个工具可能处理多种退化

---

## 📊 对比分析

### **场景1: 3种退化 [rain, haze, noise]**

#### **旧规则**
```python
# ❌ 违规：只调用2个工具
<tool_call>[
  {"name": "universal_restoration_tool", ...},  # 可以处理多种退化
  {"name": "swinir_denoising", ...}
]</tool_call>
→ format_score = -1.0 (2 < 3)

# ✅ 通过：必须3个工具
<tool_call>[
  {"name": "tool1", ...},
  {"name": "tool2", ...},
  {"name": "tool3", ...}
]</tool_call>
→ format_score = 1.0 (3 >= 3)
```

#### **新规则**
```python
# ✅ 通过：至少1个工具
<tool_call>[
  {"name": "universal_restoration_tool", ...}
]</tool_call>
→ format_score = 1.0 (1 >= 1)

# ✅ 通过：2个工具也可以
<tool_call>[
  {"name": "tool1", ...},
  {"name": "tool2", ...}
]</tool_call>
→ format_score = 1.0 (2 >= 1)

# ✅ 通过：3个或更多
<tool_call>[
  {"name": "tool1", ...},
  {"name": "tool2", ...},
  {"name": "tool3", ...}
]</tool_call>
→ format_score = 1.0 (3 >= 1)
```

---

### **场景2: Clean样本**

#### **两种规则都相同**
```python
# 不检查工具数量，允许直接输出answer
<think>图像已经很清晰了</think>
<answer>{"restoration_log": []}</answer>
→ format_score = 1.0 (clean样本不受约束)
```

---

### **场景3: 非clean样本但没有调用工具**

#### **两种规则都违规**
```python
# ❌ 违规：没有调用任何工具
<think>图像有退化但我不想处理</think>
<answer>{"restoration_log": []}</answer>
→ format_score = -1.0 (0 < 1)

# 目的：防止模型偷懒，强制至少尝试处理
```

---

## 🎯 修改动机

### **1. 现实场景考虑**

**多功能工具的存在**：
```python
# 某些工具可能处理多种退化
visual_toolbox_v5:
  - 可以同时处理噪声、模糊、色彩等多种问题
  
xrestormer:
  - motion_deblurring: 处理运动模糊
  - deraining: 顺便也改善了整体质量
```

**工具组合的协同效应**：
```python
# 2个工具可能足以处理3种退化
<tool_call>[
  {"name": "mprnet_deraining", ...},      # 去雨 + 顺便改善噪声
  {"name": "dehazeformer_dehaze", ...}    # 去雾 + 顺便改善对比度
]</tool_call>
# 虽然只有2个工具，但可能已经处理了3种退化
```

---

### **2. 训练策略考虑**

**鼓励模型探索**：
- 旧规则：模型为了满足数量要求，可能堆砌工具
- 新规则：模型可以自由探索最优工具组合

**避免无效堆叠**：
```python
# 旧规则可能导致的问题
<tool_call>[
  {"name": "useful_tool_1", ...},
  {"name": "useful_tool_2", ...},
  {"name": "redundant_tool", ...}  # 为了凑数而添加
]</tool_call>

# 新规则下模型的自由选择
<tool_call>[
  {"name": "useful_tool_1", ...},
  {"name": "useful_tool_2", ...}
  # 不需要凑数，只用必要的工具
]</tool_call>
```

---

### **3. 配合MAX_TOOLS_PER_TURN**

**双重约束的平衡**：
```python
# 下限：至少1个工具（防止偷懒）
if total_tool_calls < 1:
    return -1.0

# 上限：每轮最多N个工具（防止浪费）
if turn_tool_count > max_tools_per_turn:
    return -1.0
```

**给模型足够的自由度**：
- 下限宽松（≥1）：不强制数量
- 上限严格（≤N）：控制成本
- 中间自由：模型根据效果决定

---

## 🔧 如何恢复原规则

如果需要恢复原来的严格规则，只需要：

### **步骤1: 修改代码**
```python
# 文件: verl/utils/reward_score/image_restoration.py
# 位置: check_multiturn_format_v3_enhanced 函数

# 注释掉新规则
# if not is_clean_sample:
#     if total_tool_calls < 1:
#         print(f' [ENHANCED FORMAT] Tool_call数量不足: {total_tool_calls} < 1')
#         return -1.0

# 取消注释原规则
if not is_clean_sample and degradation_count > 0:
    if total_tool_calls < degradation_count:
        print(f' [ENHANCED FORMAT] Tool_call数量不足: {total_tool_calls} < {degradation_count}')
        return -1.0
    print(f' [ENHANCED FORMAT] Tool_call数量验证通过: {total_tool_calls} >= {degradation_count}')
```

### **步骤2: 更新配置说明**
```bash
# 文件: examples/agent/IR.sh
# 恢复原说明
# - Tool_call总数必须 >= 退化数量（对于非clean样本）
```

---

## 📈 预期影响

### **训练指标变化**

#### **格式合规率**
```
旧规则: 75% → 新规则: 95%
原因: 放宽约束，更多样本满足格式要求
```

#### **平均工具数**
```
旧规则: 强制≥退化数
新规则: 模型自主决定（可能更少）
预期: 平均工具数可能下降，但质量奖励会引导最优选择
```

#### **训练速度**
```
旧规则: 较慢（更多格式违规的负样本）
新规则: 较快（更少格式惩罚，更多探索）
```

---

### **模型行为变化**

#### **更智能的工具选择**
```python
# 旧规则下：凑数思维
模型: "需要3个工具，那我就选3个"

# 新规则下：效果导向
模型: "这2个工具够了，质量奖励高"
```

#### **更多的策略探索**
```python
# 旧规则：固定模式
3种退化 → 必须3个工具 → 策略单一

# 新规则：灵活尝试
3种退化 → 尝试1-5个工具 → 发现最优组合
```

---

## 💡 推荐配置

### **配置1: 完全灵活（推荐）**
```bash
export USE_ENHANCED_FORMAT=True
export MAX_TOOLS_PER_TURN=5    # 上限控制成本
# 下限=1（代码中固定），防止偷懒
```

### **配置2: 温和约束**
```bash
export USE_ENHANCED_FORMAT=True
export MAX_TOOLS_PER_TURN=3    # 更严格的上限
# 下限=1，但通过质量奖励引导使用合适数量
```

### **配置3: 恢复严格（如果需要）**
```bash
# 代码中恢复原规则（取消注释）
# 强制：工具数 >= 退化数
```

---

## 📊 监控建议

训练时关注以下指标：

```bash
# 1. 格式合规率
grep "ENHANCED FORMAT.*所有检查通过" logs/*.log | wc -l

# 2. 平均工具数分布
grep "tool_calls=" logs/*.log | awk -F'tool_calls=' '{print $2}' | awk '{print $1}' | sort | uniq -c

# 3. 质量奖励vs工具数的关系
# 分析：是否工具数少但质量高的样本获得更多奖励

# 4. 是否有大量0工具的违规
grep "Tool_call数量不足: 0 < 1" logs/*.log | wc -l
```

---

## ✅ 总结

| 维度 | 旧规则 | 新规则 |
|------|--------|--------|
| **下限约束** | ≥退化数量 | ≥1 |
| **灵活性** | 低 | 高 |
| **探索空间** | 受限 | 开放 |
| **格式合规率** | 中等 | 高 |
| **适用场景** | 严格监督 | 自主探索 |
| **代码保留** | ✅ 已注释 | ✅ 当前使用 |

**修改理由**：
1. ✅ 给模型更多自由度
2. ✅ 鼓励高效工具组合
3. ✅ 防止无意义的工具堆叠
4. ✅ 保持基本约束（至少尝试处理）

**恢复方式**：简单注释切换，无需重写代码

---

**修改时间**: 2025-10-21  
**版本**: v8-4+  
**状态**: 已应用，原规则已保留

