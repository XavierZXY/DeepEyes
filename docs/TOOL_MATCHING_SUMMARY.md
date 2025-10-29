# 工具-退化匹配统计 - 功能总结

## ✅ 已实现的功能

### 📊 统计内容

针对**8种退化类型**，统计模型调用对应工具的匹配情况：

| 退化类型 | 需要调用的工具 |
|---------|--------------|
| rain | 去雨工具（mprnet_deraining等） |
| haze | 去雾工具（dehazeformer_dehaze） |
| dark | 增强工具（retinexformer系列） |
| motion blur | 运动去模糊（xrestormer等） |
| defocus blur | 散焦去模糊（drbnet等） |
| noise | 去噪工具（swinir等） |
| low resolution | 超分辨率（swinir_super_resolution） |
| jpeg compression artifact | JPEG伪影去除 |

---

## 🎯 核心逻辑（完全符合你的要求）

### 1️⃣ 只统计真实存在的退化

```python
✅ 正确实现：
for deg_type in degradation_types:  # degradation_types 来自该样本的 reward_model/env_name
    if deg_type == 'clean':
        continue  # 跳过clean
    
    degradation_total_count[deg_type] += 1  # 只对真实存在的退化计数
```

**不会发生：** 统计所有样本的noise，即使样本没有noise退化

---

### 2️⃣ 从 reward_model 或 env_name 获取

参考了现有代码 `verl/utils/reward_score/image_restoration.py`：

```python
✅ 优先从 reward_model 提取：
for item in reward_model:
    if 'degradation_type' in item:  # 注意字段名
        degradation_types.append(item['degradation_type'])

✅ 备用从 env_name 提取：
parts = env_name.split(',')
degradation_types = list(reversed(parts))  # 逆序
```

**代码位置：** `parallel_env.py` 第817-830行

---

### 3️⃣ 只有调用了对应工具才算

```python
✅ 严格匹配检查：
correct_tools = DEGRADATION_TO_TOOLS.get(deg_type, [])

for tool_name in tools_to_use:
    if tool_name in correct_tools:  # 必须在对应工具列表中
        degradation_tool_count_repeat[deg_type] += 1
```

**示例：**
- 样本有 `rain` 退化
- 调用了 `swinir_denoising` → **不计数**（不是去雨工具）
- 调用了 `mprnet_deraining` → **计数**（是去雨工具）

---

### 4️⃣ 重复和不重复统计

#### 重复统计（工具调用次数级别）

```python
样本有rain, 调用了3次去雨工具
→ rain_repeat_count += 3  # 每次都计数

结果: rain_repeat_ratio = 总调用次数 / 退化出现次数
```

**含义：** 平均每个rain退化调用了多少次对应工具

#### 不重复统计（样本级别）

```python
样本有rain, 调用了3次去雨工具
→ rain_unique_matched += 1  # 只计数一次

结果: rain_unique_ratio = 匹配样本数 / 有该退化的样本数
```

**含义：** 有多少比例的rain样本至少调用了一次去雨工具

---

### 5️⃣ 单轮多工具只统计最后一轮

```python
if conversation_mode == 'multi_tool_planning':
    if tool_calls_dict:
        max_turn = max(tool_calls_dict.keys())  # 找到最后一轮
        tools_to_use = tool_calls_dict.get(max_turn, [])  # 只用最后一轮
```

**特殊情况：** 如果只有1轮，`max_turn=1`，就统计第1轮

---

### 6️⃣ WandB 新 Panel

所有指标使用 `tool_match/` 前缀，自动在 WandB 创建独立面板：

```
WandB 会自动分组：
┌─────────────────────────┐
│ tool_match              │
├─────────────────────────┤
│ rain_repeat_ratio       │
│ rain_repeat_count       │
│ rain_unique_ratio       │
│ rain_unique_matched     │
│ haze_repeat_ratio       │
│ ...                     │
└─────────────────────────┘
```

---

## 📈 WandB 指标清单

### 每种退化类型6个指标

```python
# 以 rain 为例：

# 重复统计（次数级别）
'tool_match/rain_repeat_ratio'       # 匹配率 = 调用次数/退化出现次数
'tool_match/rain_repeat_count'       # 对应工具被调用的总次数
'tool_match/rain_total_count'        # rain退化出现的总次数

# 不重复统计（样本级别）
'tool_match/rain_unique_ratio'       # 匹配率 = 匹配样本数/有该退化的样本数
'tool_match/rain_unique_matched'     # 至少调用过一次对应工具的样本数
'tool_match/rain_unique_total'       # 有rain退化的样本总数
```

### 总计

8个退化类型 × 6个指标 = **48个新指标**

---

## 🔍 验证清单

运行训练后，检查以下输出：

### ✅ 日志检查

```bash
# 1. 模式确认
[AGENT MODE] 对话模式: multi_tool_planning  ← 或 single_tool_iterative

# 2. 退化类型提取
[TOOL STATS] 样本0: 真实退化类型 ['rain', 'haze']  ← 非空列表
[TOOL STATS] 样本1: 真实退化类型 ['noise']

# 3. 工具调用收集
[TOOL STATS] 样本0 轮次1: 调用工具 ['mprnet_deraining', 'dehazeformer_dehaze']

# 4. 匹配统计
[TOOL STATS] === 工具-退化匹配统计 ===
[TOOL STATS]   rain: 28/30 = 0.933  ← 有具体数字
[TOOL STATS]   haze: 15/20 = 0.750

# 5. 指标收集
[METRICS] 收集了 48 个工具-退化匹配指标  ← 确认数量
```

### ✅ WandB 检查

1. 打开项目的 Charts 页面
2. 搜索 `tool_match/`
3. 应该看到 48 个指标
4. 创建折线图，观察匹配率随训练变化

---

## 🎯 实际应用价值

### 问题诊断

**场景1：某个退化类型匹配率低**
```
tool_match/motion blur_unique_ratio = 0.35
```
**分析：** 模型对运动模糊识别能力弱
**行动：** 增加运动模糊样本比例，或调整奖励权重

**场景2：重复率远大于1**
```
tool_match/noise_repeat_ratio = 2.8
tool_match/noise_unique_ratio = 0.95
```
**分析：** 识别率高，但重复调用多次
**行动：** 可能是单工具模式正常现象；多工具模式需要优化

**场景3：不同退化类型差异大**
```
tool_match/rain_unique_ratio = 0.95
tool_match/defocus blur_unique_ratio = 0.45
```
**分析：** 模型对雨天处理好，但对散焦模糊识别差
**行动：** 增加散焦模糊训练数据

---

## 📚 技术细节

### 数据提取（参考现有代码）

```python
# 参考: verl/workers/reward_manager/naive.py 第86-93行
ground_truth = {
    "reward_model": data_item.non_tensor_batch.get("reward_model", []),
    "env_name": data_item.non_tensor_batch.get("env_name", "")
}

# 参考: verl/utils/reward_score/image_restoration.py
# - parse_reward_model_to_degradations_v2 (第696-710行)
# - parse_env_name_to_degradations_v2 (第623-633行)
```

### 统计流程

```
1. 提取真实退化类型
   ├─ 优先：reward_model[i]['degradation_type']
   └─ 备用：env_name (逗号分隔，逆序)

2. 收集工具调用
   ├─ 单轮多工具：只看最后一轮
   └─ 多轮单工具：看所有轮次

3. 匹配检查
   └─ 工具名 in DEGRADATION_TO_TOOLS[退化类型]

4. 分别统计
   ├─ 重复：每次调用都计数
   └─ 不重复：样本级别只计数一次

5. 上传到 WandB
   └─ tool_match/* 命名空间
```

---

## ✅ 完成确认

所有需求已实现：

- ✅ 统计的是该类别的（只统计真实存在的退化）
- ✅ 从 reward_model 或 env_name 获取类别
- ✅ 参考了现有代码的提取方式
- ✅ 调用了对应工具才算匹配
- ✅ 重复和不重复两种统计
- ✅ 单轮多工具只看最后一轮
- ✅ WandB 独立 panel

准备就绪，可以运行训练测试了！🚀

