# 🎉 评估系统已就绪！

## ✅ 所有问题已修复

### 修复列表
1. ✅ **图像数据格式** - 正确解析 `{'bytes': b'...'}`
2. ✅ **GT图像提取** - 从 `extra_info['original_image']` 获取
3. ✅ **工具创建** - 使用 `ToolBase.create()` 工厂方法
4. ✅ **工具调用** - 传入正确的 `action_string` 格式
5. ✅ **错误处理** - 友好的错误提示，不抛出traceback
6. ✅ **指标对比** - 计算退化图、复原图、改善幅度

### 测试验证通过
```bash
✅ 数据加载测试: python eval/test_data_loading.py
✅ 工具调用测试: python eval/test_tool_execution.py  
✅ 单样本测试: python eval/test_single_sample.py
```

## 🚀 立即开始使用

### 基本命令（推荐）

```bash
cd /app/xiaominl/DeepEyes_v2

python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct" \
    --num_samples 10
```

### 关键参数说明

| 参数 | 必需? | 说明 | 默认值 |
|------|-------|------|--------|
| `--data_path` | ✅ | parquet文件路径 | 无 |
| `--api_url` | ✅ | vLLM API地址 | `http://localhost:8000/v1` |
| `--model_name` | 推荐 | 模型名称 | 自动检测 |
| `--output_dir` |  | 输出目录 | `./eval_results` |
| `--num_samples` |  | 评估样本数 | 全部（324个） |

## 📊 你会得到什么结果

### 1. CSV表格（evaluation_results.csv）

包含**完整的对比指标**：

```csv
sample_id,degraded_psnr,restored_psnr,improvement_psnr,improvement_psnr_pct,...
0,24.79,28.45,+3.66,+14.8%,...
```

**每个指标都有三列**：
- `degraded_*` - 退化图的基线
- `restored_*` - 复原图的结果
- `improvement_*` - 改善幅度（绝对值和百分比）

### 2. 三张图像对比

```
images/sample_0000/
├── degraded.png   # 退化图（输入）
├── restored.png   # 复原图（Agent输出）
└── gt.png         # GT图（参考标准）
```

### 3. 详细的对话记录

```json
{
  "conversation_history": [
    {"turn": 1, "model_output": "<think>...</think><tool_call>...</tool_call>"}
  ],
  "tool_results": [
    {"tool_name": "nafnet_deblur", "success": true, "reward": 0.85}
  ],
  "metrics": {...}
}
```

## 📈 典型输出示例

```
[INFO] 执行工具 1/3: nafnet_deblur
[NAFNET API] ✅ API调用成功，图像处理完成
[INFO] 工具执行成功，图像尺寸: (510, 336)

[INFO] 执行工具 2/3: retinexformer_enhance
[RETINEXFORMER API] ✅ API调用成功
[INFO] 工具执行成功，图像尺寸: (510, 336)

[INFO] 执行工具 3/3: scunet_real_denoising_psnr
[SCUNET API] ✅ API调用成功
[INFO] 工具执行成功，图像尺寸: (510, 336)

[INFO] 计算退化图的基线指标...
  退化图指标: PSNR=24.79, SSIM=0.7980, LPIPS=0.3547

[INFO] 计算复原图的指标...
  复原图指标: PSNR=28.45, SSIM=0.8756, LPIPS=0.2134

[INFO] 计算改善幅度...
  改善幅度: ΔPSNR=+3.66dB, ΔSSIM=+0.0776, ΔLPIPS=+0.1413
  改善百分比: PSNR +14.8%, SSIM +9.7%, LPIPS +39.8%
```

## 🎯 评估流程

```
1. 读取parquet数据
   ├─ 提取退化图（images[0]['bytes']）
   ├─ 提取GT图（extra_info['original_image']）
   └─ 提取系统提示词（prompt[0]['content']）

2. 调用vLLM推理
   └─ 获取工具调用序列

3. 执行工具链
   ├─ 使用ToolBase.create()创建工具
   ├─ 调用tool.reset()初始化
   └─ 调用tool.execute()执行

4. 计算指标
   ├─ 退化图 vs GT（基线）
   ├─ 复原图 vs GT（评估）
   └─ 计算改善幅度

5. 保存结果
   ├─ CSV表格
   ├─ 图像对比
   └─ 详细记录
```

## 🔧 配置选项

### 系统提示词模式

```bash
# 模式1: 使用parquet中的提示词（默认，推荐）
python eval/eval_agent_restoration.py --data_path DATA.parquet ...

# 模式2: 使用自定义提示词
python eval/eval_agent_restoration.py --data_path DATA.parquet \
    --no_parquet_system_prompt \
    --custom_system_prompt my_prompt.txt ...

# 模式3: 使用内置提示词
python eval/eval_agent_restoration.py --data_path DATA.parquet \
    --no_parquet_system_prompt ...
```

### 对话模式

```bash
# 多工具规划模式（一次输出多个工具，链式执行）
--conversation_mode multi_tool_planning --max_turns 1

# 单工具迭代模式（每次一个工具，逐步处理）
--conversation_mode single_tool_iterative --max_turns 5
```

### 指标选择

```bash
# 仅有参考指标（更快）
--no_no_reference_metrics

# 仅无参考指标
--no_reference_metrics

# 全部指标（默认）
# （不加任何标志）
```

## 📋 评估前检查清单

在运行完整评估前，请确认：

- [ ] vLLM服务已启动（`curl http://10.21.9.6:8008/v1/models`）
- [ ] 工具服务已启动（`TOOL_SERVICE_IP=10.21.9.6`）
- [ ] 数据路径正确（`/app/xiaominl/air_full_v1/shard-test-000000.parquet`）
- [ ] 已运行测试脚本验证（`python eval/test_tool_execution.py`）

## 💡 推荐工作流

### 第一次使用

```bash
# 1. 验证环境
python eval/test_tool_execution.py

# 2. 快速测试（1个样本）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_test \
    --api_url http://10.21.9.6:8008/v1 \
    --num_samples 1

# 3. 检查结果
cat ./eval_test/summary.txt
ls ./eval_test/images/sample_0000/

# 4. 如果一切正常，运行完整评估
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://10.21.9.6:8008/v1
```

### 日常使用

```bash
# 直接运行示例脚本
bash eval/eval_agent_restoration_example.sh
```

## 📞 遇到问题？

### 错误1: "Connection refused"
**原因**: vLLM服务未启动  
**解决**: 检查 `curl http://10.21.9.6:8008/v1/models`

### 错误2: "工具执行失败"
**原因**: 工具服务未启动或网络不通  
**解决**: 检查 `TOOL_SERVICE_IP` 和端口（5001-5012）

### 错误3: "GPU内存不足"
**原因**: 指标计算占用GPU  
**解决**: 使用 `--no_no_reference_metrics` 跳过部分指标

---

## 🎊 准备就绪！

所有代码已经过测试验证，可以直接使用：

```bash
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct" \
    --num_samples 10
```

**祝评估顺利！** 🚀

