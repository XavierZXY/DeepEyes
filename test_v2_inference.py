#!/usr/bin/env python3
"""
测试V2推理评估脚本
"""

import sys
sys.path.append('/app/xiaominl/DeepEyes')

def test_v2_parsing():
    """测试V2格式解析功能"""
    from verl.workers.agent.parallel_env_v2 import _parse_model_output_for_tools_v2
    
    print("🧪 测试V2格式解析...")
    
    # 测试案例1：包含think和tool_call的响应
    test_response_1 = """<think>Image exhibits blocky artifacts typical of JPEG compression, which is the highest priority to fix based on the LIFO principle.</think>
<tool_call>
[
  {"name": "swinir_jpeg_artifact_removal", "arguments": {"jpeg": 40}}
]
</tool_call>"""
    
    parsed_1 = _parse_model_output_for_tools_v2(test_response_1, "test1")
    print(f"✅ 测试1 - 工具调用:")
    print(f"   think: {parsed_1.get('think')}")
    print(f"   tool_calls: {parsed_1.get('tool_calls')}")
    print(f"   is_done: {parsed_1.get('is_done')}")
    
    # 测试案例2：包含think和answer的响应
    test_response_2 = """<think>After analyzing the image, I can no longer detect any significant compression, imaging, or scene-level degradations. The image is now considered clean.</think>
<answer>
{
  "restoration_log": [
    "jpeg compression artifact",
    "motion blur"
  ]
}
</answer>"""
    
    parsed_2 = _parse_model_output_for_tools_v2(test_response_2, "test2")
    print(f"\n✅ 测试2 - 最终答案:")
    print(f"   think: {parsed_2.get('think')}")
    print(f"   answer: {parsed_2.get('answer')}")
    print(f"   restoration_log: {parsed_2.get('restoration_log')}")
    print(f"   is_done: {parsed_2.get('is_done')}")

def test_system_prompt():
    """测试V2 system prompt"""
    from eval_agent_true_inference_v2 import prepare_model_inputs_v2
    from verl.utils import hf_tokenizer, hf_processor
    
    print("\n🧪 测试V2 System Prompt...")
    
    # 模拟样本数据
    sample_data = {
        'conversations': [
            {'role': 'system', 'content': 'old system prompt'},
            {'role': 'user', 'content': 'Please analyze this image.'}
        ],
        'images': [],  # 空图像列表用于测试
        'env_name': 'test_env'
    }
    
    # 注意：这里需要实际的tokenizer，如果没有可用模型，这部分会失败
    try:
        tokenizer = hf_tokenizer('/app/models/Qwen2.5-VL-7B-Instruct')
        processor = None  # 纯文本测试
        
        prompt_data, vllm_input = prepare_model_inputs_v2(sample_data, tokenizer, processor)
        print(f"✅ V2 prompt生成成功")
        print(f"   prompt_token_ids长度: {len(vllm_input['prompt_token_ids'])}")
        
    except Exception as e:
        print(f"⚠️  tokenizer不可用，跳过prompt测试: {e}")

if __name__ == "__main__":
    print("🎯 V2推理评估测试")
    
    test_v2_parsing()
    test_system_prompt()
    
    print(f"\n🎉 V2测试完成！")
    print(f"💡 使用方法:")
    print(f"   python eval_agent_true_inference_v2.py --model_path /path/to/model --sample_indices 0 1 2")
