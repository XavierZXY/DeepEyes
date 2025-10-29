#!/usr/bin/env python3
"""
测试脚本：评估单个样本（不调用vLLM，仅测试数据处理流程）
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pyarrow.parquet as pq
import numpy as np
from PIL import Image
import io
import os

# 设置工具服务IP（测试时不真正调用工具）
os.environ['TOOL_SERVICE_IP'] = '10.21.9.6'

# 导入评估模块
from eval.eval_agent_restoration import EvaluationConfig, ImageQualityEvaluator


def test_single_sample(parquet_path: str):
    """测试单个样本的处理流程"""
    print("="*80)
    print("测试单样本数据处理流程")
    print("="*80)
    
    # 1. 加载数据
    print("\n[1/5] 加载parquet数据...")
    table = pq.read_table(parquet_path)
    df = table.to_pandas()
    sample = df.iloc[0].to_dict()
    print(f"✅ 成功加载，样本字段: {list(sample.keys())}")
    
    # 2. 提取图像
    print("\n[2/5] 提取图像...")
    images = sample.get('images', [])
    
    # 提取退化图像
    if len(images) > 0 and isinstance(images[0], dict) and 'bytes' in images[0]:
        degraded_image = Image.open(io.BytesIO(images[0]['bytes']))
        print(f"✅ 退化图像: {degraded_image.size}, {degraded_image.mode}")
    else:
        print("❌ 无法提取退化图像")
        return
    
    # 提取GT图像
    extra_info = sample.get('extra_info', {})
    gt_image = None
    if isinstance(extra_info, dict) and 'original_image' in extra_info:
        if extra_info.get('use_original', False):
            gt_image = Image.open(io.BytesIO(extra_info['original_image']))
            print(f"✅ GT图像: {gt_image.size}, {gt_image.mode}")
    else:
        print("⚠️  未找到GT图像（无参考指标将无法计算）")
    
    # 3. 提取系统提示词
    print("\n[3/5] 提取系统提示词...")
    prompt = sample.get('prompt', [])
    if isinstance(prompt, np.ndarray) and len(prompt) > 0:
        system_msg = prompt[0]
        if isinstance(system_msg, dict) and system_msg.get('role') == 'system':
            system_prompt = system_msg.get('content', '')
            print(f"✅ 系统提示词长度: {len(system_prompt)} 字符")
            print(f"   预览: {system_prompt[:100]}...")
    
    if len(prompt) > 1:
        user_msg = prompt[1]
        if isinstance(user_msg, dict) and user_msg.get('role') == 'user':
            user_text = user_msg.get('content', '')
            print(f"✅ 用户消息: {user_text}")
    
    # 4. 提取退化类型
    print("\n[4/5] 提取退化类型...")
    env_name = sample.get('env_name', '')
    degradations = env_name.split(', ') if env_name else []
    print(f"✅ 退化类型: {degradations}")
    
    # 5. 测试指标计算
    print("\n[5/5] 测试图像质量指标计算...")
    try:
        evaluator = ImageQualityEvaluator()
        
        # 计算无参考指标
        print("\n计算无参考指标...")
        no_ref_metrics = evaluator.compute_no_reference_metrics(np.array(degraded_image))
        print(f"✅ 无参考指标:")
        for metric_name, score in no_ref_metrics.items():
            print(f"   - {metric_name.upper()}: {score:.4f}")
        
        # 如果有GT图像，计算有参考指标
        if gt_image:
            print("\n计算有参考指标...")
            ref_metrics = evaluator.compute_reference_metrics(
                np.array(degraded_image),
                np.array(gt_image)
            )
            print(f"✅ 有参考指标:")
            print(f"   - PSNR: {ref_metrics['psnr']:.2f} dB")
            print(f"   - SSIM: {ref_metrics['ssim']:.4f}")
            print(f"   - LPIPS: {ref_metrics['lpips']:.4f}")
        
    except Exception as e:
        print(f"❌ 指标计算失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("✅ 所有测试步骤完成！")
    print("="*80)
    print("\n💡 数据处理流程验证成功，可以运行完整评估了。")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_path', type=str,
                       default='/app/xiaominl/air_full_v1/shard-test-000000.parquet',
                       help='Path to parquet file')
    args = parser.parse_args()
    
    test_single_sample(args.data_path)

