# 数据集1 vs 数据集2 完整对比

## 🎯 核心差异

| 维度 | 数据集1: Image Restoration | 数据集2: Defect Detection |
|------|---------------------------|--------------------------|
| **任务** | 图像复原 | 工业缺陷检测 |
| **目标** | 恢复退化的图像 | 判断是否有缺陷 |
| **答案类型** | 图像质量 | Yes/No |
| **env_name** | `noise`, `blur`, `haze`, `rain`等 | `visual_toolbox_v2` |
| **data_source** | `image_restoration_v2` | `vstar_visual_toolbox_v2` |

---

## 🔧 工具行为差异

### 数据集1: 链式处理
```python
# XRestormerToolbox, SwinIRToolbox, MPRNetToolbox等
def reset(self, raw_prompt, multi_modal_data, origin_multi_modal_data, **kwargs):
    self.multi_modal_data = multi_modal_data  # 使用当前图像
    
def execute(self, action_string, **kwargs):
    current_image = self.multi_modal_data['image'][0]  # 上一个工具的输出
    restored_image = process(current_image)
    self.multi_modal_data['image'][0] = restored_image  # 更新为新图
```

**流程**: 退化图 → 工具1处理 → 工具2处理 → ... → 最终复原图

### 数据集2: 独立处理
```python
# visual_toolbox_v2.py
def reset(self, raw_prompt, multi_modal_data, origin_multi_modal_data, **kwargs):
    self.origin_multi_modal_data = origin_multi_modal_data  # 保存原始图
    
def execute(self, action_string, **kwargs):
    img = self.origin_multi_modal_data['image'][0]  # 始终用原始输入
    if tool_name == "image_zoom_in_tool":
        cropped_img = img.crop(bbox)  # 处理原始图
    elif tool_name == "image_rotate_tool":
        rotated_img = img.rotate(angle)  # 处理原始图
```

**流程**: 原始图 → 工具1(crop) → 显示裁剪区域
          原始图 → 工具2(rotate) → 显示旋转结果

---

## 🏆 Reward计算差异

### 数据集1: Image Restoration
```python
total_reward = FORMAT_WEIGHT × format_score 
             + QUALITY_WEIGHT × quality_score
             + DEGRADATION_TYPE_WEIGHT × type_score  # 可选
```

**组成**:
- `format_score`: 1.0 (完美) 或 -1.0 (违规)
- `quality_score`: 0.0 ~ 1.0 (连续，SSIM/LPIPS/PSNR或NIQE/BRISQUE等)
- `degradation_type_score`: 0.0 ~ 1.0 (工具选择正确性)

**权重**:
- FORMAT_WEIGHT = 0.3
- QUALITY_WEIGHT = 0.7
- DEGRADATION_TYPE_WEIGHT = 1.0 (可选)

**总分范围**: -0.3 ~ 2.0 (不启用type) 或 -0.3 ~ 3.0 (启用type)

### 数据集2: Defect Detection
```python
total_reward = format_reward + acc_reward
```

**组成**:
- `format_reward`: -1 (有错误) 或 1 (完美格式)
- `acc_reward`: 0 (错误) 或 1 (正确)

**总分范围**: -1 ~ 2
- 最差：-1 (格式错误 + 答案错误)
- 格式错但答案对：0
- 格式对但答案错：1
- 最好：2 (格式正确 + 答案正确)

---

## 📝 格式要求差异

### 数据集1: Image Restoration

**格式1 (工具请求)**:
```xml
<think>检测到JPEG压缩伪影...</think>
<tool_call>[{"name": "swinir_jpeg_artifact_removal", "arguments": {...}}]</tool_call>
```

**格式2 (最终答案)**:
```xml
<think>图像已复原</think>
<answer>Image has been successfully restored.</answer>
```

### 数据集2: Defect Detection

**Format 1 (工具请求)**:
```xml
<think>需要放大查看...</think>
<tool_call>[{"name": "image_zoom_in_tool", "arguments": {"bbox_2d": [x1,y1,x2,y2]}}]</tool_call>
```

**Format 2 (有缺陷)**:
```xml
<think>检测到裂纹...</think>
<location>[{"bbox2d": [x1,y1,x2,y2]}]</location>
<type>crack</type>
<answer>yes</answer>
```

**Format 3 (无缺陷)**:
```xml
<think>表面光滑，无缺陷</think>
<location>[]</location>
<type>good</type>
<answer>no</answer>
```

---

## 📊 Wandb指标对比

### 数据集1指标

**奖励组成**:
- `reward/format_correct_ratio` - 格式正确率
- `reward/quality_score_mean` - 图像质量均值
- `reward/quality_score_std` - 质量标准差
- `reward/degradation_type_score_mean` - 退化类型识别准确率（可选）

**图像质量细节**:
- `ssim_score_ref` - 结构相似性（有参考）
- `lpips_score_ref` - 感知损失（有参考）
- `psnr_score_ref` - 峰值信噪比（有参考）
- `niqe_score` - 自然度（无参考）
- `brisque_score` - 盲质量（无参考）

**Caption示例**:
```
Sample 42 [BEST] | Quality: 0.856 | Type: jpeg compression | 
SSIM: 0.923 | LPIPS: 0.145 | PSNR: 28.4
```

### 数据集2指标

**奖励组成**:
- `reward/format_correct_ratio` - 格式正确率
- `reward/format_violation_ratio` - 格式违规率
- `reward/format_score_mean` - 格式分数均值
- `reward/accuracy_mean` - 准确性均值
- `reward/accuracy_ratio` - 准确率（acc=1的比例）✨

**Caption示例**:
```
Sample 42 [BEST] | Quality: 2.0 | Format: 1.0 | Acc: 1.0
```

**表格列**:
- `Format_Reward`: -1 或 1
- `Acc_Reward`: 0 或 1
- `Tool_Status`: ✅ Success / ⚠️ Requested but Failed / ❌ No Tool Request
- `Failure_Reason`: max_turns限制 / 工具未产生新图像 / 等

---

## 🔍 代码位置对比

### Reward函数

**数据集1**:
```
文件: verl/utils/reward_score/image_restoration.py
函数: compute_score_v2()
配置: 环境变量控制（FORMAT_WEIGHT, QUALITY_WEIGHT等）
```

**数据集2**:
```
文件: verl/utils/reward_score/visual_toolbox_v2_reward.py
函数: compute_visual_toolbox_v2_score()
配置: 固定（format: -1/1, acc: 0/1）
```

### 工具实现

**数据集1**:
```
文件: verl/workers/agent/envs/mm_process_engine/
  - SwinIRToolbox.py
  - MPRNetToolbox.py
  - RestormerToolbox.py
  - XRestormerToolbox.py
  - DehazeFormerToolbox.py
  - BrighteningToolbox.py
```

**数据集2**:
```
文件: verl/workers/agent/envs/mm_process_engine/visual_toolbox_v2.py
工具: 
  - image_zoom_in_tool (裁剪放大)
  - image_rotate_tool (旋转)
```

### 训练脚本

**数据集1**:
```
文件: examples/agent/IR.sh
数据: /app/xiaominl/datasets/air/shard-train-*.parquet
```

**数据集2**:
```
文件: examples/agent/visual_toolbox_v2.sh
数据: /home/takisobe@amd.com/zxy/codes/DeepEyes/data/train/train_dataset.parquet
```

---

## 🎨 图像历史对比

### 数据集1: 链式处理
```
image_history = [
    退化图 (初始输入),
    工具1处理后 (SwinIR去噪),
    工具2处理后 (Restormer去模糊),
    最终复原图
]
```

Wandb显示：
```
[Ground Truth] → [Degraded Input] → [Step 1: SwinIR] → [Step 2: Restormer] → [Restored]
```

### 数据集2: 独立处理
```
image_history = [
    原始输入图,
    裁剪区域 (zoom_in),
    旋转结果 (rotate)
]
```

Wandb显示：
```
[Original Input] → [Step 1: Zoomed Region] → [Step 2: Rotated View]
                    ↑ zoom_in             ↑ rotate
                    (都是从原图处理)
```

---

## 🚦 训练监控建议

### 数据集1监控重点
- `reward/quality_score_mean` 持续上升
- `reward/quality_score_std` 逐渐下降（稳定性）
- `val/ssim_mean` > 0.9
- `val/lpips_mean` < 0.2

### 数据集2监控重点
- `reward/format_correct_ratio` > 0.95
- `reward/accuracy_ratio` > 0.8
- `critic/score/max` → 2.0
- 工具使用率 (`agent/tool_call_mean`)

---

## 📦 数据集字段对比

### 数据集1字段
```python
{
    'data_source': 'image_restoration_v2',
    'env_name': 'noise',  # 或其他退化类型
    'prompt': [...],
    'images': [...],  # 退化图
    'reward_model': [{
        'degradation_type': 'noise',
        'degradation_addition_order': ['noise', 'blur', ...]
    }],
    'extra_info': {
        'original_image': ...,  # Ground Truth
        'degradation_type': 'noise'
    }
}
```

### 数据集2字段
```python
{
    'data_source': 'vstar_visual_toolbox_v2',
    'env_name': 'visual_toolbox_v2',
    'prompt': [...],
    'images': [...],
    'reward_model': {
        'ground_truth': {
            'answer': 'yes' or 'no',
            'bboxes': [...]
        },
        'reward_function': 'compute_visual_toolbox_v2_score',
        'style': 'visual_toolbox_v2'
    },
    'extra_info': {
        'question': '...',
        'answer': {'answer': 'yes/no', 'bboxes': [...]},
        'bboxes': [...],
        'defect_type': 'crack' or 'good',
        'supported_tools': ['image_zoom_in_tool', 'image_rotate_tool']
    }
}
```

---

## ✨ 新功能亮点（数据集2）

1. **简化的奖励**: 只有format和accuracy，易于理解和调试
2. **直接匹配**: Yes/No匹配，不需要LLM judge
3. **独立工具**: 每个工具都处理原始图，便于可视化
4. **准确率统计**: `reward/accuracy_ratio`直接显示模型准确率
5. **工具状态追踪**: 清楚显示工具是否成功执行

---

## 🔄 迁移摘要

### 修改的文件（8个）
1. `verl/utils/reward_score/__init__.py` - 添加分支
2. `verl/workers/reward_manager/naive.py` - 添加统计
3. `examples/agent/visual_toolbox_v2.sh` - 新训练脚本
4. `test_visual_toolbox_v2_reward.py` - 新测试脚本

### 已支持的文件（无需修改）
1. `verl/utils/reward_score/visual_toolbox_v2_reward.py` - reward函数 ✓
2. `verl/workers/agent/envs/mm_process_engine/visual_toolbox_v2.py` - 工具实现 ✓
3. `verl/utils/tracking_image_utils.py` - wandb上传 ✓
4. `verl/trainer/ppo/metric_utils.py` - 指标统计 ✓

### 向后兼容
- ✅ 数据集1训练不受影响
- ✅ 可以混合训练（如果需要）
- ✅ 所有wandb功能都支持

---

## 🎓 使用建议

### 选择数据集1的场景
- 图像复原、增强任务
- 需要多步骤链式处理
- 关注图像质量指标
- 有Ground Truth参考图

### 选择数据集2的场景
- 分类任务（Yes/No）
- 缺陷检测、质量控制
- 需要简单清晰的奖励
- 关注准确率而非图像质量

---

## 🎉 就绪状态

数据集2迁移已完成！所有功能测试通过，可以开始训练。

**立即开始**:
```bash
bash examples/agent/visual_toolbox_v2.sh
```

