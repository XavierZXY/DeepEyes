# 🔧 单轮最大工具数限制功能

## 📋 功能概述

新增 `MAX_TOOLS_PER_TURN` 环境变量，用于限制多工具链式模式下每轮对话可调用的最大工具数量。

---

## 🎯 功能特性

### **1. 双重限制机制**

#### **执行层面限制** (`parallel_env.py`)
```python
# 超过限制的工具直接截断，不执行
if max_tools_per_turn > 0 and len(valid_tools) > max_tools_per_turn:
    print(f'[TOOL LIMIT] 工具数量超限: {len(valid_tools)} > {max_tools_per_turn}，截断到前{max_tools_per_turn}个')
    tools = tools[:max_tools_per_turn]
```

**作用**：
- ✅ 节省计算时间（不执行超出限制的工具）
- ✅ 减少API调用成本
- ✅ 避免无效工具堆叠

#### **奖励层面限制** (`image_restoration.py`)
```python
# 超过限制的响应格式奖励为-1.0
if max_tools_per_turn > 0 and turn_tool_count > max_tools_per_turn:
    print(f' [ENHANCED FORMAT] 第{i+1}轮工具数量超限: {turn_tool_count} > {max_tools_per_turn}')
    return -1.0  # 格式违规
```

**作用**：
- ✅ 通过负奖励引导模型学习约束
- ✅ 强制模型精简工具规划
- ✅ 避免模型"暴力堆叠"所有工具

---

## ⚙️ 配置方式

### **IR.sh (多轮对话)**
```bash
export MAX_TOOLS_PER_TURN=3  # 推荐3-5，适合多工具链式模式
export USE_ENHANCED_FORMAT=True  # 必须启用才能检查格式
```

### **IRv2.sh (单轮对话)**
```bash
export MAX_TOOLS_PER_TURN=0  # 单轮模式建议0（无限制）
```

---

## 📊 参数说明

| 参数值 | 含义 | 适用场景 |
|--------|------|---------|
| `0` | 无限制（默认） | 探索阶段、单轮模式 |
| `3` | 每轮最多3个工具 | 严格控制成本 |
| `5` | 每轮最多5个工具 | 平衡性能和灵活性 |
| `>10` | 宽松限制 | 复杂任务、多退化场景 |

---

## 🔍 工作原理

### **完整流程**

```
1. 模型生成响应
   <tool_call>[tool1, tool2, tool3, tool4, tool5]</tool_call>

2. 执行层检查 (如果MAX_TOOLS_PER_TURN=3)
   ✓ 截断: [tool1, tool2, tool3]
   ✗ 不执行: [tool4, tool5]
   ⏱️ 节省时间

3. 奖励计算阶段
   ✓ 格式检查: 5个工具 > 3个限制
   ✗ 格式奖励: -1.0
   ✓ 质量奖励: 正常计算（基于实际执行的3个工具）
   
4. 总奖励
   total_reward = 0.3 × (-1.0) + 0.7 × quality_score
   = -0.3 + 0.7 × quality_score
   
5. 模型学习
   通过负奖励，模型学会控制工具数量 ≤ 3
```

---

## 💡 使用建议

### **推荐配置组合**

#### **方案1: 严格训练（推荐）**
```bash
export USE_ENHANCED_FORMAT=True
export MAX_TOOLS_PER_TURN=3
export FORMAT_REWARD_WEIGHT=0.3
export QUALITY_REWARD_WEIGHT=0.7
```
**优点**：
- 强制模型精简规划
- 节省计算成本
- 适合资源受限场景

#### **方案2: 灵活探索**
```bash
export USE_ENHANCED_FORMAT=True
export MAX_TOOLS_PER_TURN=5
export FORMAT_REWARD_WEIGHT=0.3
export QUALITY_REWARD_WEIGHT=0.7
```
**优点**：
- 保留一定灵活性
- 适合复杂退化场景
- 平衡性能和成本

#### **方案3: 无限制（baseline）**
```bash
export USE_ENHANCED_FORMAT=False
export MAX_TOOLS_PER_TURN=0
```
**优点**：
- 完全自由探索
- 适合初期实验
- 对比基准

---

## 📈 训练效果预期

### **限制前（MAX_TOOLS_PER_TURN=0）**
```
样本1: [tool1, tool2, tool3, tool4, tool5, tool6] → 6个工具，耗时60s
样本2: [tool1, tool2, ..., tool10] → 10个工具，耗时100s
平均工具数: 8个/样本
```

### **限制后（MAX_TOOLS_PER_TURN=3）**
```
初期（模型未学会）:
  样本1: [tool1, tool2, tool3, (tool4, tool5被截断)] → 格式奖励-1.0
  样本2: [tool1, tool2, (tool3...tool10被截断)] → 格式奖励-1.0

训练后（模型已学会）:
  样本1: [tool1, tool2, tool3] → 格式奖励+1.0，耗时30s ✅
  样本2: [tool1, tool2, tool3] → 格式奖励+1.0，耗时30s ✅
  平均工具数: 3个/样本
  训练速度提升: 60% ⚡
```

---

## 🧪 测试验证

```python
# 测试脚本
import os
os.environ['MAX_TOOLS_PER_TURN'] = '3'
os.environ['USE_ENHANCED_FORMAT'] = 'True'

response = """
<think>需要处理雨、雾、噪声、模糊、压缩伪影</think>
<tool_call>[
  {"name": "mprnet_deraining", "arguments": {}},
  {"name": "dehazeformer_dehaze", "arguments": {}},
  {"name": "swinir_denoising", "arguments": {}},
  {"name": "xrestormer_motion_deblurring", "arguments": {}},
  {"name": "fbcnn_jpeg_artifact_removal", "arguments": {}}
]</tool_call>
"""

# 预期结果:
# - 执行: 前3个工具 (mprnet, dehazeformer, swinir)
# - 不执行: 后2个工具 (xrestormer, fbcnn)
# - 格式奖励: -1.0 (因为5 > 3)
# - 质量奖励: 基于前3个工具的效果
```

---

## 🔧 实现细节

### **修改的文件**

1. **`parallel_env.py`** (执行层限制)
   - `agent_rollout_loop()`: 读取环境变量
   - `ParallelEnv.__init__()`: 保存参数
   - `execute_tool_call()`: 截断工具列表

2. **`image_restoration.py`** (奖励层限制)
   - `check_multiturn_format_v3_enhanced()`: 新增参数和检查
   - `compute_score_v2()`: 传递参数

3. **`__init__.py`** (参数传递)
   - 读取环境变量
   - 传递给`compute_score_v2()`

4. **`IR.sh` / `IRv2.sh`** (配置文件)
   - 添加`MAX_TOOLS_PER_TURN`环境变量
   - 添加详细说明文档

---

## ⚠️ 注意事项

### **1. 必须配合USE_ENHANCED_FORMAT使用**
```bash
# ❌ 无效配置
export MAX_TOOLS_PER_TURN=3
export USE_ENHANCED_FORMAT=False  # 不检查格式

# ✅ 正确配置
export MAX_TOOLS_PER_TURN=3
export USE_ENHANCED_FORMAT=True  # 必须启用
```

### **2. 不影响单轮模式**
```bash
# IRv2.sh (单轮对话)
export MAX_TOOLS_PER_TURN=0  # 单轮模式建议0
export USE_SINGLE_TURN_FORMAT=True  # 单轮已有其他格式检查
```

### **3. 只限制单轮工具数，不限制总工具数**
```bash
# 多轮对话示例 (MAX_TOOLS_PER_TURN=3)
轮次1: [tool1, tool2, tool3] ✅ 符合限制
轮次2: [tool4, tool5] ✅ 符合限制
总共: 5个工具 ✅ 允许

# 单轮违规示例
轮次1: [tool1, tool2, tool3, tool4, tool5] ❌ 违反限制
```

---

## 📝 监控日志

训练时关注以下日志：

```bash
# 1. 配置加载
[AGENT MODE] 单轮最大工具数: 3 (超过将被截断)
[INFO] Max Tools Per Turn: 3

# 2. 执行层截断
[TOOL LIMIT T1-样本0] 工具数量超限: 5 > 3，截断到前3个

# 3. 格式检查
[ENHANCED FORMAT] 第1轮工具数量超限: 5 > 3（单轮最大工具数）

# 4. 奖励计算
[DEBUG image_restoration_v2] format_score=-1.000, quality_score=0.750
[DEBUG image_restoration_v2] total_score=-0.050 (format违规)
```

---

## 🎓 FAQ

**Q1: 为什么既要执行层截断，又要奖励层惩罚？**  
A: 
- 执行层截断：节省时间和成本
- 奖励层惩罚：引导模型学习，避免以后再犯

**Q2: 如果退化数量>MAX_TOOLS_PER_TURN怎么办？**  
A: 模型需要多轮处理或选择最重要的退化。这正是训练目标之一。

**Q3: 会不会影响模型性能？**  
A: 
- 短期：可能降低性能（限制了工具数量）
- 长期：提升效率（模型学会精简规划）
- 建议：根据任务复杂度调整限制值

**Q4: IRv2为什么建议设置为0？**  
A: IRv2是单轮对话模式，已经在system prompt层面引导单个工具，无需此限制。

---

**功能完成时间**: 2025-10-21  
**适用版本**: AIR v8+  
**推荐配置**: `MAX_TOOLS_PER_TURN=3` + `USE_ENHANCED_FORMAT=True`

