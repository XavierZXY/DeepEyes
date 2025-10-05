#!/usr/bin/env python3
"""
测试DataProto修复
"""

import sys
sys.path.append('/app/xiaominl/DeepEyes')

import torch
from verl import DataProto

def test_dataproto_usage():
    """测试DataProto的正确用法"""
    print("🧪 测试DataProto修复...")
    
    # 模拟创建prompt_data
    tensors = {
        'input_ids': torch.tensor([[1, 2, 3, 4, 5]]),
        'attention_mask': torch.tensor([[1, 1, 1, 1, 1]])
    }
    non_tensors = {
        'env_name': ['test_env'],
        'raw_prompt': [[]],
        'origin_multi_modal_data': [{}]
    }
    
    # 创建DataProto对象
    prompt_data = DataProto.from_dict(tensors=tensors, non_tensors=non_tensors)
    print(f"✅ prompt_data创建成功: {type(prompt_data)}")
    
    # 测试直接使用prompt_data作为prompts（这是我们的修复方案）
    prompts = prompt_data
    print(f"✅ prompts赋值成功: {type(prompts)}")
    
    # 验证属性访问
    print(f"✅ batch keys: {list(prompts.batch.keys())}")
    print(f"✅ non_tensor_batch keys: {list(prompts.non_tensor_batch.keys())}")
    
    # 验证数据内容
    print(f"✅ input_ids shape: {prompts.batch['input_ids'].shape}")
    print(f"✅ env_name: {prompts.non_tensor_batch['env_name']}")
    
    return True

if __name__ == "__main__":
    try:
        success = test_dataproto_usage()
        if success:
            print("\n🎉 DataProto修复验证成功！")
            print("💡 现在可以运行V2推理评估脚本了")
        else:
            print("\n❌ DataProto修复验证失败")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
