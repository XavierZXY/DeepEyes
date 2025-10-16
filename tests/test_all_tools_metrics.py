#!/usr/bin/env python3
"""
测试所有图像修复工具的性能评估脚本

功能：
1. 从parquet文件读取样本（包含原图和退化图）
2. 对每个样本，使用所有可用的工具进行修复（不叠加，每次都从退化图开始）
3. 计算PSNR/SSIM/LPIPS指标（退化图vs原图，修复图vs原图）
4. 生成详细的性能报告

用法：
    python3 tests/test_all_tools_metrics.py --parquet /path/to/data.parquet --output_dir ./test_results
"""

import sys
import os
sys.path.insert(0, '/app/xiaominl/DeepEyes_v2')

import argparse
import json
import pandas as pd
import numpy as np
from pathlib import Path
from PIL import Image
import io
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 导入图像质量评估工具
from verl.utils.reward_score.image_quality_metrics import get_image_quality_metrics

# 全局打印锁（用于并发时的线程安全打印）
_print_lock = threading.Lock()


# ==================== 工具定义 ====================
class ToolRegistry:
    """
    所有可用的图像修复工具注册表
    每个工具包含：名称、API URL、任务参数构建函数
    """
    
    def __init__(self):
        # 从环境变量获取服务IP
        self.tool_service_ip = os.environ.get('TOOL_SERVICE_IP', '10.21.9.6')
        
        # 定义所有工具
        self.tools = {
            # SwinIR 系列 (端口5001)
            'swinir_denoising': {
                'api_url': f'http://{self.tool_service_ip}:5001/process',
                'task_name': 'denoising',
                'description': 'SwinIR去噪',
                'params': lambda: {'task': 'denoising', 'noise_level': 15}
            },
            'swinir_jpeg_artifact_removal': {
                'api_url': f'http://{self.tool_service_ip}:5001/process',
                'task_name': 'jpeg_compression_artifact_removal',
                'description': 'SwinIR JPEG伪影去除',
                'params': lambda: {'task': 'jpeg_compression_artifact_removal', 'quality': 40}
            },
            'swinir_super_resolution': {
                'api_url': f'http://{self.tool_service_ip}:5001/process',
                'task_name': 'super_resolution',
                'description': 'SwinIR超分辨率',
                'params': lambda: {'task': 'super_resolution', 'scale': 2}  # 训练时使用2倍，不是4倍
            },
            
            # Restormer 系列 (端口5006)
            'restormer_motion_deblurring': {
                'api_url': f'http://{self.tool_service_ip}:5006/process',
                'task_name': 'motion_deblurring',
                'description': 'Restormer运动去模糊',
                'params': lambda: {'task': 'motion_deblurring'}
            },
            'restormer_defocus_deblurring': {
                'api_url': f'http://{self.tool_service_ip}:5006/process',
                'task_name': 'defocus_deblurring',
                'description': 'Restormer散焦去模糊',
                'params': lambda: {'task': 'defocus_deblurring'}
            },
            'restormer_deraining': {
                'api_url': f'http://{self.tool_service_ip}:5006/process',
                'task_name': 'deraining',
                'description': 'Restormer去雨',
                'params': lambda: {'task': 'deraining'}
            },
            
            # XRestormer 系列 (端口5007)
            'xrestormer_motion_deblurring': {
                'api_url': f'http://{self.tool_service_ip}:5007/process',
                'task_name': 'deblur',
                'description': 'XRestormer运动去模糊',
                'params': lambda: {'task': 'deblur'}
            },
            'xrestormer_deraining': {
                'api_url': f'http://{self.tool_service_ip}:5007/process',
                'task_name': 'derain',
                'description': 'XRestormer去雨',
                'params': lambda: {'task': 'derain'}
            },
            
            # MPRNet 系列 (端口5004)
            'mprnet_denoising': {
                'api_url': f'http://{self.tool_service_ip}:5004/process',
                'task_name': 'denoising',
                'description': 'MPRNet去噪',
                'params': lambda: {'task': 'denoising'}
            },
            'mprnet_motion_deblurring': {
                'api_url': f'http://{self.tool_service_ip}:5004/process',
                'task_name': 'motion_deblurring',
                'description': 'MPRNet运动去模糊',
                'params': lambda: {'task': 'motion_deblurring'}
            },
            'mprnet_deraining': {
                'api_url': f'http://{self.tool_service_ip}:5004/process',
                'task_name': 'deraining',
                'description': 'MPRNet去雨',
                'params': lambda: {'task': 'deraining'}
            },
            
            # FBCNN (端口5005)
            'fbcnn_jpeg_artifact_removal': {
                'api_url': f'http://{self.tool_service_ip}:5005/process',
                'task_name': 'jpeg_car',
                'description': 'FBCNN JPEG伪影去除',
                'params': lambda: {'task': 'jpeg_car', 'jpeg': 40}
            },
            
            # DRBNet (端口5003)
            'drbnet_defocus_deblurring': {
                'api_url': f'http://{self.tool_service_ip}:5003/deblur',
                'task_name': 'deblur',
                'description': 'DRBNet散焦去模糊',
                'params': lambda: {},  # DRBNet不需要task参数
                'file_field': 'image_c'  # DRBNet使用特殊的文件字段名
            },
            
            # DehazeFormer (端口5002)
            'dehazeformer_dehaze': {
                'api_url': f'http://{self.tool_service_ip}:5002/process',
                'task_name': 'dehaze',
                'description': 'DehazeFormer去雾',
                'params': lambda: {'task': 'dehaze'}
            },
        }
    
    def get_all_tools(self) -> List[str]:
        """返回所有工具名称"""
        return list(self.tools.keys())
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """获取工具信息"""
        return self.tools.get(tool_name)


# ==================== 工具调用 ====================
def call_tool_api(tool_info: Dict[str, Any], image: Image.Image) -> Optional[Image.Image]:
    """
    调用工具API处理图像
    
    Args:
        tool_info: 工具信息字典
        image: PIL图像
        
    Returns:
        处理后的PIL图像，失败返回None
    """
    import requests
    import base64
    
    api_url = tool_info['api_url']
    params = tool_info['params']()
    
    # 将图像转换为bytes
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    image_bytes = buf.getvalue()
    
    # 支持自定义文件字段名（如DRBNet使用image_c）
    file_field = tool_info.get('file_field', 'image')
    files = {file_field: ('image.png', image_bytes, 'image/png')}
    
    try:
        print(f"    [API] 调用 {api_url} with params {params}")
        response = requests.post(api_url, files=files, data=params, timeout=300)
        
        # 检查HTTP状态码
        if response.status_code != 200:
            print(f"    [API] ❌ HTTP {response.status_code}: {response.text[:200]}")
            return None
        
        # 尝试解析JSON响应
        try:
            result = response.json()
        except ValueError as e:
            # 可能是直接返回图像数据（如DehazeFormer）
            if response.headers.get('Content-Type', '').startswith('image/'):
                print(f"    [API] ⚠️  响应是图像格式，尝试直接解析")
                try:
                    restored_image = Image.open(io.BytesIO(response.content)).convert('RGB')
                    print(f"    [API] ✅ 直接从响应解析图像成功")
                    return restored_image
                except Exception as img_err:
                    print(f"    [API] ❌ 无法解析图像: {img_err}")
                    return None
            else:
                print(f"    [API] ❌ 响应不是有效JSON: {response.text[:200]}")
                return None
        
        # 处理JSON响应
        if result.get('success'):
            img_b64 = result.get('image')
            if not img_b64:
                print(f"    [API] ❌ 响应中缺少图像数据")
                return None
                
            img_bytes = base64.b64decode(img_b64)
            restored_image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            print(f"    [API] ✅ 调用成功")
            return restored_image
        else:
            error_msg = result.get('error', 'Unknown error')
            print(f"    [API] ❌ API返回错误: {error_msg}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"    [API] ❌ 请求超时 (300s)")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"    [API] ❌ 连接错误: {e}")
        return None
    except Exception as e:
        print(f"    [API] ❌ 未知错误: {type(e).__name__}: {str(e)[:100]}")
        return None


# ==================== 数据加载 ====================
def load_parquet_data(parquet_path: str, max_samples: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    从parquet文件加载数据
    
    Args:
        parquet_path: parquet文件路径
        max_samples: 最大样本数量（用于测试）
        
    Returns:
        样本列表，每个样本包含：
        - sample_id: 样本ID
        - original_image: 原图 (PIL.Image)
        - degraded_image: 退化图 (PIL.Image)
        - degradation_types: 退化类型列表
        - degradation_levels: 退化等级列表
    """
    print(f"\n{'='*80}")
    print(f"📂 加载数据: {parquet_path}")
    print(f"{'='*80}")
    
    df = pd.read_parquet(parquet_path)
    print(f"总样本数: {len(df)}")
    
    if max_samples:
        df = df.head(max_samples)
        print(f"限制样本数: {max_samples}")
    
    samples = []
    
    for idx, row in df.iterrows():
        try:
            # 提取原图（从extra_info）
            extra_info = row.get('extra_info', {})
            # extra_info 已经是 dict，不需要 JSON 解析
            
            original_image_data = extra_info.get('original_image')
            if not original_image_data:
                print(f"  [警告] 样本 {idx} 缺少原图，跳过")
                continue
            
            # 转换为PIL图像
            if isinstance(original_image_data, bytes):
                original_image = Image.open(io.BytesIO(original_image_data)).convert('RGB')
            elif isinstance(original_image_data, dict) and 'bytes' in original_image_data:
                original_image = Image.open(io.BytesIO(original_image_data['bytes'])).convert('RGB')
            else:
                print(f"  [警告] 样本 {idx} 原图格式不支持，跳过")
                continue
            
            # 提取退化图（从images字段，注意是复数！）
            degraded_image = None
            
            # 方法1: 从images字段获取（numpy.ndarray）
            if 'images' in row:
                img_data = row['images']
                # images 是 numpy.ndarray，取第一个元素
                if isinstance(img_data, np.ndarray) and len(img_data) > 0:
                    img_data = img_data[0]
                    if isinstance(img_data, bytes):
                        degraded_image = Image.open(io.BytesIO(img_data)).convert('RGB')
                    elif isinstance(img_data, dict) and 'bytes' in img_data:
                        degraded_image = Image.open(io.BytesIO(img_data['bytes'])).convert('RGB')
            
            # 方法2: 尝试从image字段（兼容旧格式）
            if degraded_image is None and 'image' in row:
                img_data = row['image']
                if isinstance(img_data, list) and len(img_data) > 0:
                    img_data = img_data[0]
                elif isinstance(img_data, np.ndarray) and len(img_data) > 0:
                    img_data = img_data[0]
                    
                if isinstance(img_data, bytes):
                    degraded_image = Image.open(io.BytesIO(img_data)).convert('RGB')
                elif isinstance(img_data, dict) and 'bytes' in img_data:
                    degraded_image = Image.open(io.BytesIO(img_data['bytes'])).convert('RGB')
            
            if degraded_image is None:
                print(f"  [警告] 样本 {idx} 缺少退化图，跳过")
                continue
            
            # 提取退化类型和等级（从reward_model，numpy.ndarray）
            reward_model = row.get('reward_model', [])
            # reward_model 已经是 numpy.ndarray，不需要 JSON 解析
            
            degradation_types = []
            degradation_levels = []
            
            # 处理 numpy.ndarray 或 list
            if isinstance(reward_model, (list, np.ndarray)):
                for deg in reward_model:
                    if isinstance(deg, dict):
                        deg_type = deg.get('degradation_type', '')
                        deg_level = deg.get('degradation_level', '')
                        if deg_type:
                            degradation_types.append(deg_type)
                            degradation_levels.append(deg_level)
            
            # 跳过haze样本（数据质量问题：退化图=原图）
            if 'haze' in degradation_types:
                print(f"  ⚠️  样本 {idx}: {degradation_types} - 跳过（haze数据质量问题）")
                continue
            
            sample = {
                'sample_id': f"sample_{idx}",
                'original_image': original_image,
                'degraded_image': degraded_image,
                'degradation_types': degradation_types,
                'degradation_levels': degradation_levels,
            }
            
            samples.append(sample)
            print(f"  ✅ 样本 {idx}: {degradation_types} ({degradation_levels})")
            
        except Exception as e:
            print(f"  [错误] 样本 {idx} 加载失败: {e}")
            traceback.print_exc()
            continue
    
    print(f"\n成功加载 {len(samples)} 个样本")
    return samples


# ==================== 指标计算 ====================
def calculate_metrics(image1: Image.Image, image2: Image.Image, 
                     metrics_calculator) -> Dict[str, float]:
    """
    计算两张图像之间的PSNR/SSIM/LPIPS
    
    Args:
        image1: PIL图像1
        image2: PIL图像2
        metrics_calculator: 图像质量评估器实例
        
    Returns:
        包含psnr, ssim, lpips的字典
    """
    try:
        # 确保图像大小一致
        if image1.size != image2.size:
            print(f"    [警告] 图像尺寸不一致: {image1.size} vs {image2.size}，调整为相同尺寸")
            image2 = image2.resize(image1.size, Image.LANCZOS)
        
        # 计算指标
        psnr = metrics_calculator.calculate_psnr(image1, image2)
        ssim = metrics_calculator.calculate_ssim(image1, image2)
        lpips = metrics_calculator.calculate_lpips(image1, image2)
        
        # 处理inf值（当两张图完全相同时PSNR会是inf）
        if psnr is not None and np.isinf(psnr):
            psnr = 100.0  # 使用一个合理的上限值表示"完全相同"
        
        return {
            'psnr': float(psnr) if psnr is not None else 0.0,
            'ssim': float(ssim) if ssim is not None else 0.0,
            'lpips': float(lpips) if lpips is not None else 0.0,
        }
    except Exception as e:
        print(f"    [错误] 指标计算失败: {e}")
        return {'psnr': 0.0, 'ssim': 0.0, 'lpips': 0.0}


# ==================== 单样本测试 ====================
def _test_single_sample(sample_data: Tuple, registry: ToolRegistry, 
                       metrics_calculator, tools_to_test: List[str],
                       save_images: bool, images_dir: Path) -> List[Dict[str, Any]]:
    """
    测试单个样本的所有工具（用于并发调用）
    
    Args:
        sample_data: (sample_idx, sample) 元组
        registry: 工具注册表
        metrics_calculator: 指标计算器
        tools_to_test: 要测试的工具列表
        save_images: 是否保存图像
        images_dir: 图像保存目录
        
    Returns:
        该样本的所有测试结果列表
    """
    sample_idx, sample = sample_data
    sample_id = sample['sample_id']
    original_image = sample['original_image']
    degraded_image = sample['degraded_image']
    degradation_types = sample['degradation_types']
    degradation_levels = sample['degradation_levels']
    
    with _print_lock:
        print(f"\n{'='*80}")
        print(f"📊 样本 {sample_idx + 1}: {sample_id}")
        print(f"   退化类型: {degradation_types}")
        print(f"   退化等级: {degradation_levels}")
        print(f"{'='*80}")
    
    sample_results = []
    
    # 创建样本图像目录
    if save_images:
        sample_images_dir = images_dir / sample_id
        sample_images_dir.mkdir(exist_ok=True, parents=True)
        
        # 保存原图和退化图
        original_image.save(sample_images_dir / 'original.png')
        degraded_image.save(sample_images_dir / 'degraded.png')
    
    # 计算退化图 vs 原图的基线指标
    baseline_metrics = calculate_metrics(degraded_image, original_image, metrics_calculator)
    with _print_lock:
        print(f"  🔍 计算基线指标（退化图 vs 原图）...")
        print(f"     PSNR: {baseline_metrics['psnr']:.2f} dB")
        print(f"     SSIM: {baseline_metrics['ssim']:.4f}")
        print(f"     LPIPS: {baseline_metrics['lpips']:.4f}")
    
    # 测试每个工具
    for tool_idx, tool_name in enumerate(tools_to_test):
        tool_info = registry.get_tool_info(tool_name)
        if not tool_info:
            with _print_lock:
                print(f"  🔧 工具 {tool_idx + 1}/{len(tools_to_test)}: {tool_name}")
                print(f"     ❌ 工具不存在，跳过")
            continue
        
        with _print_lock:
            print(f"  🔧 工具 {tool_idx + 1}/{len(tools_to_test)}: {tool_name}")
            print(f"     描述: {tool_info['description']}")
        
        # 调用工具处理图像（从退化图开始）
        restored_image = call_tool_api(tool_info, degraded_image)
        
        if restored_image is None:
            with _print_lock:
                print(f"     ❌ 工具调用失败，记录为0分")
            tool_metrics = {'psnr': 0.0, 'ssim': 0.0, 'lpips': 0.0}
            success = False
        else:
            # 保存修复图
            if save_images:
                restored_image.save(sample_images_dir / f'{tool_name}.png')
            
            # 计算修复图 vs 原图的指标
            tool_metrics = calculate_metrics(restored_image, original_image, metrics_calculator)
            with _print_lock:
                print(f"     🔍 计算指标（修复图 vs 原图）...")
                print(f"     PSNR: {tool_metrics['psnr']:.2f} dB ({tool_metrics['psnr'] - baseline_metrics['psnr']:+.2f})")
                print(f"     SSIM: {tool_metrics['ssim']:.4f} ({tool_metrics['ssim'] - baseline_metrics['ssim']:+.4f})")
                print(f"     LPIPS: {tool_metrics['lpips']:.4f} ({baseline_metrics['lpips'] - tool_metrics['lpips']:+.4f})")
            success = True
        
        # 记录结果
        result = {
            'sample_id': sample_id,
            'sample_index': sample_idx,
            'degradation_types': ', '.join(degradation_types),
            'degradation_levels': ', '.join(degradation_levels),
            'tool_name': tool_name,
            'tool_description': tool_info['description'],
            'success': success,
            
            # 基线指标（退化图 vs 原图）
            'baseline_psnr': baseline_metrics['psnr'],
            'baseline_ssim': baseline_metrics['ssim'],
            'baseline_lpips': baseline_metrics['lpips'],
            
            # 工具指标（修复图 vs 原图）
            'restored_psnr': tool_metrics['psnr'],
            'restored_ssim': tool_metrics['ssim'],
            'restored_lpips': tool_metrics['lpips'],
            
            # 改进量
            'psnr_improvement': tool_metrics['psnr'] - baseline_metrics['psnr'],
            'ssim_improvement': tool_metrics['ssim'] - baseline_metrics['ssim'],
            'lpips_improvement': baseline_metrics['lpips'] - tool_metrics['lpips'],  # LPIPS越低越好
        }
        
        sample_results.append(result)
    
    return sample_results


# ==================== 主测试流程 ====================
def test_all_tools(samples: List[Dict[str, Any]], 
                   output_dir: Path,
                   tools_to_test: Optional[List[str]] = None,
                   save_images: bool = True,
                   max_workers: int = 4) -> Dict[str, Any]:
    """
    测试所有工具的性能（支持并发）
    
    Args:
        samples: 样本列表
        output_dir: 输出目录
        tools_to_test: 要测试的工具列表（None表示测试所有工具）
        save_images: 是否保存图像
        max_workers: 最大并发worker数（默认4）
        
    Returns:
        测试结果列表
    """
    print(f"\n{'='*80}")
    print(f"🧪 开始测试（并发模式）")
    print(f"{'='*80}")
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / 'images'
    if save_images:
        images_dir.mkdir(exist_ok=True)
    
    # 初始化工具注册表和指标计算器
    registry = ToolRegistry()
    metrics_calculator = get_image_quality_metrics()
    
    # 确定要测试的工具
    if tools_to_test is None:
        tools_to_test = registry.get_all_tools()
    
    # # 移除dehazeformer（因为haze样本已被过滤）
    # if 'dehazeformer_dehaze' in tools_to_test:
    #     tools_to_test.remove('dehazeformer_dehaze')
    #     print(f"⚠️  自动移除 dehazeformer_dehaze (haze样本已过滤)")
    
    print(f"测试工具数量: {len(tools_to_test)}")
    print(f"测试样本数量: {len(samples)}")
    print(f"并发Worker数: {max_workers}")
    print(f"⚠️  注意: haze样本已自动过滤（数据质量问题）")
    
    # 存储所有结果
    all_results = []
    
    # 使用线程池并发处理样本
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_sample = {}
        for sample_idx, sample in enumerate(samples):
            future = executor.submit(
                _test_single_sample,
                (sample_idx, sample),
                registry,
                metrics_calculator,
                tools_to_test,
                save_images,
                images_dir
            )
            future_to_sample[future] = sample_idx
        
        # 收集结果
        completed = 0
        for future in as_completed(future_to_sample):
            sample_idx = future_to_sample[future]
            try:
                sample_results = future.result()
                all_results.extend(sample_results)
                completed += 1
                print(f"\n✅ 样本 {sample_idx + 1} 完成 ({completed}/{len(samples)})")
            except Exception as e:
                print(f"\n❌ 样本 {sample_idx + 1} 处理失败: {e}")
                traceback.print_exc()
    
    return all_results


# ==================== 统计分析 ====================
def _generate_statistical_report(df: pd.DataFrame, output_dir: Path):
    """
    生成详细的统计分析报告
    """
    stats_path = output_dir / 'statistical_analysis.txt'
    
    with open(stats_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("统计分析报告\n")
        f.write("=" * 80 + "\n\n")
        
        # 1. 按工具统计
        f.write("=" * 80 + "\n")
        f.write("1. 按工具分析（对所有退化类型的表现）\n")
        f.write("=" * 80 + "\n\n")
        
        tool_stats = df.groupby('tool_name').agg({
            'psnr_improvement': ['mean', 'std', 'min', 'max', 'median'],
            'ssim_improvement': ['mean', 'std', 'min', 'max', 'median'],
            'lpips_improvement': ['mean', 'std', 'min', 'max', 'median'],
            'success': 'mean'
        }).round(4)
        
        for tool_name in tool_stats.index:
            f.write(f"工具: {tool_name}\n")
            f.write(f"  成功率: {tool_stats.loc[tool_name, ('success', 'mean')]*100:.1f}%\n")
            f.write(f"  PSNR改进: 平均{tool_stats.loc[tool_name, ('psnr_improvement', 'mean')]:+.2f}dB, ")
            f.write(f"标准差{tool_stats.loc[tool_name, ('psnr_improvement', 'std')]:.2f}, ")
            f.write(f"范围[{tool_stats.loc[tool_name, ('psnr_improvement', 'min')]:+.2f}, {tool_stats.loc[tool_name, ('psnr_improvement', 'max')]:+.2f}]\n")
            f.write(f"  SSIM改进: 平均{tool_stats.loc[tool_name, ('ssim_improvement', 'mean')]:+.4f}, ")
            f.write(f"中位数{tool_stats.loc[tool_name, ('ssim_improvement', 'median')]:+.4f}\n")
            f.write(f"  LPIPS改进: 平均{tool_stats.loc[tool_name, ('lpips_improvement', 'mean')]:+.4f}, ")
            f.write(f"中位数{tool_stats.loc[tool_name, ('lpips_improvement', 'median')]:+.4f}\n")
            f.write("\n")
        
        # 2. 按样本统计
        f.write("=" * 80 + "\n")
        f.write("2. 按样本分析（每个样本的最佳工具）\n")
        f.write("=" * 80 + "\n\n")
        
        for sample_id in df['sample_id'].unique():
            sample_df = df[df['sample_id'] == sample_id]
            best_tool = sample_df.loc[sample_df['psnr_improvement'].idxmax()]
            worst_tool = sample_df.loc[sample_df['psnr_improvement'].idxmin()]
            
            degradation_types = sample_df['degradation_types'].iloc[0]
            baseline_psnr = sample_df['baseline_psnr'].iloc[0]
            baseline_ssim = sample_df['baseline_ssim'].iloc[0]
            baseline_lpips = sample_df['baseline_lpips'].iloc[0]
            
            f.write(f"样本: {sample_id}\n")
            f.write(f"  退化类型: {degradation_types}\n")
            f.write(f"  退化图基线: PSNR={baseline_psnr:.2f}dB, SSIM={baseline_ssim:.4f}, LPIPS={baseline_lpips:.4f}\n")
            f.write(f"  最佳工具: {best_tool['tool_name']} (PSNR改进 {best_tool['psnr_improvement']:+.2f}dB)\n")
            f.write(f"  最差工具: {worst_tool['tool_name']} (PSNR改进 {worst_tool['psnr_improvement']:+.2f}dB)\n")
            f.write("\n")
        
        # 3. 工具针对性分析（处理对应退化 vs 处理其他退化）
        f.write("=" * 80 + "\n")
        f.write("3. 工具针对性分析（对口 vs 不对口）\n")
        f.write("=" * 80 + "\n\n")
        
        # 定义工具和对应退化的映射
        tool_degradation_map = {
            'swinir_denoising': 'noise',
            'mprnet_denoising': 'noise',
            'restormer_motion_deblurring': 'motion blur',
            'xrestormer_motion_deblurring': 'motion blur',
            'mprnet_motion_deblurring': 'motion blur',
            'restormer_defocus_deblurring': 'defocus blur',
            'drbnet_defocus_deblurring': 'defocus blur',
            'restormer_deraining': 'rain',
            'xrestormer_deraining': 'rain',
            'mprnet_deraining': 'rain',
            'swinir_jpeg_artifact_removal': 'jpeg compression artifact',
            'fbcnn_jpeg_artifact_removal': 'jpeg compression artifact',
            'swinir_super_resolution': 'low resolution',
            'dehazeformer_dehaze': 'haze',
        }
        
        for tool_name, target_degradation in tool_degradation_map.items():
            tool_df = df[df['tool_name'] == tool_name]
            if len(tool_df) == 0:
                continue
            
            # 对口样本（包含目标退化）
            matched_df = tool_df[tool_df['degradation_types'].str.contains(target_degradation, na=False)]
            # 不对口样本（不包含目标退化）
            unmatched_df = tool_df[~tool_df['degradation_types'].str.contains(target_degradation, na=False)]
            
            f.write(f"工具: {tool_name}\n")
            f.write(f"  针对退化: {target_degradation}\n")
            
            if len(matched_df) > 0:
                matched_improvement = matched_df['psnr_improvement'].mean()
                f.write(f"  对口样本: {len(matched_df)}个, 平均PSNR改进 {matched_improvement:+.2f}dB\n")
            else:
                f.write(f"  对口样本: 0个\n")
            
            if len(unmatched_df) > 0:
                unmatched_improvement = unmatched_df['psnr_improvement'].mean()
                f.write(f"  非对口样本: {len(unmatched_df)}个, 平均PSNR改进 {unmatched_improvement:+.2f}dB\n")
                
                if len(matched_df) > 0:
                    diff = matched_improvement - unmatched_improvement
                    f.write(f"  针对性差异: {diff:+.2f}dB ")
                    if diff > 2.0:
                        f.write("(✅ 工具有很强的针对性)\n")
                    elif diff > 0.5:
                        f.write("(✅ 工具有一定针对性)\n")
                    else:
                        f.write("(⚠️ 工具针对性不强)\n")
            else:
                f.write(f"  非对口样本: 0个\n")
            
            f.write("\n")
        
        # 4. 退化类型分析
        f.write("=" * 80 + "\n")
        f.write("4. 按退化类型的详细分析\n")
        f.write("=" * 80 + "\n\n")
        
        for deg_type in df['degradation_types'].unique():
            if not deg_type or deg_type == '':
                continue
            
            deg_df = df[df['degradation_types'] == deg_type]
            
            f.write(f"退化类型: {deg_type}\n")
            f.write(f"  样本数: {deg_df['sample_id'].nunique()}\n")
            
            # 该退化类型的平均基线
            avg_baseline = deg_df[['baseline_psnr', 'baseline_ssim', 'baseline_lpips']].iloc[0]
            f.write(f"  退化图基线: PSNR={avg_baseline['baseline_psnr']:.2f}dB, ")
            f.write(f"SSIM={avg_baseline['baseline_ssim']:.4f}, LPIPS={avg_baseline['baseline_lpips']:.4f}\n")
            
            # 该退化类型的最佳工具TOP5
            deg_summary = deg_df.groupby('tool_name').agg({
                'psnr_improvement': 'mean',
                'ssim_improvement': 'mean',
                'lpips_improvement': 'mean'
            }).sort_values('psnr_improvement', ascending=False)
            
            f.write(f"  最佳工具TOP5:\n")
            for rank, (tool, row) in enumerate(deg_summary.head(5).iterrows(), 1):
                f.write(f"    {rank}. {tool}: PSNR {row['psnr_improvement']:+.2f}dB, ")
                f.write(f"SSIM {row['ssim_improvement']:+.4f}, LPIPS {row['lpips_improvement']:+.4f}\n")
            
            f.write("\n")
    
    print(f"✅ 统计分析报告已保存: {stats_path}")


def _generate_visualization_plots(df: pd.DataFrame, output_dir: Path):
    """
    生成可视化图表
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # 无GUI后端
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        plots_dir = output_dir / 'plots'
        plots_dir.mkdir(exist_ok=True)
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 1. 工具PSNR改进对比（条形图）
        fig, ax = plt.subplots(figsize=(12, 8))
        tool_improvement = df.groupby('tool_name')['psnr_improvement'].mean().sort_values()
        colors = ['green' if x > 0 else 'red' for x in tool_improvement.values]
        tool_improvement.plot(kind='barh', ax=ax, color=colors)
        ax.axvline(x=0, color='black', linestyle='--', linewidth=1)
        ax.set_xlabel('PSNR Improvement (dB)', fontsize=12)
        ax.set_ylabel('Tool Name', fontsize=12)
        ax.set_title('Tool Performance: PSNR Improvement', fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        plt.savefig(plots_dir / 'tool_psnr_improvement.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # 2. 工具改进量箱线图（显示分布）
        fig, axes = plt.subplots(3, 1, figsize=(14, 12))
        
        # PSNR箱线图
        df_sorted = df.sort_values('psnr_improvement', ascending=False)
        tool_order = df_sorted.groupby('tool_name')['psnr_improvement'].mean().sort_values(ascending=False).index
        sns.boxplot(data=df, x='tool_name', y='psnr_improvement', order=tool_order, ax=axes[0])
        axes[0].axhline(y=0, color='red', linestyle='--', linewidth=1)
        axes[0].set_title('PSNR Improvement Distribution by Tool', fontsize=12, fontweight='bold')
        axes[0].set_xlabel('')
        axes[0].set_ylabel('PSNR Improvement (dB)', fontsize=10)
        axes[0].tick_params(axis='x', rotation=45)
        axes[0].grid(axis='y', alpha=0.3)
        
        # SSIM箱线图
        sns.boxplot(data=df, x='tool_name', y='ssim_improvement', order=tool_order, ax=axes[1])
        axes[1].axhline(y=0, color='red', linestyle='--', linewidth=1)
        axes[1].set_title('SSIM Improvement Distribution by Tool', fontsize=12, fontweight='bold')
        axes[1].set_xlabel('')
        axes[1].set_ylabel('SSIM Improvement', fontsize=10)
        axes[1].tick_params(axis='x', rotation=45)
        axes[1].grid(axis='y', alpha=0.3)
        
        # LPIPS箱线图
        sns.boxplot(data=df, x='tool_name', y='lpips_improvement', order=tool_order, ax=axes[2])
        axes[2].axhline(y=0, color='red', linestyle='--', linewidth=1)
        axes[2].set_title('LPIPS Improvement Distribution by Tool', fontsize=12, fontweight='bold')
        axes[2].set_xlabel('Tool Name', fontsize=10)
        axes[2].set_ylabel('LPIPS Improvement', fontsize=10)
        axes[2].tick_params(axis='x', rotation=45)
        axes[2].grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(plots_dir / 'tool_improvement_distribution.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # 3. 退化类型热力图
        if df['degradation_types'].nunique() > 1:
            pivot_data = df.pivot_table(
                values='psnr_improvement',
                index='tool_name',
                columns='degradation_types',
                aggfunc='mean'
            )
            
            fig, ax = plt.subplots(figsize=(12, 10))
            sns.heatmap(pivot_data, annot=True, fmt='.2f', cmap='RdYlGn', center=0, 
                       cbar_kws={'label': 'PSNR Improvement (dB)'}, ax=ax)
            ax.set_title('Tool Performance Heatmap by Degradation Type', fontsize=14, fontweight='bold')
            ax.set_xlabel('Degradation Type', fontsize=12)
            ax.set_ylabel('Tool Name', fontsize=12)
            plt.tight_layout()
            plt.savefig(plots_dir / 'degradation_heatmap.png', dpi=150, bbox_inches='tight')
            plt.close()
        
        # 4. 基线 vs 修复对比散点图
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        
        # PSNR散点图
        axes[0].scatter(df['baseline_psnr'], df['restored_psnr'], alpha=0.5, s=30)
        max_val = max(df['baseline_psnr'].max(), df['restored_psnr'].max())
        axes[0].plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='y=x (no change)')
        axes[0].set_xlabel('Baseline PSNR (dB)', fontsize=11)
        axes[0].set_ylabel('Restored PSNR (dB)', fontsize=11)
        axes[0].set_title('PSNR: Degraded vs Restored', fontsize=12, fontweight='bold')
        axes[0].legend()
        axes[0].grid(alpha=0.3)
        
        # SSIM散点图
        axes[1].scatter(df['baseline_ssim'], df['restored_ssim'], alpha=0.5, s=30)
        axes[1].plot([0, 1], [0, 1], 'r--', linewidth=2, label='y=x (no change)')
        axes[1].set_xlabel('Baseline SSIM', fontsize=11)
        axes[1].set_ylabel('Restored SSIM', fontsize=11)
        axes[1].set_title('SSIM: Degraded vs Restored', fontsize=12, fontweight='bold')
        axes[1].legend()
        axes[1].grid(alpha=0.3)
        
        # LPIPS散点图
        axes[2].scatter(df['baseline_lpips'], df['restored_lpips'], alpha=0.5, s=30)
        max_val = max(df['baseline_lpips'].max(), df['restored_lpips'].max())
        axes[2].plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='y=x (no change)')
        axes[2].set_xlabel('Baseline LPIPS', fontsize=11)
        axes[2].set_ylabel('Restored LPIPS', fontsize=11)
        axes[2].set_title('LPIPS: Degraded vs Restored', fontsize=12, fontweight='bold')
        axes[2].legend()
        axes[2].grid(alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(plots_dir / 'baseline_vs_restored.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # 5. 成功率饼图
        if df['tool_name'].nunique() > 1:
            success_rates = df.groupby('tool_name')['success'].mean().sort_values(ascending=False)
            
            fig, ax = plt.subplots(figsize=(10, 8))
            colors_pie = ['green' if x > 0.95 else 'orange' if x > 0.8 else 'red' for x in success_rates.values]
            success_rates.plot(kind='pie', ax=ax, autopct='%1.1f%%', startangle=90, colors=colors_pie)
            ax.set_ylabel('')
            ax.set_title('Tool Success Rate', fontsize=14, fontweight='bold')
            plt.tight_layout()
            plt.savefig(plots_dir / 'success_rate_pie.png', dpi=150, bbox_inches='tight')
            plt.close()
        
        print(f"✅ 可视化图表已保存: {plots_dir}/")
        print(f"   - tool_psnr_improvement.png (工具PSNR改进对比)")
        print(f"   - tool_improvement_distribution.png (改进量分布箱线图)")
        print(f"   - degradation_heatmap.png (退化类型热力图)")
        print(f"   - baseline_vs_restored.png (退化图vs修复图散点图)")
        print(f"   - success_rate_pie.png (成功率饼图)")
        
    except ImportError as e:
        print(f"⚠️  matplotlib/seaborn未安装，跳过可视化: {e}")
    except Exception as e:
        print(f"⚠️  生成可视化图表时出错: {e}")


# ==================== 报告生成 ====================
def generate_report(results: List[Dict[str, Any]], output_dir: Path):
    """
    生成测试报告
    
    Args:
        results: 测试结果列表
        output_dir: 输出目录
    """
    print(f"\n{'='*80}")
    print(f"📊 生成报告")
    print(f"{'='*80}")
    
    df = pd.DataFrame(results)
    
    # 保存详细结果
    csv_path = output_dir / 'detailed_results.csv'
    df.to_csv(csv_path, index=False)
    print(f"✅ 详细结果已保存: {csv_path}")
    
    # 生成汇总报告
    summary_path = output_dir / 'summary_report.txt'
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("图像修复工具性能测试报告\n")
        f.write("=" * 80 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"测试样本数: {df['sample_id'].nunique()}\n")
        f.write(f"测试工具数: {df['tool_name'].nunique()}\n")
        f.write(f"总测试次数: {len(df)}\n")
        f.write("\n")
        
        # 添加退化图基线指标
        f.write("=" * 80 + "\n")
        f.write("退化图基线指标（所有样本平均）\n")
        f.write("=" * 80 + "\n")
        avg_baseline_psnr = df['baseline_psnr'].mean()
        avg_baseline_ssim = df['baseline_ssim'].mean()
        avg_baseline_lpips = df['baseline_lpips'].mean()
        f.write(f"退化图 vs 原图:\n")
        f.write(f"  平均PSNR: {avg_baseline_psnr:.2f} dB\n")
        f.write(f"  平均SSIM: {avg_baseline_ssim:.4f}\n")
        f.write(f"  平均LPIPS: {avg_baseline_lpips:.4f}\n")
        f.write("\n")
        f.write("说明: 这是工具处理前的图像质量，代表退化的严重程度。\n")
        f.write("      PSNR越低、SSIM越低、LPIPS越高，说明退化越严重。\n")
        f.write("\n")
        
        # 按工具统计
        f.write("=" * 80 + "\n")
        f.write("工具性能汇总（所有样本平均）\n")
        f.write("=" * 80 + "\n")
        f.write(f"注: 括号内显示相对于退化图的改进量\n")
        f.write(f"    基线 - 退化图: PSNR={avg_baseline_psnr:.2f}dB, SSIM={avg_baseline_ssim:.4f}, LPIPS={avg_baseline_lpips:.4f}\n")
        f.write("\n")
        
        tool_summary = df.groupby('tool_name').agg({
            'success': 'mean',
            'baseline_psnr': 'mean',
            'baseline_ssim': 'mean', 
            'baseline_lpips': 'mean',
            'restored_psnr': 'mean',
            'restored_ssim': 'mean',
            'restored_lpips': 'mean',
            'psnr_improvement': 'mean',
            'ssim_improvement': 'mean',
            'lpips_improvement': 'mean',
        }).round(4)
        
        tool_summary = tool_summary.sort_values('psnr_improvement', ascending=False)
        
        for tool_name, row in tool_summary.iterrows():
            f.write(f"\n工具: {tool_name}\n")
            f.write(f"  成功率: {row['success']*100:.1f}%\n")
            f.write(f"  退化图→修复图:\n")
            f.write(f"    PSNR: {row['baseline_psnr']:.2f} → {row['restored_psnr']:.2f} dB (改进: {row['psnr_improvement']:+.2f})\n")
            f.write(f"    SSIM: {row['baseline_ssim']:.4f} → {row['restored_ssim']:.4f} (改进: {row['ssim_improvement']:+.4f})\n")
            f.write(f"    LPIPS: {row['baseline_lpips']:.4f} → {row['restored_lpips']:.4f} (改进: {row['lpips_improvement']:+.4f})\n")
        
        # 按退化类型统计
        f.write("\n" + "=" * 80 + "\n")
        f.write("按退化类型的工具性能\n")
        f.write("=" * 80 + "\n")
        
        for deg_type in df['degradation_types'].unique():
            if not deg_type or deg_type == '':
                continue
            
            f.write(f"\n退化类型: {deg_type}\n")
            f.write("-" * 40 + "\n")
            
            deg_df = df[df['degradation_types'] == deg_type]
            deg_summary = deg_df.groupby('tool_name')['psnr_improvement'].mean().sort_values(ascending=False)
            
            for tool_name, improvement in deg_summary.head(5).items():
                f.write(f"  {tool_name}: {improvement:+.2f} dB\n")
        
        # 最佳工具推荐
        f.write("\n" + "=" * 80 + "\n")
        f.write("推荐工具（按PSNR改进排序）\n")
        f.write("=" * 80 + "\n")
        f.write(f"参考基线（退化图）: PSNR={avg_baseline_psnr:.2f}dB, SSIM={avg_baseline_ssim:.4f}, LPIPS={avg_baseline_lpips:.4f}\n")
        f.write("\n")
        
        top_tools = tool_summary.head(10)
        for idx, (tool_name, row) in enumerate(top_tools.iterrows(), 1):
            f.write(f"{idx}. {tool_name}\n")
            f.write(f"   退化图 → 修复图: PSNR {row['baseline_psnr']:.2f} → {row['restored_psnr']:.2f} dB\n")
            f.write(f"   改进量: PSNR {row['psnr_improvement']:+.2f} dB, SSIM {row['ssim_improvement']:+.4f}, LPIPS {row['lpips_improvement']:+.4f}\n")
            f.write("\n")
    
    print(f"✅ 汇总报告已保存: {summary_path}")
    
    # 生成统计分析报告
    _generate_statistical_report(df, output_dir)
    
    # 生成可视化图表
    _generate_visualization_plots(df, output_dir)
    
    # 在控制台输出简要报告
    print(f"\n{'='*80}")
    print(f"📊 简要报告")
    print(f"{'='*80}")
    print(f"\n退化图基线（平均）:")
    print(f"  PSNR: {avg_baseline_psnr:.2f} dB, SSIM: {avg_baseline_ssim:.4f}, LPIPS: {avg_baseline_lpips:.4f}")
    print(f"\n前5名工具（按PSNR改进排序）：")
    for idx, (tool_name, row) in enumerate(tool_summary.head(5).iterrows(), 1):
        print(f"{idx}. {tool_name}: {row['baseline_psnr']:.2f} → {row['restored_psnr']:.2f} dB (改进 {row['psnr_improvement']:+.2f})")


# ==================== 主函数 ====================
def main():
    parser = argparse.ArgumentParser(description='测试所有图像修复工具的性能')
    parser.add_argument('--parquet', type=str, required=True,
                       help='输入parquet文件路径')
    parser.add_argument('--output_dir', type=str, default='./test_results',
                       help='输出目录（默认：./test_results）')
    parser.add_argument('--max_samples', type=int, default=None,
                       help='最大样本数（用于快速测试，默认：全部）')
    parser.add_argument('--tools', type=str, nargs='+', default=None,
                       help='指定要测试的工具（默认：全部）')
    parser.add_argument('--no_save_images', action='store_true',
                       help='不保存图像（节省空间）')
    parser.add_argument('--workers', type=int, default=4,
                       help='并发worker数量（默认：4，设为1则禁用并发）')
    
    args = parser.parse_args()
    
    # 检查parquet文件是否存在
    if not os.path.exists(args.parquet):
        print(f"❌ 错误: 文件不存在: {args.parquet}")
        return
    
    # 创建输出目录
    output_dir = Path(args.output_dir)
    
    # 加载数据
    samples = load_parquet_data(args.parquet, max_samples=args.max_samples)
    
    if len(samples) == 0:
        print(f"❌ 错误: 没有成功加载任何样本")
        return
    
    # 测试所有工具
    results = test_all_tools(
        samples=samples,
        output_dir=output_dir,
        tools_to_test=args.tools,
        save_images=not args.no_save_images,
        max_workers=args.workers
    )
    
    # 生成报告
    generate_report(results, output_dir)
    
    print(f"\n{'='*80}")
    print(f"✅ 测试完成！")
    print(f"{'='*80}")
    print(f"输出目录: {output_dir}")
    print(f"详细结果: {output_dir}/detailed_results.csv")
    print(f"汇总报告: {output_dir}/summary_report.txt")
    if not args.no_save_images:
        print(f"图像文件: {output_dir}/images/")


if __name__ == '__main__':
    main()

