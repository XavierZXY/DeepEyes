# 更新说明：Wandb错误预测上传控制

## 📅 更新日期
2025-10-14

## 🎯 更新目标
将"上传错误图像到wandb"的功能改为通过IR.sh中的环境变量控制，而不是硬编码在代码中。

## ✅ 已完成的修改

### 1. 环境变量配置 (IR.sh)

**文件**: `examples/agent/IR.sh`  
**行数**: 第59行

添加了新的环境变量：
```bash
export WANDB_LOG_WRONG_PREDICTIONS=True
```

**配置说明**:
- `True` / `true` / `1` / `yes` → 启用错误预测上传
- `False` / `false` / `0` / `no` → 禁用错误预测上传
- 未设置时默认为 `True`（启用）

### 2. 代码逻辑修改 (ray_trainer.py)

**文件**: `verl/trainer/ppo/ray_trainer.py`  
**行数**: 第855-873行

修改了验证阶段的逻辑：
```python
import os
if os.environ.get('WANDB_LOG_WRONG_PREDICTIONS', 'True').lower() in ['true', '1', 'yes']:
    # 调用上传函数
    log_validation_wrong_predictions_to_wandb(...)
else:
    print(f"[INFO] Skipping wrong predictions upload (WANDB_LOG_WRONG_PREDICTIONS=False)")
```

### 3. 文档和测试

新增文件：
- ✅ `WANDB_WRONG_PREDICTIONS_CONFIG.md` - 详细的功能说明文档
- ✅ `WANDB_CONTROL_SUMMARY.md` - 快速参考指南
- ✅ `test_wandb_wrong_predictions_config.py` - 配置测试脚本
- ✅ `UPDATE_WANDB_CONTROL.md` - 本更新说明

## 🔍 功能说明

### 启用时（默认）
验证阶段会：
1. 识别预测错误的样本（退化类型识别不准确）
2. 创建包含以下内容的表格：
   - 原图（Ground Truth）
   - 退化图（输入）
   - 复原图（输出）
   - GT退化类型 vs 预测退化类型
   - 漏检/误检的类型
   - 完整对话内容
3. 上传到 Wandb: `val_errors/wrong_predictions`

**日志输出**：
```
[INFO] Found 15 wrong predictions out of 100 samples
[INFO] Uploading wrong predictions table to: val_errors/wrong_predictions
```

### 禁用时
验证阶段会：
1. 跳过错误样本的收集和分析
2. 不创建和上传错误预测表格
3. 节省存储空间和上传带宽

**日志输出**：
```
[INFO] Skipping wrong predictions upload (WANDB_LOG_WRONG_PREDICTIONS=False)
```

## 🧪 测试验证

运行测试脚本验证配置：
```bash
python test_wandb_wrong_predictions_config.py
```

测试结果：
```
✅ 所有测试通过！
- 13个测试用例全部通过
- 环境变量解析逻辑正确
- 默认值处理正确
```

## 📊 使用场景

### 建议启用（True）

✅ **训练早期** - 快速发现模型问题  
✅ **调试阶段** - 深入分析错误case  
✅ **最终评估** - 完整记录错误模式  

### 建议禁用（False）

⚠️ **训练后期** - 错误样本少，上传价值低  
⚠️ **快速迭代** - 只关注总体指标  
⚠️ **资源受限** - 节省存储和带宽  

## 📝 修改文件清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `examples/agent/IR.sh` | 修改 | 添加环境变量配置 |
| `verl/trainer/ppo/ray_trainer.py` | 修改 | 添加条件判断逻辑 |
| `WANDB_WRONG_PREDICTIONS_CONFIG.md` | 新增 | 详细功能说明 |
| `WANDB_CONTROL_SUMMARY.md` | 新增 | 快速参考指南 |
| `test_wandb_wrong_predictions_config.py` | 新增 | 配置测试脚本 |
| `UPDATE_WANDB_CONTROL.md` | 新增 | 本更新说明 |

## 🔗 相关文档

- 📖 [详细配置说明](WANDB_WRONG_PREDICTIONS_CONFIG.md)
- 📖 [快速参考](WANDB_CONTROL_SUMMARY.md)
- 📖 [Wandb完整指南](WANDB_UPLOAD_COMPLETE_GUIDE.md)
- 📖 [Wandb功能总结](WANDB_FEATURES_SUMMARY.md)

## ⚙️ 示例配置

### 训练早期（启用）
```bash
# IR.sh
export WANDB_LOG_WRONG_PREDICTIONS=True
```

### 训练后期（禁用）
```bash
# IR.sh
export WANDB_LOG_WRONG_PREDICTIONS=False
```

## 🚀 立即使用

1. **编辑配置**:
   ```bash
   vim examples/agent/IR.sh
   # 修改第59行的 WANDB_LOG_WRONG_PREDICTIONS
   ```

2. **运行训练**:
   ```bash
   bash examples/agent/IR.sh
   ```

3. **查看日志**:
   ```bash
   tail -f logs/*.log | grep "wrong predictions"
   ```

4. **在Wandb查看**:
   - 进入项目页面
   - Tables → `val_errors/wrong_predictions`

## ✨ 优势

### 灵活性
- ✅ 通过环境变量控制，无需修改代码
- ✅ 可以在不同实验中使用不同配置
- ✅ 支持多种配置值格式（True/true/1/yes）

### 兼容性
- ✅ 向后兼容（未设置时默认启用）
- ✅ 不影响其他wandb功能
- ✅ 独立的配置选项

### 可维护性
- ✅ 配置集中在IR.sh中
- ✅ 清晰的日志输出
- ✅ 完善的文档和测试

## 💡 注意事项

1. **环境变量在训练启动时读取**
   - 训练过程中不会重新读取
   - 修改后需要重启训练才能生效

2. **默认值为True（启用）**
   - 如果未设置环境变量，默认会上传错误预测
   - 如果想禁用，必须显式设置为False

3. **独立功能**
   - 只影响错误预测表格的上传
   - 不影响正常的图像上传、指标上传等

## ❓ 常见问题

**Q: 如何知道当前是否启用了错误预测上传？**  
A: 查看训练日志，搜索关键字 "wrong predictions"

**Q: 禁用后会影响其他功能吗？**  
A: 不会，只影响错误预测表格，其他wandb功能正常

**Q: 可以在训练中途切换吗？**  
A: 不可以，需要重启训练才能生效

**Q: 为什么我看不到错误预测表格？**  
A: 可能原因：
- 环境变量设置为False
- 当前step没有错误预测（模型表现完美）
- 数据集中没有退化类型标签

---

## 📞 联系方式

如有问题或建议，请联系：
- 项目维护者：DeepEyes Team
- 文档更新日期：2025-10-14

---

**状态**: ✅ 已完成并测试通过  
**版本**: v1.0  
**兼容性**: 与现有代码完全兼容

