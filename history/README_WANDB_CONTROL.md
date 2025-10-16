# Wandb错误预测上传控制 - 快速指南

## 🆕 新功能

现在可以通过 `IR.sh` 中的环境变量控制是否上传错误预测样本到Wandb！

## ⚙️ 配置方法

### 在 IR.sh 中设置

```bash
# 启用错误预测上传（默认）
export WANDB_LOG_WRONG_PREDICTIONS=True

# 禁用错误预测上传
export WANDB_LOG_WRONG_PREDICTIONS=False
```

**位置**: `examples/agent/IR.sh` 第59行

## 📊 功能说明

### 启用时（True）

✅ 验证阶段会上传预测错误的样本到 `val_errors/wrong_predictions` 表格  
✅ 表格包含：原图、退化图、复原图、GT vs 预测的退化类型、漏检/误检类型  
✅ 帮助分析模型在哪些情况下容易出错  

### 禁用时（False）

⚠️ 跳过错误样本的收集和上传  
⚠️ 节省Wandb存储空间和上传带宽  
⚠️ 加快验证速度  

## 🔍 日志示例

**启用时**:
```
[INFO] Found 15 wrong predictions out of 100 samples
[INFO] Uploading wrong predictions table to: val_errors/wrong_predictions
```

**禁用时**:
```
[INFO] Skipping wrong predictions upload (WANDB_LOG_WRONG_PREDICTIONS=False)
```

## 💡 使用建议

| 场景 | 推荐配置 | 原因 |
|------|---------|------|
| 🔬 训练早期 | `True` | 快速发现模型问题 |
| 🐛 调试阶段 | `True` | 深入分析错误case |
| 🚀 训练后期 | `False` | 节省资源，错误样本少 |
| ⚡ 快速实验 | `False` | 只关注总体指标 |

## 🧪 验证配置

运行测试脚本：
```bash
python test_wandb_wrong_predictions_config.py
```

## 📚 详细文档

- 📖 [详细配置说明](WANDB_WRONG_PREDICTIONS_CONFIG.md)
- 📖 [快速参考](WANDB_CONTROL_SUMMARY.md)
- 📖 [更新说明](UPDATE_WANDB_CONTROL.md)
- 📖 [实现总结](IMPLEMENTATION_SUMMARY.md)
- 📖 [文档索引](WANDB_DOCS_INDEX.md)

## ❓ 常见问题

**Q: 默认是启用还是禁用？**  
A: 默认**启用**（未设置时为True），保持向后兼容。

**Q: 会影响其他Wandb功能吗？**  
A: **不会**。只影响错误预测表格，其他功能（训练图像、验证图像、指标等）完全正常。

**Q: 如何查看当前配置？**  
A: 查看训练日志中的 "wrong predictions" 关键字。

---

**快速开始**: 编辑 `IR.sh` → 设置环境变量 → 运行 `bash examples/agent/IR.sh` 🚀

