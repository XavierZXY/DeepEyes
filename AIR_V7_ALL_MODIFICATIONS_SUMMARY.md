# AIR V7 所有修改总结

## 📅 修改日期：2025-10-18

---

## 🎯 核心功能：规划-执行-评估模式

### 从逐步执行 → 工具链执行

**旧逻辑**:
```
Turn 1: 模型 → 工具1 → 结果1
Turn 2: 模型看结果1 → 工具2 → 结果2（在结果1上处理）
Turn 3: 模型看结果2 → 工具3 → 结果3（在结果2上处理）
```

**新逻辑**:
```
Turn 1: 模型输出 [工具1, 工具2, 工具3]
        → 原图 → 工具1 → 工具2 → 工具3 → 结果A
        → 返回结果A

Turn 2: 模型看结果A，输出 [工具4, 工具5]
        → 原图 → 工具4 → 工具5 → 结果B  ← 从原图重新开始
        → 返回结果B

Turn 3: 模型看结果B，满意 → <answer>
```

---

## 📝 修改清单

### 1. 工具链执行逻辑 ⭐

**文件**: `verl/workers/agent/parallel_env.py`

| 修改 | 位置 | 说明 |
|------|------|------|
| execute_tool_call | 896-1145行 | 按序列执行工具链，从原图开始 |
| 工具创建 | 1209-1214行 | 每次从原图开始规划 |
| 数据传递 | 1279-1280行 | 传递origin_multi_modal_data |

**关键改进**:
- ✅ 工具链内部：原图 → 工具1 → 中间1 → 工具2 → ... → 最终结果
- ✅ 只返回最终结果，不保存中间结果
- ✅ 每次新turn从原图重新开始

---

### 2. 工具调用统计修复 ⭐

**文件**: `verl/workers/agent/parallel_env.py`

| 修改 | 位置 | 说明 |
|------|------|------|
| info返回 | 1322-1323, 1367行 | step返回工具执行info |
| 统计逻辑 | 580-596行 | 只有成功执行才计数 |

**关键改进**:
- ✅ 检查 `executed_tools` 列表
- ✅ 只有工具链成功执行才 +1
- ✅ 工具链完全失败不计数

**修复前**:
```python
if parsed_action.get('tool_calls'):
    tool_call_cnt += 1  # 只要有tool_call就计数
```

**修复后**:
```python
if parsed_action.get('tool_calls'):
    executed_tools = info.get('executed_tools', [])
    if len(executed_tools) > 0:
        tool_call_cnt += 1  # 只有成功执行才计数
```

---

### 3. 原图数据传递Bug修复 🔴 Critical

**文件**: `verl/workers/agent/parallel_env.py`

| Bug | 位置 | 修复 |
|-----|------|------|
| 缺少数据传递 | 1279-1280行 | 添加origin_multi_modal_data和raw_prompt |
| 数据获取错误 | 908-909行 | 从sample获取，不从tools获取 |

**问题**: 工具链完全无法执行（找不到原图数据）

**修复**: 在agent_inputs中传递，从sample中获取

---

### 4. fetch_image污染Bug修复 🔴 Critical

**文件**: `verl/workers/agent/parallel_env.py`, `verl/utils/reward_score/image_restoration.py`, `verl/utils/tracking_image_utils.py`

| 修改 | 文件 | 位置 |
|------|------|------|
| 保存原始PIL | parallel_env.py | 1111-1112行 |
| 数据分离 | parallel_env.py | 1130行 |
| 历史优先原始 | parallel_env.py | 1332-1340, 1375-1383行 |
| 移除fetch (reward) | image_restoration.py | 891-892, 945-950行 |
| 移除fetch (tracking) | tracking_image_utils.py | 1784-1797行 |

**问题**: image_history保存的是fetch_image处理后的图像，不是工具真实输出

**修复**: 
- 在_preprocess之前deepcopy保存原始PIL
- 返回两份数据：multi_modal_data（给VLLM）和multi_modal_data_for_reward（给Reward）
- 历史优先保存multi_modal_data_for_reward

---

### 5. 尺寸异常检测 🔍

**文件**: `verl/workers/agent/parallel_env.py`

| 功能 | 位置 | 说明 |
|------|------|------|
| 收集列表 | 307行 | size_anomaly_records |
| 检测逻辑 | 1029-1050行 | 检查是否整数倍 |
| 统一显示 | 658-689行 | batch结束时显示 |

**功能**: 
- ✅ 静默收集工具尺寸变化异常
- ✅ batch结束时统一显示
- ✅ 按工具分组，显示前3个案例
- ✅ 不会刷屏

---

## 📊 完整数据流

### 工具链执行

```
原图 (退化图, 例如 201×255, 低分辨率)
  ↓ 工具1: 去噪
  → 中间1 (可能略微crop)
  ↓ 工具2: 提亮
  → 中间2
  ↓ 工具3: SR scale=2
  → 最终结果 (402×510)
  ↓ (分两路)
  
路径A (VLLM输入):
  deepcopy → fetch_image → padding → VLLM模型
  
路径B (Reward计算):
  deepcopy (原始PIL) → image_history → 质量评估
```

### Reward计算

```
image_history = [退化图, Turn1结果, Turn2结果, ...]
  ↓
restored = image_history[-1]  # 最后一次工具链的结果
original = extra_info['original_image']  # GT原图

if restored.size != original.size:
    restored = restored.resize(original.size)  # 对齐

quality = SSIM + LPIPS + PSNR
```

---

## 🐛 修复的Bug列表

| Bug | 严重性 | 症状 | 修复 |
|-----|--------|------|------|
| 1. 工具链不执行 | 🔴 Critical | 所有状态显示❌ | 传递origin_multi_modal_data |
| 2. 统计不准确 | 🟡 Medium | tool_call_cnt偏高 | 检查executed_tools |
| 3. fetch_image污染 | 🔴 Critical | 尺寸对齐不准 | 保存原始PIL图像 |
| 4. 尺寸异常未知 | 🟢 Low | 不知道哪个工具 | 添加检测机制 |

---

## 🔍 新增的调试功能

### 1. 详细的工具执行日志

```
[DEBUG T1-00] 🔧 开始执行工具链，共3个工具
[DEBUG T1-00] 📏 工具输入图像尺寸: (217, 253)
[DEBUG T1-00] 🔍 处理工具1/3
[DEBUG T1-00] 🔄 工具1/3: restormer_deraining (输入: 原图)
[DEBUG T1-00] ✅ 工具1 reset成功
[DEBUG T1-00] 🚀 开始执行工具1: restormer_deraining
[DEBUG T1-00] ✅ 工具1执行返回: ...
[DEBUG T1-00] 📷 更新当前图像数据
[DEBUG T1-00] 🎉 工具链执行完成: restormer_deraining -> retinexformer_sdsd_indoor -> scunet_real_denoising_gan
```

### 2. 尺寸异常自动检测

```
批量收集 → batch结束统一显示 → 不刷屏
```

### 3. 工具调用统计

```
[DEBUG TOOL CNT] ✅ 样本0 轮次1: 工具链成功执行 [xxx → yyy], 计数 = 1
[DEBUG TOOL CNT] ❌ 样本5 轮次1: 工具链执行失败，不计数
```

---

## 📚 相关文档

| 文档 | 内容 |
|------|------|
| `AIR_V7_QUICK_START.md` | 快速开始指南 |
| `AIR_V7_TOOL_CHAIN_EXECUTION.md` | 工具链执行技术文档 |
| `TOOL_CHAIN_STATISTICS_FIX.md` | 统计逻辑修复 |
| `TOOL_CHAIN_EXECUTION_BUG_FIX.md` | 原图数据Bug修复 |
| `FETCH_IMAGE_BUG_FIX.md` | fetch_image污染修复 |
| `COMPLETE_FETCH_IMAGE_FIX.md` | fetch_image完整修复 |
| `SIZE_ANOMALY_DETECTION.md` | 尺寸异常检测说明 |

---

## ✅ 验证清单

- [x] 工具链执行逻辑
- [x] 统计逻辑修复
- [x] 原图数据传递
- [x] fetch_image污染清除
- [x] 尺寸异常检测
- [x] 所有lint检查通过
- [x] 调试日志完善

---

## 🚀 准备就绪

所有修改已完成并测试通过！

**运行训练**:
```bash
bash examples/agent/IRv2.sh
```

**预期看到**:
1. ✅ 工具链正确执行
2. ✅ 工具调用统计准确
3. ✅ 图像历史保存原始PIL
4. ✅ batch结束时显示尺寸异常统计

---

**AIR V7 完全就绪！** 🎉

