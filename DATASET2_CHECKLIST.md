# 数据集2迁移检查清单

## ✅ 已完成的修改

### 1. Reward系统
- [x] `verl/utils/reward_score/__init__.py`
  - [x] 添加`visual_toolbox_v2`, `vstar_visual_toolbox_v2`分支
  - [x] 调用`visual_toolbox_v2_reward.compute_visual_toolbox_v2_score`
  
- [x] `verl/utils/reward_score/visual_toolbox_v2_reward.py`
  - [x] 格式检查（-1或1）
  - [x] Yes/No匹配（0或1）
  - [x] 返回dict格式：`{score, format_reward, acc_reward, format_errors_count}`

### 2. Reward Manager
- [x] `verl/workers/reward_manager/naive.py`
  - [x] 添加`visual_toolbox_v2`和`vstar_visual_toolbox_v2`到统计分支
  - [x] 提取`format_reward`（-1或1）
  - [x] 提取`acc_reward`（0或1）
  - [x] 添加到`reward_extra_info`字典
  - [x] 兼容性：为所有样本添加必要字段

### 3. Wandb上传
- [x] `verl/utils/tracking_image_utils.py`
  - [x] 检测数据集类型：`is_visual_toolbox_v2`
  - [x] 表格列适配：`Format_Reward`, `Acc_Reward`
  - [x] Caption显示：`Format: X | Acc: Y`
  
- [x] `verl/trainer/ppo/metric_utils.py`
  - [x] 支持`format_reward`统计
  - [x] 支持`acc_reward`统计
  - [x] 计算准确率：`reward/accuracy_ratio`

### 4. 工具实现
- [x] `verl/workers/agent/envs/mm_process_engine/visual_toolbox_v2.py`
  - [x] 使用`origin_multi_modal_data`（原始输入图）
  - [x] 不使用`multi_modal_data`（上一个工具输出）
  - [x] 支持`image_zoom_in_tool`
  - [x] 支持`image_rotate_tool`

### 5. 训练配置
- [x] `examples/agent/visual_toolbox_v2.sh`
  - [x] 数据集路径配置
  - [x] env_name使用`env_name`字段
  - [x] max_turns=5（允许多轮）
  - [x] Wandb配置

### 6. 测试
- [x] `test_visual_toolbox_v2_reward.py`
  - [x] 测试格式正确
  - [x] 测试格式错误
  - [x] 测试答案正确/错误
  - [x] 测试工具请求turn
  - [x] 测试invalid JSON

---

## 📋 验证步骤

### Step 1: 运行reward测试
```bash
cd /home/takisobe@amd.com/zxy/codes/DeepEyes
python3 test_visual_toolbox_v2_reward.py
```

**预期**: 所有6个测试通过 ✓

### Step 2: 检查数据集
```bash
python3 -c "
import pandas as pd
df = pd.read_parquet('data/train/train_dataset.parquet')
print('样本数:', len(df))
print('env_name:', df.iloc[0]['env_name'])
print('data_source:', df.iloc[0]['data_source'])
print('工具:', df.iloc[0]['extra_info']['supported_tools'])
"
```

**预期**: 
- env_name: visual_toolbox_v2
- data_source: vstar_visual_toolbox_v2
- 工具: ['image_zoom_in_tool', 'image_rotate_tool']

### Step 3: 语法检查
```bash
python3 -m py_compile verl/utils/reward_score/__init__.py
python3 -m py_compile verl/utils/reward_score/visual_toolbox_v2_reward.py
python3 -m py_compile verl/workers/reward_manager/naive.py
```

**预期**: 无语法错误

### Step 4: 试运行训练（1个epoch）
```bash
# 修改visual_toolbox_v2.sh中的trainer.total_epochs=1
bash examples/agent/visual_toolbox_v2.sh
```

**预期日志**:
```
[INFO] Using visual_toolbox_v2 reward (format: -1/1, accuracy: 0/1)
[visual_toolbox_v2] Score breakdown: format=1.00, acc=1.00, final=2.00
[DEBUG] 样本0 score字典键: ['score', 'format_reward', 'acc_reward', 'format_errors_count']
[DEBUG WANDB IMAGE] Found X image histories
[DEBUG WANDB TABLE] visual_toolbox_v2 mode: Format_Reward=-1.0, Acc_Reward=1.0
```

### Step 5: 检查Wandb

1. 进入wandb.ai
2. 找到项目：`visual_toolbox_v2`
3. 找到run：`defect_detection_train`
4. 检查：
   - [x] Media tab出现
   - [x] train/trajectories有图像
   - [x] Charts有reward/format_correct_ratio
   - [x] Charts有reward/accuracy_ratio
   - [x] train/conversation_details表格有数据

---

## 🔧 常见问题

### Q1: format_reward和acc_reward没有出现在wandb中
**A**: 检查reward_extra_info是否包含这些字段
```bash
grep "format_reward.*append\|acc_reward.*append" verl/workers/reward_manager/naive.py
```

### Q2: 工具仍然使用上一个处理后的图
**A**: 检查visual_toolbox_v2.py是否使用origin_multi_modal_data
```bash
grep "origin_multi_modal_data\['image'\]\[0\]" verl/workers/agent/envs/mm_process_engine/visual_toolbox_v2.py
```
应该看到第89行和第98行

### Q3: reward计算报错
**A**: 运行测试脚本检查
```bash
python3 test_visual_toolbox_v2_reward.py
```

---

## 🎉 完成！

所有修改已完成，可以开始训练数据集2！

**下一步**: 运行`bash examples/agent/visual_toolbox_v2.sh`

