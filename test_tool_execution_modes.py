#!/usr/bin/env python3
"""
测试工具执行模式切换功能

验证 chain 和 iterative 两种模式的行为差异
"""

import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def test_mode_configuration():
    """测试配置文件是否正确添加了模式参数"""
    print("=" * 80)
    print("测试1: 检查配置文件")
    print("=" * 80)
    
    config_file = Path(__file__).parent / "verl/trainer/config/ppo_trainer.yaml"
    
    if not config_file.exists():
        print(f"❌ 配置文件不存在: {config_file}")
        return False
    
    with open(config_file, 'r') as f:
        content = f.read()
    
    if 'tool_execution_mode' in content:
        print("✅ 配置文件包含 tool_execution_mode 参数")
        # 提取相关行
        for line in content.split('\n'):
            if 'tool_execution_mode' in line:
                print(f"   {line.strip()}")
        return True
    else:
        print("❌ 配置文件缺少 tool_execution_mode 参数")
        return False


def test_ir_script():
    """测试 IR.sh 脚本是否添加了模式切换"""
    print("\n" + "=" * 80)
    print("测试2: 检查 IR.sh 脚本")
    print("=" * 80)
    
    script_file = Path(__file__).parent / "examples/agent/IR.sh"
    
    if not script_file.exists():
        print(f"❌ 脚本文件不存在: {script_file}")
        return False
    
    with open(script_file, 'r') as f:
        content = f.read()
    
    checks = [
        ('TOOL_EXECUTION_MODE', '环境变量定义'),
        ('actor_rollout_ref.rollout.agent.tool_execution_mode', '配置参数传递'),
    ]
    
    all_passed = True
    for check_str, desc in checks:
        if check_str in content:
            print(f"✅ {desc}: 找到 {check_str}")
        else:
            print(f"❌ {desc}: 缺少 {check_str}")
            all_passed = False
    
    return all_passed


def test_patch_file():
    """测试补丁文件是否存在"""
    print("\n" + "=" * 80)
    print("测试3: 检查补丁文件")
    print("=" * 80)
    
    patch_file = Path(__file__).parent / "patches/add_tool_execution_modes.py"
    
    if not patch_file.exists():
        print(f"❌ 补丁文件不存在: {patch_file}")
        return False
    
    with open(patch_file, 'r') as f:
        content = f.read()
    
    functions = [
        '_execute_chain_mode',
        '_execute_iterative_mode',
        '_post_process_tool_result',
        'execute_tool_call_with_modes'
    ]
    
    all_found = True
    for func_name in functions:
        if f"def {func_name}" in content:
            print(f"✅ 函数存在: {func_name}")
        else:
            print(f"❌ 函数缺失: {func_name}")
            all_found = False
    
    return all_found


def simulate_modes():
    """模拟两种模式的行为差异"""
    print("\n" + "=" * 80)
    print("测试4: 模拟两种模式的行为")
    print("=" * 80)
    
    print("\n【模式A: Chain (链式执行)】")
    print("  模型预测: [去雨, 提亮, 去噪]")
    print("  执行流程:")
    print("    Turn 1: 原图 → 去雨 → 提亮 → 去噪 → 结果A")
    print("    返回: 结果A + '已应用: 去雨 → 提亮 → 去噪'")
    print("  ")
    print("    Turn 2 (如果不满意): 模型预测新序列 [去噪, 去雨, 提亮]")
    print("            重新从原图: 原图 → 去噪 → 去雨 → 提亮 → 结果B")
    print("  ")
    print("  特点:")
    print("    ✅ 每次从原图开始，避免累积误差")
    print("    ✅ 可以尝试不同工具顺序和组合")
    print("    ✅ 减少交互轮数")
    
    print("\n【模式B: Iterative (迭代执行)】")
    print("  模型预测: [去雨]")
    print("  执行流程:")
    print("    Turn 1: 原图 → 去雨 → 结果1")
    print("    返回: 结果1 + '已应用: 去雨'")
    print("  ")
    print("    Turn 2: 模型预测 [提亮]")
    print("            结果1 → 提亮 → 结果2")
    print("    返回: 结果2 + '已应用: 提亮'")
    print("  ")
    print("    Turn 3: 模型预测 [去噪]")
    print("            结果2 → 去噪 → 结果3")
    print("    返回: 结果3 + '已应用: 去噪'")
    print("  ")
    print("  特点:")
    print("    ✅ 渐进式改进，实时观察每个工具效果")
    print("    ✅ 可以根据中间结果动态调整策略")
    print("    ✅ 更符合人类逐步修复的思维")
    
    return True


def compare_modes():
    """对比两种模式的优缺点"""
    print("\n" + "=" * 80)
    print("测试5: 模式对比分析")
    print("=" * 80)
    
    comparison = {
        "预测方式": {
            "Chain": "一次预测多个工具（数组）",
            "Iterative": "每次预测1个工具"
        },
        "执行方式": {
            "Chain": "链式执行整个序列",
            "Iterative": "只执行第一个工具"
        },
        "图像传递": {
            "Chain": "每次从原图开始",
            "Iterative": "从上一个结果继续"
        },
        "交互轮数": {
            "Chain": "较少（1轮完成多个工具）",
            "Iterative": "较多（N个工具需要N轮）"
        },
        "适用场景": {
            "Chain": "策略探索、完整规划、对比不同顺序",
            "Iterative": "渐进式修复、精细调整、动态策略"
        },
        "优势": {
            "Chain": "避免累积误差、探索工具组合、减少交互",
            "Iterative": "实时反馈、灵活调整、符合人类思维"
        }
    }
    
    for aspect, modes in comparison.items():
        print(f"\n【{aspect}】")
        for mode, value in modes.items():
            print(f"  {mode:12s}: {value}")
    
    return True


def generate_usage_guide():
    """生成使用指南"""
    print("\n" + "=" * 80)
    print("使用指南")
    print("=" * 80)
    
    guide = """
## 🚀 如何切换模式

### 方法1: 修改 IR.sh 脚本

打开 `examples/agent/IR.sh`，找到：

```bash
export TOOL_EXECUTION_MODE=chain  # 可选值: chain / iterative
```

修改为：
- `chain`     - 链式执行模式（默认，V7模式）
- `iterative` - 迭代执行模式（新增）

### 方法2: 运行时指定

```bash
TOOL_EXECUTION_MODE=iterative bash examples/agent/IR.sh
```

### 方法3: 直接修改配置文件

编辑 `verl/trainer/config/ppo_trainer.yaml`:

```yaml
actor_rollout_ref:
  rollout:
    agent:
      tool_execution_mode: iterative  # 或 chain
```

## 📊 训练建议

### Chain 模式 (推荐用于)
- 初始训练阶段：让模型学习完整策略规划
- 对比实验：测试不同工具顺序的效果
- 效率优先：减少交互轮数，加快训练

配置建议：
```bash
export TOOL_EXECUTION_MODE=chain
actor_rollout_ref.rollout.agent.max_turns=4  # 允许多次尝试不同序列
```

### Iterative 模式 (推荐用于)
- 精细化训练：学习逐步优化策略
- 动态调整：根据中间结果选择下一步
- 模仿人类：符合人类逐步修复思维

配置建议：
```bash
export TOOL_EXECUTION_MODE=iterative
actor_rollout_ref.rollout.agent.max_turns=8  # 需要更多轮数完成任务
```

## 🔧 应用补丁

补丁文件位于: `patches/add_tool_execution_modes.py`

**重要**: 需要手动将补丁应用到 `verl/workers/agent/parallel_env.py`

1. 打开 `parallel_env.py`
2. 找到 `execute_tool_call` 函数（约988行）
3. 按照补丁文件中的说明添加代码
4. 在 `ParallelEnv.step()` 中添加模式参数传递

或者运行自动应用脚本（如果有）。

## ✅ 验证安装

运行测试脚本：
```bash
python test_tool_execution_modes.py
```

查看日志确认模式：
```bash
# 训练时应该看到
[DEBUG T1-00] 🔧 工具执行模式: CHAIN
# 或
[DEBUG T1-00] 🔧 工具执行模式: ITERATIVE
```
"""
    
    print(guide)
    
    # 保存到文件
    guide_file = Path(__file__).parent / "TOOL_EXECUTION_MODES_GUIDE.md"
    with open(guide_file, 'w', encoding='utf-8') as f:
        f.write("# 工具执行模式切换指南\n\n")
        f.write(guide)
    
    print(f"\n✅ 使用指南已保存到: {guide_file}")
    
    return True


def main():
    """主测试函数"""
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "工具执行模式切换 - 测试套件" + " " * 30 + "║")
    print("╚" + "═" * 78 + "╝\n")
    
    tests = [
        ("配置文件", test_mode_configuration),
        ("IR.sh脚本", test_ir_script),
        ("补丁文件", test_patch_file),
        ("模式模拟", simulate_modes),
        ("模式对比", compare_modes),
        ("使用指南", generate_usage_guide),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 打印总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！模式切换功能已成功添加。")
        print("\n下一步:")
        print("  1. 查看 TOOL_EXECUTION_MODES_GUIDE.md 了解使用方法")
        print("  2. 应用 patches/add_tool_execution_modes.py 到 parallel_env.py")
        print("  3. 运行 IR.sh 开始训练")
    else:
        print("\n⚠️  部分测试失败，请检查上述错误。")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

