# fetch_image污染图像历史Bug - 修复总结

## 🐛 严重Bug发现

**发现者**: 用户 🎯

**问题**: `image_history` 保存的是经过 `fetch_image` 处理后的图像，而不是原始PIL图像！

---

## 🔍 问题分析

### 数据污染路径

```python
# 工具输出（第1054行）
final_tool_result = {
    "prompt": result_prompt,
    "multi_modal_data": current_image_data  # ← PIL图像 (2016, 1344)
}

# 后处理（第1095行）
prompt_str = final_tool_result.pop("prompt", "")  # pop掉prompt

# _preprocess_multi_modal_inputs（第1111行）
# **final_tool_result = {"multi_modal_data": {"image": [PIL图像]}}
_preprocess_multi_modal_inputs(prompt_str, processor, **final_tool_result)

# _preprocess_multi_modal_inputs内部（第264, 281行）
input_mm_data = kwargs.get("multi_modal_data", ...)  # ← 获取引用
input_mm_data["image"] = [process_image(img) for ...]  # ← 修改原始数据！
# process_image 调用 fetch_image，会padding到28的倍数

# 返回到execute_tool_call（第1116行）
**final_tool_result  # ← multi_modal_data已经被修改！

# 保存到历史（第1278行）
self.multi_modal_data_history_list[valid_idx].append(
    deepcopy(obs['multi_modal_data'])  # ← 保存的是fetch后的！
)
```

### 导致的后果

```python
工具输出: PIL图像 (2016, 1344)
  ↓
_preprocess_multi_modal_inputs 修改
  ↓
fetch_image处理: (2016, 1344) → (2016, 1344)  # 或可能变化
  ↓
保存到history: fetch后的图像
  ↓
Reward计算: 使用fetch后的图像 vs GT原图

❌ 问题：两者都经过fetch_image，尺寸对齐不准确！
```

---

## ✅ 修复方案

### 修复1: 保存原始PIL图像

**文件**: `verl/workers/agent/parallel_env.py`

**位置**: 第1104-1123行

```python
# 🔥 关键修复：保存原始PIL图像（用于reward计算）
# _preprocess_multi_modal_inputs 会修改 multi_modal_data（调用process_image/fetch_image）
# 所以先deepcopy保存原始数据
original_multi_modal_data_for_reward = deepcopy(final_tool_result.get("multi_modal_data", {}))
print(f'[DEBUG {turn_info}] 💾 保存原始multi_modal_data用于reward计算')

print(f'[DEBUG {turn_info}] 🔄 预处理multi_modal输入...')
prompt_str_vllm, obs_token_ids_model, mm_inputs = _preprocess_multi_modal_inputs(
    prompt_str, processor, **final_tool_result
)  # ← 这里会修改 final_tool_result["multi_modal_data"]

tool_result_info = {
    "prompt_token_ids_vllm": obs_token_ids_vllm,
    "prompt_token_ids_model": obs_token_ids_model,
    **final_tool_result   # multi_modal_data (已被fetch_image处理，用于VLLM)
}

# 🔥 关键：添加原始multi_modal_data用于reward计算
tool_result_info["multi_modal_data_for_reward"] = original_multi_modal_data_for_reward
```

### 修复2: 优先保存原始图像到历史

**位置**: 第1286-1295行, 第1322-1331行

```python
# 🔥 优先使用原始PIL图像（用于reward计算），而不是fetch后的
if isinstance(obs, dict):
    if 'multi_modal_data_for_reward' in obs:
        # 使用原始PIL图像（工具直接输出，未经fetch_image）
        self.multi_modal_data_history_list[valid_idx].append(
            deepcopy(obs['multi_modal_data_for_reward'])
        )
        print(f'[DEBUG] 💾 保存原始PIL图像到历史')
    elif 'multi_modal_data' in obs:
        # Fallback: 使用fetch后的（兼容旧逻辑）
        self.multi_modal_data_history_list[valid_idx].append(
            deepcopy(obs['multi_modal_data'])
        )
        print(f'[DEBUG] ⚠️  使用fetch后的图像（fallback）')
```

### 修复3: 移除reward计算中的fetch_image

**文件**: `verl/utils/reward_score/image_restoration.py`

**位置**: 第889-892行, 第943-950行

```python
# 直接使用PIL图像，不做fetch_image处理
# （fetch_image是为vision transformer准备的，reward计算不需要）
restored_image = restored_image_pil
print(f"[DEBUG] 复原图尺寸（直接使用PIL）: {restored_image.size}")

# 原图同样不做fetch_image
print(f"[DEBUG] 原图尺寸（直接使用PIL）: {original_image.size}")
```

---

## 📊 修复前后对比

### 修复前（Bug）❌

```python
工具输出:
  PIL图像 (2016, 1344)
    ↓
  _preprocess_multi_modal_inputs 修改原始数据
    ↓
  fetch_image处理
    ↓
  保存到 image_history: fetch后的图像 (可能变成 2016, 1344 padding后)
    ↓
Reward计算:
  原图: bytes → PIL (2040, 1524) → fetch_image → (2044, 1512)
  复原图: fetch后的图像
  
  尺寸不匹配！需要resize对齐
```

### 修复后（Correct）✅

```python
工具输出:
  PIL图像 (2016, 1344)
    ↓ (分两路)
    
路径1（给VLLM用）:
  deepcopy → _preprocess_multi_modal_inputs → fetch_image
    ↓
  obs["multi_modal_data"] (fetch后，给VLLM)
  
路径2（给Reward用）:
  deepcopy → 直接保存
    ↓
  obs["multi_modal_data_for_reward"] (原始PIL)
    ↓
  保存到 image_history: 原始PIL图像 (2016, 1344)
    ↓
Reward计算:
  原图: bytes → PIL (2040, 1524) → 直接使用 ✅
  复原图: 原始PIL (2016, 1344) → 直接使用 ✅
  
  尺寸对齐更准确！
```

---

## 🎯 关键改进

### 1. 数据隔离

```python
obs = {
    "multi_modal_data": fetch后的图像,           # ← 给VLLM模型用
    "multi_modal_data_for_reward": 原始PIL图像,  # ← 给Reward计算用
}
```

**好处**:
- ✅ VLLM得到正确处理的输入（fetch_image padding）
- ✅ Reward计算得到原始图像（无padding干扰）
- ✅ 两者互不影响

### 2. 历史保存优先级

```python
if 'multi_modal_data_for_reward' in obs:
    # 优先使用原始PIL
    save(obs['multi_modal_data_for_reward'])
elif 'multi_modal_data' in obs:
    # Fallback: 兼容旧逻辑
    save(obs['multi_modal_data'])
```

### 3. 移除Reward计算中的fetch_image

```python
# 原图和复原图都不使用fetch_image
# 直接使用PIL图像计算SSIM/LPIPS/PSNR
```

---

## 📈 预期效果

### 修复后的日志输出

```bash
[DEBUG T1-00] 💾 保存原始multi_modal_data用于reward计算
[DEBUG T1-00] 🔄 预处理multi_modal输入...
[DEBUG T1-00] ✅ 预处理完成，已保存原始图像用于reward
[DEBUG step 1-00] 💾 保存原始PIL图像到历史

[DEBUG] 复原图尺寸（直接使用PIL）: (2016, 1344)  ← 原始尺寸
[DEBUG] 原图尺寸（直接使用PIL）: (2040, 1524)      ← 原始尺寸
[DEBUG] 尺寸不匹配: restored=(2016, 1344) vs original=(2040, 1524)
[DEBUG] 复原图已resize到: (2040, 1524)  ← resize对齐
[DEBUG image_quality] ssim=0.8234, lpips=0.1567, psnr=28.45 ✅
```

---

## 🔍 验证方法

### 运行训练后检查

```bash
# 1. 检查是否保存了原始PIL图像
grep "💾 保存原始PIL图像到历史" logs/*.log | wc -l

# 2. 检查是否有fallback（不应该有）
grep "⚠️  使用fetch后的图像" logs/*.log | wc -l

# 3. 检查尺寸对齐
grep "尺寸不匹配" logs/*.log | head -10
```

**健康指标**:
- `保存原始PIL图像` 的数量 >> `使用fetch后的图像` 的数量
- 如果都是 `💾 保存原始PIL` → ✅ 完美
- 如果有 `⚠️  使用fetch后的` → 需要检查为什么

---

## 🎉 修复总结

### 三层修复

| 层次 | 修复内容 | 位置 |
|------|---------|------|
| 1. 数据保存 | 保存原始PIL图像副本 | parallel_env.py 第1107行 |
| 2. 历史更新 | 优先使用原始PIL | parallel_env.py 第1288, 1324行 |
| 3. Reward计算 | 移除fetch_image处理 | image_restoration.py 第889-950行 |

### 数据流图

```
工具输出 (PIL图像)
  ↓ (分叉)
  ├─→ [路径1: VLLM输入]
  │     deepcopy
  │       ↓
  │     _preprocess_multi_modal_inputs
  │       ↓
  │     fetch_image (padding到28倍数)
  │       ↓
  │     obs["multi_modal_data"]
  │       ↓
  │     VLLM模型
  │
  └─→ [路径2: Reward计算] ← 🔥 新增
        deepcopy
          ↓
        obs["multi_modal_data_for_reward"]
          ↓
        image_history (原始PIL)
          ↓
        Reward计算 (直接使用PIL，不fetch)
```

---

## ✅ 验证清单

- [x] 保存原始multi_modal_data（第1107行）
- [x] 添加multi_modal_data_for_reward到返回（第1122行）
- [x] 历史更新优先使用原始PIL（第1288, 1324行）
- [x] Reward计算移除fetch_image（image_restoration.py）
- [x] 添加调试日志
- [x] 无linter错误

---

**修复时间**: 2025-10-18  
**发现者**: 用户  
**严重程度**: 🔴 Critical（影响reward准确性）  
**状态**: ✅ 已修复  
**影响**: 更准确的图像质量评估，避免fetch_image padding干扰

