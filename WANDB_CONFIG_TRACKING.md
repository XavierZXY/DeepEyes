# WandB配置追踪说明

## 🎯 功能概述

现在所有的**奖励配置参数**（包括环境变量）都会自动记录到WandB，方便追踪和对比不同实验的配置。

---

## ✅ 记录的奖励参数

### 1. 图像质量奖励配置

| 参数名 | 默认值 | 说明 |
|-------|--------|------|
| `IMAGE_QUALITY_USE_NO_REFERENCE` | `True` | 是否使用无参考指标 |
| `IMAGE_QUALITY_DISCRETIZE_LEVELS` | `0` | 离散化等级 |

### 2. 退化类型Bonus配置

| 参数名 | 默认值 | 说明 |
|-------|--------|------|
| `ENABLE_DEGRADATION_TYPE_BONUS` | `False` | 是否启用退化类型奖励 |
| `DEGRADATION_TYPE_BONUS_WEIGHT` | `1.0` | 退化类型奖励权重 |

---

## 📍 在WandB中查看配置

### 方法1: Overview页面（推荐）

1. 打开你的WandB项目
   ```
   https://wandb.ai/your-team/your-project
   ```

2. 点击具体的run（实验）

3. 在**Overview** tab中，向下滚动找到 `Config` 部分

4. 找到 `reward_config` 字段：
   ```yaml
   reward_config:
     IMAGE_QUALITY_USE_NO_REFERENCE: "False"
     IMAGE_QUALITY_DISCRETIZE_LEVELS: "10"
     ENABLE_DEGRADATION_TYPE_BONUS: "True"
     DEGRADATION_TYPE_BONUS_WEIGHT: "1.5"
   ```

---

### 方法2: 通过API查询

```python
import wandb

# 连接到你的run
api = wandb.Api()
run = api.run("your-team/your-project/run-id")

# 获取奖励配置
reward_config = run.config.get('reward_config', {})

print("图像质量配置:")
print(f"  使用无参考指标: {reward_config.get('IMAGE_QUALITY_USE_NO_REFERENCE')}")
print(f"  离散化等级: {reward_config.get('IMAGE_QUALITY_DISCRETIZE_LEVELS')}")

print("\n退化类型Bonus配置:")
print(f"  启用: {reward_config.get('ENABLE_DEGRADATION_TYPE_BONUS')}")
print(f"  权重: {reward_config.get('DEGRADATION_TYPE_BONUS_WEIGHT')}")
```

---

### 方法3: 下载完整配置文件

1. 在run页面，点击 **Files** tab

2. 找到并下载 `config.yaml`

3. 打开文件，找到 `reward_config` 部分：
   ```yaml
   reward_config:
     IMAGE_QUALITY_USE_NO_REFERENCE: 'False'
     IMAGE_QUALITY_DISCRETIZE_LEVELS: '10'
     ENABLE_DEGRADATION_TYPE_BONUS: 'True'
     DEGRADATION_TYPE_BONUS_WEIGHT: '1.5'
   ```

---

## 🔍 对比不同实验的配置

### 使用WandB Runs Table

1. 在项目页面，点击 **Table** 或 **Workspace** 

2. 添加列：
   - 点击右上角的 `+ Column`
   - 选择 `config.reward_config.IMAGE_QUALITY_USE_NO_REFERENCE`
   - 选择 `config.reward_config.ENABLE_DEGRADATION_TYPE_BONUS`
   - 等等...

3. 现在可以在表格中对比多个实验的奖励配置

---

### 使用Sweep（超参数搜索）

如果使用WandB Sweep进行超参数搜索，可以将这些参数作为sweep配置的一部分：

```yaml
# sweep.yaml
program: examples/agent/IR.sh
method: grid
parameters:
  IMAGE_QUALITY_USE_NO_REFERENCE:
    values: [True, False]
  DEGRADATION_TYPE_BONUS_WEIGHT:
    values: [0.5, 1.0, 1.5]
```

---

## 📊 配置记录的完整示例

### IR.sh配置
```bash
export IMAGE_QUALITY_USE_NO_REFERENCE=False
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10
export ENABLE_DEGRADATION_TYPE_BONUS=True
export DEGRADATION_TYPE_BONUS_WEIGHT=1.5
```

### WandB中显示的config
```json
{
  "trainer": {
    "project_name": "agent_vlagent",
    "experiment_name": "debug_for_TIR_IR_bs32",
    "total_epochs": 32,
    ...
  },
  "data": {
    "train_batch_size": 32,
    ...
  },
  "reward_config": {
    "IMAGE_QUALITY_USE_NO_REFERENCE": "False",
    "IMAGE_QUALITY_DISCRETIZE_LEVELS": "10",
    "ENABLE_DEGRADATION_TYPE_BONUS": "True",
    "DEGRADATION_TYPE_BONUS_WEIGHT": "1.5"
  },
  ...
}
```

---

## 🎯 使用场景

### 场景1: 追踪实验配置

**问题**: "这个实验用的是哪种图像质量指标？"

**解决**: 
1. 打开WandB run
2. 查看 `config.reward_config.IMAGE_QUALITY_USE_NO_REFERENCE`
3. `True` = 无参考指标，`False` = 有参考指标

---

### 场景2: 对比不同配置的效果

**问题**: "启用退化类型bonus对训练有什么影响？"

**解决**:
1. 运行两个实验：一个 `ENABLE_DEGRADATION_TYPE_BONUS=True`，另一个 `False`
2. 在WandB Table中对比两个run
3. 查看 `critic/score/mean` 等指标的差异

---

### 场景3: 复现实验

**问题**: "如何复现这个好结果的实验？"

**解决**:
1. 下载该run的 `config.yaml`
2. 查看 `reward_config` 部分
3. 在 `IR.sh` 中设置相同的环境变量
4. 重新运行训练

---

## 🚀 快速验证

运行测试脚本验证配置记录功能：

```bash
# 设置测试环境变量
export IMAGE_QUALITY_USE_NO_REFERENCE=False
export IMAGE_QUALITY_DISCRETIZE_LEVELS=10
export ENABLE_DEGRADATION_TYPE_BONUS=True
export DEGRADATION_TYPE_BONUS_WEIGHT=1.5

# 运行测试
python test_wandb_config.py
```

预期输出：
```
✅ 配置记录测试完成

reward_config:
  IMAGE_QUALITY_USE_NO_REFERENCE: False
  IMAGE_QUALITY_DISCRETIZE_LEVELS: 10
  ENABLE_DEGRADATION_TYPE_BONUS: True
  DEGRADATION_TYPE_BONUS_WEIGHT: 1.5
```

---

## 📝 注意事项

### 1. 环境变量优先级

配置读取优先级：
1. 环境变量（IR.sh中的export）
2. 代码中的默认值

### 2. 配置不可变

一旦run开始，config就被记录并**不可修改**。这确保了实验的可重现性。

### 3. 字符串类型

环境变量在config中以**字符串**形式存储：
- `"True"` / `"False"` (字符串)
- `"10"` (字符串)
- `"1.5"` (字符串)

代码中会正确解析这些字符串为相应的类型。

---

## 🔧 技术实现

### 代码位置

**文件**: `verl/utils/tracking.py`

**核心代码**:
```python
# 将环境变量配置的奖励参数添加到config中
if config is not None:
    config_with_env = dict(config)
    
    reward_config = {
        'IMAGE_QUALITY_USE_NO_REFERENCE': os.environ.get('IMAGE_QUALITY_USE_NO_REFERENCE', 'True'),
        'IMAGE_QUALITY_DISCRETIZE_LEVELS': os.environ.get('IMAGE_QUALITY_DISCRETIZE_LEVELS', '0'),
        'ENABLE_DEGRADATION_TYPE_BONUS': os.environ.get('ENABLE_DEGRADATION_TYPE_BONUS', 'False'),
        'DEGRADATION_TYPE_BONUS_WEIGHT': os.environ.get('DEGRADATION_TYPE_BONUS_WEIGHT', '1.0'),
    }
    
    config_with_env['reward_config'] = reward_config
    print(f"[INFO] Added reward config to wandb: {reward_config}")
    
    wandb.init(project=project_name, name=experiment_name, config=config_with_env)
```

---

## ✅ 验证清单

训练开始后，检查以下内容：

- [ ] 控制台显示 `[INFO] Added reward config to wandb: {...}`
- [ ] WandB Overview中有 `reward_config` 字段
- [ ] 所有4个参数都正确记录
- [ ] 参数值与 `IR.sh` 中的配置一致
- [ ] 下载的 `config.yaml` 包含完整的 `reward_config`

---

## 📚 相关文档

- `IMAGE_QUALITY_AND_FORMAT_REWARD_REPORT.md` - 图像质量奖励详解
- `DEGRADATION_TYPE_BONUS_GUIDE.md` - 退化类型bonus使用指南
- `REWARD_CONFIG_IMPLEMENTATION_SUMMARY.md` - 奖励配置实现总结

---

**更新完成** 🎉

现在所有的奖励配置参数都会自动记录到WandB，便于实验追踪和结果复现！

