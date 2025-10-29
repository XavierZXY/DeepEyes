# Agent图像复原评估系统 - 完整使用指南

## ✅ 功能清单

### 核心功能
- ✅ 通过OpenAI兼容接口调用vLLM部署的模型
- ✅ 支持两种对话模式（多工具规划 / 单工具迭代）
- ✅ 计算6种图像质量指标（PSNR/SSIM/LPIPS + MANIQA/MUSIQ/CLIP-IQA）
- ✅ **对比退化图和复原图的指标，计算改善幅度**
- ✅ 灵活的系统提示词配置（parquet / 自定义 / 内置）
- ✅ 保存完整的对话历史和工具调用记录
- ✅ 保存三张图像（退化图 / 复原图 / GT图）

### 关键修复
- ✅ 正确解析parquet中的图像数据（`{'bytes': b'...'}`）
- ✅ 正确提取GT图像（`extra_info['original_image']`）
- ✅ 使用与训练代码一致的工具调用方式（`ToolBase.create()`）
- ✅ 正确传递工具参数（`raw_prompt`, `multi_modal_data`）

## 🚀 快速开始（3步）

### 步骤1: 启动vLLM服务

```bash
vllm serve /path/to/your/trained/model \
    --port 8008 \
    --gpu-memory-utilization 0.8 \
    --max-model-len 32768 \
    --tensor-parallel-size 4 \
    --trust-remote-code
```

### 步骤2: 确保工具服务运行

确保所有图像处理工具服务在 `TOOL_SERVICE_IP` 上运行（端口5001-5012）

### 步骤3: 运行评估

```bash
cd /app/xiaominl/DeepEyes_v2

# 快速测试（10个样本）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct" \
    --num_samples 10

# 完整评估（所有324个样本）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/full \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct"
```

## 📊 评估指标详解

### 有参考指标（需要GT图像）

| 指标 | 说明 | 范围 | 越大/小越好 |
|------|------|------|-------------|
| **PSNR** | 峰值信噪比 | 10-50 dB | 越大越好 |
| **SSIM** | 结构相似性 | 0-1 | 越大越好 |
| **LPIPS** | 感知相似性 | 0-1 | **越小越好** |

### 无参考指标（仅需复原图）

| 指标 | 说明 | 越大/小越好 |
|------|------|-------------|
| **MANIQA** | 多维度注意力质量评估 | 越大越好 |
| **MUSIQ** | 多尺度图像质量 | 越大越好 |
| **CLIP-IQA** | CLIP语义质量 | 越大越好 |

### 输出指标详解

**对于每种指标，都会输出3组数据**：

1. **退化图基线** (`degraded_*`)
   - 示例: `degraded_psnr=24.79`
   - 含义: 退化图相对于GT的质量

2. **复原图指标** (`restored_*`)
   - 示例: `restored_psnr=28.45`
   - 含义: 复原图相对于GT的质量

3. **改善幅度** (`improvement_*`)
   - 绝对值: `improvement_psnr=+3.66`（复原 - 退化）
   - 百分比: `improvement_psnr_pct=+14.8%`
   - 含义: 复原相比退化提升了多少

## 📈 结果解读示例

查看 `evaluation_results.csv`:

```csv
sample_id,degraded_psnr,restored_psnr,improvement_psnr,improvement_psnr_pct,...
0,24.79,28.45,+3.66,+14.8%,...
```

**解读**:
- 退化图PSNR=24.79dB（中等质量）
- 复原图PSNR=28.45dB（良好质量）
- **提升了3.66dB，改善14.8%** ✨

对于LPIPS（越小越好的指标）：
```csv
degraded_lpips,restored_lpips,improvement_lpips,...
0.3547,0.2134,+0.1413,...
```

**解读**:
- 退化图LPIPS=0.3547（感知质量差）
- 复原图LPIPS=0.2134（感知质量好）
- **降低了0.1413，改善39.8%** ✨（正值表示改善，因为LPIPS越小越好）

## 🎨 图像对比

查看保存的图像：

```bash
# 样本0的三张图像
ls eval_results/images/sample_0000/
# degraded.png  - 退化图
# restored.png  - 复原图
# gt.png        - GT图

# 可以用图像查看器对比
eog eval_results/images/sample_0000/*.png  # Linux
# 或
open eval_results/images/sample_0000/*.png  # macOS
```

## 🔧 高级配置

### 使用自定义系统提示词

```bash
# 创建自定义提示词
cat > custom_prompt.txt << 'EOF'
You are an expert image restoration agent.
Analyze the image and restore it efficiently.
EOF

# 使用自定义提示词评估
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/custom \
    --api_url http://10.21.9.6:8008/v1 \
    --no_parquet_system_prompt \
    --custom_system_prompt custom_prompt.txt \
    --num_samples 10
```

### 对比两种对话模式

```bash
# 模式1: 多工具规划（一次输出多个工具）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/multi_tool \
    --api_url http://10.21.9.6:8008/v1 \
    --conversation_mode multi_tool_planning \
    --max_turns 1

# 模式2: 单工具迭代（每次输出一个工具）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/single_tool \
    --api_url http://10.21.9.6:8008/v1 \
    --conversation_mode single_tool_iterative \
    --max_turns 5
```

### 仅计算特定指标

```bash
# 仅计算有参考指标（更快）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://10.21.9.6:8008/v1 \
    --no_no_reference_metrics

# 仅计算无参考指标
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://10.21.9.6:8008/v1 \
    --no_reference_metrics
```

## 📚 相关文档

- **快速开始**: [QUICKSTART.md](QUICKSTART.md)
- **完整文档**: [AGENT_EVALUATION_README.md](AGENT_EVALUATION_README.md)
- **数据格式**: [DATA_FORMAT_NOTES.md](DATA_FORMAT_NOTES.md)
- **修复说明**: [FIXES_SUMMARY.md](FIXES_SUMMARY.md)

## 🐛 调试工具

```bash
# 1. 测试数据是否能正确加载
python eval/test_data_loading.py

# 2. 测试工具是否能正确创建
python eval/test_tool_execution.py

# 3. 测试指标计算是否正常
python eval/test_single_sample.py
```

## 💡 常见问题

### Q: 评估很慢怎么办？
A: 使用 `--num_samples 10` 限制样本数，或使用 `--no_no_reference_metrics` 跳过无参考指标

### Q: 工具执行失败？
A: 确保 `TOOL_SERVICE_IP` 设置正确，所有工具服务正常运行

### Q: LPIPS指标是负改善？
A: 记住LPIPS越小越好，所以 `improvement_lpips = degraded - restored`，正值表示改善

### Q: 图像尺寸不匹配？
A: 脚本会自动处理（如超分场景），下采样较大图像进行对比

---

## 🎯 完整示例输出

```
================================================================================
评估样本 1/10
================================================================================
[DEBUG] 退化图像尺寸: (510, 336)
[DEBUG] GT图像: 是
[DEBUG] GT图像尺寸: (2040, 1344)
[INFO] 使用parquet中的系统提示词（长度: 9886）

[INFO] Turn 1/1
[INFO] 执行 3 个工具
[INFO] 执行工具 1/3: nafnet_deblur
[INFO] 工具执行成功，图像尺寸: (510, 336)
[INFO] 执行工具 2/3: retinexformer_enhance
[INFO] 工具执行成功，图像尺寸: (510, 336)
[INFO] 执行工具 3/3: scunet_real_denoising_psnr
[INFO] 工具执行成功，图像尺寸: (510, 336)

[INFO] 计算退化图的基线指标...
  退化图指标: PSNR=24.79, SSIM=0.7980, LPIPS=0.3547
[INFO] 计算复原图的指标...
[DEBUG PSNR] 图像尺寸不匹配: image1=336x510, image2=1344x2040
[DEBUG PSNR] 下采样较大图像到336x510 (缩放比例: 4.0x)
  复原图指标: PSNR=28.45, SSIM=0.8756, LPIPS=0.2134
[INFO] 计算改善幅度...
  改善幅度: ΔPSNR=+3.66dB, ΔSSIM=+0.0776, ΔLPIPS=+0.1413
  改善百分比: PSNR +14.8%, SSIM +9.7%, LPIPS +39.8%

[INFO] 计算退化图的无参考指标...
  退化图: {'maniqa': 0.1983, 'musiq': 40.23, 'clipiqa': 0.3272}
[INFO] 计算复原图的无参考指标...
  复原图: {'maniqa': 0.2845, 'musiq': 58.67, 'clipiqa': 0.4156}
  改善: MANIQA +0.0862 (+43.5%), MUSIQ +18.44 (+45.9%), CLIPIQA +0.0884 (+27.0%)
```

---

**所有问题已修复，评估系统可以正常使用！** 🎉

现在你可以使用：

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct" \
    --num_samples 10
```

结果会包含**退化图基线、复原图指标、改善幅度**三组完整数据，方便你对比复原效果！

