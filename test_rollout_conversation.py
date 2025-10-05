#!/usr/bin/env python3
"""
测试文件：模拟rollout对话格式的工具调用过程
展示每一轮对话、工具处理后的图片和文本回答
"""

import os
import json
import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from datetime import datetime
from copy import deepcopy

# 模拟导入必要的模块
from verl.workers.agent.parallel_env_v2 import (
    _parse_model_output_for_tools_v2,
    _create_tools_from_parsed_output_v2,
    execute_tool_call_v2,
    ParallelEnvV2
)
from verl.workers.agent.tool_envs import ToolBase


class MockTokenizer:
    """模拟tokenizer"""
    def __init__(self):
        self.pad_token_id = 0
        self.eos_token_id = 2
    
    def encode(self, text, add_special_tokens=False, return_tensors=None):
        # 简单模拟编码
        token_ids = [1, 2, 3, 4, 5]  # 模拟token序列
        if return_tensors == 'pt':
            return torch.tensor([token_ids])
        return token_ids
    
    def apply_chat_template(self, messages, add_generation_prompt=True, tokenize=False, return_tensors=None):
        if tokenize:
            return torch.tensor([[1, 2, 3, 4]])
        return "<|im_start|>user\nTest message<|im_end|>\n<|im_start|>assistant\n"


class MockProcessor:
    """模拟processor"""
    def __init__(self):
        pass
    
    def __call__(self, text=None, images=None, return_tensors="pt"):
        return {
            "input_ids": torch.tensor([[1, 2, 3, 4]]),
            "attention_mask": torch.tensor([[1, 1, 1, 1]]),
            "pixel_values": torch.randn(1, 3, 224, 224) if images else None
        }


class ConversationTester:
    """对话测试器"""
    
    def __init__(self, output_dir="test_results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 初始化模拟组件
        self.tokenizer = MockTokenizer()
        self.processor = MockProcessor()
        
        # 创建测试图片
        self.create_test_image()
        
        # 对话历史
        self.conversation_history = []
        self.current_turn = 0
        
    def create_test_image(self):
        """创建一个测试图片（模拟有JPEG压缩、运动模糊和雾霾的图片）"""
        # 创建一个有问题的测试图片
        img = Image.new('RGB', (512, 512), color='lightblue')
        
        # 添加一些简单的图案来模拟内容
        import numpy as np
        img_array = np.array(img)
        
        # 添加一些方块图案（模拟JPEG压缩伪影）
        for i in range(0, 512, 8):
            for j in range(0, 512, 8):
                if (i//8 + j//8) % 2 == 0:
                    img_array[i:i+8, j:j+8] = [100, 150, 200]
        
        # 添加噪声（模拟压缩和其他问题）
        noise = np.random.normal(0, 20, img_array.shape)
        img_array = np.clip(img_array + noise, 0, 255).astype(np.uint8)
        
        self.current_image = Image.fromarray(img_array)
        self.original_image = self.current_image.copy()
        
        # 保存原始图片
        self.current_image.save(os.path.join(self.output_dir, "original_image.png"))
        print(f"✅ 创建测试图片: {self.current_image.size}")
    
    def simulate_model_response(self, turn):
        """模拟模型的响应"""
        if turn == 1:
            # 第一轮：检测JPEG压缩伪影
            return """<think>The image shows noticeable 8x8 blockiness and ringing artifacts, especially in flat areas. According to the restoration principle, compression artifacts are Priority 1 and must be fixed first.</think>
<tool_call>
[
  {"name": "swinir_jpeg_artifact_removal", "arguments": {"jpeg": 40}}
]
</tool_call>"""
        
        elif turn == 2:
            # 第二轮：检测运动模糊
            return """<think>The compression artifacts are gone, but a clear directional blur is now visible, indicating camera shake. This is an imaging degradation (Priority 2) and is now the most critical issue.</think>
<tool_call>
[
  {"name": "xrestormer_motion_deblurring", "arguments": {"strength": 0.8}}
]
</tool_call>"""
        
        elif turn == 3:
            # 第三轮：检测雾霾
            return """<think>Motion blur has been addressed, but the image still appears hazy with reduced contrast and visibility. This is a scene degradation (Priority 3) that needs to be fixed.</think>
<tool_call>
[
  {"name": "dehazeformer_dehaze", "arguments": {"strength": 0.7}}
]
</tool_call>"""
        
        else:
            # 最后一轮：完成
            return """<think>After analyzing the image, I can no longer detect any significant compression, imaging, or scene-level degradations. The image is now considered clean.</think>
<answer>
{
  "restoration_log": [
    "jpeg compression artifact",
    "motion blur", 
    "haze"
  ]
}
</answer>"""
    
    def create_mock_tool_result(self, tool_name, turn):
        """模拟工具执行结果"""
        # 创建一个稍微不同的图片来模拟工具处理结果
        img_array = np.array(self.current_image)
        
        if "jpeg" in tool_name:
            # 模拟JPEG去压缩：减少块状伪影
            img_array = img_array + np.random.normal(0, 5, img_array.shape)
            tool_message = "Successfully removed JPEG compression artifacts. Blockiness reduced significantly."
            
        elif "motion" in tool_name:
            # 模拟去运动模糊：增加清晰度
            img_array = img_array * 1.1  # 增加对比度
            tool_message = "Motion blur correction applied. Image sharpness improved."
            
        elif "dehaze" in tool_name:
            # 模拟去雾：增加对比度和饱和度
            img_array = img_array * 1.2
            tool_message = "Haze removal completed. Visibility and contrast enhanced."
            
        else:
            tool_message = f"Tool {tool_name} executed successfully."
        
        # 确保像素值在有效范围内
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        processed_image = Image.fromarray(img_array)
        
        # 更新当前图片
        self.current_image = processed_image
        
        # 保存处理后的图片
        image_filename = f"turn_{turn}_{tool_name.replace('_', '-')}.png"
        image_path = os.path.join(self.output_dir, image_filename)
        processed_image.save(image_path)
        
        return {
            "prompt": f"\n<|im_start|>user\n{tool_message}<|im_end|>\n<|im_start|>assistant\n",
            "multi_modal_data": {"image": [processed_image]},
            "tool_message": tool_message,
            "image_path": image_path
        }
    
    def run_conversation_test(self):
        """运行完整的对话测试"""
        print("🚀 开始对话测试")
        print("=" * 60)
        
        restoration_log = []
        max_turns = 5
        
        for turn in range(1, max_turns + 1):
            print(f"\n🔄 轮次 {turn}")
            print("-" * 40)
            
            # 1. 模拟模型响应
            model_response = self.simulate_model_response(turn)
            print(f"🤖 模型输出:")
            print(model_response)
            
            # 2. 解析模型输出
            parsed_output = _parse_model_output_for_tools_v2(
                model_response, 
                f"测试轮次{turn}"
            )
            
            print(f"\n📝 解析结果:")
            print(f"  - Think: {parsed_output.get('think', 'None')}")
            print(f"  - Tool calls: {len(parsed_output.get('tool_calls', []))}")
            print(f"  - Is done: {parsed_output.get('is_done', False)}")
            
            # 3. 检查是否完成
            if parsed_output.get('is_done', False):
                answer = parsed_output.get('answer', {})
                if isinstance(answer, dict):
                    restoration_log = answer.get('restoration_log', [])
                print(f"\n✅ 对话完成！修复日志: {restoration_log}")
                break
            
            # 4. 执行工具调用
            tool_calls = parsed_output.get('tool_calls', [])
            if tool_calls:
                for i, tool_call in enumerate(tool_calls):
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get('name', 'unknown')
                        tool_args = tool_call.get('arguments', {})
                        
                        print(f"\n🔧 执行工具: {tool_name}")
                        print(f"  参数: {tool_args}")
                        
                        # 模拟工具执行结果
                        tool_result = self.create_mock_tool_result(tool_name, turn)
                        
                        print(f"  ✅ 工具执行成功")
                        print(f"  📸 图片保存: {tool_result['image_path']}")
                        print(f"  💬 工具回复: {tool_result['tool_message']}")
                        
                        # 记录到对话历史
                        self.conversation_history.append({
                            'turn': turn,
                            'model_response': model_response,
                            'parsed_output': parsed_output,
                            'tool_name': tool_name,
                            'tool_args': tool_args,
                            'tool_result': tool_result
                        })
            
            self.current_turn = turn
        
        # 5. 保存对话历史
        self.save_conversation_summary(restoration_log)
        
        print(f"\n🎉 测试完成！结果保存在: {self.output_dir}")
    
    def save_conversation_summary(self, restoration_log):
        """保存对话摘要"""
        summary = {
            "test_info": {
                "timestamp": datetime.now().isoformat(),
                "total_turns": self.current_turn,
                "output_directory": self.output_dir
            },
            "restoration_log": restoration_log,
            "conversation_history": []
        }
        
        for entry in self.conversation_history:
            summary_entry = {
                "turn": entry['turn'],
                "think_content": entry['parsed_output'].get('think'),
                "tool_name": entry['tool_name'],
                "tool_arguments": entry['tool_args'],
                "tool_message": entry['tool_result']['tool_message'],
                "image_path": entry['tool_result']['image_path']
            }
            summary["conversation_history"].append(summary_entry)
        
        # 保存JSON摘要
        summary_path = os.path.join(self.output_dir, "conversation_summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # 保存Markdown报告
        self.save_markdown_report(summary)
        
        print(f"📄 对话摘要保存: {summary_path}")
    
    def save_markdown_report(self, summary):
        """保存Markdown格式的报告"""
        report_path = os.path.join(self.output_dir, "conversation_report.md")
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# 图像修复对话测试报告\n\n")
            f.write(f"**测试时间**: {summary['test_info']['timestamp']}\n")
            f.write(f"**总轮次**: {summary['test_info']['total_turns']}\n")
            f.write(f"**最终修复日志**: {summary['restoration_log']}\n\n")
            
            f.write("## 原始图片\n")
            f.write("![原始图片](original_image.png)\n\n")
            
            f.write("## 对话过程\n\n")
            
            for entry in summary["conversation_history"]:
                f.write(f"### 轮次 {entry['turn']}\n\n")
                f.write(f"**思考过程**: {entry['think_content']}\n\n")
                f.write(f"**工具调用**: `{entry['tool_name']}`\n")
                f.write(f"**参数**: `{entry['tool_arguments']}`\n\n")
                f.write(f"**工具回复**: {entry['tool_message']}\n\n")
                
                # 获取图片文件名
                image_name = os.path.basename(entry['image_path'])
                f.write(f"**处理后图片**:\n")
                f.write(f"![轮次{entry['turn']}结果]({image_name})\n\n")
                f.write("---\n\n")
            
            f.write("## 总结\n\n")
            f.write("本次测试成功模拟了完整的图像修复对话流程，包括：\n")
            f.write("1. 模型推理和输出解析\n")
            f.write("2. 工具调用和执行\n")
            f.write("3. 图像处理和保存\n")
            f.write("4. 对话历史记录\n\n")
            f.write(f"所有结果文件保存在: `{self.output_dir}/`\n")
        
        print(f"📋 Markdown报告保存: {report_path}")
    
    def create_comparison_plot(self):
        """创建前后对比图"""
        fig, axes = plt.subplots(1, 2, figsize=(12, 6))
        
        axes[0].imshow(self.original_image)
        axes[0].set_title("原始图片")
        axes[0].axis('off')
        
        axes[1].imshow(self.current_image)
        axes[1].set_title("最终修复结果")
        axes[1].axis('off')
        
        plt.tight_layout()
        comparison_path = os.path.join(self.output_dir, "before_after_comparison.png")
        plt.savefig(comparison_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"📊 对比图保存: {comparison_path}")


def main():
    """主函数"""
    print("🎯 图像修复对话格式测试")
    print("模拟完整的rollout对话过程")
    print("=" * 60)
    
    # 创建测试器实例
    tester = ConversationTester()
    
    try:
        # 运行对话测试
        tester.run_conversation_test()
        
        # 创建对比图
        tester.create_comparison_plot()
        
        print("\n✨ 测试完成！")
        print(f"📁 查看结果: {tester.output_dir}")
        print("📋 详细报告: conversation_report.md")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
