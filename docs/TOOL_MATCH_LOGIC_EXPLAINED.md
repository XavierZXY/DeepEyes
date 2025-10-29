# 工具-退化匹配统计逻辑详解

## 🎯 核心逻辑

### 统计原则

**只统计样本中真实存在的退化类型，且只有调用了对应工具才算匹配**

---

## 📋 统计逻辑详解

### 步骤1：提取真实退化类型

从 parquet 数据的 `reward_model` 或 `env_name` 字段获取：

```python
# 方法1：从 reward_model 提取（优先）
reward_model = [
    {'degradation_type': 'rain', 'intensity': 0.5},
    {'degradation_type': 'haze', 'intensity': 0.3}
]
→ degradation_types = ['rain', 'haze']

# 方法2：从 env_name 提取（备用）
env_name = "noise, haze, rain"  # 逆序（先加rain，再haze，最后noise）
→ degradation_types = ['rain', 'haze', 'noise']  # 逆序后得到添加顺序
```

**代码位置：** `parallel_env.py` 第805-837行

---

### 步骤2：收集工具调用

根据对话模式选择统计哪些轮次：

#### 单轮多工具模式（multi_tool_planning）

```python
工具调用记录：
{
    1: ['dehaze', 'deblur'],      # 第1轮
    2: ['denoise', 'enhance']     # 第2轮
}

统计时只看最后一轮：
tools_to_use = ['denoise', 'enhance']  # ← 只统计第2轮
```

**原因：** 多工具模式可能在前几轮试错，最后一轮才是最终方案

#### 多轮单工具模式（single_tool_iterative）

```python
工具调用记录：
{
    1: ['dehaze'],     # 第1轮
    2: ['deblur'],     # 第2轮
    3: ['denoise']     # 第3轮
}

统计时使用所有轮次：
tools_to_use = ['dehaze', 'deblur', 'denoise']  # ← 所有轮次
```

**原因：** 单工具模式每轮都有意义，都应该统计

---

### 步骤3：匹配统计

对每个样本的每种真实退化类型进行匹配：

```python
样本示例：
- 真实退化: ['rain', 'haze']
- 调用工具: ['mprnet_deraining', 'dehazeformer_dehaze', 'swinir_denoising']

匹配过程：
┌─────────────────────────────────────────────────────┐
│ 退化类型: rain                                       │
│ 对应工具: [mprnet_deraining, restormer_deraining, ...]│
│                                                     │
│ 检查调用的工具:                                      │
│   - mprnet_deraining ✓ (匹配！)                     │
│   - dehazeformer_dehaze ✗ (不匹配)                  │
│   - swinir_denoising ✗ (不匹配)                     │
│                                                     │
│ 结果:                                               │
│   - 重复统计: +1 (调用了1次对应工具)                │
│   - 不重复统计: matched (该样本匹配)                 │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 退化类型: haze                                      │
│ 对应工具: [dehazeformer_dehaze]                     │
│                                                     │
│ 检查调用的工具:                                      │
│   - mprnet_deraining ✗ (不匹配)                     │
│   - dehazeformer_dehaze ✓ (匹配！)                  │
│   - swinir_denoising ✗ (不匹配)                     │
│                                                     │
│ 结果:                                               │
│   - 重复统计: +1 (调用了1次对应工具)                │
│   - 不重复统计: matched (该样本匹配)                 │
└─────────────────────────────────────────────────────┘

注意: swinir_denoising 虽然被调用了，但不匹配任何真实退化，不计入统计
```

**关键代码：**
```python
for deg_type in degradation_types:  # 只遍历真实存在的退化
    correct_tools = degradation_to_tools.get(deg_type, [])
    
    for tool_name in tools_to_use:
        if tool_name in correct_tools:  # 只有匹配的工具才计数
            degradation_tool_count_repeat[deg_type] += 1
            sample_matched = True
```

---

## 📊 统计示例

### 完整示例

**批次数据：**
```
样本1: 退化=['rain', 'haze'], 调用=['mprnet_deraining', 'dehazeformer_dehaze']
样本2: 退化=['rain'], 调用=['mprnet_deraining', 'restormer_deraining']
样本3: 退化=['rain'], 调用=['swinir_denoising']  # 错误！
样本4: 退化=['haze'], 调用=['dehazeformer_dehaze']
```

**统计结果：**

#### Rain 退化（出现在样本1, 2, 3）

**重复统计：**
```
总出现次数: 3次 (样本1, 2, 3)
对应工具调用次数: 3次
  - 样本1: mprnet_deraining (1次)
  - 样本2: mprnet_deraining + restormer_deraining (2次)
  - 样本3: 无匹配 (0次)

rain_repeat_ratio = 3 / 3 = 1.0
rain_repeat_count = 3
rain_total_count = 3
```

**不重复统计：**
```
有rain的样本数: 3个
调用了去雨工具的样本数: 2个 (样本1, 2)
  - 样本1: 调用了 ✓
  - 样本2: 调用了 ✓
  - 样本3: 未调用 ✗

rain_unique_ratio = 2 / 3 = 0.667
rain_unique_matched = 2
rain_unique_total = 3
```

#### Haze 退化（出现在样本1, 4）

**重复统计：**
```
总出现次数: 2次
对应工具调用次数: 2次
  - 样本1: dehazeformer_dehaze (1次)
  - 样本4: dehazeformer_dehaze (1次)

haze_repeat_ratio = 2 / 2 = 1.0
```

**不重复统计：**
```
有haze的样本数: 2个
调用了去雾工具的样本数: 2个

haze_unique_ratio = 2 / 2 = 1.0
```

---

## ✅ 验证逻辑正确性

### 核心检查点

1. ✅ **只统计真实存在的退化**
   ```python
   for deg_type in degradation_types:  # 只遍历该样本真实的退化
   ```

2. ✅ **从 reward_model/env_name 获取**
   ```python
   reward_model = data_item.non_tensor_batch.get("reward_model", [])
   env_name = data_item.non_tensor_batch.get("env_name", "")
   ```

3. ✅ **只计数匹配的工具**
   ```python
   if tool_name in correct_tools:  # 只有对应工具才计数
   ```

4. ✅ **区分重复和不重复**
   ```python
   # 重复：每次调用都计数
   degradation_tool_count_repeat[deg_type] += 1
   
   # 不重复：样本级别只计数一次
   if sample_matched:
       degradation_sample_matched_unique[deg_type] += 1
   ```

---

## 🔍 特殊情况处理

### 情况1：样本有多个退化

```python
样本: 退化=['rain', 'haze', 'noise']
调用: ['mprnet_deraining', 'dehazeformer_dehaze']

统计:
- rain: 匹配 ✓ (调用了mprnet_deraining)
- haze: 匹配 ✓ (调用了dehazeformer_dehaze)
- noise: 不匹配 ✗ (没调用去噪工具)

结果:
- rain的统计 +1（总数）+1（匹配）
- haze的统计 +1（总数）+1（匹配）
- noise的统计 +1（总数）+0（匹配）
```

### 情况2：调用了多次同类工具

```python
样本: 退化=['rain']
调用: ['mprnet_deraining', 'restormer_deraining', 'xrestormer_deraining']

统计:
- 重复统计: +3 (每次调用都计数)
- 不重复统计: +1 (样本级别只计数一次)

结果:
- rain_repeat_count = 3
- rain_unique_matched = 1
```

### 情况3：Clean 样本

```python
样本: 退化=[] 或 env_name="clean"
调用: <answer>

统计: 跳过（不参与任何统计）
```

---

## 🎨 WandB Panel 展示

### 推荐的图表布局

#### Panel 1: 匹配率总览（不重复统计）

```
┌─────────────────────────────────────────────┐
│ Tool-Degradation Matching Rate (Unique)    │
├─────────────────────────────────────────────┤
│                                             │
│  1.0 ┤                                      │
│      │   ●────●────●────●  rain             │
│  0.8 ┤      ○────○────○  haze               │
│      │         △────△  noise                │
│  0.6 ┤                                      │
│      │                                      │
│  0.4 ┤                                      │
│      └────────────────────────────────→     │
│       0    500   1000  1500  steps          │
└─────────────────────────────────────────────┘

指标: tool_match/*_unique_ratio
```

#### Panel 2: 调用覆盖率（重复统计）

```
┌─────────────────────────────────────────────┐
│ Tool Call Coverage (Repeat)                │
├─────────────────────────────────────────────┤
│                                             │
│  2.0 ┤                                      │
│      │   ●────●────●  rain                  │
│  1.5 ┤      ○────○  haze                    │
│      │                                      │
│  1.0 ┤         △────△  noise                │
│      │                                      │
│  0.5 ┤                                      │
│      └────────────────────────────────→     │
│       0    500   1000  1500  steps          │
└─────────────────────────────────────────────┘

指标: tool_match/*_repeat_ratio
```

#### Panel 3: 详细对比表格

| 退化类型 | 样本数 | 匹配样本 | Unique Ratio | 调用次数 | Repeat Ratio |
|---------|-------|---------|-------------|---------|-------------|
| rain | 30 | 28 | 0.933 | 35 | 1.167 |
| haze | 25 | 24 | 0.960 | 26 | 1.040 |
| noise | 40 | 32 | 0.800 | 38 | 0.950 |
| ... | ... | ... | ... | ... | ... |

---

## 🧪 验证示例

### 模拟批次

```python
批次大小: 5个样本

样本0: reward_model=[{'degradation_type': 'rain'}, {'degradation_type': 'haze'}]
       调用: ['mprnet_deraining', 'dehazeformer_dehaze']
       
样本1: reward_model=[{'degradation_type': 'rain'}]
       调用: ['mprnet_deraining', 'restormer_deraining']  # 调用2次
       
样本2: reward_model=[{'degradation_type': 'rain'}]
       调用: ['swinir_denoising']  # 错误工具
       
样本3: reward_model=[{'degradation_type': 'haze'}]
       调用: ['dehazeformer_dehaze']
       
样本4: env_name="clean"
       调用: <answer>
```

### 预期统计结果

#### Rain 退化统计

```
样本0: 有rain, 调用了mprnet_deraining ✓
样本1: 有rain, 调用了mprnet_deraining + restormer_deraining ✓✓
样本2: 有rain, 调用了swinir_denoising ✗ (不是去雨工具)
样本3: 无rain
样本4: 无rain

重复统计:
- rain_total_count = 3 (样本0, 1, 2)
- rain_repeat_count = 3 (样本0: 1次, 样本1: 2次, 样本2: 0次)
- rain_repeat_ratio = 3 / 3 = 1.0

不重复统计:
- rain_unique_total = 3 (样本0, 1, 2)
- rain_unique_matched = 2 (样本0, 1)
- rain_unique_ratio = 2 / 3 = 0.667
```

#### Haze 退化统计

```
样本0: 有haze, 调用了dehazeformer_dehaze ✓
样本1: 无haze
样本2: 无haze
样本3: 有haze, 调用了dehazeformer_dehaze ✓
样本4: 无haze

重复统计:
- haze_total_count = 2 (样本0, 3)
- haze_repeat_count = 2 (样本0: 1次, 样本3: 1次)
- haze_repeat_ratio = 2 / 2 = 1.0

不重复统计:
- haze_unique_total = 2 (样本0, 3)
- haze_unique_matched = 2 (样本0, 3)
- haze_unique_ratio = 2 / 2 = 1.0
```

---

## 🎯 关键特性

### 1. 只统计真实存在的退化

```python
# ❌ 错误理解
所有样本的noise统计 += 调用去噪工具的次数

# ✅ 正确逻辑
for 每个样本:
    if 样本真的有noise退化:
        noise总数 += 1
        if 调用了去噪工具:
            noise匹配数 += 1
```

### 2. 只计数对应的工具

```python
样本: 退化=['rain']
调用: ['mprnet_deraining', 'swinir_denoising', 'dehazeformer_dehaze']

# ❌ 错误理解
rain匹配数 = 3 (调用了3个工具)

# ✅ 正确逻辑
rain匹配数 = 1 (只有mprnet_deraining是去雨工具)
```

### 3. 区分两种计数方式

```python
样本有rain, 调用了3次去雨工具

# 重复统计
rain_repeat_count += 3  # 每次调用都计数

# 不重复统计
rain_unique_matched += 1  # 样本级别只计数一次
```

---

## 📝 日志输出示例

### 提取退化类型

```bash
[TOOL STATS] 开始提取真实退化类型...
[TOOL STATS] 样本0: 真实退化类型 ['rain', 'haze'] (来源: reward_model)
[TOOL STATS] 样本1: 真实退化类型 ['rain'] (来源: reward_model)
[TOOL STATS] 样本2: 真实退化类型 ['rain', 'noise', 'dark'] (来源: env_name)
```

### 收集工具调用

```bash
[TOOL STATS] 样本0 轮次1: 调用工具 ['mprnet_deraining', 'dehazeformer_dehaze']
[TOOL STATS] 样本1 轮次1: 调用工具 ['mprnet_deraining']
[TOOL STATS] 样本1 轮次2: 调用工具 ['restormer_deraining']
```

### 匹配统计结果

```bash
[TOOL STATS] === 工具-退化匹配统计 ===
[TOOL STATS] 统计模式: multi_tool_planning
[TOOL STATS] 样本数量: 128

[TOOL STATS] 重复统计（工具调用次数级别）:
[TOOL STATS]   rain: 85/90 = 0.944
[TOOL STATS]   haze: 45/50 = 0.900
[TOOL STATS]   dark: 28/30 = 0.933
[TOOL STATS]   motion blur: 15/20 = 0.750
[TOOL STATS]   noise: 38/40 = 0.950

[TOOL STATS] 不重复统计（样本级别）:
[TOOL STATS]   rain: 82/90 = 0.911
[TOOL STATS]   haze: 43/50 = 0.860
[TOOL STATS]   dark: 27/30 = 0.900
[TOOL STATS]   motion blur: 14/20 = 0.700
[TOOL STATS]   noise: 36/40 = 0.900
[TOOL STATS] === 统计完成 ===
```

---

## 🔧 代码实现关键点

### 退化类型到工具的映射（parallel_env.py 第298-311行）

```python
DEGRADATION_TO_TOOLS = {
    'rain': ['mprnet_deraining', 'restormer_deraining', 'xrestormer_deraining'],
    'haze': ['dehazeformer_dehaze'],
    'dark': ['retinexformer_enhance', 'retinexformer_lol_v1', ...],
    'motion blur': ['xrestormer_motion_deblurring', 'mprnet_motion_deblurring', ...],
    'defocus blur': ['drbnet_defocus_deblurring', 'restormer_defocus_deblurring'],
    'noise': ['swinir_denoising', 'mprnet_denoising', 'scunet_*_denoising'],
    'low resolution': ['swinir_super_resolution'],
    'jpeg compression artifact': ['swinir_jpeg_artifact_removal', 'fbcnn_jpeg_artifact_removal'],
}
```

**注意：** 工具名称必须与实际注册的工具名称完全匹配（大小写敏感）

### 统计计算（parallel_env.py 第322-368行）

```python
for idx in range(num_samples):
    degradation_types = degradation_types_per_sample[idx]  # 该样本的真实退化
    
    # 决定使用哪些工具（根据模式）
    if conversation_mode == 'multi_tool_planning':
        tools_to_use = tool_calls_dict.get(max_turn, [])  # 只用最后一轮
    else:
        tools_to_use = [所有轮次的工具]  # 用全部轮次
    
    # 对该样本的每种真实退化进行匹配
    for deg_type in degradation_types:
        correct_tools = degradation_to_tools.get(deg_type, [])
        
        for tool_name in tools_to_use:
            if tool_name in correct_tools:
                # 计数...
```

---

## ✅ 总结

### 统计逻辑三原则

1. ✅ **只看真实退化**：从 reward_model 或 env_name 提取
2. ✅ **只计对应工具**：通过 DEGRADATION_TO_TOOLS 映射检查
3. ✅ **区分计数方式**：重复（次数级） vs 不重复（样本级）

### 与你的需求对照

- ✅ "统计的是该类别的" → 只遍历真实存在的退化类型
- ✅ "从 reward_model 或 env_name 获取" → 参考了现有代码的提取方式
- ✅ "调用了对应的工具才算" → 通过映射表严格检查

### 代码已就绪

所有逻辑已实现并通过检查，可以直接使用！ 🎉

