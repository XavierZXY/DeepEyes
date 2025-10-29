# 新工具添加检查清单

## 📋 添加新工具时必须更新的地方

当你添加一个新的图像处理工具（如 `nerd_deraining`）时，需要在以下位置添加：

---

## ✅ 必须修改的文件

### 1. 工具实现文件 ✅

**位置：** `verl/workers/agent/envs/mm_process_engine/NeRDToolbox.py`

**内容：**
```python
class NeRDDerainingToolbox(BaseNeRDToolbox):
    name = "nerd_deraining"  # ← 工具名称
    task_name = "deraining"
```

**验证：**
```bash
python3 -c "
from verl.workers.agent.tool_envs import ToolBase
print('nerd_deraining' in ToolBase.registry)
"
```

---

### 2. 统计映射表 ✅

**位置：** `verl/workers/agent/parallel_env.py` 第524行

**修改：**
```python
DEGRADATION_TO_TOOLS = {
    'rain': ['mprnet_deraining', 'restormer_deraining', 'xrestormer_deraining', 'nerd_deraining'],  # ← 添加
    # ...
}
```

**作用：** 让统计系统知道 `nerd_deraining` 对应 `rain` 退化

**验证：**
```bash
grep "'rain':" verl/workers/agent/parallel_env.py
# 应该看到 nerd_deraining 在列表中
```

---

### 3. 格式检查允许列表 ✅

**位置：** `verl/utils/reward_score/image_restoration.py` 第21-76行

**修改：**
```python
ALLOWED_TOOLS = {
    # Deraining
    "mprnet_deraining",
    "restormer_deraining",
    "xrestormer_deraining",
    "nerd_deraining",  # ← 添加
    # ...
}
```

**作用：** 让格式检查允许模型调用这个工具（否则会被惩罚）

**验证：**
```bash
grep "nerd_deraining" verl/utils/reward_score/image_restoration.py
# 应该在 ALLOWED_TOOLS 中找到
```

---

## 🔍 验证工具已完整添加

### 快速检查脚本

```bash
#!/bin/bash

TOOL_NAME="nerd_deraining"
echo "检查 $TOOL_NAME 是否完整添加..."

echo -e "\n1. 工具注册检查:"
python3 -c "
import sys
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')
from verl.workers.agent.tool_envs import ToolBase
if '$TOOL_NAME' in ToolBase.registry:
    print('  ✅ 工具已注册')
else:
    print('  ❌ 工具未注册！')
"

echo -e "\n2. 统计映射表检查:"
if grep -q "$TOOL_NAME" verl/workers/agent/parallel_env.py; then
    echo "  ✅ 已添加到 DEGRADATION_TO_TOOLS"
    grep "'rain':" verl/workers/agent/parallel_env.py
else
    echo "  ❌ 未添加到 DEGRADATION_TO_TOOLS！"
fi

echo -e "\n3. 格式检查允许列表:"
if grep -q "$TOOL_NAME" verl/utils/reward_score/image_restoration.py; then
    echo "  ✅ 已添加到 ALLOWED_TOOLS"
else
    echo "  ❌ 未添加到 ALLOWED_TOOLS！"
fi

echo -e "\n检查完成！"
```

保存为 `check_new_tool.sh` 并运行：
```bash
chmod +x check_new_tool.sh
./check_new_tool.sh
```

---

## 📊 对于 nerd_deraining 的检查结果

### ✅ 1. 工具注册
```
已注册: nerd_deraining ✅
```

### ✅ 2. 统计映射表（刚添加）
```python
'rain': ['mprnet_deraining', 'restormer_deraining', 'xrestormer_deraining', 'nerd_deraining']  ✅
```

### ✅ 3. 格式检查允许列表（刚添加）
```python
ALLOWED_TOOLS = {
    "nerd_deraining",  ✅
}
```

---

## 🎯 完整的工具添加流程

### 步骤1: 实现工具类
```python
class NeRDDerainingToolbox(BaseNeRDToolbox):
    name = "nerd_deraining"  # 定义工具名
```

### 步骤2: 添加到统计映射
```python
# parallel_env.py
'rain': [..., 'nerd_deraining']
```

### 步骤3: 添加到格式允许列表
```python
# image_restoration.py
ALLOWED_TOOLS = {
    "nerd_deraining",
}
```

### 步骤4: 清理缓存并测试
```bash
ray stop
find . -name "*.pyc" -delete
bash examples/agent/IRv2.sh
```

### 步骤5: 验证功能
```bash
# 查看是否有调用
grep "nerd_deraining" logs/*.log

# 查看统计是否计入
grep "rain:" logs/*.log
```

---

## ⚠️ 常见遗漏

### 遗漏1: 只实现了工具类，忘记添加到映射表

**后果：**
- 工具可以调用 ✓
- 但统计不会计数 ❌
- `tool_match/unique_count/rain` 会偏低

**检查：**
```bash
grep "nerd_deraining" verl/workers/agent/parallel_env.py
```

---

### 遗漏2: 只添加了映射表，忘记添加到允许列表

**后果：**
- 统计会计数（如果不检查格式）✓
- 但模型调用时会被格式检查惩罚 ❌
- format_score = -1.0，总奖励很低
- 模型学会不调用这个工具

**检查：**
```bash
grep "nerd_deraining" verl/utils/reward_score/image_restoration.py
```

---

### 遗漏3: 工具名称不一致

**错误示例：**
```python
# 工具类
name = "nerd_deraining"

# 映射表
'rain': ['NeRD_deraining']  # ❌ 大小写不一致

# 允许列表
"nerd-deraining"  # ❌ 连字符不一致
```

**正确：** 所有地方使用完全相同的名称（大小写敏感）

---

## 📝 其他需要考虑的地方

### 可选：添加到文档

更新以下文档（如果存在）：
- README 中的工具列表
- API 文档
- 使用示例

### 可选：添加测试

```python
# 测试工具是否正确注册和工作
def test_nerd_deraining():
    tool = ToolBase.create("nerd_deraining")
    assert tool is not None
    # ...
```

---

## ✅ nerd_deraining 检查结果

### 当前状态

| 检查项 | 状态 | 位置 |
|--------|------|------|
| 工具实现 | ✅ | NeRDToolbox.py |
| 工具注册 | ✅ | 自动注册 |
| 统计映射表 | ✅ | parallel_env.py:524 (刚添加) |
| 格式允许列表 | ✅ | image_restoration.py:34 (刚添加) |

### 验证命令

```bash
# 验证所有配置
grep "nerd_deraining" verl/workers/agent/parallel_env.py
grep "nerd_deraining" verl/utils/reward_score/image_restoration.py

# 都应该有输出
```

---

## 🎉 总结

**nerd_deraining 已完整添加到所有必要位置！**

现在：
- ✅ 模型可以调用它
- ✅ 调用时不会被格式检查惩罚
- ✅ 会被正确统计到 `tool_match/unique_count/rain`

**可以直接使用了！** 🚀

---

## 📞 未来添加新工具时

请参考这个检查清单，确保：
1. ✅ 添加到 `DEGRADATION_TO_TOOLS` (parallel_env.py)
2. ✅ 添加到 `ALLOWED_TOOLS` (image_restoration.py)
3. ✅ 工具名称完全一致（大小写敏感）

这样就不会有遗漏了！

