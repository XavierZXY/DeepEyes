#!/usr/bin/env python3
"""
Agent推理评估脚本 - 基于训练脚本的推理版本
"""

import os
import sys
import json
import torch
import pandas as pd
import numpy as np
from PIL import Image
from pathlib import Path
from datetime import datetime
import io

# 添加项目路径
sys.path.append('/app/xiaominl/DeepEyes')

def create_inference_config(model_path: str, data_file: str, output_dir: str):
    """创建推理配置文件"""
    
    config_content = f"""# Agent推理评估配置
# 基于训练配置修改

defaults:
  - _self_

debug: false
vs_debug: false

data:
  train_files: []  # 推理时不需要
  val_files: ["{data_file}"]
  train_batch_size: 1  # 推理时使用小批次
  val_batch_size: 1
  max_prompt_length: 8192
  max_response_length: 20480
  return_raw_chat: true
  filter_overlong_prompts: true

algorithm:
  adv_estimator: grpo
  kl_ctrl:
    kl_coef: 0.0

actor_rollout_ref:
  model:
    path: "{model_path}"
    use_remove_padding: true
  
  rollout:
    name: vllm
    tensor_model_parallel_size: 1
    log_prob_micro_batch_size_per_gpu: 1
    
    agent:
      activate_agent: true
      tool_name_key: env_name
      single_response_max_tokens: 10240
      max_turns: 6
      concurrent_workers: 1
      show_tqdm: true
      custom_stop: []

trainer:
  test_freq: 1  # 每次都验证
  val_before_train: true
  val_only: true  # 只进行验证，不训练
  logger: ['console']
  project_name: "agent_eval"
  experiment_name: "inference_test"
"""
    
    config_path = Path(output_dir) / "inference_config.yaml"
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    print(f"📝 创建推理配置: {config_path}")
    return config_path

def create_inference_script(model_path: str, data_file: str, output_dir: str, num_samples: int = 3):
    """创建推理脚本"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    full_output_dir = f"{output_dir}/inference_{timestamp}"
    Path(full_output_dir).mkdir(parents=True, exist_ok=True)
    
    # 创建配置文件
    config_path = create_inference_config(model_path, data_file, full_output_dir)
    
    # 创建推理脚本
    script_content = f'''#!/bin/bash
# Agent推理脚本

set -e

export PYTHONPATH=/app/xiaominl/DeepEyes:$PYTHONPATH
export CUDA_VISIBLE_DEVICES=0

# 参数
MODEL_PATH="{model_path}"
DATA_FILE="{data_file}"
OUTPUT_DIR="{full_output_dir}"
CONFIG_FILE="{config_path}"

echo "🎯 Agent推理评估"
echo "🤖 模型: $MODEL_PATH"
echo "📁 数据: $DATA_FILE"
echo "📁 输出: $OUTPUT_DIR"
echo "⚙️  配置: $CONFIG_FILE"

# 修改数据文件为只包含前几个样本
echo "📊 准备测试数据..."
python3 -c "
import pandas as pd
df = pd.read_parquet('$DATA_FILE')
test_df = df.head({num_samples})
test_file = '$OUTPUT_DIR/test_data.parquet'
test_df.to_parquet(test_file)
print(f'保存测试数据: {{test_file}}, 样本数: {{len(test_df)}}')
"

# 更新配置文件中的数据路径
sed -i 's|{data_file}|{full_output_dir}/test_data.parquet|g' "$CONFIG_FILE"

# 运行推理
echo "🚀 开始推理..."
cd /app/xiaominl/DeepEyes

PYTHONUNBUFFERED=1 python3 -m verl.trainer.main_ppo \\
    --config-path "$OUTPUT_DIR" \\
    --config-name "inference_config" \\
    2>&1 | tee "$OUTPUT_DIR/inference.log"

echo "✅ 推理完成！"
echo "📁 查看结果: $OUTPUT_DIR"
echo "📝 日志文件: $OUTPUT_DIR/inference.log"
'''
    
    script_path = Path(full_output_dir) / "run_inference.sh"
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    os.chmod(script_path, 0o755)
    
    print(f"📝 创建推理脚本: {script_path}")
    return script_path

def create_image_extraction_hook():
    """创建图像提取钩子脚本"""
    
    hook_content = '''#!/usr/bin/env python3
"""
图像提取钩子 - 在parallel_env.py中添加此代码来保存每一步的图像
"""

# 在parallel_env.py的agent_rollout_loop函数开始处添加：

import os
from pathlib import Path
from datetime import datetime

# 创建图像保存目录
EVAL_OUTPUT_DIR = os.environ.get('AGENT_EVAL_OUTPUT_DIR', 'agent_eval_images')
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
IMAGE_SAVE_DIR = Path(EVAL_OUTPUT_DIR) / f"inference_{timestamp}"
IMAGE_SAVE_DIR.mkdir(parents=True, exist_ok=True)

print(f"🖼️  图像将保存到: {IMAGE_SAVE_DIR}")

# 在agent_rollout_loop的主循环中，在调用env.step前添加：
def save_current_images(step, active_indices, vllm_input_list):
    """保存当前轮次的图像"""
    for local_idx, global_idx in enumerate(active_indices):
        if global_idx < len(vllm_input_list):
            vllm_input = vllm_input_list[global_idx]
            if 'multi_modal_data' in vllm_input and 'image' in vllm_input['multi_modal_data']:
                images = vllm_input['multi_modal_data']['image']
                
                sample_dir = IMAGE_SAVE_DIR / f"sample_{global_idx:02d}"
                step_dir = sample_dir / f"step_{step+1:02d}"
                step_dir.mkdir(parents=True, exist_ok=True)
                
                for img_idx, img in enumerate(images):
                    if hasattr(img, 'save'):  # PIL图像
                        img_path = step_dir / f"image_{img_idx:02d}.png"
                        img.save(img_path)
                        print(f"💾 保存: step_{step+1:02d}/image_{img_idx:02d}.png")

# 使用方法：
# 1. 设置环境变量: export AGENT_EVAL_OUTPUT_DIR="your_output_dir"
# 2. 在parallel_env.py中添加上述代码
# 3. 运行推理脚本
'''
    
    hook_file = Path("image_extraction_hook.py")
    with open(hook_file, 'w') as f:
        f.write(hook_content)
    
    print(f"📝 创建图像提取钩子: {hook_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent推理评估")
    parser.add_argument("--model_path", help="训练好的模型路径")
    parser.add_argument("--data_file", default="/app/datasets/IRdataset/shard-000003.parquet", help="测试数据文件")
    parser.add_argument("--output_dir", default="agent_inference_results", help="输出目录")
    parser.add_argument("--num_samples", type=int, default=3, help="评估样本数量")
    parser.add_argument("--create_only", action="store_true", help="只创建脚本，不运行推理")
    
    args = parser.parse_args()
    
    print(f"🎯 Agent推理评估工具")
    
    if args.create_only or not args.model_path:
        # 只创建脚本和钩子
        print(f"📝 创建评估工具...")
        create_image_extraction_hook()
        
        if args.model_path:
            script_path = create_inference_script(
                model_path=args.model_path,
                data_file=args.data_file,
                output_dir=args.output_dir,
                num_samples=args.num_samples
            )
            print(f"✅ 推理脚本已创建: {script_path}")
            print(f"💡 运行: bash {script_path}")
        else:
            print(f"💡 指定 --model_path 来创建完整的推理脚本")
    else:
        # 运行完整评估
        print(f"🚀 运行完整评估...")
        script_path = create_inference_script(
            model_path=args.model_path,
            data_file=args.data_file,
            output_dir=args.output_dir,
            num_samples=args.num_samples
        )
        
        print(f"📝 推理脚本: {script_path}")
        print(f"💡 手动运行: bash {script_path}")
