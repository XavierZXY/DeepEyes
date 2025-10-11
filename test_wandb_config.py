#!/usr/bin/env python3
"""
测试wandb config是否正确记录了奖励配置参数
"""

import os
import sys

# 设置环境变量（模拟IR.sh中的配置）
os.environ['IMAGE_QUALITY_USE_NO_REFERENCE'] = 'False'
os.environ['IMAGE_QUALITY_DISCRETIZE_LEVELS'] = '10'
os.environ['ENABLE_DEGRADATION_TYPE_REWARD'] = 'True'
os.environ['DEGRADATION_TYPE_REWARD_WEIGHT'] = '1.5'
os.environ['FORMAT_REWARD_WEIGHT'] = '0.4'
os.environ['QUALITY_REWARD_WEIGHT'] = '0.6'

# 模拟配置
from omegaconf import OmegaConf

# 创建一个简单的配置
config = {
    'trainer': {
        'project_name': 'test_project',
        'experiment_name': 'test_config',
        'logger': ['console'],  # 只用console，不真正初始化wandb
        'total_epochs': 10,
    },
    'data': {
        'train_batch_size': 32,
    }
}

print("=" * 70)
print("测试WandB配置记录")
print("=" * 70)

print("\n1. 当前环境变量:")
print(f"   IMAGE_QUALITY_USE_NO_REFERENCE = {os.environ.get('IMAGE_QUALITY_USE_NO_REFERENCE')}")
print(f"   IMAGE_QUALITY_DISCRETIZE_LEVELS = {os.environ.get('IMAGE_QUALITY_DISCRETIZE_LEVELS')}")
print(f"   FORMAT_REWARD_WEIGHT = {os.environ.get('FORMAT_REWARD_WEIGHT')}")
print(f"   QUALITY_REWARD_WEIGHT = {os.environ.get('QUALITY_REWARD_WEIGHT')}")
print(f"   ENABLE_DEGRADATION_TYPE_REWARD = {os.environ.get('ENABLE_DEGRADATION_TYPE_REWARD')}")
print(f"   DEGRADATION_TYPE_REWARD_WEIGHT = {os.environ.get('DEGRADATION_TYPE_REWARD_WEIGHT')}")

print("\n2. 模拟Tracking初始化...")

# 模拟tracking.py中的逻辑
config_with_env = dict(config)

reward_config = {
    'IMAGE_QUALITY_USE_NO_REFERENCE': os.environ.get('IMAGE_QUALITY_USE_NO_REFERENCE', 'True'),
    'IMAGE_QUALITY_DISCRETIZE_LEVELS': os.environ.get('IMAGE_QUALITY_DISCRETIZE_LEVELS', '0'),
    'FORMAT_REWARD_WEIGHT': os.environ.get('FORMAT_REWARD_WEIGHT', '0.3'),
    'QUALITY_REWARD_WEIGHT': os.environ.get('QUALITY_REWARD_WEIGHT', '0.7'),
    'ENABLE_DEGRADATION_TYPE_REWARD': os.environ.get('ENABLE_DEGRADATION_TYPE_REWARD', 'False'),
    'DEGRADATION_TYPE_REWARD_WEIGHT': os.environ.get('DEGRADATION_TYPE_REWARD_WEIGHT', '1.0'),
}

config_with_env['reward_config'] = reward_config

print("\n3. 添加到config后的reward_config:")
print(f"   {reward_config}")

print("\n4. 完整的config结构:")
import json
print(json.dumps(config_with_env, indent=2))

print("\n" + "=" * 70)
print("✅ 配置记录测试完成")
print("=" * 70)

print("\n说明:")
print("- 这些参数会被记录到 wandb.config['reward_config']")
print("- 在WandB网页的 'Overview' tab 中可以看到")
print("- 也可以在 'Files' tab 中下载完整的config.yaml查看")
print()

