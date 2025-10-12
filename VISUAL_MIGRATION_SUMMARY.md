# 🎨 数据集2迁移可视化总结

## 📊 数据流对比

### 数据集1: Image Restoration
```
┌─────────────┐
│ 退化图输入   │
│ (Degraded)  │
└──────┬──────┘
       │
       ▼
┌─────────────┐    使用multi_modal_data
│ SwinIR      │    (上一个工具的输出)
│ 去噪        │◄───────────┐
└──────┬──────┘            │
       │                   │
       ▼                   │
┌─────────────┐            │
│ Restormer   │            │
│ 去模糊      │────────────┘
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 最终复原图   │
│ (Restored)  │
└─────────────┘
       │
       ▼
    Reward
 质量评估: 0.0~1.0
 format: 1/-1
 Total: -0.3~2.0
```

### 数据集2: Defect Detection ⭐
```
┌─────────────┐
│ 原始输入图   │
│ (Original)  │
└──────┬──────┘
       │
       ├─────────────────┐
       │                 │
       ▼                 ▼
┌─────────────┐   ┌─────────────┐
│image_zoom_in│   │image_rotate │
│裁剪放大区域  │   │旋转观察     │
└──────┬──────┘   └──────┬──────┘
       │                 │
       └─────────┬───────┘
                 │
                 ▼
         都使用origin_multi_modal_data
         (原始输入图，不用上个工具输出)
                 │
                 ▼
              Reward
         format: -1/1
         accuracy: 0/1
         Total: -1~2
```

---

## 🏆 Reward计算流程

### 数据集1流程
```
输入: solution_str
  │
  ├─> 检查格式 → format_score (1.0 或 -1.0)
  │
  ├─> 提取image_history → 最后一张图
  │
  ├─> 计算图像质量
  │   ├─ 有参考: SSIM, LPIPS, PSNR
  │   └─ 无参考: NIQE, BRISQUE, CPBD, CLIP-IQA
  │   │
  │   └─> quality_score (0.0 ~ 1.0)
  │
  ├─> (可选) 检查退化类型匹配
  │   └─> degradation_type_score (0.0 ~ 1.0)
  │
  └─> total = 0.3×format + 0.7×quality [+ type]
```

### 数据集2流程 ⭐
```
输入: solution_str
  │
  ├─> 检查格式 → format_reward (-1 或 1)
  │   ├─ 检查<think>标签匹配
  │   ├─ 检查<answer>标签匹配
  │   ├─ 检查<location>标签匹配
  │   ├─ 检查<type>标签匹配
  │   └─ 检查JSON格式有效性
  │
  ├─> 提取answer → "yes" 或 "no"
  │
  ├─> 匹配ground_truth
  │   └─> acc_reward (0 或 1)
  │       ├─ 都是yes → 1
  │       ├─ 都是no → 1
  │       └─ 不匹配 → 0
  │
  └─> total = format_reward + acc_reward
      范围: -1 ~ 2
```

**特殊情况**: 工具请求turn（Format 1）只返回format_reward，不计算acc_reward

---

## 📁 代码路由

### 数据集识别
```python
# 1. 数据集加载时
df.iloc[0]['data_source']
  ├─ "image_restoration_v2" → 数据集1
  └─ "vstar_visual_toolbox_v2" → 数据集2 ⭐

# 2. Reward计算时
verl/utils/reward_score/__init__.py
  ├─ elif data_source in ["image_restoration_v2"]:
  │   └─> image_restoration.compute_score_v2()
  │
  └─ elif data_source in ["vstar_visual_toolbox_v2"]: ⭐
      └─> visual_toolbox_v2_reward.compute_visual_toolbox_v2_score()

# 3. Reward Manager
verl/workers/reward_manager/naive.py
  ├─ if data_source in ["image_restoration_v2"]:
  │   └─> 提取 format_score, quality_score
  │
  └─ elif data_source in ["vstar_visual_toolbox_v2"]: ⭐
      └─> 提取 format_reward, acc_reward

# 4. Wandb上传
verl/utils/tracking_image_utils.py
  自动检测:
  ├─ is_image_restoration = 'degradation_type' in dict
  └─ is_visual_toolbox_v2 = 'format_reward' in dict ⭐
     └─> 显示 Format_Reward, Acc_Reward列
```

---

## 🎯 Wandb展示示例

### 训练图像Caption（数据集2）
```
Sample 42 [BEST] | Quality: 2.0 | Format: 1.0 | Acc: 1.0
Sample 15 | Quality: 1.0 | Format: 1.0 | Acc: 0.0
Sample 8 [WORST] | Quality: -1.0 | Format: -1.0 | Acc: 0.0
```

### 对话表格（数据集2）

| Step | Sample_ID | Format_Reward | Acc_Reward | Total_Score | Tool_Status | Turn1_Think | Turn1_Tools |
|------|-----------|---------------|------------|-------------|-------------|-------------|-------------|
| 1 | train_0 | 1.0 | 1.0 | 2.0 | ✅ Success | "需要放大..." | zoom_in |
| 1 | train_1 | 1.0 | 0.0 | 1.0 | ❌ No Tool | "表面光滑" | [ANSWER] |
| 1 | train_2 | -1.0 | 0.0 | -1.0 | ⚠️ Failed | "检测中..." | (格式错误) |

---

## 🔧 关键代码片段

### Reward函数调用
```python
# verl/utils/reward_score/__init__.py (第122行)
elif data_source in ["visual_toolbox_v2", "defect_detection", "vstar_visual_toolbox_v2"]:
    from . import visual_toolbox_v2_reward
    res = visual_toolbox_v2_reward.compute_visual_toolbox_v2_score(
        data_source, solution_str, ground_truth, extra_info
    )
```

### 工具处理（独立）
```python
# verl/workers/agent/envs/mm_process_engine/visual_toolbox_v2.py
def execute(self, action_string, **kwargs):
    if tool_name == "image_zoom_in_tool":
        # ⭐ 关键：使用原始输入图
        img = self.origin_multi_modal_data['image'][0]
        cropped_img = img.crop(bbox)
        # 返回新的observation，但不更新self.multi_modal_data
```

### Reward提取
```python
# verl/workers/reward_manager/naive.py (第150-166行)
elif data_source in ["visual_toolbox_v2", "vstar_visual_toolbox_v2"]:
    if isinstance(score, dict):
        format_score = score.get("format_reward", 0.0)  # -1 或 1
        accuracy_score = score.get("acc_reward", 0.0)   # 0 或 1
        # 添加到reward_extra_info供wandb使用
        reward_extra_info['ir_format_score'].append(format_score)
        reward_extra_info['ir_accuracy_score'].append(accuracy_score)
```

---

## ⚡ 快速故障排查

| 症状 | 原因 | 解决 |
|------|------|------|
| reward全是1.0 | 只返回format | 检查是否有`<answer>`标签 |
| wandb无Format列 | reward不是dict | 检查reward函数返回值 |
| 工具用上个输出 | 用错了类 | 确认env_name=visual_toolbox_v2 |
| accuracy始终0 | yes/no匹配失败 | 检查ground_truth格式 |

---

## 📈 期望指标值

### 格式奖励
- 初始: ~50% (format_correct_ratio)
- 收敛: >95%
- 速度: 快（前100步）

### 准确性
- 初始: ~50% (随机)
- 收敛: >80%
- 速度: 中等（500-1000步）

### 总分
- 最大值: 2.0 (完美)
- 均值目标: >1.5
- 最小值: -1.0 (最差)

---

## 🚀 启动命令

```bash
# 完整流程
cd /home/takisobe@amd.com/zxy/codes/DeepEyes

# 1. 测试
python3 test_visual_toolbox_v2_reward.py

# 2. 训练
bash examples/agent/visual_toolbox_v2.sh

# 3. 监控
# 打开浏览器访问 wandb.ai
```

---

## 📚 文档索引

- **快速开始**: `QUICK_REFERENCE_DATASET2.md` (本文档)
- **迁移指南**: `MIGRATION_DATASET2_GUIDE.md`
- **检查清单**: `DATASET2_CHECKLIST.md`
- **详细对比**: `DATASET_COMPARISON.md`
- **完成报告**: `DATASET2_MIGRATION_COMPLETE.md`
- **Wandb功能**: `WANDB_FEATURES_SUMMARY.md`

---

Done! 🎉

