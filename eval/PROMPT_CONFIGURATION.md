# Prompt配置详解

## 📝 System Prompt 和 User Prompt 配置

评估脚本现在支持灵活配置系统提示词和用户消息。

## 🎯 默认行为（推荐）

**默认使用parquet中的完整prompt**，与训练时保持一致：

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results
```

这会使用：
- ✅ System Prompt: `prompt[0]['content']`（约10K字符的完整指令）
- ✅ User Prompt: `prompt[1]['content']`（包含退化类型提示）

**示例parquet内容**:
```python
prompt[1] = {
    'role': 'user',
    'content': '''<image>
Detected degradations: defocus blur, motion blur, low resolution

Restore this image step-by-step, choosing the best tool and order for each degradation.'''
}
```

## 🔧 配置模式

### 模式1: 完全使用parquet（默认）

```bash
python eval/eval_agent_restoration.py \
    --data_path DATA.parquet \
    --output_dir ./eval_results/mode1_parquet
```

- System Prompt: ✅ 从parquet
- User Prompt: ✅ 从parquet（**包含退化类型提示**）
- 用途: 与训练时完全一致的评估

### 模式2: 测试模型诊断能力（不提供退化类型）

```bash
python eval/eval_agent_restoration.py \
    --data_path DATA.parquet \
    --output_dir ./eval_results/mode2_no_hint \
    --no_parquet_user_prompt \
    --no_degradation_hint
```

- System Prompt: ✅ 从parquet
- User Prompt: ⚠️ 默认消息（**不包含退化类型**）
  - 发送: "Please analyze and restore this degraded image."
- 用途: 测试模型自主诊断退化类型的能力

### 模式3: 提供退化类型提示但使用默认格式

```bash
python eval/eval_agent_restoration.py \
    --data_path DATA.parquet \
    --output_dir ./eval_results/mode3_with_hint \
    --no_parquet_user_prompt
```

- System Prompt: ✅ 从parquet
- User Prompt: ⚠️ 默认消息（**包含退化类型**）
  - 发送: "Detected degradations: rain, noise\n\nPlease analyze and restore this degraded image."
- 用途: 简化用户消息但保留退化类型提示

### 模式4: 完全自定义

```bash
python eval/eval_agent_restoration.py \
    --data_path DATA.parquet \
    --output_dir ./eval_results/mode4_custom \
    --no_parquet_system_prompt \
    --custom_system_prompt my_system.txt \
    --no_parquet_user_prompt \
    --custom_user_prompt "Fix this image using any tools you need."
```

- System Prompt: ⚠️ 自定义文件
- User Prompt: ⚠️ 自定义文本
- 用途: 完全自定义的评估场景

## 📊 不同模式的对比

| 模式 | System | User | 退化提示 | 用途 |
|------|--------|------|----------|------|
| **模式1** | parquet | parquet | ✅ | 与训练一致（推荐） |
| **模式2** | parquet | 默认 | ❌ | 测试诊断能力 |
| **模式3** | parquet | 默认 | ✅ | 简化但保留提示 |
| **模式4** | 自定义 | 自定义 | - | 完全自定义 |

## 🎯 实际使用场景

### 场景1: 标准评估（与训练一致）

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/standard \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct"
```

**发送给模型的内容**:
```
System: You are a helpful assistant specialized in image restoration...
        [9886字符的完整指令]

User: <image>
      Detected degradations: defocus blur, motion blur, low resolution
      
      Restore this image step-by-step, choosing the best tool and order...
```

### 场景2: 测试模型诊断能力（不提供退化类型）

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/diagnosis_test \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct" \
    --no_parquet_user_prompt \
    --no_degradation_hint \
    --num_samples 50
```

**发送给模型的内容**:
```
System: You are a helpful assistant specialized in image restoration...
        [完整指令]

User: <image>
      Please analyze and restore this degraded image.
```

**这样可以评估**:
- 模型能否自主诊断退化类型
- 模型的诊断准确率
- 诊断错误对复原质量的影响

### 场景3: 简化评估（提供退化类型但用简单消息）

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/simplified \
    --api_url http://10.21.9.6:8008/v1 \
    --no_parquet_user_prompt
```

**发送给模型的内容**:
```
User: <image>
      Detected degradations: defocus blur, motion blur, low resolution
      
      Please analyze and restore this degraded image.
```

### 场景4: A/B测试不同提示词

```bash
# A组: 使用parquet提示词
python eval/eval_agent_restoration.py \
    --data_path DATA.parquet \
    --output_dir ./eval_results/group_A \
    --num_samples 100

# B组: 不提供退化类型提示
python eval/eval_agent_restoration.py \
    --data_path DATA.parquet \
    --output_dir ./eval_results/group_B \
    --no_parquet_user_prompt \
    --no_degradation_hint \
    --num_samples 100

# 对比结果
diff eval_results/group_A/summary.txt eval_results/group_B/summary.txt
```

## 💡 推荐配置

### 训练后的标准评估
```bash
# 完全与训练一致
python eval/eval_agent_restoration.py --data_path DATA.parquet ...
```

### 测试模型泛化能力
```bash
# 不提供退化类型，看模型能否自主诊断
python eval/eval_agent_restoration.py --data_path DATA.parquet \
    --no_parquet_user_prompt --no_degradation_hint ...
```

### 测试不同指令风格
```bash
# 使用更简洁的指令
python eval/eval_agent_restoration.py --data_path DATA.parquet \
    --custom_user_prompt "Fix this image." ...
```

## 📋 参数完整列表

| 参数 | 作用 | 默认值 |
|------|------|--------|
| `--no_parquet_system_prompt` | 不使用parquet的系统提示词 | False |
| `--custom_system_prompt` | 自定义系统提示词（文件或文本） | None |
| `--no_parquet_user_prompt` | 不使用parquet的用户消息 | False |
| `--custom_user_prompt` | 自定义用户消息文本 | None |
| `--no_degradation_hint` | 不提供退化类型提示 | False |

## 🔍 决策树

```
是否使用parquet的用户消息？
├─ 是（默认）
│  └─ 使用 prompt[1]['content']
│     例: "Detected degradations: rain, noise\n\nRestore..."
│
└─ 否（--no_parquet_user_prompt）
   ├─ 有自定义消息？（--custom_user_prompt）
   │  └─ 使用自定义文本
   │
   └─ 无自定义消息
      ├─ 提供退化提示？（默认）
      │  └─ "Detected degradations: {列表}\n\nPlease..."
      │
      └─ 不提供？（--no_degradation_hint）
         └─ "Please analyze and restore this degraded image."
```

## ⚠️ 注意事项

1. **退化类型提示的影响**:
   - 有提示: 模型知道要处理哪些退化，任务更简单
   - 无提示: 模型需要自主诊断，任务更难，但能测试诊断能力

2. **与训练的一致性**:
   - 如果训练时提供了退化类型，评估时也应该提供
   - 如果要测试泛化能力，可以故意不提供

3. **parquet中的消息格式**:
   - parquet中的消息通常是训练时使用的完整指令
   - 包含详细的任务说明和格式要求

## 📈 建议的评估流程

```bash
# 1. 标准评估（与训练一致）
python eval/eval_agent_restoration.py \
    --data_path DATA.parquet \
    --output_dir ./eval_standard \
    --num_samples 100

# 2. 诊断能力测试（不提供退化类型）
python eval/eval_agent_restoration.py \
    --data_path DATA.parquet \
    --output_dir ./eval_diagnosis \
    --no_parquet_user_prompt \
    --no_degradation_hint \
    --num_samples 100

# 3. 对比两组结果
python -c "
import pandas as pd
std = pd.read_csv('eval_standard/evaluation_results.csv')
diag = pd.read_csv('eval_diagnosis/evaluation_results.csv')

print('标准评估（有退化提示）:')
print(f'  平均PSNR改善: {std[\"improvement_psnr\"].mean():.2f}dB')
print(f'  平均SSIM改善: {std[\"improvement_ssim\"].mean():.4f}')

print('\\n诊断测试（无退化提示）:')
print(f'  平均PSNR改善: {diag[\"improvement_psnr\"].mean():.2f}dB')
print(f'  平均SSIM改善: {diag[\"improvement_ssim\"].mean():.4f}')
"
```

---

**总结**: 默认使用parquet中的完整prompt（包括退化类型提示），与训练一致。可以通过参数灵活调整测试不同场景。

