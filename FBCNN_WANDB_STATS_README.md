# 工具统计管理器 - 独立的WandB统计功能

## 概述

已将DeepEyes系统的工具统计功能从actor环境中分离出来，创建了独立的工具统计管理器(`ToolStatisticsManager`)。现在可以更清晰地管理和追踪各种工具的使用情况，并将统计数据发送到WandB。

## 新增功能

### 1. 工具调用统计
系统现在会统计以下工具的使用次数：
- **FBCNN工具**:
  - `fbcnn_jpeg_artifact_removal` - FBCNN JPEG压缩伪影去除
  - `fbcnn_blind_quality_assessment` - FBCNN盲质量评估

- **SwinIR工具**:
  - `swinir_denoising` - SwinIR去噪
  - `swinir_jpeg_artifact_removal` - SwinIR JPEG伪影去除  
  - `swinir_super_resolution` - SwinIR超分辨率

- **其他工具**:
  - `mprnet_denoising`, `mprnet_deraining`, `mprnet_motion_deblurring`
  - `xrestormer_deraining`, `xrestormer_motion_deblurring`
  - `dehazeformer_dehaze`, `drbnet_defocus_deblurring`
  - `visual_toolbox`, `visual_toolbox_v2`, `visual_toolbox_v3`, `visual_toolbox_v4`, `visual_toolbox_v5`

### 2. WandB指标

每个工具会生成以下WandB指标：
- `agent/tool_{tool_name}_total` - 工具总使用次数
- `agent/tool_{tool_name}_mean` - 平均使用次数
- `agent/tool_{tool_name}_max` - 最大使用次数
- `agent/tool_{tool_name}_usage_rate` - 工具使用率（使用该工具的样本比例）

例如，FBCNN工具会产生：
- `agent/tool_fbcnn_jpeg_artifact_removal_total`
- `agent/tool_fbcnn_jpeg_artifact_removal_mean`
- `agent/tool_fbcnn_jpeg_artifact_removal_max`
- `agent/tool_fbcnn_jpeg_artifact_removal_usage_rate`

### 3. 日志输出

训练过程中会在控制台输出详细的工具使用统计：
```
[TOOL STATS] T1-样本0 使用工具: fbcnn_jpeg_artifact_removal
[STATS SUMMARY] 工具使用统计:
[STATS SUMMARY]   fbcnn_jpeg_artifact_removal: 5 次
[STATS SUMMARY]   swinir_denoising: 3 次
[METRICS DEBUG] fbcnn_jpeg_artifact_removal: total=5.0, mean=0.250, rate=0.400
```

## 新架构设计

### 1. **独立的工具统计管理器** (`/verl/utils/tool_statistics_manager.py`)
- `ToolStatisticsManager`类：专门负责工具统计管理
- 单例模式：通过`get_tool_stats_manager()`获取全局实例
- 功能分离：将统计逻辑从actor环境中完全分离

### 2. **核心功能模块**
- **统计收集**：`record_tool_usage()` - 记录工具使用
- **数据处理**：`get_tensor_stats()` - 生成tensor数据
- **WandB集成**：`get_wandb_metrics()` - 生成WandB指标
- **摘要输出**：`print_statistics_summary()` - 打印统计摘要

## 修改的文件

### 1. **新建文件** `/verl/utils/tool_statistics_manager.py`
- 创建了独立的`ToolStatisticsManager`类
- 提供了完整的工具统计功能
- 支持单例模式和便捷函数

### 2. **更新** `/verl/workers/agent/parallel_env_v2.py`  
- 导入并使用工具统计管理器
- 移除原有的工具统计逻辑
- 通过统计管理器记录工具使用和生成统计数据

### 3. **更新** `/verl/trainer/ppo/metric_utils.py`
- 使用工具统计管理器获取工具列表
- 保持原有的WandB指标处理逻辑

## 使用方法

### 在训练脚本中
无需额外配置，统计功能会自动启用。在训练过程中，工具使用统计会自动收集并发送到WandB。

### 在WandB界面中
可以在WandB的指标面板中查看：
1. 打开WandB项目页面
2. 在Metrics标签页中查找`agent/tool_*`指标
3. 可以创建自定义图表来可视化工具使用趋势

### 代码使用示例
```python
# 导入工具统计管理器
from verl.utils.tool_statistics_manager import get_tool_stats_manager, record_tool_usage

# 记录工具使用（便捷函数）
record_tool_usage("fbcnn_jpeg_artifact_removal", sample_index=0)

# 获取管理器实例
tool_stats_manager = get_tool_stats_manager()

# 生成WandB指标
wandb_metrics = tool_stats_manager.get_wandb_metrics()

# 打印统计摘要
tool_stats_manager.print_statistics_summary()
```

## 验证功能

可以通过以下方式验证功能是否正常：

1. **检查日志输出**:
   ```bash
   # 运行训练时查看是否有工具统计日志
   grep "TOOL STATS" training.log
   grep "工具使用统计" training.log
   ```

2. **检查WandB指标**:
   - 登录WandB查看是否有`agent/tool_*`开头的指标
   - 确认指标值符合预期

3. **代码验证**:
   ```python
   # 检查工具是否正确注册
   from verl.workers.agent.tool_envs import ToolBase
   print("fbcnn_jpeg_artifact_removal" in ToolBase.registry)  # 应该返回True
   ```

## 优势与特点

1. **架构分离**: 工具统计逻辑完全独立于actor环境，便于维护和测试
2. **性能优化**: 统计功能对性能影响很小，主要是额外的计数操作
3. **存储效率**: WandB存储的指标数据量不大，但信息丰富
4. **兼容性**: 与现有的退化类型统计功能完全兼容
5. **扩展性**: 添加新工具时只需在`ToolStatisticsManager.all_tool_names`列表中添加即可
6. **可重用**: 统计管理器可以在其他项目中重用

## 故障排除

如果工具统计不工作：

1. **检查工具注册**: 确保工具在`ToolBase.registry`中
2. **检查工具名称**: 确保工具名称在`ToolStatisticsManager.all_tool_names`列表中
3. **检查日志**: 查看是否有`[TOOL STATS]`或`[STATS V2 SUMMARY]`日志输出
4. **检查WandB连接**: 确保WandB正常工作且有权限写入指标
5. **检查管理器**: 确保`get_tool_stats_manager()`返回有效实例

## 总结

通过引入独立的工具统计管理器，我们实现了：

### **架构改进**
- **职责分离**: 工具统计逻辑从actor环境中分离，提高代码可维护性
- **模块化设计**: 独立的管理器可以在不同场景下重用
- **清晰接口**: 提供了简洁的API用于统计收集和数据导出

### **功能增强**  
- **完整统计**: FBCNN、SwinIR、MPRNet等所有工具的详细使用统计
- **WandB集成**: 自动生成和发送工具使用指标到WandB
- **调试友好**: 详细的日志输出便于问题排查

### **分析价值**
现在可以通过WandB清晰地分析：
- 哪些工具被使用得最多
- 工具使用的趋势变化  
- 不同实验配置下的工具使用模式
- 训练过程中工具选择的演化

这种架构设计不仅提高了代码质量，还为深入理解和优化多模态代理的行为提供了强有力的工具。
