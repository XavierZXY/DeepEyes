# 评估脚本修复总结

## 🐛 遇到的问题

### 问题1: 图像数据格式错误
```
TypeError: argument should be a bytes-like object or ASCII string, not 'dict'
```

**原因**: parquet中的images字段是字典格式 `{'bytes': b'...'}`，不是base64字符串

**修复**: 添加 `_extract_image_from_data()` 方法，支持多种格式
- ✅ 字典格式: `{'bytes': b'...'}`
- ✅ 直接bytes
- ✅ base64字符串
- ✅ 文件路径

### 问题2: 工具初始化错误
```
TypeError: ToolBase.__init__() got multiple values for keyword argument 'name'
TypeError: BaseSwinIRToolbox.__init__() missing 3 required positional arguments
```

**原因**: 评估脚本使用了错误的工具创建方式
```python
# ❌ 错误方式
tool_instance = tool_class(name=tool_name, description="", parameters={})
```

**修复**: 使用与训练代码一致的方式
```python
# ✅ 正确方式（与训练代码一致）
tool_instance = ToolBase.create(tool_name)
tool_instance.reset(
    raw_prompt=raw_prompt,
    multi_modal_data=deepcopy(multi_modal_data),
    origin_multi_modal_data=deepcopy(origin_multi_modal_data)
)
```

### 问题3: 工具reset参数错误
```
TypeError: DeblurToolbox.reset() missing 1 required positional argument: 'raw_prompt'
```

**原因**: 没有传入必需的 `raw_prompt` 参数

**修复**: 从parquet的prompt字段提取并传入

## ✅ 已修复的功能

### 1. 数据加载
- ✅ 正确提取退化图像（`images[0]['bytes']`）
- ✅ 正确提取GT图像（`extra_info['original_image']`）
- ✅ 正确提取系统提示词（`prompt[0]['content']`）
- ✅ 正确提取用户消息（`prompt[1]['content']`）
- ✅ 正确提取退化类型（`env_name.split(', ')`）

### 2. 工具调用
- ✅ 使用 `ToolBase.create()` 工厂方法
- ✅ 传入正确的参数：`raw_prompt`, `multi_modal_data`, `origin_multi_modal_data`
- ✅ 使用PIL Image格式（不是base64）
- ✅ 正确处理deepcopy

### 3. 指标计算
- ✅ 计算退化图 vs GT（基线）
- ✅ 计算复原图 vs GT（评估）
- ✅ 计算改善幅度（绝对值和百分比）
- ✅ 支持6种指标：PSNR, SSIM, LPIPS, MANIQA, MUSIQ, CLIP-IQA

### 4. 结果保存
- ✅ 保存三张图像：`degraded.png`, `restored.png`, `gt.png`
- ✅ 保存详细对话历史
- ✅ 保存所有指标（退化图、复原图、改善幅度）

## 📊 输出指标说明

### CSV文件包含的指标列

**有参考指标**:
- `degraded_psnr`, `degraded_ssim`, `degraded_lpips` - 退化图基线
- `restored_psnr`, `restored_ssim`, `restored_lpips` - 复原图指标
- `improvement_psnr`, `improvement_ssim`, `improvement_lpips` - 改善幅度
- `improvement_psnr_pct`, `improvement_ssim_pct`, `improvement_lpips_pct` - 改善百分比

**无参考指标**:
- `degraded_maniqa`, `degraded_musiq`, `degraded_clipiqa` - 退化图基线
- `restored_maniqa`, `restored_musiq`, `restored_clipiqa` - 复原图指标
- `improvement_maniqa`, `improvement_musiq`, `improvement_clipiqa` - 改善幅度
- `improvement_maniqa_pct`, `improvement_musiq_pct`, `improvement_clipiqa_pct` - 改善百分比

**其他**:
- `num_tools_used` - 使用的工具数
- `tools_used` - 工具名称列表
- `gt_degradations` - GT退化类型
- `num_turns` - 对话轮次

### 统计输出示例

```
📉 退化图基线指标（vs GT）:
  PSNR:  Mean=24.79 ± 2.15 dB
  SSIM:  Mean=0.7980 ± 0.0523
  LPIPS: Mean=0.3547 ± 0.0892

📈 复原图指标（vs GT）:
  PSNR:  Mean=28.45 ± 2.38 dB
  SSIM:  Mean=0.8756 ± 0.0412
  LPIPS: Mean=0.2134 ± 0.0654

✨ 改善幅度:
  ΔPSNR:  Mean=+3.66 ± 1.24 dB (+14.8%)
  ΔSSIM:  Mean=+0.0776 ± 0.0234 (+9.7%)
  ΔLPIPS: Mean=+0.1413 ± 0.0321 (+39.8%)
```

## 🧪 测试验证

运行以下测试脚本验证修复：

```bash
# 1. 测试数据加载
python eval/test_data_loading.py
# 预期: ✅ 成功提取退化图像 和 GT图像

# 2. 测试工具调用
python eval/test_tool_execution.py
# 预期: ✅ 成功创建工具 和 Reset成功

# 3. 测试单样本处理（含指标计算）
python eval/test_single_sample.py
# 预期: ✅ 所有测试步骤完成
```

## 🚀 现在可以使用的命令

```bash
# 基本评估（10个样本）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct" \
    --num_samples 10

# 完整评估（所有样本）
python eval/eval_agent_restoration.py \
    --data_path /app/xiaominl/air_full_v1/shard-test-000000.parquet \
    --output_dir ./eval_results/full \
    --api_url http://10.21.9.6:8008/v1 \
    --model_name "Qwen2.5-VL-7B-Instruct"
```

## 📁 输出目录结构

```
eval_results/
├── config.json
├── evaluation_results.csv      # 主要结果（包含所有指标）
├── summary.txt
├── details/
│   ├── sample_0000.json        # 对话历史+工具调用+指标
│   └── ...
└── images/
    ├── sample_0000/
    │   ├── degraded.png        # 退化图
    │   ├── restored.png        # 复原图
    │   └── gt.png              # GT图（用于对比）
    └── sample_0001/
        ├── degraded.png
        ├── restored.png
        └── gt.png
```

## 🔑 关键改进

1. **与训练代码完全一致**：工具创建和调用方式与训练时相同
2. **完整的指标对比**：退化图、复原图、改善幅度一目了然
3. **保存三张图像**：方便人工检查复原效果
4. **灵活的系统提示词**：支持parquet、自定义文件、内置三种模式
5. **详细的日志**：便于调试问题

## ⚠️ 注意事项

1. **工具服务必须启动**：评估会真实调用工具服务进行图像处理
2. **网络连接**：确保能访问 `TOOL_SERVICE_IP` 的所有端口
3. **GPU显存**：指标计算需要GPU（LPIPS、MANIQA等）
4. **评估时间**：完整评估324个样本可能需要较长时间

## 📞 调试建议

如果遇到问题：

1. **先运行测试脚本**：
   ```bash
   python eval/test_data_loading.py      # 测试数据加载
   python eval/test_tool_execution.py    # 测试工具调用
   python eval/test_single_sample.py     # 测试指标计算
   ```

2. **检查工具服务**：
   ```bash
   # 测试每个工具服务端口
   curl http://${TOOL_SERVICE_IP}:5001/health  # SwinIR
   curl http://${TOOL_SERVICE_IP}:5012/health  # NAFNet
   # ... 其他端口
   ```

3. **使用小样本测试**：
   ```bash
   --num_samples 1  # 先测试一个样本
   ```

---

**状态**: ✅ 所有已知问题已修复，评估脚本可以正常使用！

