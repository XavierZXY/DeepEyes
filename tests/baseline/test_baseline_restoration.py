#!/usr/bin/env python3
"""
Baseline测试脚本：对退化图像应用工具进行修复

支持两种修复策略：
1. 随机修复：随机选择工具顺序
2. 逆序修复：按照reward_model中的逆序应用工具

计算指标：
- 原图与退化图的 PSNR、SSIM、LPIPS
- 原图与修复图的 PSNR、SSIM、LPIPS
"""

import os
import sys
import json
import random
import argparse
import numpy as np
import pandas as pd
from PIL import Image
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
import io

# 添加项目路径
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

# 导入工具类
from verl.workers.agent.envs.mm_process_engine.SwinIRToolbox import (
    SwinIRDenoisingToolbox,
    SwinIRJpegArtifactRemovalToolbox,
    SwinIRSrToolbox
)
from verl.workers.agent.envs.mm_process_engine.RestormerToolbox import (
    RestormerMotionDeblurringToolbox,
    RestormerDefocusDeblurringToolbox,
    RestormerDerrainingToolbox
)
from verl.workers.agent.envs.mm_process_engine.MPRNetToolbox import (
    MPRNetDenoisingToolbox,
    MPRNetDeraininingToolbox,
    MPRNetMotionDeblurringToolbox
)
from verl.workers.agent.envs.mm_process_engine.DeblurToolbox import DeblurToolbox
from verl.workers.agent.envs.mm_process_engine.DehazeFormerToolbox import DehazeFormerToolbox
from verl.workers.agent.envs.mm_process_engine.BrighteningToolbox import (
    GammaCorrectionTool,
    ConstantShiftTool,
    HistogramEqualizationTool
)
from verl.workers.agent.envs.mm_process_engine.NeRDToolbox import NeRDDerainingToolbox
from verl.workers.agent.envs.mm_process_engine.FBCNNToolbox import FBCNNJpegArtifactRemovalToolbox
from verl.workers.agent.envs.mm_process_engine.SCUNetToolbox import SCUNetRealDenoisingPSNRToolbox,SCUNetRealDenoisingGANToolbox,SCUNetColorDenoisingToolbox
from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerLOLv1Toolbox, RetinexformerLOLv2RealToolbox, RetinexformerLOLv2SyntheticToolbox,RetinexformerSDSDIndoorToolbox,RetinexformerFiveKToolbox
from verl.workers.agent.envs.mm_process_engine.HATToolbox import HATSuperResolutionToolbox
# ==================== 退化类型到工具的映射 ====================
DEGRADATION_TO_TOOLS = {
    'motion blur': [
        ('RestormerMotionDeblurringToolbox', RestormerMotionDeblurringToolbox, {}),
        # ('MPRNetMotionDeblurringToolbox', MPRNetMotionDeblurringToolbox, {}),
    ],
    'defocus blur': [
        ('RestormerDefocusDeblurringToolbox', RestormerDefocusDeblurringToolbox, {}),
        # ('DeblurToolbox', DeblurToolbox, {}),
    ],
    'jpeg compression artifact': [
        # ('SwinIRJpegArtifactRemovalToolbox', SwinIRJpegArtifactRemovalToolbox, {'quality_factor': 10}),
        ('FBCNNJpegArtifactRemovalToolbox', FBCNNJpegArtifactRemovalToolbox, {'quality_factor': 10}),
    ],
    'noise': [
        # ('SwinIRDenoisingToolbox', SwinIRDenoisingToolbox, {'noise_level': 25}),
        # ('MPRNetDenoisingToolbox', MPRNetDenoisingToolbox, {}),
        ('SCUNetRealDenoisingGANToolbox', SCUNetRealDenoisingGANToolbox, {}),
    ],
    'rain': [
        # ('RestormerDerrainingToolbox', RestormerDerrainingToolbox, {}),
        ('NeRDDerainingToolbox', NeRDDerainingToolbox, {}),
        # ('MPRNetDeraininingToolbox', MPRNetDeraininingToolbox, {}),
    ],
    'low resolution': [
        # ('SwinIRSrToolbox', SwinIRSrToolbox, {'scale': 2}),
        ('HATSuperResolutionToolbox', HATSuperResolutionToolbox, {'scale': 4}),
    ],
    'dark': [
        # ('GammaCorrectionTool', GammaCorrectionTool, {'gamma': 0.6}),
        ('RetinexformerFiveKToolbox', RetinexformerFiveKToolbox, {}),
        # ('ConstantShiftTool', ConstantShiftTool, {'shift': 50}),
        # ('HistogramEqualizationTool', HistogramEqualizationTool, {'clipLimit': 3.0}),
    ],
    'haze': [
        ('DehazeFormerToolbox', DehazeFormerToolbox, {}),
    ],
}


# ==================== 图像质量评估 ====================
def calculate_psnr(img1: Image.Image, img2: Image.Image) -> float:
    """计算PSNR"""
    try:
        import cv2
        arr1 = np.array(img1)
        arr2 = np.array(img2)
        
        # 确保尺寸一致
        if arr1.shape != arr2.shape:
            # 调整大小到较小的尺寸
            h = min(arr1.shape[0], arr2.shape[0])
            w = min(arr1.shape[1], arr2.shape[1])
            arr1 = cv2.resize(arr1, (w, h))
            arr2 = cv2.resize(arr2, (w, h))
        
        mse = np.mean((arr1.astype(float) - arr2.astype(float)) ** 2)
        if mse == 0:
            return 100.0
        return 10 * np.log10(255.0 ** 2 / mse)
    except Exception as e:
        print(f"[WARNING] PSNR calculation failed: {e}")
        return 0.0


def calculate_ssim(img1: Image.Image, img2: Image.Image) -> float:
    """计算SSIM"""
    try:
        from skimage.metrics import structural_similarity as ssim
        import cv2
        
        arr1 = np.array(img1)
        arr2 = np.array(img2)
        
        # 确保尺寸一致
        if arr1.shape != arr2.shape:
            h = min(arr1.shape[0], arr2.shape[0])
            w = min(arr1.shape[1], arr2.shape[1])
            arr1 = cv2.resize(arr1, (w, h))
            arr2 = cv2.resize(arr2, (w, h))
        
        # 转换为灰度图
        if len(arr1.shape) == 3:
            arr1_gray = cv2.cvtColor(arr1, cv2.COLOR_RGB2GRAY)
            arr2_gray = cv2.cvtColor(arr2, cv2.COLOR_RGB2GRAY)
        else:
            arr1_gray = arr1
            arr2_gray = arr2
        
        return ssim(arr1_gray, arr2_gray)
    except Exception as e:
        print(f"[WARNING] SSIM calculation failed: {e}")
        return 0.0


def calculate_lpips(img1: Image.Image, img2: Image.Image) -> float:
    """计算LPIPS"""
    try:
        import torch
        import lpips
        
        # 初始化LPIPS模型（只初始化一次）
        if not hasattr(calculate_lpips, 'loss_fn'):
            calculate_lpips.loss_fn = lpips.LPIPS(net='alex').cuda() if torch.cuda.is_available() else lpips.LPIPS(net='alex')
        
        # 转换图像
        def img_to_tensor(img):
            arr = np.array(img).astype(np.float32) / 255.0
            if len(arr.shape) == 2:
                arr = np.stack([arr, arr, arr], axis=2)
            tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
            return tensor * 2.0 - 1.0  # 归一化到[-1, 1]
        
        import cv2
        arr1 = np.array(img1)
        arr2 = np.array(img2)
        
        # 确保尺寸一致
        if arr1.shape != arr2.shape:
            h = min(arr1.shape[0], arr2.shape[0])
            w = min(arr1.shape[1], arr2.shape[1])
            img1 = Image.fromarray(cv2.resize(arr1, (w, h)))
            img2 = Image.fromarray(cv2.resize(arr2, (w, h)))
        
        tensor1 = img_to_tensor(img1)
        tensor2 = img_to_tensor(img2)
        
        if torch.cuda.is_available():
            tensor1 = tensor1.cuda()
            tensor2 = tensor2.cuda()
        
        with torch.no_grad():
            distance = calculate_lpips.loss_fn(tensor1, tensor2)
        
        return distance.item()
    except Exception as e:
        print(f"[WARNING] LPIPS calculation failed: {e}")
        return 1.0


def calculate_all_metrics(img1: Image.Image, img2: Image.Image) -> Dict[str, float]:
    """计算所有指标"""
    return {
        'psnr': calculate_psnr(img1, img2),
        'ssim': calculate_ssim(img1, img2),
        'lpips': calculate_lpips(img1, img2)
    }


# ==================== 工具调用相关 ====================
def get_tool_for_degradation(degradation_type: str, degradation_level: str = None) -> Tuple[str, Any, Dict]:
    """根据退化类型获取工具"""
    if degradation_type not in DEGRADATION_TO_TOOLS:
        print(f"[WARNING] Unknown degradation type: {degradation_type}")
        return None, None, {}
    
    tools = DEGRADATION_TO_TOOLS[degradation_type]
    # 随机选择一个工具
    tool_name, tool_class, default_args = random.choice(tools)
    return tool_name, tool_class, default_args


def apply_tool(tool_class, tool_args: Dict, image: Image.Image) -> Tuple[Image.Image, bool, str]:
    """
    应用工具到图像
    
    Returns:
        (processed_image, success, error_message)
    """
    try:
        # 创建工具实例
        tool = tool_class(_name="", _desc="", _params={})
        
        # 设置multi_modal_data
        tool.multi_modal_data = {'image': [image]}
        
        # 构建工具调用的action_string
        # 根据工具类型构建合适的参数
        action_dict = {
            "name": tool.name,
            "arguments": tool_args
        }
        action_string = f"<tool_call>{json.dumps(action_dict)}</tool_call>"
        
        print(f"  [TOOL] Applying {tool.name} with args: {tool_args}")
        
        # 执行工具
        obs, reward, done, info = tool.execute(action_string)
        
        # 获取处理后的图像
        if tool.multi_modal_data and 'image' in tool.multi_modal_data and len(tool.multi_modal_data['image']) > 0:
            processed_image = tool.multi_modal_data['image'][0]
            return processed_image, True, ""
        else:
            return image, False, "No processed image returned"
    
    except Exception as e:
        error_msg = f"Tool execution failed: {str(e)}"
        print(f"  [ERROR] {error_msg}")
        return image, False, error_msg


# ==================== 修复策略 ====================
def random_restoration(image: Image.Image, reward_model: List[Dict], sample_idx: int = None) -> Tuple[Image.Image, List[Dict]]:
    """
    随机修复策略：随机打乱退化类型顺序，然后依次应用工具
    
    Args:
        image: 输入图像
        reward_model: 退化模型信息
        sample_idx: 样本索引（用于增加随机性，但每个样本有独立的随机序列）
    
    Returns:
        (restored_image, restoration_log)
    """
    print("\n[STRATEGY] Random Restoration")
    
    # 提取所有退化类型
    degradations = []
    for item in reward_model:
        degradations.append({
            'type': item['degradation_type'],
            'level': item.get('degradation_level', 'unknown')
        })
    
    # 使用样本索引创建可重复但独立的随机序列
    # 这样：1) 相同样本总是得到相同的随机顺序（可重复）
    #       2) 不同样本得到不同的随机顺序（真随机）
    if sample_idx is not None:
        # 为这个特定样本创建独立的随机生成器
        # 使用哈希来避免某些seed值总是产生逆序
        import hashlib
        seed_str = f"random_restoration_{sample_idx}_{len(degradations)}"
        seed_value = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        sample_random = random.Random(seed_value)
        sample_random.shuffle(degradations)
    else:
        # 如果没有sample_idx，使用全局随机状态
        random.shuffle(degradations)
    
    print(f"  [ORDER] Randomized order: {[d['type'] for d in degradations]}")
    
    # 显示原始顺序用于对比
    original_order = [item['degradation_type'] for item in reward_model]
    is_reversed = ([d['type'] for d in degradations] == list(reversed(original_order)))
    is_original = ([d['type'] for d in degradations] == original_order)
    
    if is_reversed:
        print(f"  [INFO] ⚠️  恰好是逆序（这是随机结果，不是bug）")
    elif is_original:
        print(f"  [INFO] 保持了原序（这是随机结果）")
    else:
        print(f"  [INFO] 不同于原序和逆序（真随机）")
    
    print(f"  [COMPARE] Original order was: {original_order}")
    
    # 依次应用工具
    current_image = image
    restoration_log = []
    
    for i, deg in enumerate(degradations):
        tool_name, tool_class, tool_args = get_tool_for_degradation(deg['type'], deg['level'])
        
        if tool_class is None:
            print(f"  [SKIP] Step {i+1}: No tool for {deg['type']}")
            restoration_log.append({
                'step': i + 1,
                'degradation': deg['type'],
                'tool': None,
                'success': False,
                'error': 'No tool available'
            })
            continue
        
        print(f"  [STEP {i+1}] Applying {tool_name} for {deg['type']}")
        processed_image, success, error_msg = apply_tool(tool_class, tool_args, current_image)
        
        restoration_log.append({
            'step': i + 1,
            'degradation': deg['type'],
            'level': deg['level'],
            'tool': tool_name,
            'tool_args': tool_args,
            'success': success,
            'error': error_msg if not success else None
        })
        
        if success:
            current_image = processed_image
            print(f"  [SUCCESS] Step {i+1} completed")
        else:
            print(f"  [FAILED] Step {i+1}: {error_msg}")
    
    return current_image, restoration_log


def reverse_restoration(image: Image.Image, reward_model: List[Dict]) -> Tuple[Image.Image, List[Dict]]:
    """
    逆序修复策略：按照reward_model中的逆序应用工具
    
    Returns:
        (restored_image, restoration_log)
    """
    print("\n[STRATEGY] Reverse Restoration")
    
    # 提取所有退化类型并逆序
    degradations = []
    for item in reward_model:
        degradations.append({
            'type': item['degradation_type'],
            'level': item.get('degradation_level', 'unknown')
        })
    
    degradations.reverse()
    print(f"  [ORDER] Reversed order: {[d['type'] for d in degradations]}")
    
    # 依次应用工具
    current_image = image
    restoration_log = []
    
    for i, deg in enumerate(degradations):
        tool_name, tool_class, tool_args = get_tool_for_degradation(deg['type'], deg['level'])
        
        if tool_class is None:
            print(f"  [SKIP] Step {i+1}: No tool for {deg['type']}")
            restoration_log.append({
                'step': i + 1,
                'degradation': deg['type'],
                'tool': None,
                'success': False,
                'error': 'No tool available'
            })
            continue
        
        print(f"  [STEP {i+1}] Applying {tool_name} for {deg['type']}")
        processed_image, success, error_msg = apply_tool(tool_class, tool_args, current_image)
        
        restoration_log.append({
            'step': i + 1,
            'degradation': deg['type'],
            'level': deg['level'],
            'tool': tool_name,
            'tool_args': tool_args,
            'success': success,
            'error': error_msg if not success else None
        })
        
        if success:
            current_image = processed_image
            print(f"  [SUCCESS] Step {i+1} completed")
        else:
            print(f"  [FAILED] Step {i+1}: {error_msg}")
    
    return current_image, restoration_log


# ==================== 主测试函数 ====================
def test_single_sample(
    sample_idx: int,
    degraded_image: Image.Image,
    original_image: Image.Image,
    reward_model: List[Dict],
    strategy: str
) -> Dict:
    """测试单个样本"""
    print(f"\n{'='*80}")
    print(f"Processing Sample {sample_idx}")
    print(f"{'='*80}")
    
    # 计算退化图与原图的指标
    print("\n[METRICS] Degraded vs Original:")
    degraded_metrics = calculate_all_metrics(degraded_image, original_image)
    for metric, value in degraded_metrics.items():
        print(f"  {metric.upper()}: {value:.4f}")
    
    # 应用修复策略
    if strategy == 'random':
        restored_image, restoration_log = random_restoration(degraded_image, reward_model, sample_idx=sample_idx)
    elif strategy == 'reverse':
        restored_image, restoration_log = reverse_restoration(degraded_image, reward_model)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    # 计算修复图与原图的指标
    print("\n[METRICS] Restored vs Original:")
    restored_metrics = calculate_all_metrics(restored_image, original_image)
    for metric, value in restored_metrics.items():
        print(f"  {metric.upper()}: {value:.4f}")
    
    # 计算提升
    improvements = {}
    for metric in ['psnr', 'ssim', 'lpips']:
        if metric == 'lpips':
            # LPIPS越小越好
            improvements[metric] = degraded_metrics[metric] - restored_metrics[metric]
        else:
            # PSNR和SSIM越大越好
            improvements[metric] = restored_metrics[metric] - degraded_metrics[metric]
    
    print("\n[IMPROVEMENTS]:")
    for metric, value in improvements.items():
        print(f"  {metric.upper()}: {value:+.4f}")
    
    return {
        'sample_idx': sample_idx,
        'strategy': strategy,
        'degraded_metrics': degraded_metrics,
        'restored_metrics': restored_metrics,
        'improvements': improvements,
        'restoration_log': restoration_log,
        'degradation_types': [item['degradation_type'] for item in reward_model]
    }


def load_image_from_data(image_data) -> Image.Image:
    """从数据中加载图像"""
    if isinstance(image_data, Image.Image):
        return image_data
    elif isinstance(image_data, bytes):
        try:
            return Image.open(io.BytesIO(image_data)).convert('RGB')
        except Exception as e:
            print(f"[ERROR] Failed to load image from bytes: {e}")
            raise
    elif isinstance(image_data, np.ndarray):
        # numpy array - 获取第一个元素
        if len(image_data) > 0:
            return load_image_from_data(image_data[0])
        else:
            raise ValueError("Empty numpy array")
    elif isinstance(image_data, dict):
        if 'bytes' in image_data:
            return Image.open(io.BytesIO(image_data['bytes'])).convert('RGB')
        elif 'image' in image_data:
            return load_image_from_data(image_data['image'])
    elif isinstance(image_data, list) and len(image_data) > 0:
        return load_image_from_data(image_data[0])
    else:
        raise ValueError(f"Unsupported image data type: {type(image_data)}")


def main():
    parser = argparse.ArgumentParser(description='Baseline Restoration Testing')
    parser.add_argument('--data-path', type=str, 
                        default='/app/xiaominl/datasets/air_sp11np_up3_sample1_nosw/shard-test-000000.parquet',
                        help='Path to parquet file')
    parser.add_argument('--strategy', type=str, choices=['random', 'reverse', 'both'], default='both',
                        help='Restoration strategy: random, reverse, or both')
    parser.add_argument('--num-samples', type=int, default=10,
                        help='Number of samples to test')
    parser.add_argument('--output-dir', type=str, 
                        default='/app/xiaominl/DeepEyes_v2/tests/baseline/results',
                        help='Output directory for results')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed')
    parser.add_argument('--save-images', action='store_true',
                        help='Save degraded, restored, and original images')
    
    args = parser.parse_args()
    
    # 设置随机种子
    random.seed(args.seed)
    np.random.seed(args.seed)
    
    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 读取数据
    print(f"\n[INFO] Loading data from {args.data_path}")
    df = pd.read_parquet(args.data_path)
    print(f"[INFO] Total samples: {len(df)}")
    
    # 限制样本数量
    num_samples = min(args.num_samples, len(df))
    print(f"[INFO] Testing {num_samples} samples")
    
    # 测试结果
    all_results = []
    
    strategies = ['random', 'reverse'] if args.strategy == 'both' else [args.strategy]
    
    for strategy in strategies:
        print(f"\n{'#'*80}")
        print(f"# Testing Strategy: {strategy.upper()}")
        print(f"{'#'*80}")
        
        for idx in range(num_samples):
            row = df.iloc[idx]
            
            # 提取数据
            degraded_image_data = row['images']
            extra_info = row['extra_info']
            reward_model = row['reward_model']
            
            # 加载图像
            if isinstance(degraded_image_data, list):
                degraded_image = load_image_from_data(degraded_image_data[0])
            else:
                degraded_image = load_image_from_data(degraded_image_data)
            
            original_image = load_image_from_data(extra_info['original_image'])
            
            # 测试样本
            try:
                result = test_single_sample(
                    sample_idx=idx,
                    degraded_image=degraded_image,
                    original_image=original_image,
                    reward_model=reward_model,
                    strategy=strategy
                )
                all_results.append(result)
                
                # 保存图像（如果需要）
                if args.save_images:
                    sample_dir = output_dir / f"sample_{idx}_{strategy}"
                    sample_dir.mkdir(exist_ok=True)
                    
                    degraded_image.save(sample_dir / "degraded.png")
                    original_image.save(sample_dir / "original.png")
                    # restored_image.save(sample_dir / "restored.png")  # TODO: save from result
            
            except Exception as e:
                print(f"\n[ERROR] Failed to process sample {idx}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    # 保存结果
    results_file = output_dir / f"results_{timestamp}.json"
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[INFO] Results saved to {results_file}")
    
    # 生成统计报告
    print(f"\n{'='*80}")
    print("SUMMARY STATISTICS")
    print(f"{'='*80}")
    
    for strategy in strategies:
        strategy_results = [r for r in all_results if r['strategy'] == strategy]
        
        if not strategy_results:
            continue
        
        print(f"\n{strategy.upper()} Strategy:")
        print(f"  Samples tested: {len(strategy_results)}")
        
        # 计算平均指标
        avg_degraded = {
            'psnr': np.mean([r['degraded_metrics']['psnr'] for r in strategy_results]),
            'ssim': np.mean([r['degraded_metrics']['ssim'] for r in strategy_results]),
            'lpips': np.mean([r['degraded_metrics']['lpips'] for r in strategy_results])
        }
        
        avg_restored = {
            'psnr': np.mean([r['restored_metrics']['psnr'] for r in strategy_results]),
            'ssim': np.mean([r['restored_metrics']['ssim'] for r in strategy_results]),
            'lpips': np.mean([r['restored_metrics']['lpips'] for r in strategy_results])
        }
        
        avg_improvements = {
            'psnr': np.mean([r['improvements']['psnr'] for r in strategy_results]),
            'ssim': np.mean([r['improvements']['ssim'] for r in strategy_results]),
            'lpips': np.mean([r['improvements']['lpips'] for r in strategy_results])
        }
        
        # 计算标准差
        std_degraded = {
            'psnr': np.std([r['degraded_metrics']['psnr'] for r in strategy_results]),
            'ssim': np.std([r['degraded_metrics']['ssim'] for r in strategy_results]),
            'lpips': np.std([r['degraded_metrics']['lpips'] for r in strategy_results])
        }
        
        std_restored = {
            'psnr': np.std([r['restored_metrics']['psnr'] for r in strategy_results]),
            'ssim': np.std([r['restored_metrics']['ssim'] for r in strategy_results]),
            'lpips': np.std([r['restored_metrics']['lpips'] for r in strategy_results])
        }
        
        std_improvements = {
            'psnr': np.std([r['improvements']['psnr'] for r in strategy_results]),
            'ssim': np.std([r['improvements']['ssim'] for r in strategy_results]),
            'lpips': np.std([r['improvements']['lpips'] for r in strategy_results])
        }
        
        # 计算中位数
        median_improvements = {
            'psnr': np.median([r['improvements']['psnr'] for r in strategy_results]),
            'ssim': np.median([r['improvements']['ssim'] for r in strategy_results]),
            'lpips': np.median([r['improvements']['lpips'] for r in strategy_results])
        }
        
        # 计算最大/最小改善
        max_improvements = {
            'psnr': np.max([r['improvements']['psnr'] for r in strategy_results]),
            'ssim': np.max([r['improvements']['ssim'] for r in strategy_results]),
            'lpips': np.max([r['improvements']['lpips'] for r in strategy_results])
        }
        
        min_improvements = {
            'psnr': np.min([r['improvements']['psnr'] for r in strategy_results]),
            'ssim': np.min([r['improvements']['ssim'] for r in strategy_results]),
            'lpips': np.min([r['improvements']['lpips'] for r in strategy_results])
        }
        
        # 成功率统计
        total_steps = sum(len(r['restoration_log']) for r in strategy_results)
        successful_steps = sum(sum(1 for log in r['restoration_log'] if log['success']) 
                             for r in strategy_results)
        success_rate = successful_steps / total_steps * 100 if total_steps > 0 else 0
        
        print(f"\n  Average Degraded Metrics:")
        for metric, value in avg_degraded.items():
            print(f"    {metric.upper()}: {value:.4f} (±{std_degraded[metric]:.4f})")
        
        print(f"\n  Average Restored Metrics:")
        for metric, value in avg_restored.items():
            print(f"    {metric.upper()}: {value:.4f} (±{std_restored[metric]:.4f})")
        
        print(f"\n  Average Improvements:")
        for metric, value in avg_improvements.items():
            print(f"    {metric.upper()}: {value:+.4f} (±{std_improvements[metric]:.4f})")
        
        print(f"\n  Median Improvements:")
        for metric, value in median_improvements.items():
            print(f"    {metric.upper()}: {value:+.4f}")
        
        print(f"\n  Best Improvements:")
        for metric, value in max_improvements.items():
            print(f"    {metric.upper()}: {value:+.4f}")
        
        print(f"\n  Worst Improvements:")
        for metric, value in min_improvements.items():
            print(f"    {metric.upper()}: {value:+.4f}")
        
        print(f"\n  Tool Success Rate: {success_rate:.1f}% ({successful_steps}/{total_steps} steps)")
    
    # 保存统计报告
    summary_file = output_dir / f"summary_{timestamp}.txt"
    with open(summary_file, 'w') as f:
        f.write("BASELINE RESTORATION TEST SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Test Time: {timestamp}\n")
        f.write(f"Data Path: {args.data_path}\n")
        f.write(f"Samples Tested: {num_samples}\n")
        f.write(f"Strategies: {', '.join(strategies)}\n\n")
        
        for strategy in strategies:
            strategy_results = [r for r in all_results if r['strategy'] == strategy]
            if not strategy_results:
                continue
            
            f.write(f"\n{strategy.upper()} Strategy Results:\n")
            f.write("-" * 80 + "\n")
            
            # 重新计算所有统计量（为了文件保存）
            avg_degraded = {
                'psnr': np.mean([r['degraded_metrics']['psnr'] for r in strategy_results]),
                'ssim': np.mean([r['degraded_metrics']['ssim'] for r in strategy_results]),
                'lpips': np.mean([r['degraded_metrics']['lpips'] for r in strategy_results])
            }
            
            avg_restored = {
                'psnr': np.mean([r['restored_metrics']['psnr'] for r in strategy_results]),
                'ssim': np.mean([r['restored_metrics']['ssim'] for r in strategy_results]),
                'lpips': np.mean([r['restored_metrics']['lpips'] for r in strategy_results])
            }
            
            avg_improvements = {
                'psnr': np.mean([r['improvements']['psnr'] for r in strategy_results]),
                'ssim': np.mean([r['improvements']['ssim'] for r in strategy_results]),
                'lpips': np.mean([r['improvements']['lpips'] for r in strategy_results])
            }
            
            std_improvements = {
                'psnr': np.std([r['improvements']['psnr'] for r in strategy_results]),
                'ssim': np.std([r['improvements']['ssim'] for r in strategy_results]),
                'lpips': np.std([r['improvements']['lpips'] for r in strategy_results])
            }
            
            median_improvements = {
                'psnr': np.median([r['improvements']['psnr'] for r in strategy_results]),
                'ssim': np.median([r['improvements']['ssim'] for r in strategy_results]),
                'lpips': np.median([r['improvements']['lpips'] for r in strategy_results])
            }
            
            max_improvements = {
                'psnr': np.max([r['improvements']['psnr'] for r in strategy_results]),
                'ssim': np.max([r['improvements']['ssim'] for r in strategy_results]),
                'lpips': np.max([r['improvements']['lpips'] for r in strategy_results])
            }
            
            min_improvements = {
                'psnr': np.min([r['improvements']['psnr'] for r in strategy_results]),
                'ssim': np.min([r['improvements']['ssim'] for r in strategy_results]),
                'lpips': np.min([r['improvements']['lpips'] for r in strategy_results])
            }
            
            total_steps = sum(len(r['restoration_log']) for r in strategy_results)
            successful_steps = sum(sum(1 for log in r['restoration_log'] if log['success']) 
                                 for r in strategy_results)
            success_rate = successful_steps / total_steps * 100 if total_steps > 0 else 0
            
            f.write(f"\nAverage Degraded Metrics:\n")
            for metric, value in avg_degraded.items():
                f.write(f"  {metric.upper()}: {value:.4f}\n")
            
            f.write(f"\nAverage Restored Metrics:\n")
            for metric, value in avg_restored.items():
                f.write(f"  {metric.upper()}: {value:.4f}\n")
            
            f.write(f"\nAverage Improvements:\n")
            for metric, value in avg_improvements.items():
                f.write(f"  {metric.upper()}: {value:+.4f} (±{std_improvements[metric]:.4f})\n")
            
            f.write(f"\nMedian Improvements:\n")
            for metric, value in median_improvements.items():
                f.write(f"  {metric.upper()}: {value:+.4f}\n")
            
            f.write(f"\nBest Improvements:\n")
            for metric, value in max_improvements.items():
                f.write(f"  {metric.upper()}: {value:+.4f}\n")
            
            f.write(f"\nWorst Improvements:\n")
            for metric, value in min_improvements.items():
                f.write(f"  {metric.upper()}: {value:+.4f}\n")
            
            f.write(f"\nTool Success Rate: {success_rate:.1f}% ({successful_steps}/{total_steps} steps)\n")
    
    print(f"\n[INFO] Summary saved to {summary_file}")
    
    # 生成更详细的统计报告（按退化类型分组）
    detailed_stats_file = output_dir / f"detailed_stats_{timestamp}.txt"
    with open(detailed_stats_file, 'w') as f:
        f.write("DETAILED STATISTICS BY DEGRADATION TYPE\n")
        f.write("=" * 80 + "\n\n")
        
        # 收集所有退化类型
        all_degradation_types = set()
        for result in all_results:
            all_degradation_types.update(result['degradation_types'])
        
        f.write(f"Total Unique Degradation Types: {len(all_degradation_types)}\n")
        f.write(f"Types: {sorted(all_degradation_types)}\n\n")
        
        # 按退化类型统计
        for deg_type in sorted(all_degradation_types):
            f.write(f"\n{'-'*80}\n")
            f.write(f"Degradation Type: {deg_type}\n")
            f.write(f"{'-'*80}\n")
            
            # 找出包含此退化类型的样本
            samples_with_deg = [r for r in all_results if deg_type in r['degradation_types']]
            
            if not samples_with_deg:
                continue
            
            f.write(f"Samples containing this degradation: {len(samples_with_deg)}\n\n")
            
            # 按策略分组
            for strategy in strategies:
                strategy_samples = [r for r in samples_with_deg if r['strategy'] == strategy]
                if not strategy_samples:
                    continue
                
                avg_imp = {
                    'psnr': np.mean([r['improvements']['psnr'] for r in strategy_samples]),
                    'ssim': np.mean([r['improvements']['ssim'] for r in strategy_samples]),
                    'lpips': np.mean([r['improvements']['lpips'] for r in strategy_samples])
                }
                
                f.write(f"  {strategy.upper()} strategy ({len(strategy_samples)} samples):\n")
                f.write(f"    Average improvements:\n")
                for metric, value in avg_imp.items():
                    f.write(f"      {metric.upper()}: {value:+.4f}\n")
                f.write("\n")
        
        # 策略对比
        f.write(f"\n{'='*80}\n")
        f.write(f"STRATEGY COMPARISON\n")
        f.write(f"{'='*80}\n\n")
        
        if len(strategies) >= 2:
            for i, strategy1 in enumerate(strategies):
                for strategy2 in strategies[i+1:]:
                    results1 = [r for r in all_results if r['strategy'] == strategy1]
                    results2 = [r for r in all_results if r['strategy'] == strategy2]
                    
                    if not results1 or not results2:
                        continue
                    
                    f.write(f"{strategy1.upper()} vs {strategy2.upper()}:\n")
                    f.write("-" * 80 + "\n")
                    
                    for metric in ['psnr', 'ssim', 'lpips']:
                        avg1 = np.mean([r['improvements'][metric] for r in results1])
                        avg2 = np.mean([r['improvements'][metric] for r in results2])
                        diff = avg2 - avg1
                        
                        better = strategy2 if diff > 0 else strategy1
                        if metric == 'lpips':
                            # LPIPS越小越好，所以反过来
                            better = strategy2 if diff < 0 else strategy1
                        
                        f.write(f"\n{metric.upper()}:\n")
                        f.write(f"  {strategy1}: {avg1:+.4f}\n")
                        f.write(f"  {strategy2}: {avg2:+.4f}\n")
                        f.write(f"  Difference: {diff:+.4f}\n")
                        f.write(f"  Better: {better}\n")
    
    print(f"[INFO] Detailed statistics saved to {detailed_stats_file}")
    
    # 保存CSV格式的统计数据（便于进一步分析）
    csv_file = output_dir / f"statistics_{timestamp}.csv"
    with open(csv_file, 'w') as f:
        # 写入表头
        f.write("strategy,metric,mean,std,median,min,max,samples\n")
        
        for strategy in strategies:
            strategy_results = [r for r in all_results if r['strategy'] == strategy]
            if not strategy_results:
                continue
            
            for metric in ['psnr', 'ssim', 'lpips']:
                improvements = [r['improvements'][metric] for r in strategy_results]
                
                f.write(f"{strategy},{metric},")
                f.write(f"{np.mean(improvements):.6f},")
                f.write(f"{np.std(improvements):.6f},")
                f.write(f"{np.median(improvements):.6f},")
                f.write(f"{np.min(improvements):.6f},")
                f.write(f"{np.max(improvements):.6f},")
                f.write(f"{len(strategy_results)}\n")
    
    print(f"[INFO] CSV statistics saved to {csv_file}")
    
    # 保存按退化类型分组的CSV
    degradation_csv_file = output_dir / f"by_degradation_{timestamp}.csv"
    with open(degradation_csv_file, 'w') as f:
        f.write("degradation_type,strategy,metric,mean_improvement,sample_count\n")
        
        all_degradation_types = set()
        for result in all_results:
            all_degradation_types.update(result['degradation_types'])
        
        for deg_type in sorted(all_degradation_types):
            samples_with_deg = [r for r in all_results if deg_type in r['degradation_types']]
            
            for strategy in strategies:
                strategy_samples = [r for r in samples_with_deg if r['strategy'] == strategy]
                if not strategy_samples:
                    continue
                
                for metric in ['psnr', 'ssim', 'lpips']:
                    avg_imp = np.mean([r['improvements'][metric] for r in strategy_samples])
                    f.write(f"{deg_type},{strategy},{metric},{avg_imp:.6f},{len(strategy_samples)}\n")
    
    print(f"[INFO] Degradation-wise CSV saved to {degradation_csv_file}")
    
    # 打印策略对比摘要
    if len(strategies) >= 2:
        print(f"\n{'='*80}")
        print("STRATEGY COMPARISON SUMMARY")
        print(f"{'='*80}")
        
        for i, strategy1 in enumerate(strategies):
            for strategy2 in strategies[i+1:]:
                results1 = [r for r in all_results if r['strategy'] == strategy1]
                results2 = [r for r in all_results if r['strategy'] == strategy2]
                
                if not results1 or not results2:
                    continue
                
                print(f"\n{strategy1.upper()} vs {strategy2.upper()}:")
                
                for metric in ['psnr', 'ssim', 'lpips']:
                    avg1 = np.mean([r['improvements'][metric] for r in results1])
                    avg2 = np.mean([r['improvements'][metric] for r in results2])
                    diff = avg2 - avg1
                    
                    if metric == 'lpips':
                        better = strategy2 if diff < 0 else strategy1
                        comparison = "lower is better"
                    else:
                        better = strategy2 if diff > 0 else strategy1
                        comparison = "higher is better"
                    
                    print(f"  {metric.upper()}: {strategy1}={avg1:+.4f}, {strategy2}={avg2:+.4f}, diff={diff:+.4f} → {better} wins ({comparison})")
    
    print("\n[INFO] Test completed!")


if __name__ == '__main__':
    main()


