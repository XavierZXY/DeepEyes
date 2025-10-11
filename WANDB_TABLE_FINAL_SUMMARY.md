# Wandb表格最终增强总结

## 🎉 完成的功能

### 新增3个列

| 列名 | 含义 | 示例值 |
|------|------|--------|
| **Degradation_Type** | 原始退化类别 | `motion_blur`, `jpeg_artifact`, `haze`, `noise` |
| **Tool_Status** | 工具执行状态 | `✅ Success`, `⚠️ Requested but Failed`, `❌ No Tool Request` |
| **Failure_Reason** | 失败原因详情 | 见下方详情 |

---

## 📋 Failure_Reason详细说明

### 场景1: ✅ Success
```
Failure_Reason: "-"
```
工具请求并成功执行，无失败原因。

---

### 场景2: ⚠️ Requested but Failed
**可能的原因组合**：

```
示例1: "max_turns=1 (工具来不及执行) | 请求工具: swinir_denoising"
       ↑ 只有1轮对话                    ↑ 显示具体请求的工具

示例2: "工具未产生新图像 | 请求工具: restormer_motion_deblurring"
       ↑ 工具被调用但没有新图像输出

示例3: "image_history为空 | 请求工具: dehazeformer_dehaze"
       ↑ 工具完全没有执行

示例4: "max_turns=1 (工具来不及执行) | 工具未产生新图像 | 请求工具: swinir_super_resolution"
       ↑ 多个原因组合显示
```

**失败原因包括**：
1. `max_turns=1 (工具来不及执行)` - 对话轮数限制
2. `工具未产生新图像` - 工具执行但无输出
3. `image_history为空` - 工具完全未执行
4. `请求工具: xxx` - 显示请求的具体工具名称

---

### 场景3: ❌ No Tool Request
```
Failure_Reason: "模型直接给出答案，未调用工具"
              或
Failure_Reason: "无工具请求"
```
模型没有请求任何工具，直接给出了答案或其他输出。

---

## 📊 完整表格结构（19列）

```
| Step | Sample_ID | Trajectory_Image | Quality_Score | Num_Tools |
  Degradation_Type | Tool_Status | Failure_Reason | User_Input |
  Turn1_Think | Turn1_Tools | Turn2_Think | Turn2_Tools | 
  Turn3_Think | Turn3_Tools | Turn4_Think | Turn4_Tools |
  Turn5_Think | Turn5_Tools |
```

---

## 🔍 使用示例

### 查找工具执行失败的样本
**筛选**: `Tool_Status = "⚠️ Requested but Failed"`

**查看**:
- `Failure_Reason` - 了解失败原因
- `Turn1_Tools` - 查看请求的工具
- `Degradation_Type` - 查看退化类型

**常见原因及解决方案**:

| 失败原因 | 解决方案 |
|---------|---------|
| `max_turns=1` | 增加max_turns到3或更多 |
| `工具未产生新图像` | 检查工具配置和依赖 |
| `image_history为空` | 检查工具环境和日志 |

---

### 分析特定退化类型的处理
**筛选**: `Degradation_Type = "motion_blur"`

**分析**:
- 成功率: 统计 `✅ Success` 的比例
- 常用工具: 查看 `Turn1_Tools` 中的工具选择
- 失败原因: 分析 `Failure_Reason` 的分布

---

### 查看直接给答案的样本
**筛选**: `Tool_Status = "❌ No Tool Request"`

**分析**:
- `Failure_Reason` - 确认是否是 "模型直接给出答案"
- `Turn1_Tools` - 查看answer内容 `<answer>...</answer>`
- `Degradation_Type` - 是否是clean样本

---

## 🎯 改进点

### 1. Turn_Tools列改进
**之前**: 只显示 `[ANSWER]`  
**现在**: 显示完整内容 `<answer>{"restoration_log": [...]}</answer>`

### 2. 失败诊断能力
- ✅ 自动识别4种失败原因
- ✅ 显示请求的具体工具名称
- ✅ 多原因组合显示
- ✅ 区分直接给answer的情况

### 3. 退化类型追踪
- ✅ 显示原始退化类别
- ✅ 方便按类型分析效果
- ✅ 来自数据集的reward_model字段

---

## ✅ 逻辑完整性保证

1. **所有分支都设置failure_reason** ✅
2. **所有变量正确初始化** ✅
3. **边界情况全部处理** ✅
4. **原有功能完全保留** ✅
5. **Linter无错误** ✅
6. **列数匹配行数** ✅ (19列)

---

## 📝 日志示例

训练时会看到：
```
[DEBUG CONV TABLE] First row data: 
  quality=0.856, 
  num_tools=1, 
  degradation=motion_blur, 
  tool_status=✅ Success, 
  failure_reason=-, 
  user_input_len=128, 
  turn_data_count=1, 
  total_cols=19
```

---

## 🚀 快速开始

**无需任何配置更改**，直接运行训练即可看到新增的列！

新的表格会自动包含：
- ✅ Degradation_Type - 退化类别
- ✅ Tool_Status - 工具状态  
- ✅ Failure_Reason - 失败原因

在Wandb中打开 `train/conversation_details` 或 `val/conversation_details` 表格即可查看。

---

**更新时间**: 2025-10-11  
**版本**: v3.0 Final

