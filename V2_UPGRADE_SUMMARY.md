# Agent推理评估 V2 升级说明

## 概述

`eval_agent_true_inference_v2.py` 是对原始推理评估脚本的升级版本，完全兼容新的V2输出格式。

## 🔄 主要变化

### 1. **输出格式变化**

#### V1格式 (旧版本)
```xml
<think>
{
  "diagnosis": {"labels": ["jpeg compression artifact"], "levels": {"jpeg": "medium"}},
  "pass": false
}
</think>
```

#### V2格式 (新版本)
```xml
<think>Image exhibits blocky artifacts typical of JPEG compression, which is the highest priority to fix based on the LIFO principle.</think>
```

### 2. **System Prompt更新**

V2版本使用了完全重写的system prompt，强调：
- **LIFO原则**：后进先出的修复顺序
- **优先级分层**：压缩 > 成像 > 场景退化
- **简化的思考格式**：`<think>`块只包含简短推理文本
- **结构化的最终报告**：`<answer>`块包含`restoration_log`数组

### 3. **核心函数升级**

| 功能 | V1版本 | V2版本 |
|------|--------|--------|
| 主要函数 | `agent_rollout_loop` | `agent_rollout_loop_v2` |
| 解析器 | `_parse_model_output_for_tools` | `_parse_model_output_for_tools_v2` |
| 输入准备 | `prepare_model_inputs` | `prepare_model_inputs_v2` |
| 结果保存 | `save_inference_results` | `save_inference_results_v2` |

### 4. **新增功能**

#### 图像历史管理
- 自动保存每个修复步骤的图像
- 完整的图像处理历史追踪
- 支持图像历史的可视化保存

#### 增强的统计信息
- 工具使用统计
- 退化类型统计
- 修复步骤长度统计
- V2格式兼容的tensor数据

## 🚀 使用方法

### 基本用法
```bash
python eval_agent_true_inference_v2.py \
    --model_path /path/to/your/trained/model \
    --data_file /path/to/test/data.parquet \
    --sample_indices 0 1 2 3 4
```

### 参数说明
- `--model_path`: 训练好的模型路径
- `--data_file`: 测试数据文件（parquet格式）
- `--sample_indices`: 指定要评估的样本索引
- `--num_samples`: 评估样本数量（从start_idx开始）
- `--start_idx`: 起始样本索引
- `--output_dir`: 输出目录

### 输出文件结构
```
real_agent_eval_v2_20241229_143022/
├── evaluation_summary_v2.json          # 总体评估摘要
├── sample_00/
│   ├── basic_info.json                 # 样本基本信息
│   ├── original_image_00.png           # 原始图像
│   ├── model_response_v2.txt           # 模型完整响应
│   ├── response_analysis_v2.json       # V2响应分析
│   ├── tensor_info_v2.json            # V2统计信息
│   ├── turn_01_analysis_v2.json        # 第1轮解析结果
│   ├── turn_02_analysis_v2.json        # 第2轮解析结果
│   └── image_history/                  # 图像处理历史
│       ├── step_00_img_00.png         # 输入图像
│       ├── step_01_img_00.png         # 第1步处理结果
│       └── step_02_img_00.png         # 第2步处理结果
└── sample_01/
    └── ...
```

## 🧪 测试验证

运行测试脚本验证V2功能：
```bash
python test_v2_inference.py
```

测试内容包括：
- V2格式解析功能
- System prompt生成
- 基本功能验证

## 🔧 技术细节

### V2解析器特性
1. **think块解析**：提取纯文本推理内容
2. **tool_call块解析**：解析JSON格式的工具调用数组
3. **answer块解析**：提取包含restoration_log的JSON对象
4. **兼容性检查**：自动检测并处理格式错误

### 图像历史管理
1. **自动追踪**：每次工具执行后自动保存图像状态
2. **CPU优化**：确保图像数据在CPU上，避免GPU显存累积
3. **历史访问**：支持获取任意步骤的图像状态

### 统计信息增强
1. **工具使用统计**：详细记录每种工具的使用情况
2. **退化类型统计**：统计各种退化类型的出现频率
3. **修复步骤统计**：记录修复过程的完整信息

## ⚠️ 注意事项

1. **模型兼容性**：确保使用的模型是基于V2格式训练的
2. **工具模块导入**：确保所有必要的工具模块都已正确导入
3. **GPU内存管理**：大批量评估时注意GPU内存使用
4. **数据格式**：确保输入数据符合预期的parquet格式

## 🔄 从V1迁移

如果你之前使用V1版本，升级到V2的步骤：

1. **更新脚本**：使用`eval_agent_true_inference_v2.py`
2. **检查模型**：确保模型支持V2格式输出
3. **更新分析逻辑**：使用新的V2解析结果格式
4. **验证输出**：检查生成的文件是否符合预期

## 📊 性能对比

| 特性 | V1版本 | V2版本 | 改进 |
|------|--------|--------|------|
| 格式检查 | 基础 | 严格+渐进式 | ✅ |
| 图像历史 | 无 | 完整追踪 | ✅ |
| 统计信息 | 基础 | 详细分类 | ✅ |
| 错误处理 | 基础 | 增强容错 | ✅ |
| 输出分析 | 简单 | 结构化 | ✅ |

V2版本在保持向后兼容的同时，显著提升了功能完整性和分析深度。
