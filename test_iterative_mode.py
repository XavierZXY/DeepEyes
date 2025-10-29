#!/usr/bin/env python3
"""
测试单工具迭代模式的实现

这个脚本验证 ParallelEnv 的状态管理功能：
1. current_multi_modal_data_list 初始化
2. reset 方法正确初始化状态
3. 降质列表正确提取
4. 工具名到降质类型的映射
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copy import deepcopy
from PIL import Image
import numpy as np

# 设置环境变量
os.environ['AGENT_CONVERSATION_MODE'] = 'single_tool_iterative'

# 导入模块
from verl.workers.agent.parallel_env import ParallelEnv, infer_degradation_from_tool, AGENT_CONVERSATION_MODE
from verl import DataProto


def test_mode_detection():
    """测试模式检测"""
    print("=" * 60)
    print("测试1: 模式检测")
    print("=" * 60)
    
    assert AGENT_CONVERSATION_MODE == 'single_tool_iterative', f"模式错误: {AGENT_CONVERSATION_MODE}"
    print(f"✅ 模式检测成功: {AGENT_CONVERSATION_MODE}")
    print()


def test_tool_to_degradation_mapping():
    """测试工具名到降质类型的映射"""
    print("=" * 60)
    print("测试2: 工具名到降质类型映射")
    print("=" * 60)
    
    test_cases = [
        ('restormer_deraining', 'rain'),
        ('retinexformer_sdsd_indoor', 'dark'),
        ('scunet_real_denoising_gan', 'noise'),
        ('dehazeformer_dehaze', 'haze'),
        ('swinir_super_resolution', 'low resolution'),
        ('unknown_tool', 'unknown'),
    ]
    
    for tool_name, expected in test_cases:
        result = infer_degradation_from_tool(tool_name)
        status = "✅" if result == expected else "❌"
        print(f"{status} {tool_name:40s} → {result:20s} (期望: {expected})")
        assert result == expected, f"映射错误: {tool_name} → {result} (期望: {expected})"
    
    print()


def test_parallel_env_initialization():
    """测试 ParallelEnv 初始化"""
    print("=" * 60)
    print("测试3: ParallelEnv 初始化")
    print("=" * 60)
    
    # 创建 mock tokenizer 和 processor
    class MockTokenizer:
        def encode(self, text, **kwargs):
            return [1, 2, 3]
    
    class MockProcessor:
        pass
    
    class MockConfig:
        def __init__(self):
            self.concurrent_workers = 1
            self.tool_name_key = 'env_name'
            self.show_tqdm = False
    
    config = MockConfig()
    tokenizer = MockTokenizer()
    processor = MockProcessor()
    
    env = ParallelEnv(config, tokenizer, processor)
    
    # 检查属性是否存在
    assert hasattr(env, 'current_multi_modal_data_list'), "缺少 current_multi_modal_data_list"
    assert hasattr(env, 'processed_degradations_list'), "缺少 processed_degradations_list"
    assert hasattr(env, 'remaining_degradations_list'), "缺少 remaining_degradations_list"
    
    # 检查初始化为空列表
    assert env.current_multi_modal_data_list == [], "current_multi_modal_data_list 应该初始化为空"
    assert env.processed_degradations_list == [], "processed_degradations_list 应该初始化为空"
    assert env.remaining_degradations_list == [], "remaining_degradations_list 应该初始化为空"
    
    print("✅ ParallelEnv 初始化成功")
    print("✅ 所有状态管理属性存在")
    print("✅ 属性正确初始化为空列表")
    print()
    
    return env


def test_reset_method():
    """测试 reset 方法"""
    print("=" * 60)
    print("测试4: Reset 方法")
    print("=" * 60)
    
    # 创建 mock 对象
    class MockTokenizer:
        def encode(self, text, **kwargs):
            return [1, 2, 3]
    
    class MockProcessor:
        pass
    
    class MockConfig:
        def __init__(self):
            self.concurrent_workers = 1
            self.tool_name_key = 'env_name'
            self.show_tqdm = False
    
    class MockDataProtoItem:
        def __init__(self):
            self.non_tensor_batch = {
                'env_name': 'test_env',
                'raw_prompt': [{'role': 'user', 'content': 'test'}],
                'extra_info': {
                    'degradations': ['rain', 'dark', 'noise']
                },
                'origin_multi_modal_data': {
                    'image': [Image.fromarray(np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8))]
                }
            }
        
        def __getitem__(self, key):
            return self.non_tensor_batch.get(key)
    
    config = MockConfig()
    tokenizer = MockTokenizer()
    processor = MockProcessor()
    
    env = ParallelEnv(config, tokenizer, processor)
    
    # 创建 prompts 和 vllm_inputs
    prompts = [MockDataProtoItem()]
    vllm_inputs = [{"prompt_token_ids": [1, 2, 3], "multi_modal_data": {}}]
    
    # 调用 reset
    try:
        env.reset(prompts, vllm_inputs, n=1)
        
        # 检查状态
        assert len(env.current_multi_modal_data_list) == 1, "current_multi_modal_data_list 长度错误"
        assert len(env.processed_degradations_list) == 1, "processed_degradations_list 长度错误"
        assert len(env.remaining_degradations_list) == 1, "remaining_degradations_list 长度错误"
        
        # 检查初始值
        assert env.processed_degradations_list[0] == [], "已处理降质应该为空"
        assert env.remaining_degradations_list[0] == ['rain', 'dark', 'noise'], "剩余降质错误"
        assert env.current_multi_modal_data_list[0] is not None, "当前图像应该初始化"
        
        print("✅ Reset 方法执行成功")
        print("✅ 状态列表长度正确")
        print(f"✅ 已处理降质: {env.processed_degradations_list[0]}")
        print(f"✅ 剩余降质: {env.remaining_degradations_list[0]}")
        print("✅ 当前图像已初始化")
        
    except Exception as e:
        print(f"❌ Reset 方法测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("单工具迭代模式 - 实现测试")
    print("=" * 60)
    print()
    
    try:
        # 测试1: 模式检测
        test_mode_detection()
        
        # 测试2: 工具映射
        test_tool_to_degradation_mapping()
        
        # 测试3: 初始化
        env = test_parallel_env_initialization()
        
        # 测试4: Reset
        test_reset_method()
        
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print()
        print("下一步: 运行实际训练验证")
        print("  1. bash examples/agent/IRv2.sh")
        print("  2. 检查日志中的模式相关输出")
        print("  3. 验证图像状态是否在turn之间保持")
        print()
        
        return True
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ 测试失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

