# 图像轨迹可视化布局说明

## 完整布局结构（精简版）

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│ Ground   │ Degraded │  Step 1  │  Step 2  │ Restored │  ← 顶部标签(30px)
│  Truth   │  Input   │          │          │          │
├──────────┼──────────┼──────────┼──────────┼──────────┤
│          │          │          │          │          │
│  原图    │  退化图  │  处理1   │  处理2   │  最终图  │  ← 图像
│  (GT)    │          │          │          │          │
│          │          │          │          │          │
├──────────┼──────────┼──────────┼──────────┼──────────┤
│          │          │  工具A   │  工具B   │          │  ← 底部工具名称(40px)
│          │          │          │          │          │
└──────────┴──────────┴──────────┴──────────┴──────────┘

注：对话内容可在wandb的val/generations表格中查看
```

## 各部分详细说明

### 1. 图像轨迹区域

#### 图像排列（从左到右）

**情况A: 有Ground Truth原图**
```
位置0: Ground Truth (未退化的原图)
位置1: Degraded Input (退化后的输入图)
位置2: Step 1 (第一次工具处理后)
位置3: Step 2 (第二次工具处理后)
...
最后: Restored (最终恢复的图)
```

**情况B: 无Ground Truth**
```
位置0: Degraded Input (退化后的输入图)
位置1: Step 1 (第一次工具处理后)
位置2: Step 2 (第二次工具处理后)
...
最后: Restored (最终恢复的图)
```

#### 顶部标签样式
- **Ground Truth**: 浅蓝色背景（lightblue）
- **Restored**: 浅绿色背景（lightgreen）
- **其他**: 浅黄色背景（lightyellow）

#### 底部工具名称
- **位置**: 紧贴图像下方
- **背景**: 浅灰色（lightgray）
- **字体**: 深蓝色（darkblue）单间距字体
- **内容**: 
  - 对于Ground Truth和Degraded Input: 不显示工具名
  - 对于中间步骤: 显示该步使用的工具（例如：`swinir_jpeg_artifact_removal`）
  - 对于Restored: 不显示工具名
  - 如果该步没有工具: 显示 `None`
  - 如果该步给出answer: 显示 `Answer`

### 2. Caption（Wandb图片标题）

**验证模式**：
```
Val Sample 1 | Quality: 0.784 | Type: low resolution | SSIM: 0.521 | LPIPS: 0.234 | PSNR: 19.2 | NIQE: 5.23
```

**训练模式**：
```
Sample 42 | Quality: 0.856 | Type: motion blur | SSIM: 0.678 | LPIPS: 0.156 | PSNR: 24.5 [BEST]
Sample 15 | Quality: 0.321 | Type: haze | SSIM: 0.234 | LPIPS: 0.567 | PSNR: 12.3 [WORST]
```

## 数据来源

### conversation_history结构
```python
[
    {
        'turn': 1,
        'response': '<think>...</think><tool_call>[{"name": "tool_A", "arguments": {...}}]</tool_call>',
        'is_done': False
    },
    {
        'turn': 2,
        'response': '<think>...</think><answer>{"restoration_log": [...]}</answer>',
        'is_done': True
    }
]
```

### 工具名称提取逻辑
1. 从`conversation_history`中逐轮提取
2. 解析`<tool_call>`标签中的JSON
3. 提取`name`字段
4. 如果有多个工具，用逗号连接
5. 如果是`<answer>`，显示"Answer"
6. 如果都没有，显示"None"

## 尺寸说明

- **图像高度**: 自适应（保持原图比例）
- **图像宽度**: 自适应（按比例缩放）
- **顶部标签**: 30px高
- **底部工具名称**: 40px高
- **图像间距**: 15px
- **图像边框**: 2px灰色
- **总高度**: 约 30 + 图像高度 + 40 + 边框 ≈ 图像高度 + 74px

## 示例场景

### 场景1: 多步骤修复（有GT）
```
[GT原图] → [退化图] → [去噪后] → [去模糊后] → [最终图]
            None      denoiser   deblurrer      None
```

### 场景2: 单步修复（无GT）
```
[退化图] → [修复后]
  None      tool_A
```

### 场景3: 直接给答案（无GT）
```
[退化图] → [退化图]
  None      Answer
```

### 场景4: 多工具组合
```
[退化图] → [处理1] → [处理2] → [最终图]
  None    tool_A, tool_B  tool_C    None
```

## 颜色方案

| 元素 | 颜色 | RGB值 |
|------|------|-------|
| Ground Truth标签 | lightblue | #ADD8E6 |
| Restored标签 | lightgreen | #90EE90 |
| 其他标签 | lightyellow | #FFFFE0 |
| 工具名称背景 | lightgray | #D3D3D3 |
| 工具名称文字 | darkblue | #00008B |
| 图像边框 | gray | #808080 |
| 背景 | white | #FFFFFF |

## 技术实现

### 关键函数
- `create_trajectory_visualization()` - 主可视化函数
- `extract_pil_image_from_data()` - 图像提取
- `build_conversation_text()` - 对话文本构建

### 工具名称提取
```python
# 从conversation_history中提取
for conv in conversation_history:
    response = conv.get('response', '')
    tool_match = re.search(r'<tool_call>(.*?)</tool_call>', response, re.DOTALL)
    if tool_match:
        tools = json.loads(tool_match.group(1))
        names = [t.get('name', '?') for t in tools]
        tool_name = ', '.join(names)
```

### 布局计算
```python
total_height = (
    text_height +           # 对话文本区
    label_height +          # 顶部标签
    target_height +         # 图像高度
    2*border +             # 边框
    tool_label_height      # 底部工具名称
)
```

## 注意事项

1. **工具名称过长**: 自动截断到30字符（显示为"long_tool_name_here..."）
2. **多个工具**: 用逗号连接（例如："tool_A, tool_B"）
3. **无工具**: 显示"None"
4. **Answer状态**: 显示"Answer"而非工具名
5. **解析错误**: 显示"Parse Error"

## 调试

查看工具名称提取是否正常：
```bash
grep "tool_names_per_step" logs/debug_*.log
```

应该看到类似：
```
tool_names_per_step = ['swinir_jpeg_artifact_removal', 'restormer_motion_deblurring', 'Answer']
```

