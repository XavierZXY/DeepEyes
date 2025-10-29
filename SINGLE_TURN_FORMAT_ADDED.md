# 单轮格式检查功能已添加 ✅

## 📋 更新概览

已成功添加单轮对话格式检查功能，允许您在单轮对话场景中使用，不再强制要求 `<answer>` 块。

---

## 🎯 新增功能

### 1. **新的格式检查函数**

**文件**: `verl/utils/reward_score/image_restoration.py`

**函数**: `check_single_turn_format()`

**位置**: 第108-192行

#### 检查规则：

✅ **必须满足**：
- 有 `<think>` 块，且内容 >= 10字符
- 如果有 `<tool_call>`，格式必须正确
- 如果有 `<answer>`，格式必须正确
- 工具名必须在允许列表中

❌ **不允许**：
- 同时有 `<tool_call>` 和 `<answer>`
- `<think>` 内容少于10字符
- 使用未授权的工具

⭐ **关键区别**：
- **不强制要求** `<answer>` 或 `<tool_call>` 必须存在
- 只要有 `<think>` 就可以通过格式检查

---

### 2. **新的配置参数**

#### 环境变量

```bash
export USE_SINGLE_TURN_FORMAT=True   # 启用单轮格式检查
```

#### 函数参数

在 `compute_score_v2()` 中新增：
```python
use_single_turn_format: bool = False
```

---

## 📝 使用方法

### **方法1: 通过环境变量（推荐）**

在您的训练脚本 `IRv2.sh` 中：

```bash
# ========== Reward Weight Configuration ==========
export FORMAT_REWARD_WEIGHT=0.3             
export QUALITY_REWARD_WEIGHT=0.7            
export USE_ENHANCED_FORMAT=False            # 关闭增强格式（多轮）
export USE_SINGLE_TURN_FORMAT=True          # ✅ 启用单轮格式
```

### **方法2: 直接调用函数**

```python
from verl.utils.reward_score.image_restoration import compute_score_v2

score = compute_score_v2(
    solution_str=response,
    ground_truth=gt,
    extra_info=extra,
    use_single_turn_format=True,  # ✅ 启用单轮格式
    use_enhanced_format=False,    # 关闭增强格式
)
```

---

## 🔄 格式检查优先级

```
USE_SINGLE_TURN_FORMAT > USE_ENHANCED_FORMAT
```

**示例**：
```bash
# 配置1: 单轮格式生效
USE_SINGLE_TURN_FORMAT=True
USE_ENHANCED_FORMAT=True
# 结果: 使用单轮格式（忽略enhanced）

# 配置2: 增强多轮格式
USE_SINGLE_TURN_FORMAT=False
USE_ENHANCED_FORMAT=True
# 结果: 使用增强多轮格式（v3）

# 配置3: 标准多轮格式
USE_SINGLE_TURN_FORMAT=False
USE_ENHANCED_FORMAT=False
# 结果: 使用标准多轮格式（v2）
```

---

## 📊 三种格式对比

| 特性 | 单轮格式 | 标准多轮 (v2) | 增强多轮 (v3) |
|------|---------|--------------|--------------|
| **环境变量** | `USE_SINGLE_TURN_FORMAT=True` | 默认 | `USE_ENHANCED_FORMAT=True` |
| **<think>必须** | ✅ | ✅ | ✅ |
| **<tool_call>或<answer>必须** | ❌ | ✅ | ✅ |
| **answer必须在最后** | - | ❌ | ✅ |
| **tool_call数>=退化数** | - | ❌ | ✅ |
| **适用场景** | 单轮对话 | 多轮对话 | 严格多轮 |

---

## ✅ 合法示例

### **单轮格式 - 只有think**
```
<think>
这是一个分析过程，需要仔细观察图像质量。
</think>
```
✅ **通过** - 单轮格式只要求think

### **单轮格式 - think + tool_call**
```
<think>
图像有模糊问题，需要去模糊处理。
</think>
<tool_call>
[{"name": "restormer_motion_deblurring", "arguments": {}}]
</tool_call>
```
✅ **通过** - 有think和合法的tool_call

### **单轮格式 - think + answer**
```
<think>
图像质量良好，不需要处理。
</think>
<answer>
{"restoration_log": ["clean"]}
</answer>
```
✅ **通过** - 有think和合法的answer

---

## ❌ 非法示例

### **错误1: think太短**
```
<think>
ok
</think>
```
❌ **失败** - think内容少于10字符

### **错误2: 同时有tool_call和answer**
```
<think>
处理图像
</think>
<tool_call>[...]</tool_call>
<answer>{...}</answer>
```
❌ **失败** - 不能同时有两者

### **错误3: 工具名不在允许列表**
```
<think>
使用自定义工具
</think>
<tool_call>
[{"name": "my_custom_tool", "arguments": {}}]
</tool_call>
```
❌ **失败** - my_custom_tool不在ALLOWED_TOOLS中

---

## 🚀 已修改的文件

1. ✅ `verl/utils/reward_score/image_restoration.py`
   - 新增 `check_single_turn_format()` 函数（第108-192行）
   - 修改 `compute_score_v2()` 添加 `use_single_turn_format` 参数
   - 更新格式检查逻辑（第1480-1504行）

2. ✅ `verl/utils/reward_score/__init__.py`
   - 添加 `USE_SINGLE_TURN_FORMAT` 环境变量读取（第101行）
   - 传递参数到 `compute_score_v2()`（第119行）

3. ✅ `examples/agent/IRv2.sh`
   - 添加 `USE_SINGLE_TURN_FORMAT=True` 配置（第58行）
   - 更新格式检查说明文档（第86-108行）

---

## 🎯 当前配置（IRv2.sh）

```bash
export USE_ENHANCED_FORMAT=False      # 关闭增强多轮格式
export USE_SINGLE_TURN_FORMAT=True    # ✅ 启用单轮格式检查
```

**效果**：
- ✅ 只要求有 `<think>` 块
- ✅ `<answer>` 可选（不强制）
- ✅ `<tool_call>` 可选（不强制）
- ✅ 适合您的单轮对话场景

---

## 📖 完整文档

详细说明已更新到训练脚本 `IRv2.sh` 的第86-108行。

---

## ✨ 总结

您现在可以使用单轮格式检查了！只需确保：

1. 设置 `USE_SINGLE_TURN_FORMAT=True`
2. 模型输出至少包含一个有意义的 `<think>` 块
3. 如果使用工具，确保工具名在允许列表中

**不再需要强制要求 `<answer>` 块！** 🎉

