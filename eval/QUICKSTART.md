# Agent图像复原评估 - 快速开始

## 🚀 一分钟快速开始

### 1. 启动vLLM服务

```bash
vllm serve /path/to/your/trained/model \
    --port 8000 \
    --gpu-memory-utilization 0.8 \
    --trust-remote-code
```

### 2. 运行评估（使用parquet中的系统提示词）

```bash
cd /app/xiaominl/DeepEyes_v2

# 方式1: 自动检测模型名称（推荐）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://localhost:8000/v1 \
    --num_samples 10

# 方式2: 手动指定模型名称（多模型场景）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://localhost:8000/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct" \
    --num_samples 10
```

**💡 提示**: 
- 默认会自动检测vLLM中的第一个模型
- 如果vLLM托管多个模型，建议用 `--model_name` 明确指定
- 查看可用模型: `curl http://localhost:8000/v1/models`

### 3. 查看结果

```bash
cat eval_results/summary.txt
cat eval_results/evaluation_results.csv
```

---

## 📋 三种系统提示词模式

### 模式 1：使用 parquet 中的系统提示词（默认）

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/default
```

✅ **推荐**：与训练时保持一致

### 模式 2：使用自定义系统提示词文件

```bash
# 创建自定义提示词文件
cat > my_system_prompt.txt << 'EOF'
You are an expert image restoration agent.
Your task is to analyze degraded images and restore them.
EOF

# 运行评估
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/custom \
    --no_parquet_system_prompt \
    --custom_system_prompt my_system_prompt.txt
```

### 模式 3：使用内置系统提示词

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/builtin \
    --no_parquet_system_prompt
```

---

## 🔧 常用配置组合

### 配置 1：快速测试（10个样本）

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/quick_test \
    --num_samples 10 \
    --no_no_reference_metrics  # 跳过无参考指标以加速
```

### 配置 2：完整评估（所有样本+所有指标）

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/full_eval \
    --temperature 0.3  # 更确定性的输出
```

### 配置 3：单工具迭代模式

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/iterative \
    --conversation_mode single_tool_iterative \
    --max_turns 5
```

---

## 📊 评估指标说明

### 有参考指标（需要GT图像）

- **PSNR**: 峰值信噪比（越高越好，通常10-50dB）
- **SSIM**: 结构相似性（0-1，越高越好）
- **LPIPS**: 感知相似性（0-1，**越低越好**）

### 无参考指标（仅需复原图）

- **MANIQA**: 多维度注意力质量评估（越高越好）
- **MUSIQ**: 多尺度图像质量（越高越好）
- **CLIP-IQA**: CLIP语义质量（越高越好）

---

## 🐛 常见问题

### Q1: "Connection refused" 错误

**A**: 确保vLLM服务正在运行：
```bash
curl http://localhost:8000/v1/models
```

### Q2: 工具执行失败

**A**: 检查工具服务是否运行，并设置正确的IP：
```bash
--tool_service_ip YOUR_TOOL_SERVICE_IP
```

### Q3: GPU内存不足

**A**: 减少样本数或禁用部分指标：
```bash
--num_samples 5 --no_no_reference_metrics
```

---

## 📈 结果解读

查看 `eval_results/evaluation_results.csv`：

```csv
sample_id,psnr,ssim,lpips,maniqa,musiq,clipiqa,num_tools_used,tools_used
0,28.5,0.85,0.12,0.75,0.68,0.72,3,"nafnet_deblur,retinexformer_enhance,scunet_denoising"
```

- `psnr=28.5`: 良好质量
- `ssim=0.85`: 结构保持良好
- `lpips=0.12`: 感知质量优秀（越低越好）
- `num_tools_used=3`: 使用了3个工具

---

## 💡 高级用法

### 批量评估多个检查点

```bash
for ckpt in /path/to/checkpoints/*/; do
    echo "评估 $(basename $ckpt)"
    
    # 重启vLLM
    pkill -f "vllm serve"
    vllm serve $ckpt --port 8000 &
    sleep 60
    
    # 运行评估
    python eval/eval_agent_restoration.py \
        --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
        --output_dir ./eval_results/$(basename $ckpt) \
        --num_samples 100
    
    pkill -f "vllm serve"
done
```

### 对比不同温度参数

```bash
for temp in 0.3 0.7 1.0; do
    python eval/eval_agent_restoration.py \
        --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
        --output_dir ./eval_results/temp_${temp} \
        --temperature ${temp} \
        --num_samples 50
done
```

---

## 📚 更多文档

- [完整文档](AGENT_EVALUATION_README.md)
- [示例脚本](eval_agent_restoration_example.sh)

---

**祝评估顺利！** 🎉

