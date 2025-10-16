# 有参考指标调试指南

## 问题描述
Wandb上显示的有参考指标（SSIM、LPIPS、PSNR）都是0.000，但图片本身是正常的。

## 已知信息
从日志中看到：
```
[DEBUG REF METRICS] Sample 0: metrics returned: {'ssim': 0.5213, 'psnr': 19.17, 'lpips': 0.0}
```
说明计算是成功的（SSIM和PSNR有值）。

## 排查步骤

### 步骤1: 检查LPIPS库是否安装
```bash
pip install lpips
```
**已完成** ✅

### 步骤2: 查看计算统计摘要
运行训练后，在日志中搜索：
```bash
grep "DEBUG REF METRICS.*Summary" logs/debug_*.log -A 20
```

应该看到：
```
========== Summary ==========
Total samples: 256
Successfully calculated: 138
Skip reasons:
  - tool_not_executed: 118
Sample values (first 5 non-zero):
  Sample 0: SSIM=0.5213, LPIPS=0.0000, PSNR=19.17
  Sample 1: SSIM=0.5618, LPIPS=0.0000, PSNR=19.01
  ...
Returning dict with keys: ['ssim_score_ref', 'lpips_score_ref', 'psnr_score_ref']
List lengths: SSIM=256, LPIPS=256, PSNR=256
```

### 步骤3: 检查Caption构建
搜索日志：
```bash
grep "DEBUG CAPTION" logs/debug_*.log | head -30
```

应该看到：
```
[DEBUG CAPTION] Sample 0: Building caption with detailed_metrics
[DEBUG CAPTION] Sample 0: ssim_score_ref[0] = 0.5213
[DEBUG CAPTION] Sample 0: lpips_score_ref[0] = 0.0
[DEBUG CAPTION] Sample 0: psnr_score_ref[0] = 19.17
[DEBUG CAPTION] Sample 0: Added SSIM=0.521 to caption
[DEBUG CAPTION] Sample 0: Added LPIPS=0.000 to caption
[DEBUG CAPTION] Sample 0: Added PSNR=19.2 to caption
[DEBUG CAPTION] Sample 0: Final caption = Val Sample 0 | Quality: 0.784 | Type: low resolution | SSIM: 0.521 | LPIPS: 0.000 | PSNR: 19.2
```

## 可能的问题

### 问题1: LPIPS始终为0（已解决）
**原因**: lpips库未安装
**解决**: `pip install lpips` ✅

### 问题2: 所有指标都是0
**可能原因**:
1. `detailed_metrics`字典传递时丢失数据
2. 索引不对应（比如列表长度不匹配）
3. 数据类型转换问题

**排查方法**:
运行后查看日志中的：
- `[DEBUG REF METRICS] Returning dict with keys:` - 确认返回的数据
- `[DEBUG REF METRICS] Sample values (first 5 non-zero):` - 确认计算结果
- `[DEBUG CAPTION] Sample X: ssim_score_ref[X] = ?` - 确认caption构建时读取的值
- `[DEBUG CAPTION] Sample X: Final caption =` - 确认最终caption

### 问题3: 工具未执行导致指标为0
**症状**: 
```
Skip reasons:
  - tool_not_executed: 所有样本
```

**原因**: 
- `image_history`长度 < 2（只有输入图，没有工具处理）
- 模型只输出了`<answer>`，没有调用工具

**解决**: 
- 检查模型是否真的调用了工具
- 查看`agent/tool_call_mean`指标是否 > 0

## 调试命令

### 查看最新的Summary
```bash
grep "DEBUG REF METRICS.*Summary" logs/debug_*.log -A 20 | tail -30
```

### 查看Caption构建过程
```bash
grep "DEBUG.*CAPTION" logs/debug_*.log | tail -50
```

### 查看LPIPS警告
```bash
grep -i "lpips.*warning\|lpips.*error" logs/debug_*.log
```

### 查看工具调用统计
```bash
grep "agent/tool_call" logs/debug_*.log | tail -10
```

## 预期正常输出

当一切正常时，wandb caption应该显示：
```
Val Sample 1 | Quality: 0.784 | Type: low resolution | SSIM: 0.521 | LPIPS: 0.234 | PSNR: 19.2 | NIQE: 5.23
```

其中：
- **Quality**: 总体质量分数（无参考指标组合）
- **Type**: 退化类型（从数据集读取）
- **SSIM**: 结构相似度 (0-1, 越大越好)
- **LPIPS**: 感知相似度 (0-1, 越小越好)
- **PSNR**: 峰值信噪比 (10-40dB, 越大越好)
- **NIQE**: 无参考质量 (0-100, 越小越好)

## 重启要求

lpips安装后需要：
1. **重启Python进程**（重要！）
2. 重新import模块
3. 重新初始化ImageQualityMetrics

建议完全重启训练脚本。

