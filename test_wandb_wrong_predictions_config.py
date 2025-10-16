#!/usr/bin/env python3
"""
测试 WANDB_LOG_WRONG_PREDICTIONS 环境变量配置

用法:
    python test_wandb_wrong_predictions_config.py
"""

import os
import sys

def test_config_parsing():
    """测试环境变量的解析逻辑"""
    
    test_cases = [
        # (环境变量值, 期望结果, 描述)
        ("True", True, "True -> 启用"),
        ("true", True, "true -> 启用"),
        ("1", True, "1 -> 启用"),
        ("yes", True, "yes -> 启用"),
        ("YES", True, "YES -> 启用"),
        ("False", False, "False -> 禁用"),
        ("false", False, "false -> 禁用"),
        ("0", False, "0 -> 禁用"),
        ("no", False, "no -> 禁用"),
        ("NO", False, "NO -> 禁用"),
        ("", False, "空字符串 -> 禁用"),
        ("random", False, "其他值 -> 禁用"),
        (None, True, "未设置 -> 默认启用"),
    ]
    
    print("=" * 80)
    print("测试 WANDB_LOG_WRONG_PREDICTIONS 环境变量解析")
    print("=" * 80)
    print()
    
    all_passed = True
    
    for value, expected, description in test_cases:
        # 模拟环境变量设置
        if value is None:
            if 'WANDB_LOG_WRONG_PREDICTIONS' in os.environ:
                del os.environ['WANDB_LOG_WRONG_PREDICTIONS']
            env_value = None
        else:
            os.environ['WANDB_LOG_WRONG_PREDICTIONS'] = value
            env_value = value
        
        # 使用与ray_trainer.py相同的逻辑
        result = os.environ.get('WANDB_LOG_WRONG_PREDICTIONS', 'True').lower() in ['true', '1', 'yes']
        
        # 检查结果
        status = "✅ PASS" if result == expected else "❌ FAIL"
        if result != expected:
            all_passed = False
        
        print(f"{status} | {description}")
        print(f"       环境变量值: {repr(env_value)}")
        print(f"       解析结果: {result} (期望: {expected})")
        print()
    
    print("=" * 80)
    if all_passed:
        print("✅ 所有测试通过！")
        return 0
    else:
        print("❌ 部分测试失败！")
        return 1


def check_current_config():
    """检查当前环境中的配置"""
    
    print("=" * 80)
    print("检查当前环境配置")
    print("=" * 80)
    print()
    
    # 检查环境变量
    env_value = os.environ.get('WANDB_LOG_WRONG_PREDICTIONS')
    is_enabled = os.environ.get('WANDB_LOG_WRONG_PREDICTIONS', 'True').lower() in ['true', '1', 'yes']
    
    print(f"环境变量 WANDB_LOG_WRONG_PREDICTIONS:")
    print(f"  当前值: {repr(env_value)}")
    print(f"  是否启用: {'✅ 是' if is_enabled else '❌ 否'}")
    print()
    
    if is_enabled:
        print("📊 错误预测上传: 已启用")
        print("   - 验证时会上传预测错误的样本到 wandb")
        print("   - 表格位置: val_errors/wrong_predictions")
        print()
    else:
        print("⚠️  错误预测上传: 已禁用")
        print("   - 验证时跳过错误样本上传")
        print("   - 节省存储空间和带宽")
        print()
    
    # 检查相关的其他环境变量
    print("相关环境变量:")
    related_vars = [
        'WANDB_API_KEY',
        'FORMAT_REWARD_WEIGHT',
        'QUALITY_REWARD_WEIGHT',
        'ENABLE_DEGRADATION_TYPE_REWARD',
    ]
    
    for var in related_vars:
        value = os.environ.get(var)
        if value:
            print(f"  {var}: {value}")
        else:
            print(f"  {var}: (未设置)")
    
    print()
    print("=" * 80)


def show_usage_examples():
    """显示使用示例"""
    
    print()
    print("=" * 80)
    print("使用示例")
    print("=" * 80)
    print()
    
    print("📝 在 IR.sh 中配置:")
    print()
    print("  # 启用错误预测上传（默认）")
    print("  export WANDB_LOG_WRONG_PREDICTIONS=True")
    print()
    print("  # 禁用错误预测上传")
    print("  export WANDB_LOG_WRONG_PREDICTIONS=False")
    print()
    
    print("🚀 运行训练:")
    print()
    print("  bash examples/agent/IR.sh")
    print()
    
    print("📊 在 Wandb 中查看:")
    print()
    print("  1. 打开 Wandb 项目页面")
    print("  2. 进入 Tables 标签")
    print("  3. 查找 val_errors/wrong_predictions 表格")
    print()
    
    print("🔍 日志关键字:")
    print()
    print("  启用时: 'Found X wrong predictions'")
    print("  禁用时: 'Skipping wrong predictions upload'")
    print("  无错误: 'No wrong predictions found'")
    print()
    
    print("=" * 80)


def main():
    """主函数"""
    
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 15 + "WANDB_LOG_WRONG_PREDICTIONS 配置测试工具" + " " * 22 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    # 运行测试
    exit_code = test_config_parsing()
    print()
    
    # 检查当前配置
    check_current_config()
    
    # 显示使用示例
    show_usage_examples()
    
    print()
    print("📚 更多信息:")
    print("  - 详细文档: WANDB_WRONG_PREDICTIONS_CONFIG.md")
    print("  - 快速参考: WANDB_CONTROL_SUMMARY.md")
    print()
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

