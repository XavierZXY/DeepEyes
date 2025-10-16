#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图像修复工具效果测试脚本

功能：
1. 测试不同退化类型的修复工具效果
2. 计算PSNR、SSIM、LPIPS指标
3. 支持选择测试样本数量
4. 支持排除某些退化类型
5. 对比不同工具的修复效果
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import numpy as np
from PIL import Image
from tqdm import tqdm
import pandas as pd

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from verl.utils.reward_score.image_quality_metrics import ImageQualityMetrics

# 导入工具配置
from tool_config import ACTIVE_TOOL_CONFIG, TOOL_CLASS_MAP

# 使用配置文件中的工具池
DEGRADATION_TO_TOOLS = ACTIVE_TOOL_CONFIG


class ToolTester:
    """工具测试类"""
    
    def __init__(self, dataset_root: str, tool_service_ip: str = None):
        """
        初始化测试器
        
        Args:
            dataset_root: 数据集根目录
            tool_service_ip: 工具服务IP地址
        """
        self.dataset_root = Path(dataset_root)
        self.original_dir = self.dataset_root / "original"
        
        # 设置工具服务IP
        if tool_service_ip:
            os.environ['TOOL_SERVICE_IP'] = tool_service_ip
        
        # 初始化图像质量评估器
        self.metrics_calculator = ImageQualityMetrics()
        
        # 工具实例缓存
        self.tool_instances = {}
        
    def get_degradation_types(self) -> List[str]:
        """获取数据集中所有的退化类型"""
        types = []
        for item in self.dataset_root.iterdir():
            if item.is_dir() and item.name != "original":
                types.append(item.name)
        return sorted(types)
    
    def get_degradation_levels(self, deg_type: str) -> List[str]:
        """获取某个退化类型的所有等级"""
        deg_dir = self.dataset_root / deg_type
        if not deg_dir.exists():
            return []
        
        levels = []
        for item in deg_dir.iterdir():
            if item.is_dir():
                levels.append(item.name)
        return sorted(levels)
    
    def parse_image_samples(self, deg_type: str, level: str, num_samples: int = None) -> List[Dict]:
        """
        解析图像样本
        
        Args:
            deg_type: 退化类型 (如 'haze')
            level: 退化级别 (如 'low', 'medium', 'high')
            num_samples: 样本数量限制
            
        Returns:
            样本列表，每个样本包含 {sample_id, original_path, degraded_path, level_num}
        """
        deg_dir = self.dataset_root / deg_type / level
        if not deg_dir.exists():
            return []
        
        samples = []
        degraded_images = sorted(deg_dir.glob("*.png"))
        
        for deg_path in degraded_images:
            # 解析文件名: 000001_level1.png
            filename = deg_path.stem  # 000001_level1
            parts = filename.split('_')
            
            if len(parts) >= 2:
                sample_id = parts[0]  # 000001
                level_num = parts[1].replace('level', '')  # 1
            else:
                sample_id = filename
                level_num = "1"
            
            # 对应的原图路径
            original_path = self.original_dir / f"{sample_id}.png"
            
            if original_path.exists():
                samples.append({
                    'sample_id': sample_id,
                    'original_path': str(original_path),
                    'degraded_path': str(deg_path),
                    'level': level,
                    'level_num': level_num,
                    'degradation_type': deg_type
                })
        
        # 限制样本数量
        if num_samples and len(samples) > num_samples:
            samples = samples[:num_samples]
        
        return samples
    
    def load_tool(self, tool_name: str):
        """加载工具实例（使用配置映射）"""
        if tool_name in self.tool_instances:
            return self.tool_instances[tool_name]
        
        # 检查工具是否在配置中
        if tool_name not in TOOL_CLASS_MAP:
            print(f"[ERROR] Unknown tool: {tool_name}")
            print(f"[ERROR] Check tool_config.py for available tools")
            return None
        
        module_name, class_name = TOOL_CLASS_MAP[tool_name]
        
        try:
            # 动态导入模块
            module = __import__(
                f'verl.workers.agent.envs.mm_process_engine.{module_name}',
                fromlist=[class_name]
            )
            tool_class = getattr(module, class_name)
            tool = tool_class(tool_name, "", {})
            
            self.tool_instances[tool_name] = tool
            return tool
            
        except Exception as e:
            print(f"[ERROR] Failed to load tool {tool_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def apply_tool(self, tool_name: str, degraded_image: Image.Image) -> Optional[Image.Image]:
        """
        应用工具处理图像
        
        Args:
            tool_name: 工具名称
            degraded_image: 退化图像
            
        Returns:
            修复后的图像，如果失败则返回None
        """
        tool = self.load_tool(tool_name)
        if tool is None:
            return None
        
        try:
            # 准备多模态数据
            tool.multi_modal_data = {'image': [degraded_image]}
            
            # 构造工具调用字符串（使用默认参数）
            action_string = f'<tool_call>[{{"name": "{tool_name}", "arguments": {{}}}}]</tool_call>'
            
            # 执行工具
            observation, reward, done, info = tool.execute(action_string)
            
            # 方法1: 从observation中提取图像（dict格式）
            if isinstance(observation, dict) and 'image' in observation:
                restored_images = observation['image']
                if restored_images and len(restored_images) > 0:
                    return restored_images[0]
            
            # 方法2: 工具可能直接更新了multi_modal_data（最常见的方式）
            # 很多工具执行后会更新multi_modal_data['image'][0]
            if hasattr(tool, 'multi_modal_data') and tool.multi_modal_data:
                if 'image' in tool.multi_modal_data:
                    restored_images = tool.multi_modal_data['image']
                    if restored_images and len(restored_images) > 0:
                        restored_img = restored_images[0]
                        # 检查是否是PIL Image对象
                        if hasattr(restored_img, 'size'):
                            # 简单检查：对比图像均值来判断是否改变
                            import numpy as np
                            degraded_array = np.array(degraded_image)
                            restored_array = np.array(restored_img)
                            mean_diff = abs(np.mean(degraded_array) - np.mean(restored_array))
                            # 如果均值差异>0.5，认为是不同的图像
                            if mean_diff > 0.5 or degraded_image.size != restored_img.size:
                                return restored_img
                            # 即使均值相似，也可能是有效的处理结果，返回它
                            else:
                                return restored_img
            
            # 方法3: observation可能是字符串格式，工具实际在info中返回图像
            if isinstance(info, dict):
                # 检查info中是否有图像
                if 'restored_image' in info:
                    return info['restored_image']
                if 'image' in info:
                    return info['image']
            
            # 如果都没找到，打印调试信息
            print(f"[WARNING] Tool {tool_name} did not return valid image")
            print(f"  observation type: {type(observation)}")
            if isinstance(observation, dict):
                print(f"  observation keys: {list(observation.keys())}")
            print(f"  observation content: {str(observation)[:200] if observation else 'None'}")
            print(f"  info keys: {list(info.keys()) if isinstance(info, dict) else 'Not a dict'}")
            if hasattr(tool, 'multi_modal_data') and tool.multi_modal_data:
                if 'image' in tool.multi_modal_data:
                    print(f"  multi_modal_data has image: {len(tool.multi_modal_data['image'])} images")
                    if len(tool.multi_modal_data['image']) > 0:
                        img = tool.multi_modal_data['image'][0]
                        print(f"  image[0] type: {type(img)}, has size attr: {hasattr(img, 'size')}")
                        if hasattr(img, 'size'):
                            print(f"  image[0] size: {img.size}")
            return None
            
        except Exception as e:
            print(f"[ERROR] Tool {tool_name} execution failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def calculate_metrics(self, img1: Image.Image, img2: Image.Image) -> Dict[str, float]:
        """
        计算两张图像之间的质量指标
        
        Args:
            img1: 第一张图像（待评估图像）
            img2: 第二张图像（参考图像）
            
        Returns:
            包含PSNR、SSIM、LPIPS的字典
        """
        # 确保尺寸一致
        if img1.size != img2.size:
            img1 = img1.resize(img2.size, Image.Resampling.LANCZOS)
        
        metrics = self.metrics_calculator.calculate_all_metrics(img1, img2)
        
        return {
            'psnr': metrics.get('psnr', 0.0),
            'ssim': metrics.get('ssim', 0.0),
            'lpips': metrics.get('lpips', 0.0)
        }
    
    def test_degradation_type(
        self, 
        deg_type: str, 
        num_samples: int = None,
        levels: List[str] = None
    ) -> Dict:
        """
        测试某个退化类型的所有工具
        
        Args:
            deg_type: 退化类型
            num_samples: 每个级别的样本数量
            levels: 要测试的级别列表，None表示全部
            
        Returns:
            测试结果字典
        """
        print(f"\n{'='*80}")
        print(f"测试退化类型: {deg_type}")
        print(f"{'='*80}")
        
        # 获取该退化类型的所有工具
        tools = DEGRADATION_TO_TOOLS.get(deg_type, [])
        if not tools:
            print(f"[WARNING] No tools defined for degradation type: {deg_type}")
            return {}
        
        # 获取退化级别
        available_levels = self.get_degradation_levels(deg_type)
        if levels:
            available_levels = [l for l in available_levels if l in levels]
        
        if not available_levels:
            print(f"[WARNING] No levels found for {deg_type}")
            return {}
        
        results = {
            'degradation_type': deg_type,
            'tools': {},
            'baseline': {}
        }
        
        # 对每个级别进行测试
        for level in available_levels:
            print(f"\n--- 测试级别: {level} ---")
            
            # 获取样本
            samples = self.parse_image_samples(deg_type, level, num_samples)
            print(f"找到 {len(samples)} 个样本")
            
            if not samples:
                continue
            
            # 计算基线指标（退化图 vs 原图）
            baseline_metrics = []
            for sample in tqdm(samples, desc=f"计算基线指标({level})"):
                original = Image.open(sample['original_path']).convert('RGB')
                degraded = Image.open(sample['degraded_path']).convert('RGB')
                
                metrics = self.calculate_metrics(degraded, original)
                baseline_metrics.append(metrics)
            
            # 计算平均基线指标
            avg_baseline = {
                'psnr': np.mean([m['psnr'] for m in baseline_metrics]),
                'ssim': np.mean([m['ssim'] for m in baseline_metrics]),
                'lpips': np.mean([m['lpips'] for m in baseline_metrics])
            }
            
            results['baseline'][level] = avg_baseline
            
            print(f"  基线指标 (退化图 vs 原图):")
            print(f"    PSNR: {avg_baseline['psnr']:.2f} dB")
            print(f"    SSIM: {avg_baseline['ssim']:.4f}")
            print(f"    LPIPS: {avg_baseline['lpips']:.4f}")
            
            # 测试每个工具
            for tool_name, tool_display_name in tools:
                print(f"\n  测试工具: {tool_display_name} ({tool_name})")
                
                tool_metrics = []
                success_count = 0
                
                for sample in tqdm(samples, desc=f"  {tool_display_name}"):
                    original = Image.open(sample['original_path']).convert('RGB')
                    degraded = Image.open(sample['degraded_path']).convert('RGB')
                    
                    # 应用工具
                    restored = self.apply_tool(tool_name, degraded)
                    
                    if restored is not None:
                        # 计算修复后的指标
                        metrics = self.calculate_metrics(restored, original)
                        tool_metrics.append(metrics)
                        success_count += 1
                    else:
                        # 工具失败，记录为0
                        tool_metrics.append({'psnr': 0.0, 'ssim': 0.0, 'lpips': 0.0})
                
                # 计算平均指标
                if tool_metrics:
                    avg_metrics = {
                        'psnr': np.mean([m['psnr'] for m in tool_metrics]),
                        'ssim': np.mean([m['ssim'] for m in tool_metrics]),
                        'lpips': np.mean([m['lpips'] for m in tool_metrics]),
                        'success_rate': success_count / len(samples)
                    }
                    
                    # 计算改进百分比
                    improvement = {
                        'psnr': ((avg_metrics['psnr'] - avg_baseline['psnr']) / avg_baseline['psnr'] * 100) if avg_baseline['psnr'] > 0 else 0,
                        'ssim': ((avg_metrics['ssim'] - avg_baseline['ssim']) / avg_baseline['ssim'] * 100) if avg_baseline['ssim'] > 0 else 0,
                        'lpips': ((avg_baseline['lpips'] - avg_metrics['lpips']) / avg_baseline['lpips'] * 100) if avg_baseline['lpips'] > 0 else 0  # LPIPS越低越好
                    }
                    
                    if tool_name not in results['tools']:
                        results['tools'][tool_name] = {
                            'display_name': tool_display_name,
                            'levels': {}
                        }
                    
                    results['tools'][tool_name]['levels'][level] = {
                        'metrics': avg_metrics,
                        'improvement': improvement,
                        'num_samples': len(samples),
                        'success_count': success_count
                    }
                    
                    print(f"    修复后指标:")
                    print(f"      PSNR: {avg_metrics['psnr']:.2f} dB ({improvement['psnr']:+.1f}%)")
                    print(f"      SSIM: {avg_metrics['ssim']:.4f} ({improvement['ssim']:+.1f}%)")
                    print(f"      LPIPS: {avg_metrics['lpips']:.4f} ({improvement['lpips']:+.1f}%)")
                    print(f"      成功率: {avg_metrics['success_rate']:.1%} ({success_count}/{len(samples)})")
        
        return results
    
    def generate_report(self, all_results: Dict, output_dir: str):
        """生成测试报告"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 生成JSON报告
        json_path = output_dir / "test_results.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"\n✓ JSON报告已保存到: {json_path}")
        
        # 2. 生成CSV报告
        csv_data = []
        for deg_type, result in all_results.items():
            baseline = result.get('baseline', {})
            tools = result.get('tools', {})
            
            for tool_name, tool_data in tools.items():
                tool_display_name = tool_data['display_name']
                
                for level, level_data in tool_data['levels'].items():
                    metrics = level_data['metrics']
                    improvement = level_data['improvement']
                    baseline_level = baseline.get(level, {})
                    
                    csv_data.append({
                        'Degradation_Type': deg_type,
                        'Level': level,
                        'Tool': tool_display_name,
                        'Tool_Name': tool_name,
                        'Baseline_PSNR': baseline_level.get('psnr', 0),
                        'Baseline_SSIM': baseline_level.get('ssim', 0),
                        'Baseline_LPIPS': baseline_level.get('lpips', 0),
                        'Restored_PSNR': metrics['psnr'],
                        'Restored_SSIM': metrics['ssim'],
                        'Restored_LPIPS': metrics['lpips'],
                        'Improve_PSNR%': improvement['psnr'],
                        'Improve_SSIM%': improvement['ssim'],
                        'Improve_LPIPS%': improvement['lpips'],
                        'Success_Rate': metrics['success_rate'],
                        'Num_Samples': level_data['num_samples'],
                        'Success_Count': level_data['success_count']
                    })
        
        if csv_data:
            df = pd.DataFrame(csv_data)
            csv_path = output_dir / "test_results.csv"
            df.to_csv(csv_path, index=False)
            print(f"✓ CSV报告已保存到: {csv_path}")
        
        # 3. 生成Markdown报告
        md_path = output_dir / "test_results.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("# 图像修复工具测试报告\n\n")
            
            for deg_type, result in all_results.items():
                f.write(f"## {deg_type}\n\n")
                
                baseline = result.get('baseline', {})
                tools = result.get('tools', {})
                
                # 基线表格
                f.write("### 基线指标 (退化图 vs 原图)\n\n")
                f.write("| Level | PSNR (dB) | SSIM | LPIPS |\n")
                f.write("|-------|-----------|------|-------|\n")
                for level, metrics in baseline.items():
                    f.write(f"| {level} | {metrics['psnr']:.2f} | {metrics['ssim']:.4f} | {metrics['lpips']:.4f} |\n")
                f.write("\n")
                
                # 工具结果表格
                f.write("### 工具修复效果\n\n")
                for tool_name, tool_data in tools.items():
                    f.write(f"#### {tool_data['display_name']}\n\n")
                    f.write("| Level | PSNR | SSIM | LPIPS | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率 |\n")
                    f.write("|-------|------|------|-------|-------|-------|--------|--------|\n")
                    
                    for level, level_data in tool_data['levels'].items():
                        m = level_data['metrics']
                        imp = level_data['improvement']
                        f.write(f"| {level} | {m['psnr']:.2f} | {m['ssim']:.4f} | {m['lpips']:.4f} | "
                               f"{imp['psnr']:+.1f}% | {imp['ssim']:+.1f}% | {imp['lpips']:+.1f}% | "
                               f"{m['success_rate']:.1%} |\n")
                    f.write("\n")
        
        print(f"✓ Markdown报告已保存到: {md_path}")


def main():
    parser = argparse.ArgumentParser(description="图像修复工具效果测试")
    parser.add_argument('--dataset', type=str, required=True, help='数据集根目录')
    parser.add_argument('--output', type=str, default='./test_results', help='输出目录')
    parser.add_argument('--num-samples', type=int, default=None, help='每个级别的样本数量（None表示全部）')
    parser.add_argument('--types', nargs='+', default=None, 
                       help='要测试的退化类型列表（如: haze noise rain），默认全部')
    parser.add_argument('--exclude-types', nargs='+', default=[], 
                       help='要排除的退化类型列表')
    parser.add_argument('--levels', nargs='+', default=None,
                       help='要测试的级别（如: low medium high），默认全部')
    parser.add_argument('--tool-service-ip', type=str, default=None,
                       help='工具服务IP地址（默认从环境变量TOOL_SERVICE_IP读取）')
    
    args = parser.parse_args()
    
    # 初始化测试器
    tester = ToolTester(args.dataset, args.tool_service_ip)
    
    # 确定要测试的退化类型
    if args.types:
        deg_types = args.types
    else:
        deg_types = tester.get_degradation_types()
    
    # 排除指定类型
    deg_types = [t for t in deg_types if t not in args.exclude_types]
    
    print(f"\n将测试以下退化类型: {', '.join(deg_types)}")
    if args.exclude_types:
        print(f"排除的类型: {', '.join(args.exclude_types)}")
    
    # 运行测试
    all_results = {}
    for deg_type in deg_types:
        results = tester.test_degradation_type(
            deg_type, 
            num_samples=args.num_samples,
            levels=args.levels
        )
        if results:
            all_results[deg_type] = results
    
    # 生成报告
    if all_results:
        tester.generate_report(all_results, args.output)
        print(f"\n{'='*80}")
        print(f"测试完成！结果已保存到: {args.output}")
        print(f"{'='*80}")
    else:
        print("\n[WARNING] 没有生成任何测试结果")


if __name__ == "__main__":
    main()

