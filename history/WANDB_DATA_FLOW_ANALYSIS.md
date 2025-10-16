# WandB 数据上传流程分析

## 核心数据流概览

```
训练数据 → Rollout → RewardManager → Trainer → WandB上传
```

## 详细数据来源分析

### 1. 图像轨迹数据 (Image History)

**来源位置**: `verl/workers/agent/parallel_env.py`
- **字段名**: `image_history_list`
- **数据类型**: `List[List[PIL.Image | np.ndarray | bytes]]`
- **含义**: 
  - `image_history[0]`: 退化后的输入图像（degraded image）
  - `image_history[1:]`: 每次工具调用后的处理结果图像
  - 最后一张: 最终复原的图像（restored image）

**生成过程**:
1. 环境初始化时加载数据集中的图像
2. 每次调用工具（如denoising, deblurring等）时追加新图像到列表
3. 在rollout结束时打包到`non_tensor_batch['image_history_list']`

**使用位置**:
- `NaiveRewardManager`: 添加到`extra_info`供奖励计算使用
- `tracking_image_utils.py`: 创建轨迹可视化图像
- `ray_trainer.py`: 传递给wandb上传函数

---

### 2. 对话历史数据 (Conversation History)

**来源位置**: `verl/workers/agent/parallel_env.py`
- **字段名**: `conversation_history_list`
- **数据类型**: `List[List[Dict]]`
- **结构**:
```python
[
    {
        'turn': 1,
        'response': '<think>...</think><tool_call>[...]</tool_call>',
        'is_done': False
    },
    {
        'turn': 2,
        'response': '<think>...</think><answer>...</answer>',
        'is_done': True
    }
]
```

**生成过程**:
1. 每轮对话中，模型生成响应文本
2. 记录turn编号、响应内容、是否结束标志
3. 在rollout结束时打包到`non_tensor_batch['conversation_history_list']`

**使用位置**:
- `tracking_image_utils.py`: 提取工具名称用于图像标注
- `tracking_image_utils.py`: 在表格中展示每轮的think和tools内容
- 退化类型预测匹配分析

---

### 3. 原图数据 (Original/Ground Truth Images)

**来源位置**: `verl/workers/agent/parallel_env.py` → `extra_info`
- **字段名**: `original_images` (via `extra_info['original_image']`)
- **数据类型**: `List[PIL.Image | np.ndarray | bytes]`
- **含义**: 未经退化的干净原图（Ground Truth）

**生成过程**:
1. 数据集加载时同时加载原图和退化图
2. 原图存储在`extra_info['original_image']`
3. 在准备batch时提取所有样本的原图到列表

**使用位置**:
- **图像质量指标计算**: 
  - SSIM (Structural Similarity)
  - LPIPS (Learned Perceptual Image Patch Similarity)
  - PSNR (Peak Signal-to-Noise Ratio)
- **轨迹可视化**: 在图像序列最左侧显示"Ground Truth"
- **对比分析**: 计算退化图和复原图与原图的差异

---

### 4. 奖励相关数据 (Reward Extra Info)

**来源位置**: `verl/workers/reward_manager/naive.py` → `NaiveRewardManager`
- **字段名**: `reward_extra_infos_dict`
- **数据类型**: `Dict[str, List[float | str]]`

**包含的指标**:

#### 4.1 格式奖励 (Format Score)
- **来源**: `verl/utils/reward_score/image_restoration.py` → `check_multiturn_format_v2()`
- **字段**: `format_score`
- **取值**: 1.0 (完美格式) 或 -1.0 (格式错误)
- **检查内容**:
  - `<think>` 块存在且内容 ≥10字符
  - `<tool_call>` 或 `<answer>` 格式正确
  - JSON格式有效
  - 工具名称在允许列表中

#### 4.2 图像质量奖励 (Image Quality Score)
**来源**: `verl/utils/reward_score/image_quality_metrics.py`

##### 有参考指标 (Reference-based Metrics)
需要原图（Ground Truth）:
- `ssim_score_ref`: SSIM分数 (0-1, 越高越好)
- `lpips_score_ref`: LPIPS分数 (0-1, 越低越好)
- `psnr_score_ref`: PSNR分数 (dB, 越高越好)

**计算函数**: `compute_image_restoration_reward(img1, img2, target='hq')`
```python
# img1: 复原后的图像 (image_history[-1])
# img2: 原图 (original_image)
# 返回综合质量分数
```

##### 无参考指标 (No-reference Metrics)
不需要原图:
- `niqe_score`: Natural Image Quality Evaluator (越低越好)
- `brisque_score`: Blind/Referenceless Image Spatial Quality Evaluator
- `cpbd_score`: Cumulative Probability of Blur Detection
- `clip_iqa_score`: CLIP-based IQA
- `hyper_iqa_score`: HyperIQA

**计算函数**: `compute_no_reference_image_restoration_reward(img)`

#### 4.3 退化类型相关 (Degradation Type)
- **来源**: `reward_model` 字段（从数据集加载）
- **字段**:
  - `degradation_type`: 退化类型名称（如"noise", "motion blur"等）
  - `degradation_types_all`: 所有退化类型列表（多退化情况）
  - `degradation_type_score`: 退化类型预测奖励
  - `reward_model`: 完整的退化信息列表
    ```python
    [
        {
            'degradation_type': 'noise',
            'degradation_level': 'medium',
            'degradation_order': 0
        },
        {
            'degradation_type': 'motion blur',
            'degradation_level': 'severe',
            'degradation_order': 1
        }
    ]
    ```

**生成过程**:
1. 数据集定义退化类型和强度
2. 存储在`non_tensor_batch['reward_model']`
3. RewardManager提取并添加到`reward_extra_infos_dict`

#### 4.4 特殊样本标记 (Special Sample Flags)
- `is_clean_sample`: 是否为干净样本（无退化）
- `clean_accuracy`: 干净样本的判断准确度
- `ir_has_processed_image`: 是否有被工具处理过的图像
- `ir_quality_reward_zero`: 质量奖励是否为0
- `ir_quality_reward_positive`: 质量奖励是否>0

---

### 5. 退化图和复原图的指标 (Degraded & Restored Metrics)

**来源位置**: `verl/utils/tracking_image_utils.py` → `compute_degraded_and_restored_metrics_for_indices()`
- **计算时机**: 上传到wandb表格之前
- **计算逻辑**:
```python
degraded_img = image_history[0]  # 第一张是退化图
restored_img = image_history[-1]  # 最后一张是复原图
original_img = original_images[idx]  # 原图

# 计算退化图与原图的差距
degraded_ssim = compute_ssim(degraded_img, original_img)
degraded_lpips = compute_lpips(degraded_img, original_img)
degraded_psnr = compute_psnr(degraded_img, original_img)

# 计算复原图与原图的差距
restored_ssim = compute_ssim(restored_img, original_img)
restored_lpips = compute_lpips(restored_img, original_img)
restored_psnr = compute_psnr(restored_img, original_img)

# 计算提升百分比
improvement_ssim = ((restored_ssim - degraded_ssim) / max(degraded_ssim, 0.01)) * 100
improvement_lpips = ((degraded_lpips - restored_lpips) / max(degraded_lpips, 0.01)) * 100
improvement_psnr = ((restored_psnr - degraded_psnr) / max(abs(degraded_psnr), 0.1)) * 100
```

**输出字段**:
- `degraded_ssim`, `degraded_lpips`, `degraded_psnr`: 退化图指标
- `restored_ssim`, `restored_lpips`, `restored_psnr`: 复原图指标
- `improvement_ssim%`, `improvement_lpips%`, `improvement_psnr%`: 提升百分比

---

### 6. 预测退化类型分析 (Predicted Degradation Type)

**来源位置**: `verl/utils/tracking_image_utils.py` → `_log_conversation_table()`
- **提取逻辑**:
```python
# 从conversation_history中提取所有调用的工具
for turn in conversation_history:
    response = turn['response']
    # 解析 <tool_call>[{...}]</tool_call>
    tools = extract_tools_from_response(response)
    for tool in tools:
        tool_name = tool['name']
        # 映射工具名到退化类型
        degradation_type = tool_to_degradation_mapping(tool_name)
        # 例如: swinir_denoising → "noise"
```

**工具到退化类型映射**: `verl/utils/reward_score/tool_to_degradation_mapping.py`
```python
TOOL_TO_DEGRADATION_MAP = {
    "swinir_denoising": "noise",
    "mprnet_denoising": "noise",
    "restormer_motion_deblurring": "motion blur",
    "mprnet_motion_deblurring": "motion blur",
    "xrestormer_motion_deblurring": "motion blur",
    "restormer_defocus_deblurring": "defocus blur",
    "restormer_deraining": "rain",
    "mprnet_deraining": "rain",
    "swinir_jpeg_artifact_removal": "jpeg compression artifact",
    "swinir_super_resolution": "low resolution",
    "dehazeformer_dehaze": "haze",
    "gamma_correction": "dark",
    "histogram_equalization": "dark",
    # ...
}
```

**匹配判断**:
- `prediction_match`: ✅ 完全匹配 | ⚠️ 部分正确 | ❌ 完全错误 | ❓ 未知

---

### 7. 工具执行状态分析 (Tool Status & Failure Reason)

**来源位置**: `verl/utils/tracking_image_utils.py` → `_log_conversation_table()`
- **字段**:
  - `Tool_Status`: 工具执行状态
  - `Failure_Reason`: 失败原因分析

**判断逻辑**:
```python
has_tool_request = '<tool_call>' in conversation_history
has_tool_execution = len(image_history) > 1

if has_tool_request and has_tool_execution:
    tool_status = "✅ Success"
    failure_reason = "-"
elif has_tool_request and not has_tool_execution:
    tool_status = "⚠️ Requested but Failed"
    # 分析失败原因:
    # - max_turns=1 (工具来不及执行)
    # - 工具未产生新图像
    # - image_history为空
elif not has_tool_request:
    tool_status = "❌ No Tool Request"
    # 检查是否直接给出answer
```

---

## WandB上传函数调用链

### 训练时 (Training)
```
ray_trainer.py::fit()
  ↓
NaiveRewardManager.__call__()
  → 计算所有奖励指标
  → 返回 reward_extra_infos_dict
  ↓
ray_trainer.py::log_metrics()
  → 提取 image_quality_scores
  → 构建 detailed_metrics
  ↓
log_rollout_images_to_wandb()
  → 选择样本（best/worst/random）
  → create_trajectory_visualization()  # 创建可视化图像
  → _log_conversation_table()  # 记录到表格
    → compute_degraded_and_restored_metrics_for_indices()
    → wandb.log()
```

### 验证时 (Validation)
```
ray_trainer.py::validation()
  ↓
验证数据集rollout
  → 收集 val_image_histories
  → 收集 val_conversation_histories
  → 收集 val_original_images
  ↓
compute_validation_reward()
  → 返回 reward_extra_infos_dict
  ↓
log_rollout_images_to_wandb(..., mode='val')
  → 上传所有验证样本
  ↓
log_validation_wrong_predictions_to_wandb()
  → 筛选预测错误的样本
  → 单独上传到错误表格
```

---

## WandB表格列详解

### 固定列 (Fixed Columns)
1. **Step**: 训练步数
2. **Sample_ID**: 样本ID (格式: `{mode}_step{step}_idx{idx}`)
3. **Trajectory_Image**: 轨迹可视化图像（wandb.Image）
4. **Quality_Score**: 综合质量分数
5. **Num_Tools**: 使用的工具数量

### 退化信息列 (Degradation Info) - 最多4个退化
6-13. **Degradation_Type_1~4**: 退化类型1-4
14-21. **Degradation_Level_1~4**: 退化强度1-4

### 预测分析列 (Prediction Analysis)
22. **Predicted_Degradation_Type**: 预测的退化类型（从工具调用推断）
23. **Prediction_Match**: 预测是否匹配 (✅/⚠️/❌/❓)
24. **Tool_Status**: 工具执行状态
25. **Failure_Reason**: 失败原因

### 指标列 (Metrics) - 退化图 vs 复原图
26-28. **Degraded_SSIM/LPIPS/PSNR**: 退化图的指标
29-31. **Restored_SSIM/LPIPS/PSNR**: 复原图的指标
32-34. **Improve_SSIM%/LPIPS%/PSNR%**: 提升百分比

### 用户输入列 (User Input)
35. **User_Input**: 用户初始输入提示

### 对话详情列 (Conversation Details) - 最多5轮
36-45. **Turn1~5_Think**: 每轮的思考内容
46-55. **Turn1~5_Tools**: 每轮调用的工具

---

## 关键配置参数

### 环境变量配置
```bash
# 图像质量指标配置
IMAGE_QUALITY_USE_NO_REFERENCE=True  # 是否使用无参考指标
IMAGE_QUALITY_DISCRETIZE_LEVELS=0    # 离散化级别（0=连续）

# 奖励权重配置
FORMAT_REWARD_WEIGHT=0.3             # 格式奖励权重
QUALITY_REWARD_WEIGHT=0.7            # 质量奖励权重

# 退化类型奖励配置
ENABLE_DEGRADATION_TYPE_REWARD=False  # 是否启用退化类型奖励
DEGRADATION_TYPE_REWARD_WEIGHT=1.0    # 退化类型奖励权重
```

### Trainer配置
```yaml
trainer:
  log_images_to_wandb: true           # 是否上传图像到wandb
  num_samples_train: 5                # 训练时随机采样数
  num_best_worst: 2                   # 训练时best/worst采样数
  max_turns: 5                        # 最大对话轮数
```

---

## 数据流示例

### 单个样本的完整数据流
```python
# 1. Rollout阶段收集
sample = {
    'image_history': [
        degraded_img,      # 退化图
        step1_img,         # 工具1处理后
        step2_img,         # 工具2处理后
        restored_img       # 最终复原图
    ],
    'conversation_history': [
        {'turn': 1, 'response': '<think>...</think><tool_call>[...]</tool_call>'},
        {'turn': 2, 'response': '<think>...</think><answer>...</answer>'}
    ],
    'original_image': clean_img,  # 原图
    'reward_model': [
        {'degradation_type': 'noise', 'degradation_level': 'medium'},
        {'degradation_type': 'motion blur', 'degradation_level': 'severe'}
    ]
}

# 2. RewardManager计算
reward_info = {
    'format_score': 1.0,
    'quality_score': 0.85,
    'ssim_score_ref': 0.92,
    'lpips_score_ref': 0.08,
    'psnr_score_ref': 28.5,
    'niqe_score': 3.2,
    'degradation_type': 'noise, motion blur',
    'degradation_type_score': 0.8
}

# 3. 上传到WandB
wandb_row = {
    'Step': 1000,
    'Sample_ID': 'train_step1000_idx42',
    'Trajectory_Image': wandb.Image(...),  # 可视化图像
    'Quality_Score': 0.85,
    'Num_Tools': 3,
    'Degradation_Type_1': 'noise',
    'Degradation_Level_1': 'medium',
    'Degradation_Type_2': 'motion blur',
    'Degradation_Level_2': 'severe',
    'Predicted_Degradation_Type': 'noise, motion blur',
    'Prediction_Match': '✅',
    'Tool_Status': '✅ Success',
    'Degraded_SSIM': 0.65,
    'Restored_SSIM': 0.92,
    'Improve_SSIM%': 41.5,
    # ... 更多字段
}
```

---

## 总结

wandb上传的数据来源主要有：

1. **Rollout环节**: image_history, conversation_history
2. **数据集**: original_images, reward_model (退化类型和强度)
3. **RewardManager**: 所有奖励相关指标
4. **实时计算**: degraded/restored metrics, 工具状态分析, 预测匹配

整个数据流设计确保了：
- ✅ 完整记录模型的推理过程（对话历史）
- ✅ 可视化展示图像处理轨迹
- ✅ 多维度评估模型性能（格式、质量、预测准确性）
- ✅ 支持调试和问题分析（失败原因、工具状态）

