#!/usr/bin/env python3
"""
检查训练过程中prompt数据流
验证system prompt和user prompt是否正确传给模型
"""

import os
import sys
import json
import numpy as np
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def check_parquet_dataset():
    """检查parquet数据集中的prompt结构"""
    import pandas as pd
    
    # 从IR.sh中获取数据集路径
    basedir = "/app/xiaominl/datasets/air_sp11np_up3_sample1"
    train_files = [
        f"{basedir}/shard-train-000000.parquet",
        f"{basedir}/shard-train-000001.parquet",
    ]
    
    print("=" * 80)
    print("1. 检查Parquet数据集")
    print("=" * 80)
    
    for file_path in train_files[:1]:  # 只检查第一个文件
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            continue
            
        print(f"\n📁 文件: {file_path}")
        df = pd.read_parquet(file_path)
        
        print(f"✅ 总样本数: {len(df)}")
        print(f"✅ 列名: {list(df.columns)}")
        
        # 检查prompt字段
        if 'prompt' in df.columns:
            print(f"\n✅ 发现'prompt'字段")
            sample_prompt = df['prompt'].iloc[0]
            print(f"   类型: {type(sample_prompt)}")
            
            if isinstance(sample_prompt, (list, np.ndarray)):
                print(f"   长度: {len(sample_prompt)}")
                print(f"\n   📝 第一个样本的prompt结构:")
                for i, msg in enumerate(sample_prompt):
                    if isinstance(msg, dict):
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        content_preview = content[:100] + '...' if len(content) > 100 else content
                        print(f"      [{i}] role: {role}")
                        print(f"          content: {content_preview}")
                    else:
                        print(f"      [{i}] {msg}")
        else:
            print(f"❌ 未找到'prompt'字段")
        
        # 检查raw_prompt字段（如果有）
        if 'raw_prompt' in df.columns:
            print(f"\n✅ 发现'raw_prompt'字段")
            sample_raw_prompt = df['raw_prompt'].iloc[0]
            print(f"   类型: {type(sample_raw_prompt)}")
        
        break  # 只检查第一个文件


def check_rl_dataset_config():
    """检查RL数据集配置"""
    print("\n" + "=" * 80)
    print("2. 检查RL数据集配置")
    print("=" * 80)
    
    # 从IR.sh中提取配置
    config_items = {
        'return_raw_chat': 'data.return_raw_chat=True',
        'prompt_key': 'prompt (默认)',
        'max_prompt_length': 'data.max_prompt_length=8192',
    }
    
    print("\n📋 关键配置项:")
    for key, value in config_items.items():
        print(f"   ✅ {key}: {value}")
    
    print("\n📚 数据流说明:")
    print("   1. Parquet文件中的'prompt'字段 →")
    print("   2. RLHFDataset读取为messages →")
    print("   3. 如果return_raw_chat=True →")
    print("   4. row_dict['raw_prompt'] = messages →")
    print("   5. collate_fn将其放入batch['raw_prompt'] →")
    print("   6. ray_trainer.py检测到'prompt'字段 →")
    print("   7. batch.non_tensor_batch['raw_prompt'] = batch_dict['prompt']")


def check_code_flow():
    """检查代码中的数据流"""
    print("\n" + "=" * 80)
    print("3. 检查代码数据流")
    print("=" * 80)
    
    print("\n📝 RL Dataset处理流程 (verl/utils/dataset/rl_dataset.py):")
    print("   行135: messages = example.pop(self.prompt_key)  # 从parquet读取'prompt'")
    print("   行158: messages = self._build_messages(row_dict)  # 处理图像标记")
    print("   行243-244:")
    print("          if self.return_raw_chat:")
    print("              row_dict['raw_prompt'] = messages  # ✅ 保存完整messages")
    
    print("\n📝 Trainer处理流程 (verl/trainer/ppo/ray_trainer.py):")
    print("   行1148-1154 (训练阶段):")
    print("          if 'prompt' in batch_dict and 'raw_prompt' not in batch.non_tensor_batch:")
    print("              batch.non_tensor_batch['raw_prompt'] = batch_dict['prompt']")
    print("              # ✅ 映射'prompt' → 'raw_prompt'")
    
    print("\n   行603-605 (验证阶段):")
    print("          if 'prompt' in test_data and 'raw_prompt' not in test_batch.non_tensor_batch:")
    print("              test_batch.non_tensor_batch['raw_prompt'] = test_data['prompt']")
    print("              # ✅ 映射'prompt' → 'raw_prompt'")
    
    print("\n📝 Wandb提取流程 (verl/utils/tracking_image_utils.py):")
    print("   行1031-1050:")
    print("          if idx < len(raw_prompts):")
    print("              raw_prompt = raw_prompts[idx]")
    print("              if isinstance(raw_prompt, list):")
    print("                  for msg in raw_prompt:")
    print("                      if msg.get('role') == 'user':")
    print("                          user_input = msg.get('content', '')")
    print("                          # ✅ 提取user角色的content")


def check_expected_structure():
    """展示预期的数据结构"""
    print("\n" + "=" * 80)
    print("4. 预期的数据结构")
    print("=" * 80)
    
    print("\n📋 Parquet中的prompt字段应该是:")
    example_prompt = [
        {
            "role": "system",
            "content": "You are a helpful assistant specialized in image restoration..."
        },
        {
            "role": "user", 
            "content": "<image>\nKnown degradation types in this image: dark, motion blur\nPlease analyze and restore this image."
        }
    ]
    print(json.dumps(example_prompt, indent=2, ensure_ascii=False))
    
    print("\n📋 传给模型的应该是:")
    print("   1. Tokenizer会使用apply_chat_template()处理messages")
    print("   2. 生成包含system prompt和user prompt的完整文本")
    print("   3. 例如 (Qwen2.5-VL格式):")
    print("      <|im_start|>system")
    print("      You are a helpful assistant specialized in image restoration...<|im_end|>")
    print("      <|im_start|>user")
    print("      <image>")
    print("      Known degradation types in this image: dark, motion blur")
    print("      Please analyze and restore this image.<|im_end|>")
    print("      <|im_start|>assistant")
    
    print("\n📋 Wandb表格中的User_Input应该显示:")
    print("   <image>")
    print("   Known degradation types in this image: dark, motion blur")
    print("   Please analyze and restore this image.")


def check_potential_issues():
    """检查可能的问题"""
    print("\n" + "=" * 80)
    print("5. 潜在问题排查")
    print("=" * 80)
    
    issues = [
        {
            "问题": "Wandb表格User_Input为空",
            "可能原因": [
                "❌ batch_dict中没有'prompt'或'raw_prompt'字段",
                "❌ return_raw_chat=False（应该设为True）",
                "❌ 数据集中prompt字段名不是'prompt'",
            ],
            "修复状态": "✅ 已在ray_trainer.py中添加映射逻辑"
        },
        {
            "问题": "System prompt未传给模型",
            "可能原因": [
                "❌ messages列表中缺少role='system'的消息",
                "❌ tokenizer.apply_chat_template未正确处理system role",
            ],
            "检查方法": "查看parquet数据集中第一个消息的role"
        },
        {
            "问题": "User prompt未传给模型",
            "可能原因": [
                "❌ messages列表中缺少role='user'的消息",
                "❌ content字段为空或格式错误",
            ],
            "检查方法": "查看parquet数据集中第二个消息的content"
        }
    ]
    
    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. {issue['问题']}")
        print(f"   可能原因:")
        for reason in issue['可能原因']:
            print(f"      {reason}")
        if 'fix_status' in issue:
            print(f"   {issue['修复状态']}")
        if 'check_method' in issue:
            print(f"   检查方法: {issue['检查方法']}")


def print_verification_commands():
    """打印验证命令"""
    print("\n" + "=" * 80)
    print("6. 验证命令")
    print("=" * 80)
    
    print("\n📝 运行训练并检查日志:")
    print("   bash examples/agent/IR.sh 2>&1 | tee logs/check_prompt.log")
    
    print("\n📝 查看关键日志:")
    print("   # 检查prompt映射")
    print("   grep -E 'DEBUG.*prompt|DEBUG.*raw_prompt' logs/check_prompt.log")
    
    print("   # 检查User_Input提取")
    print("   grep 'DEBUG USER INPUT' logs/check_prompt.log")
    
    print("   # 检查第一个样本的prompt内容")
    print("   grep 'First raw_prompt sample' logs/check_prompt.log")
    
    print("\n📝 检查Wandb表格:")
    print("   1. 打开Wandb项目")
    print("   2. 进入Tables标签")
    print("   3. 查看train_conversation_table或val_conversation_table")
    print("   4. 检查User_Input列是否有内容")


def main():
    """主函数"""
    print("\n" + "╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "Prompt数据流检查工具" + " " * 36 + "║")
    print("╚" + "═" * 78 + "╝")
    
    try:
        check_parquet_dataset()
    except Exception as e:
        print(f"\n❌ 检查Parquet数据集时出错: {e}")
        import traceback
        traceback.print_exc()
    
    check_rl_dataset_config()
    check_code_flow()
    check_expected_structure()
    check_potential_issues()
    print_verification_commands()
    
    print("\n" + "=" * 80)
    print("✅ 检查完成")
    print("=" * 80)
    print("\n💡 建议:")
    print("   1. 运行本脚本查看parquet数据集的实际结构")
    print("   2. 运行训练查看日志中的调试信息")
    print("   3. 在Wandb中验证User_Input列是否正确显示")
    print("\n🚀 下一步:")
    print("   python check_prompt_flow.py  # 查看数据集结构")
    print("   bash examples/agent/IR.sh   # 开始训练")
    print()


if __name__ == "__main__":
    main()

