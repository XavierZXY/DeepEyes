#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试单个工具在整个文件夹数据集上的效果（所有级别）
类似 test_restoration_tools.py，但只测试指定的一个工具
"""

import sys
import os
import json
import numpy as np
from pathlib import Path
from PIL import Image
import argparse
from typing import List, Dict
from tqdm import tqdm
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from verl.utils.reward_score.image_quality_metrics import ImageQualityMetrics
from tool_config import ACTIVE_TOOL_CONFIG, TOOL_CLASS_MAP


class SingleToolTester:
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
        self.tool_instance = None
    
    def get_degradation_levels(self, deg_type: str) -> List[str]:
        """获取退化类型的所有级别"""
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
            样本列表
        """
        deg_dir = self.dataset_root / deg_type / level
        if not deg_dir.exists():
            return []
        
        samples = []
        degraded_images = sorted(deg_dir.glob("*.png"))
        
        for deg_path in degraded_images:
            # 解析文件名: 000001_level1.png
            filename = deg_path.stem
            parts = filename.split('_')
            
            if len(parts) >= 2:
                sample_id = parts[0]
                level_num = parts[1].replace('level', '')
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
        """加载工具实例"""
        if self.tool_instance is not None:
            return self.tool_instance
        
        if tool_name not in TOOL_CLASS_MAP:
            print(f"[ERROR] Unknown tool: {tool_name}")
            print(f"[ERROR] Check tool_config.py for available tools")
            return None
        
        module_name, class_name = TOOL_CLASS_MAP[tool_name]
        
        try:
            module = __import__(
                f'verl.workers.agent.envs.mm_process_engine.{module_name}',
                fromlist=[class_name]
            )
            tool_class = getattr(module, class_name)
            tool = tool_class(tool_name, "", {})
            
            self.tool_instance = tool
            return tool
            
        except Exception as e:
            print(f"[ERROR] Failed to load tool {tool_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def apply_tool(self, tool_name: str, degraded_image: Image.Image):
        """应用工具处理退化图像"""
        tool = self.load_tool(tool_name)
        if tool is None:
            return None
        
        try:
            tool.multi_modal_data = {'image': [degraded_image]}
            action_string = f'<tool_call>{{"name": "{tool_name}", "arguments": {{}}}}</tool_call>'
            observation, reward, done, info = tool.execute(action_string)
            
            # 方法1: 从observation中提取图像
            if isinstance(observation, dict):
                if 'image' in observation:
                    restored_images = observation['image']
                    if restored_images and len(restored_images) > 0:
                        return restored_images[0]
                
                # observation['multi_modal_data']['image']
                if 'multi_modal_data' in observation:
                    mmd = observation['multi_modal_data']
                    if isinstance(mmd, dict) and 'image' in mmd:
                        restored_images = mmd['image']
                        if restored_images and len(restored_images) > 0:
                            return restored_images[0]
            
            # 方法2: 从 tool.multi_modal_data 提取
            if hasattr(tool, 'multi_modal_data') and tool.multi_modal_data:
                if 'image' in tool.multi_modal_data:
                    restored_images = tool.multi_modal_data['image']
                    if restored_images and len(restored_images) > 0:
                        restored_img = restored_images[0]
                        if hasattr(restored_img, 'size'):
                            import numpy as np
                            degraded_array = np.array(degraded_image)
                            restored_array = np.array(restored_img)
                            mean_diff = abs(np.mean(degraded_array) - np.mean(restored_array))
                            if mean_diff > 0.5 or degraded_image.size != restored_img.size:
                                return restored_img
                            else:
                                return restored_img
            
            print(f"[WARNING] Tool {tool_name} did not return valid image")
            return None
            
        except Exception as e:
            print(f"[ERROR] Tool {tool_name} execution failed: {e}")
            return None
    
    def calculate_metrics(self, img1: Image.Image, img2: Image.Image) -> Dict[str, float]:
        """计算两张图像之间的质量指标"""
        if img1.size != img2.size:
            img1 = img1.resize(img2.size, Image.Resampling.LANCZOS)
        
        metrics = self.metrics_calculator.calculate_all_metrics(img1, img2)
        
        return {
            'psnr': metrics.get('psnr', 0.0),
            'ssim': metrics.get('ssim', 0.0),
            'lpips': metrics.get('lpips', 0.0)
        }
    
    def test_single_tool(self, tool_name: str, deg_type: str, num_samples: int = None, levels: List[str] = None):
        """
        测试单个工具在指定退化类型的所有级别上
        
        Args:
            tool_name: 工具名称
            deg_type: 退化类型
            num_samples: 每个级别的样本数量
            levels: 要测试的级别列表
        """
        print(f"\n{'='*80}")
        print(f"测试工具: {tool_name}")
        print(f"退化类型: {deg_type}")
        print(f"{'='*80}")
        
        # 获取工具显示名称
        tool_display_name = tool_name
        if deg_type in ACTIVE_TOOL_CONFIG:
            for t_name, t_display in ACTIVE_TOOL_CONFIG[deg_type]:
                if t_name == tool_name:
                    tool_display_name = t_display
                    break
        
        # 获取退化级别
        available_levels = self.get_degradation_levels(deg_type)
        if levels:
            available_levels = [l for l in available_levels if l in levels]
        
        if not available_levels:
            print(f"[ERROR] No levels found for {deg_type}")
            return None
        
        print(f"将测试级别: {', '.join(available_levels)}")
        
        # 加载工具
        print(f"\n加载工具 {tool_name}...")
        tool = self.load_tool(tool_name)
        if tool is None:
            return None
        print(f"✓ 工具加载成功: {tool.__class__.__name__}")
        
        results = {
            'tool_name': tool_name,
            'display_name': tool_display_name,
            'degradation_type': deg_type,
            'baseline': {},
            'levels': {}
        }
        
        # 对每个级别进行测试
        for level in available_levels:
            print(f"\n{'─'*80}")
            print(f"测试级别: {level}")
            print(f"{'─'*80}")
            
            # 获取样本
            samples = self.parse_image_samples(deg_type, level, num_samples)
            print(f"找到 {len(samples)} 个样本")
            
            if not samples:
                continue
            
            # 计算基线指标
            baseline_metrics = []
            for sample in tqdm(samples, desc=f"计算基线指标({level})"):
                original = Image.open(sample['original_path']).convert('RGB')
                degraded = Image.open(sample['degraded_path']).convert('RGB')
                
                metrics = self.calculate_metrics(degraded, original)
                baseline_metrics.append(metrics)
            
            # 平均基线指标
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
            
            # 测试工具
            tool_metrics = []
            success_count = 0
            
            for sample in tqdm(samples, desc=f"  {tool_display_name}"):
                original = Image.open(sample['original_path']).convert('RGB')
                degraded = Image.open(sample['degraded_path']).convert('RGB')
                
                # 应用工具
                restored = self.apply_tool(tool_name, degraded)
                
                if restored is not None:
                    metrics = self.calculate_metrics(restored, original)
                    tool_metrics.append(metrics)
                    success_count += 1
                else:
                    # 如果失败，记录0值
                    tool_metrics.append({'psnr': 0.0, 'ssim': 0.0, 'lpips': 0.0})
            
            # 计算平均修复指标
            if tool_metrics:
                avg_metrics = {
                    'psnr': np.mean([m['psnr'] for m in tool_metrics]),
                    'ssim': np.mean([m['ssim'] for m in tool_metrics]),
                    'lpips': np.mean([m['lpips'] for m in tool_metrics])
                }
                
                # 计算改进率
                psnr_improve = ((avg_metrics['psnr'] - avg_baseline['psnr']) / avg_baseline['psnr'] * 100) if avg_baseline['psnr'] > 0 else 0
                ssim_improve = ((avg_metrics['ssim'] - avg_baseline['ssim']) / avg_baseline['ssim'] * 100) if avg_baseline['ssim'] > 0 else 0
                lpips_improve = ((avg_baseline['lpips'] - avg_metrics['lpips']) / avg_baseline['lpips'] * 100) if avg_baseline['lpips'] > 0 else 0
                
                results['levels'][level] = {
                    'metrics': avg_metrics,
                    'improvement': {
                        'psnr': psnr_improve,
                        'ssim': ssim_improve,
                        'lpips': lpips_improve
                    },
                    'success_rate': success_count / len(samples),
                    'num_samples': len(samples),
                    'success_count': success_count
                }
                
                print(f"    修复后指标:")
                print(f"      PSNR: {avg_metrics['psnr']:.2f} dB ({psnr_improve:+.1f}%)")
                print(f"      SSIM: {avg_metrics['ssim']:.4f} ({ssim_improve:+.1f}%)")
                print(f"      LPIPS: {avg_metrics['lpips']:.4f} ({lpips_improve:+.1f}%)")
                print(f"      成功率: {success_count}/{len(samples)} ({success_count/len(samples)*100:.1f}%)")
        
        return results
    
    def generate_report(self, results: Dict, output_dir: str):
        """生成测试报告"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        tool_name = results['tool_name']
        deg_type = results['degradation_type']
        
        # 保存 JSON
        json_file = output_path / f"{tool_name}_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ JSON报告已保存到: {json_file}")
        
        # 生成 Markdown 报告
        md_file = output_path / f"{tool_name}_{timestamp}.md"
        with open(md_file, 'w') as f:
            f.write(f"# {results['display_name']} 测试报告\n\n")
            f.write(f"**工具名称**: {tool_name}\n")
            f.write(f"**退化类型**: {deg_type}\n")
            f.write(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 基线指标
            f.write(f"## 基线指标 (退化图 vs 原图)\n\n")
            f.write(f"| Level | PSNR (dB) | SSIM | LPIPS |\n")
            f.write(f"|-------|-----------|------|-------|\n")
            for level, baseline in sorted(results['baseline'].items()):
                f.write(f"| {level} | {baseline['psnr']:.2f} | {baseline['ssim']:.4f} | {baseline['lpips']:.4f} |\n")
            
            # 工具修复效果
            f.write(f"\n## 工具修复效果\n\n")
            f.write(f"### {results['display_name']}\n\n")
            f.write(f"| Level | PSNR | SSIM | LPIPS | PSNR↑ | SSIM↑ | LPIPS↓ | 成功率 |\n")
            f.write(f"|-------|------|------|-------|-------|-------|--------|--------|\n")
            
            for level, level_data in sorted(results['levels'].items()):
                metrics = level_data['metrics']
                improve = level_data['improvement']
                success_rate = level_data['success_rate']
                num = level_data['num_samples']
                success = level_data['success_count']
                
                f.write(f"| {level} | {metrics['psnr']:.2f} | {metrics['ssim']:.4f} | {metrics['lpips']:.4f} | ")
                f.write(f"{improve['psnr']:+.1f}% | {improve['ssim']:+.1f}% | {improve['lpips']:+.1f}% | ")
                f.write(f"{success_rate*100:.1f}% ({success}/{num}) |\n")
        
        print(f"✓ Markdown报告已保存到: {md_file}")
        
        # 生成 CSV
        import pandas as pd
        csv_data = []
        for level, level_data in results['levels'].items():
            baseline = results['baseline'][level]
            metrics = level_data['metrics']
            improve = level_data['improvement']
            
            csv_data.append({
                'Degradation_Type': deg_type,
                'Level': level,
                'Tool': results['display_name'],
                'Tool_Name': tool_name,
                'Baseline_PSNR': baseline['psnr'],
                'Baseline_SSIM': baseline['ssim'],
                'Baseline_LPIPS': baseline['lpips'],
                'Restored_PSNR': metrics['psnr'],
                'Restored_SSIM': metrics['ssim'],
                'Restored_LPIPS': metrics['lpips'],
                'Improve_PSNR%': improve['psnr'],
                'Improve_SSIM%': improve['ssim'],
                'Improve_LPIPS%': improve['lpips'],
                'Success_Rate': level_data['success_rate'],
                'Num_Samples': level_data['num_samples']
            })
        
        csv_file = output_path / f"{tool_name}_{timestamp}.csv"
        df = pd.DataFrame(csv_data)
        df.to_csv(csv_file, index=False)
        print(f"✓ CSV报告已保存到: {csv_file}")


def main():
    parser = argparse.ArgumentParser(description='测试单个工具在文件夹数据集上的效果')
    parser.add_argument('tool_name', type=str, help='工具名称（如: dehazeformer_dehaze）')
    parser.add_argument('degradation_type', type=str, help='退化类型（如: haze, noise, rain）')
    parser.add_argument('--dataset', type=str, 
                       default='/app/xiaominl/datasets/degraded_datasets/degraded_dataset',
                       help='数据集根目录')
    parser.add_argument('--num-samples', type=int, default=None,
                       help='每个级别的样本数量（默认: 全部）')
    parser.add_argument('--levels', type=str, nargs='+', default=None,
                       help='要测试的级别（如: low medium high）')
    parser.add_argument('--output', type=str, default='./single_tool_results',
                       help='输出目录')
    parser.add_argument('--tool-service-ip', type=str, default='10.21.9.6',
                       help='工具服务IP地址')
    
    args = parser.parse_args()
    
    # 初始化测试器
    tester = SingleToolTester(args.dataset, args.tool_service_ip)
    
    # 运行测试
    results = tester.test_single_tool(
        args.tool_name,
        args.degradation_type,
        args.num_samples,
        args.levels
    )
    
    if results:
        # 生成报告
        tester.generate_report(results, args.output)
        
        print(f"\n{'='*80}")
        print(f"测试完成！结果已保存到: {args.output}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    main()

