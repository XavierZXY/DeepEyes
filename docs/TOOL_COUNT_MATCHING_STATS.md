# 工具数量匹配统计指标说明

## 📊 新增统计指标

### 功能概述

统计样本调用的工具数量是否与退化数量匹配，分为三种情况：
- **少调用（less）**：调用的工具数 < 退化数量
- **刚好（exact）**：调用的工具数 = 退化数量
- **多调用（more）**：调用的工具数 > 退化数量

### 分组统计

**只统计2种退化和3种退化的样本**（这两种最常见）

---

## 🎯 统计逻辑

### 示例1：2种退化的样本

```python
样本A: 
  真实退化: ['rain', 'haze']  # 2种退化
  调用工具: ['mprnet_deraining']  # 只调用1个对应工具
  
  结果: 少调用 (1 < 2) ✗

样本B:
  真实退化: ['rain', 'haze']  # 2种退化
  调用工具: ['mprnet_deraining', 'dehazeformer_dehaze']  # 调用2个对应工具
  
  结果: 刚好 (2 = 2) ✓

样本C:
  真实退化: ['rain', 'haze']  # 2种退化
  调用工具: ['mprnet_deraining', 'dehazeformer_dehaze', 'swinir_denoising']  # 调用3个对应工具
  
  结果: 多调用 (3 > 2) ⚠️
```

**注意：** 只计数匹配的工具（对应退化类型的工具）

---

### 示例2：3种退化的样本

```python
样本D:
  真实退化: ['rain', 'haze', 'noise']  # 3种退化
  调用工具: ['mprnet_deraining', 'dehazeformer_dehaze']  # 只调用2个
  
  结果: 少调用 (2 < 3) ✗

样本E:
  真实退化: ['rain', 'haze', 'noise']  # 3种退化
  调用工具: ['mprnet_deraining', 'dehazeformer_dehaze', 'swinir_denoising']  # 调用3个
  
  结果: 刚好 (3 = 3) ✓

样本F:
  真实退化: ['rain', 'haze', 'noise']  # 3种退化
  调用工具: ['mprnet_deraining', 'dehazeformer_dehaze', 'swinir_denoising', 'mprnet_denoising']  # 4个
  
  结果: 多调用 (4 > 3) ⚠️
```

---

## 📈 WandB 指标列表

### 2种退化的样本（deg2）

```
tool_count_match/deg2_less_ratio      # 少调用的样本比例
tool_count_match/deg2_less_count      # 少调用的样本数量
tool_count_match/deg2_exact_ratio     # 刚好的样本比例
tool_count_match/deg2_exact_count     # 刚好的样本数量
tool_count_match/deg2_more_ratio      # 多调用的样本比例
tool_count_match/deg2_more_count      # 多调用的样本数量
tool_count_match/deg2_total           # 2种退化的样本总数
```

### 3种退化的样本（deg3）

```
tool_count_match/deg3_less_ratio      # 少调用的样本比例
tool_count_match/deg3_less_count      # 少调用的样本数量
tool_count_match/deg3_exact_ratio     # 刚好的样本比例
tool_count_match/deg3_exact_count     # 刚好的样本数量
tool_count_match/deg3_more_ratio      # 多调用的样本比例
tool_count_match/deg3_more_count      # 多调用的样本数量
tool_count_match/deg3_total           # 3种退化的样本总数
```

### 总计指标

**14个新指标** = 2组 × 7个指标/组

---

## 🎯 统计细节

### 关键逻辑

```python
# 1. 只计算匹配的工具（去重）
matched_tools_set = set()
for tool_name in tools_to_use:
    for deg_type in degradation_types:  # 只看该样本的真实退化
        if tool_name in DEGRADATION_TO_TOOLS[deg_type]:
            matched_tools_set.add(tool_name)
            break

# 2. 比较数量
num_matched_tools = len(matched_tools_set)  # 去重后的工具数
num_degradations = len(degradation_types)   # 退化数量

# 3. 分类
if num_matched_tools < num_degradations:
    → 少调用
elif num_matched_tools == num_degradations:
    → 刚好
else:
    → 多调用
```

### 重要说明

1. **只计数匹配的工具**
   ```python
   样本: 退化=['rain', 'haze']
   调用: ['mprnet_deraining', 'swinir_denoising', 'dehazeformer_dehaze']
   
   匹配工具: {'mprnet_deraining', 'dehazeformer_dehaze'}  # 2个
   → 刚好 ✓
   
   (swinir_denoising不匹配rain或haze，不计数)
   ```

2. **工具去重**
   ```python
   样本: 退化=['rain']
   调用: ['mprnet_deraining', 'mprnet_deraining', 'mprnet_deraining']  # 重复3次
   
   匹配工具: {'mprnet_deraining'}  # 去重后只有1个
   → 刚好 ✓
   ```

3. **只统计2种和3种退化**
   ```python
   样本: 退化=['rain']  # 1种 → 不统计
   样本: 退化=['rain', 'haze']  # 2种 → 统计到 deg2
   样本: 退化=['rain', 'haze', 'noise']  # 3种 → 统计到 deg3
   样本: 退化=['rain', 'haze', 'noise', 'dark']  # 4种 → 不统计
   ```

---

## 📊 批次级别统计

### 每个step的统计是独立的

```
Step 100 的 batch:
  - 有10个2种退化的样本
    * 3个少调用 → deg2_less_ratio = 0.3
    * 6个刚好 → deg2_exact_ratio = 0.6
    * 1个多调用 → deg2_more_ratio = 0.1

Step 101 的 batch:
  - 有8个2种退化的样本
    * 2个少调用 → deg2_less_ratio = 0.25
    * 5个刚好 → deg2_exact_ratio = 0.625
    * 1个多调用 → deg2_more_ratio = 0.125
```

**说明：** 每个step的值不同，反映当前batch的情况

---

## 🎨 WandB 可视化建议

### Panel 1: 2种退化样本的工具数量匹配

```
┌─────────────────────────────────────────────┐
│ Tool Count Match - 2 Degradations          │
├─────────────────────────────────────────────┤
│  1.0 ┤                                      │
│      │                                      │
│  0.8 ┤      ●────●────●  exact (刚好)       │
│      │                                      │
│  0.6 ┤                                      │
│      │   ○────○────○  less (少调用)         │
│  0.4 ┤                                      │
│      │      △────△  more (多调用)           │
│  0.2 ┤                                      │
│      │                                      │
│  0.0 ┤                                      │
│      └────────────────────────────────→     │
│       0    500   1000  1500  steps          │
└─────────────────────────────────────────────┘
```

### Panel 2: 3种退化样本的工具数量匹配

```
┌─────────────────────────────────────────────┐
│ Tool Count Match - 3 Degradations          │
├─────────────────────────────────────────────┤
│  1.0 ┤                                      │
│      │   ●────●────●  exact (刚好)          │
│  0.8 ┤                                      │
│      │      ○────○  less (少调用)           │
│  0.6 ┤                                      │
│      │                                      │
│  0.4 ┤         △  more (多调用)             │
│      │                                      │
│  0.2 ┤                                      │
│      └────────────────────────────────→     │
│       0    500   1000  1500  steps          │
└─────────────────────────────────────────────┘
```

### Panel 3: 堆叠面积图

显示 less + exact + more = 100% 的分布：

```
┌─────────────────────────────────────────────┐
│ Tool Count Distribution (2 Degradations)   │
├─────────────────────────────────────────────┤
│ 100% ┤ ▓▓▓ more                            │
│      │ ░░░ exact                            │
│  80% ┤ ▒▒▒ less                             │
│      │                                      │
│  60% ┤                                      │
│      │                                      │
│  40% ┤                                      │
│      │                                      │
│  20% ┤                                      │
│      │                                      │
│   0% └────────────────────────────────→     │
│       0    500   1000  1500  steps          │
└─────────────────────────────────────────────┘
```

---

## 💡 指标解读

### 理想情况

```
tool_count_match/deg2_exact_ratio ≈ 1.0    # 所有2种退化样本都刚好调用2个工具
tool_count_match/deg2_less_ratio ≈ 0.0     # 没有少调用
tool_count_match/deg2_more_ratio ≈ 0.0     # 没有多调用
```

### 问题诊断

#### 情况1：少调用比例高

```
tool_count_match/deg2_less_ratio = 0.6     # 60%的样本少调用
tool_count_match/deg2_exact_ratio = 0.3
tool_count_match/deg2_more_ratio = 0.1
```

**问题：** 模型经常遗漏退化类型
**建议：** 
- 增加识别退化的奖励权重
- 检查数据集是否有标注错误
- 可能需要更多训练数据

---

#### 情况2：多调用比例高

```
tool_count_match/deg2_less_ratio = 0.1
tool_count_match/deg2_exact_ratio = 0.3
tool_count_match/deg2_more_ratio = 0.6     # 60%的样本多调用
```

**问题：** 模型倾向于过度处理
**建议：**
- 正常现象（模型探索）
- 如果持续到训练后期，可能需要调整奖励函数
- 单工具模式下更常见（多轮迭代）

---

#### 情况3：刚好比例高（理想）

```
tool_count_match/deg2_less_ratio = 0.1
tool_count_match/deg2_exact_ratio = 0.8     # 80%的样本刚好
tool_count_match/deg2_more_ratio = 0.1
```

**解读：** 模型已经学会准确匹配工具数量 ✅

---

## 📝 完整示例

### 批次数据

```
Batch (10个样本):

# 2种退化的样本 (5个)
样本0: 退化=['rain', 'haze'], 调用=['mprnet_deraining'] → 少 (1 < 2)
样本1: 退化=['rain', 'haze'], 调用=['mprnet_deraining', 'dehazeformer_dehaze'] → 刚好 (2 = 2)
样本2: 退化=['rain', 'noise'], 调用=['mprnet_deraining', 'swinir_denoising'] → 刚好 (2 = 2)
样本3: 退化=['haze', 'dark'], 调用=['dehazeformer_dehaze'] → 少 (1 < 2)
样本4: 退化=['rain', 'haze'], 调用=['mprnet_deraining', 'dehazeformer_dehaze', 'swinir_denoising'] 
       → 多 (3 > 2, 注意swinir_denoising不匹配rain/haze，但前2个匹配，所以是2个匹配工具 = 2) → 刚好 (2 = 2)

# 3种退化的样本 (3个)
样本5: 退化=['rain', 'haze', 'noise'], 调用=['mprnet_deraining', 'dehazeformer_dehaze'] → 少 (2 < 3)
样本6: 退化=['rain', 'haze', 'noise'], 调用=['mprnet_deraining', 'dehazeformer_dehaze', 'swinir_denoising'] → 刚好 (3 = 3)
样本7: 退化=['rain', 'haze', 'dark'], 调用=['mprnet_deraining', 'dehazeformer_dehaze', 'retinexformer_enhance', 'swinir_denoising'] 
       → 多 (4个工具但只有3个匹配，3 = 3) → 刚好 (3 = 3)

# 其他退化数量的样本 (2个)
样本8: 退化=['rain'], 调用=['mprnet_deraining'] → 不统计 (只有1种退化)
样本9: 退化=['rain', 'haze', 'noise', 'dark'], 调用=[...] → 不统计 (有4种退化)
```

### 统计结果

```
2种退化 (deg2):
  - total: 5个样本
  - less: 2个 (样本0, 3) → less_ratio = 2/5 = 0.4
  - exact: 3个 (样本1, 2, 4) → exact_ratio = 3/5 = 0.6
  - more: 0个 → more_ratio = 0/5 = 0.0

3种退化 (deg3):
  - total: 3个样本
  - less: 1个 (样本5) → less_ratio = 1/3 = 0.333
  - exact: 2个 (样本6, 7) → exact_ratio = 2/3 = 0.667
  - more: 0个 → more_ratio = 0/3 = 0.0
```

---

## 🔍 关键实现细节

### 1. 工具去重计数

```python
# 使用set去重
matched_tools_set = set()
for tool_name in tools_to_use:
    for deg_type in degradation_types:
        if tool_name in DEGRADATION_TO_TOOLS[deg_type]:
            matched_tools_set.add(tool_name)
            break

num_matched_tools = len(matched_tools_set)  # 去重后的数量
```

**为什么去重？**
- 同一个工具调用多次，只算1个
- 反映"覆盖了多少种退化"，而不是"调用了多少次"

---

### 2. 只统计匹配的工具

```python
样本: 退化=['rain', 'haze']
调用: ['mprnet_deraining', 'swinir_denoising', 'dehazeformer_dehaze', 'enhance']

匹配检查:
  - mprnet_deraining → 匹配 rain ✓
  - swinir_denoising → 不匹配 rain/haze ✗ (是noise工具)
  - dehazeformer_dehaze → 匹配 haze ✓
  - enhance → 不匹配 rain/haze ✗ (是dark工具)

匹配工具数: 2个
退化数量: 2个
→ 刚好 ✓
```

---

### 3. 模式差异

#### 单轮多工具模式

```python
第1轮: ['tool1', 'tool2', 'tool3']
第2轮: ['tool4', 'tool5']  ← 只统计这一轮

matched_tools = {'tool4', 'tool5'}  # 只看最后一轮
```

#### 多轮单工具模式

```python
第1轮: ['tool1']
第2轮: ['tool2']
第3轮: ['tool3']

matched_tools = {'tool1', 'tool2', 'tool3'}  # 所有轮次
```

---

## 📊 日志输出示例

```bash
[TOOL STATS] === 工具-退化匹配统计（批次级别）===

[TOOL STATS] 工具数量匹配统计（样本调用的工具数 vs 退化数量）:
[TOOL STATS]   2种退化的样本 (共45个):
[TOOL STATS]     少调用: 12/45 = 0.267
[TOOL STATS]     刚好: 28/45 = 0.622
[TOOL STATS]     多调用: 5/45 = 0.111

[TOOL STATS]   3种退化的样本 (共38个):
[TOOL STATS]     少调用: 15/38 = 0.395
[TOOL STATS]     刚好: 20/38 = 0.526
[TOOL STATS]     多调用: 3/38 = 0.079

[TOOL STATS] === 统计完成 ===
```

---

## 🎯 与其他指标的关系

### 已有指标

```
tool_match/rain_unique_ratio         # rain退化的工具调用率
tool_match/haze_unique_ratio         # haze退化的工具调用率
...
```
→ **按退化类型分别统计**

### 新增指标

```
tool_count_match/deg2_exact_ratio    # 2种退化样本的数量匹配率
tool_count_match/deg3_exact_ratio    # 3种退化样本的数量匹配率
```
→ **按退化数量分组统计整体匹配情况**

### 互补性

- 已有指标：告诉你"哪种退化识别率低"
- 新增指标：告诉你"整体上工具数量是否合适"

**综合分析：**
```
如果:
  tool_match/rain_unique_ratio = 0.9  # rain识别率高
  tool_match/haze_unique_ratio = 0.9  # haze识别率高
  tool_count_match/deg2_exact_ratio = 0.7  # 但只有70%刚好

说明: 虽然单个退化识别率高，但组合识别有问题
可能: 模型对某些组合容易过度调用或遗漏
```

---

## 💡 实际应用

### 训练早期

```
tool_count_match/deg2_less_ratio = 0.7   # 大部分少调用
tool_count_match/deg2_exact_ratio = 0.2
tool_count_match/deg2_more_ratio = 0.1

→ 模型还在学习识别退化
```

### 训练中期

```
tool_count_match/deg2_less_ratio = 0.3
tool_count_match/deg2_exact_ratio = 0.5   # 开始接近刚好
tool_count_match/deg2_more_ratio = 0.2

→ 模型识别能力提升
```

### 训练后期（理想）

```
tool_count_match/deg2_less_ratio = 0.1
tool_count_match/deg2_exact_ratio = 0.8   # 大部分刚好
tool_count_match/deg2_more_ratio = 0.1

→ 模型已经收敛
```

---

## ✅ 总结

### 新增指标

**14个指标** = 2组（deg2, deg3）× 7个指标/组

### 统计逻辑

- ✅ 只计数匹配的工具（对应退化类型的工具）
- ✅ 工具去重（同一工具调用多次只算1个）
- ✅ 按退化数量分组（2种和3种）
- ✅ 三种情况（少/刚好/多）
- ✅ 批次级别统计（每个step独立）

### WandB Panel

所有指标在 `tool_count_match/` 命名空间下，自动创建独立panel

### 应用价值

- 诊断模型是否学会了准确匹配工具数量
- 对比2种退化和3种退化的处理难度
- 监控训练收敛情况

---

## 🚀 使用方法

### 1. 运行训练

```bash
bash examples/agent/IRv2.sh
```

### 2. 查看日志

```bash
[TOOL STATS] 工具数量匹配统计...
[TOOL STATS]   2种退化的样本 (共45个):
[TOOL STATS]     少调用: 12/45 = 0.267
[TOOL STATS]     刚好: 28/45 = 0.622
[TOOL STATS]     多调用: 5/45 = 0.111
```

### 3. 在WandB创建图表

- 搜索 `tool_count_match/`
- 选择 `deg2_exact_ratio` 和 `deg3_exact_ratio`
- 创建折线图观察趋势

---

## 📞 反馈

如有问题或建议，欢迎反馈！

