# V8分支问题详细报告

## 🔴 确认：v8分支存在5个Critical Bug

**当前分支**: `air_v8-2`
**检查时间**: 2025-10-18
**状态**: ❌ 包含今天在v7上修复的所有bug

---

## 📋 问题清单

### 1. 工具链执行模式是旧的 🔴 Critical

**位置**: `parallel_env.py` 第1139-1157行

**当前代码**:
```python
# Execute tools sequentially
for i, tool in enumerate(tools):
    tool_result, reward, done, info = tool.execute(...)
    final_tool_result = tool_result  # 只保留最后一个
```

**问题**:
- ❌ 逐个执行，每个工具在上一个结果上处理
- ❌ 不是从原图开始的工具链模式
- ❌ 无法实现规划-执行-评估

**影响**: 无法实现规划-执行-评估模式

---

### 2. fetch_image污染 🔴 Critical

**位置**: `parallel_env.py` execute_tool_call返回

**问题**:
- ❌ 没有保存`multi_modal_data_for_reward`
- ❌ `_preprocess_multi_modal_inputs`会修改原始数据
- ❌ image_history保存的是fetch后的图像

**影响**: 
- GT和复原图尺寸不匹配（因为fetch_image padding）
- Reward计算不准确

---

### 3. 初始化使用fetch后的数据 🔴 Critical

**位置**: `parallel_env.py` reset()函数

**当前代码**:
```python
image_history = [deepcopy(multi_modal_data)] if multi_modal_data else []
```

**问题**:
- ❌ 使用`multi_modal_data`（已被process_image/fetch_image处理）
- ❌ 应该使用`origin_multi_modal_data`（原始PIL）

**影响**: 
- image_history[0]就是错的（fetch padding后）
- 导致尺寸不匹配

---

### 4. extra_info索引错位 🔴 Critical

**位置**: `parallel_env.py` extra_info添加逻辑

**问题**:
- ❌ extra_info使用`orig_idx = i // sampling_params.n`
- ❌ image_history使用直接索引`i`
- ❌ 两者索引逻辑不一致

**影响**: 
- GT原图和复原图来自不同样本
- Reward计算完全错误
- 出现宽高比例严重不一致的情况

**症状**:
```
复原图(848, 1020) vs GT(868, 836)
→ 宽高比完全不对，来自不同样本！
```

---

### 5. 工具调用统计不准确 🟡 Medium

**问题**:
- ⚠️ 可能只要有tool_call就计数
- ⚠️ 不检查是否成功执行

**影响**: 统计指标不准确

---

## ✅ v7分支的修复（参考）

### 修复文件列表

| 文件 | 修复内容 |
|------|---------|
| `parallel_env.py` | 8处关键修复 |
| `image_restoration.py` | 移除fetch_image |
| `tracking_image_utils.py` | 移除fetch_image |

### 关键修复代码

#### 修复1: 工具链执行模式

```python
# v7 第896-1145行
def execute_tool_call(..., size_anomaly_records=None):
    # 工具链执行：逐个应用，上一个的输出作为下一个的输入
    current_image_data = origin_multi_modal_data  # 从原图开始
    
    for i, tool in enumerate(tools):
        tool.reset(multi_modal_data=current_image_data, ...)
        tool_result = tool.execute(...)
        current_image_data = tool_result['multi_modal_data']  # 链式传递
    
    # 返回最终结果
    return {"multi_modal_data": current_image_data}
```

#### 修复2: 保存原始PIL

```python
# v7 第1104-1123行
# 保存原始PIL副本
original_multi_modal_data_for_reward = deepcopy(
    final_tool_result.get("multi_modal_data", {})
)

# 调用_preprocess（会修改final_tool_result）
prompt_str_vllm, obs_token_ids_model, mm_inputs = _preprocess_multi_modal_inputs(...)

# 返回两份数据
tool_result_info = {
    "multi_modal_data": ...,  # fetch后（给VLLM）
    "multi_modal_data_for_reward": original_multi_modal_data_for_reward  # 原始（给Reward）
}
```

#### 修复3: 初始化使用origin

```python
# v7 第1518行
image_history = [deepcopy(origin_multi_modal_data)] if origin_multi_modal_data else []
```

#### 修复4: extra_info索引统一

```python
# v7 第926-929行
for i in range(expected_size):
    # 直接使用i索引（与image_history_list一致）
    extra_info_array[i] = saved_extra_info_list[i]
```

---

## 🚀 解决方案

### 推荐：从v7合并

```bash
# 切换到v8分支
git checkout air_v8-2

# 合并v7的修复
git merge air_v7

# 解决冲突（如果有）
# 然后提交
```

### 或者：手动应用修复

**需要修改3个文件**:
1. `verl/workers/agent/parallel_env.py` - 8处修复
2. `verl/utils/reward_score/image_restoration.py` - 移除fetch_image
3. `verl/utils/tracking_image_utils.py` - 移除fetch_image

**详细修改可以参考air_v7分支或今天创建的文档**

---

## 📝 v8分支问题影响

### 如果不修复会怎样

1. **无法实现规划-执行-评估** - 还是逐步执行
2. **GT原图和复原图错配** - Reward计算错误
3. **尺寸严重不匹配** - 出现(848, 1020) vs (868, 836)这种异常
4. **训练效果差** - Reward信号错误

---

## ✅ 修复后的效果（v7已验证）

```
GT索引正确:
  Sample 0,1,2,3: GT都相同（n=4 sampling）

尺寸关系正确:
  GT=(868, 932), 退化=(868, 932), 复原=(868, 932) ✅

工具链正常执行:
  原图 → 工具1 → 工具2 → 工具3 → 最终结果 ✅
```

---

**建议立即从v7合并修复！** 🚀

