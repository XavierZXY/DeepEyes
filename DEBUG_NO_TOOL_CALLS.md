# 诊断：没有工具调用

## ✅ 工具注册检查

运行检查脚本：
```bash
python debug_tool_registration.py
```

**结果**: ✅ 所有工具都已正确注册（49个工具）

---

## 🔍 新增调试日志

已在代码中添加详细的调试日志，帮助诊断问题：

### 1. 工具创建日志 (parallel_env.py 第193-196行)

```python
[DEBUG CREATE_TOOLS] T1-样本0 开始创建工具
[DEBUG CREATE_TOOLS] T1-样本0 tool_calls数量: 3
[DEBUG CREATE_TOOLS] T1-样本0 tool_calls内容: [{'name': 'restormer_deraining', ...}, ...]
```

### 2. 工具名称检查 (第206-207行)

```python
[DEBUG TOOL] tool_call: {'name': 'restormer_deraining', 'arguments': {}}
[DEBUG TOOL] tool_name: restormer_deraining, 类型: <class 'str'>
```

### 3. 工具注册检查 (第229-230行)

```python
[ERROR TOOL] T1-样本0 工具'xxx'未在注册表中找到
[ERROR TOOL] T1-样本0 已注册的工具: ['dehazeformer_dehaze', 'restormer_deraining', ...]
```

### 4. 工具链执行开始 (第914行)

```python
[DEBUG T1-00] 🔧 开始执行工具链，共3个工具
```

### 5. 工具链执行详情 (第952, 967行)

```python
[DEBUG T1-00] 🔄 工具1/3: restormer_deraining (输入: 原图)
[DEBUG T1-00] ✅ 工具1执行成功: reward=0.000, done=False
[DEBUG T1-00] 📷 更新当前图像数据
```

### 6. 工具链执行失败 (第1003-1004行)

```python
[ERROR T1-00] ❌ 所有工具执行失败！
[ERROR T1-00] 工具列表: ['restormer_deraining', 'retinexformer_sdsd_indoor', None]
```

### 7. 工具链执行完成 (第1014行)

```python
[DEBUG T1-00] 🎉 工具链执行完成: restormer_deraining -> retinexformer_sdsd_indoor -> scunet_real_denoising_gan
```

### 8. 工具调用统计 (第581, 584行)

```python
[DEBUG TOOL CNT] ✅ 样本0 轮次1: 工具链成功执行 [restormer_deraining → retinexformer_sdsd_indoor], 计数 = 1
[DEBUG TOOL CNT] ❌ 样本5 轮次1: 工具链执行失败，不计数
```

---

## 📊 诊断步骤

### 步骤1: 检查模型是否输出tool_call

```bash
# 查看模型输出
grep "DEBUG step" logs/*.log | head -20

# 查看解析到的工具
grep "工具解析" logs/*.log | head -20
```

**期望输出**:
```
[DEBUG step 1-00] 工具解析: [{'name': 'restormer_deraining', 'degradation': 'rain', 'arguments': {}}]
```

**如果为空**:
```
[DEBUG step 1-00] 工具解析: []
```
→ **问题**: 模型没有输出 `<tool_call>` 或格式错误

---

### 步骤2: 检查工具创建

```bash
# 查看工具创建日志
grep "DEBUG CREATE_TOOLS" logs/*.log | head -20
```

**期望输出**:
```
[DEBUG CREATE_TOOLS] T1-样本0 开始创建工具
[DEBUG CREATE_TOOLS] T1-样本0 tool_calls数量: 3
[DEBUG CREATE_TOOLS] T1-样本0 tool_calls内容: [{'name': 'restormer_deraining', ...}]
```

**如果工具创建失败**:
```bash
grep "ERROR TOOL" logs/*.log | head -20
```

可能的错误：
- `工具'xxx'未在注册表中找到` → 工具名称拼写错误
- `工具调用缺少name字段` → JSON格式错误
- `格式错误：name字段是字典而不是字符串` → 模型输出格式错误

---

### 步骤3: 检查工具链执行

```bash
# 查看工具链执行
grep "开始执行工具链" logs/*.log | head -10
grep "工具链执行完成" logs/*.log | head -10
```

**期望输出**:
```
[DEBUG T1-00] 🔧 开始执行工具链，共3个工具
[DEBUG T1-00] 🎉 工具链执行完成: restormer_deraining -> retinexformer_sdsd_indoor -> scunet_real_denoising_gan
```

**如果没有执行**:
```bash
grep "所有工具执行失败" logs/*.log
```

---

### 步骤4: 检查工具调用统计

```bash
# 查看统计日志
grep "DEBUG TOOL CNT" logs/*.log | head -20
```

**期望输出**:
```
[DEBUG TOOL CNT] ✅ 样本0 轮次1: 工具链成功执行 [restormer_deraining → retinexformer_sdsd_indoor], 计数 = 1
```

**如果看到**:
```
[DEBUG TOOL CNT] ❌ 样本0 轮次1: 工具链执行失败，不计数
```
→ 虽然模型输出了tool_call，但工具执行失败

---

## 🐛 常见问题

### 问题1: 模型不输出tool_call

**症状**:
```bash
grep "工具解析" logs/*.log
# 输出: 工具解析: []
```

**原因**:
- System prompt 不正确
- 模型没有学会输出 `<tool_call>` 格式
- max_turns=1 太少，模型还没来得及输出

**解决**:
- 检查 system prompt 是否正确设置
- 增加 max_turns（例如改为4）
- 检查训练数据是否包含tool_call示例

---

### 问题2: 工具名称拼写错误

**症状**:
```bash
grep "ERROR TOOL.*未在注册表中找到" logs/*.log
```

**原因**:
- 模型输出的工具名称与注册的不一致
- 例如: `restormer_derain` vs `restormer_deraining`

**解决**:
- 检查 system prompt 中的工具名称
- 对比 `debug_tool_registration.py` 输出的已注册工具

---

### 问题3: JSON格式错误

**症状**:
```bash
grep "Failed to parse valid tool calls" logs/*.log
```

**原因**:
- 模型输出的不是有效的JSON
- 例如: 缺少引号、逗号错误等

**解决**:
- 在 system prompt 中强调JSON格式
- 提供更多格式正确的示例

---

### 问题4: 工具执行失败

**症状**:
```bash
grep "所有工具执行失败" logs/*.log
# 或
grep "工具链执行失败" logs/*.log
```

**原因**:
- 工具API服务未启动
- 图像数据为None
- 工具内部错误

**解决**:
- 检查工具服务是否运行 (检查 TOOL_SERVICE_IP)
- 查看具体的错误栈 `grep "ERROR.*-00" logs/*.log`
- 检查图像数据是否正确传递

---

## 🔧 快速诊断命令

一键运行所有检查：

```bash
#!/bin/bash
echo "=== 1. 检查工具注册 ==="
python debug_tool_registration.py | tail -20

echo ""
echo "=== 2. 检查模型输出 ==="
grep "工具解析" logs/*.log | head -5

echo ""
echo "=== 3. 检查工具创建 ==="
grep "DEBUG CREATE_TOOLS.*tool_calls数量" logs/*.log | head -5

echo ""
echo "=== 4. 检查工具执行 ==="
grep "工具链执行完成" logs/*.log | wc -l
echo "成功执行的工具链数量 ↑"

echo ""
echo "=== 5. 检查执行失败 ==="
grep "所有工具执行失败" logs/*.log | wc -l
echo "失败的工具链数量 ↑"

echo ""
echo "=== 6. 检查统计 ==="
grep "DEBUG TOOL CNT.*✅" logs/*.log | wc -l
echo "统计计数的工具链 ↑"

grep "DEBUG TOOL CNT.*❌" logs/*.log | wc -l  
echo "未计数的工具链 ↑"
```

保存为 `quick_diagnosis.sh` 并运行：
```bash
bash quick_diagnosis.sh
```

---

## 📝 下一步

根据日志输出，确定问题所在：

1. **如果 tool_calls数量=0** → 模型未输出 `<tool_call>`
2. **如果 ERROR TOOL** → 工具创建失败
3. **如果 所有工具执行失败** → 工具执行失败
4. **如果 ❌ 工具链执行失败** → 工具链部分或全部失败

将相关日志发送给我，我可以帮助进一步诊断！

---

**修改时间**: 2025-10-18  
**状态**: ✅ 调试日志已添加  
**下一步**: 运行训练，查看日志输出

