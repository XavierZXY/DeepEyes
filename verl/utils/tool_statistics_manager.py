# Copyright 2024 Bytedance Ltd. and/or its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
工具统计管理器 - 独立管理工具使用统计，不依赖actor实现
用于替代原来在parallel_env中的工具统计逻辑
"""

import torch
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import numpy as np


class ToolStatisticsManager:
    """
    工具统计管理器
    
    负责收集、处理和分析工具使用统计信息，包括：
    - 工具调用次数统计
    - 工具使用率计算
    - WandB指标生成
    - 统计摘要输出
    """
    
    def __init__(self, device='cpu'):
        """
        初始化工具统计管理器
        
        Args:
            device: 用于tensor计算的设备
        """
        self.device = device
        
        # 定义需要统计的工具列表
        self.all_tool_names = [
            # FBCNN工具
            "fbcnn_jpeg_artifact_removal", 
            "fbcnn_blind_quality_assessment",
            
            # SwinIR工具
            "swinir_denoising", 
            "swinir_jpeg_artifact_removal", 
            "swinir_super_resolution",
            
            # MPRNet工具
            "mprnet_denoising", 
            "mprnet_deraining", 
            "mprnet_motion_deblurring",
            
            # XRestormer工具
            "xrestormer_deraining", 
            "xrestormer_motion_deblurring",
            
            # 其他专业工具
            "dehazeformer_dehaze", 
            "drbnet_defocus_deblurring",
            
            # 通用视觉工具
            "visual_toolbox", 
            "visual_toolbox_v2", 
            "visual_toolbox_v3", 
            "visual_toolbox_v4", 
            "visual_toolbox_v5"
        ]
        
        # 初始化统计字典
        self.reset_statistics()
    
    def reset_statistics(self):
        """重置所有统计信息"""
        self.tool_usage_stats = defaultdict(list)
        for tool_name in self.all_tool_names:
            self.tool_usage_stats[tool_name] = []
    
    def record_tool_usage(self, tool_name: str, sample_index: int = None):
        """
        记录工具使用
        
        Args:
            tool_name: 工具名称
            sample_index: 样本索引（可选，用于调试）
        """
        if tool_name in self.all_tool_names:
            # 为当前样本增加计数
            if len(self.tool_usage_stats[tool_name]) <= (sample_index or 0):
                # 扩展列表以匹配样本数量
                while len(self.tool_usage_stats[tool_name]) <= (sample_index or 0):
                    self.tool_usage_stats[tool_name].append(0)
            
            self.tool_usage_stats[tool_name][sample_index or 0] += 1
            
            # 输出调试信息
            if sample_index is not None:
                print(f"[TOOL STATS] 样本{sample_index} 使用工具: {tool_name}")
    
    def ensure_sample_count(self, num_samples: int):
        """
        确保所有工具的统计数组长度匹配样本数量
        
        Args:
            num_samples: 样本总数
        """
        for tool_name in self.all_tool_names:
            while len(self.tool_usage_stats[tool_name]) < num_samples:
                self.tool_usage_stats[tool_name].append(0)
    
    def get_wandb_metrics(self, batch_size: int = None) -> Dict[str, float]:
        """
        生成用于WandB的指标字典
        
        Args:
            batch_size: 批次大小，如果不提供则自动从统计数据推断
            
        Returns:
            包含所有工具统计指标的字典
        """
        if batch_size is None:
            batch_size = max(len(usage_list) for usage_list in self.tool_usage_stats.values()) if self.tool_usage_stats else 0
        
        # 确保所有工具统计长度一致
        self.ensure_sample_count(batch_size)
        
        metrics = {}
        
        for tool_name in self.all_tool_names:
            usage_list = self.tool_usage_stats[tool_name]
            
            if usage_list:
                total_usage = sum(usage_list)
                mean_usage = np.mean(usage_list)
                max_usage = max(usage_list)
                
                # 计算使用率（使用该工具的样本比例）
                non_zero_count = sum(1 for count in usage_list if count > 0)
                usage_rate = non_zero_count / len(usage_list) if usage_list else 0.0
                
                metrics.update({
                    f"agent/tool_{tool_name}_total": float(total_usage),
                    f"agent/tool_{tool_name}_mean": float(mean_usage),
                    f"agent/tool_{tool_name}_max": float(max_usage),
                    f"agent/tool_{tool_name}_usage_rate": float(usage_rate),
                })
                
                # 只显示使用量较高的工具，避免日志过多
                if total_usage >= 5:
                    print(f"[TOOL METRICS] {tool_name}: total={total_usage:.1f}, mean={mean_usage:.3f}, rate={usage_rate:.3f}")
        
        return metrics
    
    def get_tensor_stats(self, target_device='cpu') -> Dict[str, torch.Tensor]:
        """
        生成用于添加到DataProto batch中的tensor统计信息
        
        Args:
            target_device: 目标设备
            
        Returns:
            包含工具使用统计tensor的字典
        """
        tensor_stats = {}
        
        # 确定批次大小
        batch_size = max(len(usage_list) for usage_list in self.tool_usage_stats.values()) if self.tool_usage_stats else 0
        self.ensure_sample_count(batch_size)
        
        for tool_name in self.all_tool_names:
            usage_list = self.tool_usage_stats[tool_name]
            if usage_list:
                # 创建tensor
                usage_tensor = torch.tensor(usage_list, dtype=torch.float32).to(target_device).unsqueeze(1)
                tensor_stats[f"tool_usage_{tool_name}"] = usage_tensor
        
        return tensor_stats
    
    def print_statistics_summary(self, prefix="TOOL STATS"):
        """
        打印统计摘要
        
        Args:
            prefix: 日志前缀
        """
        # 计算使用过的工具
        used_tools = []
        for tool_name in self.all_tool_names:
            total_usage = sum(self.tool_usage_stats[tool_name])
            if total_usage > 0:
                used_tools.append((tool_name, total_usage))
        
        if used_tools:
            print(f"\n[{prefix} SUMMARY] === 工具使用统计 ===")
            print(f"[{prefix} SUMMARY] 共有 {len(used_tools)} 个工具被使用:")
            
            # 按使用次数排序，只显示前10个最常用的工具
            used_tools.sort(key=lambda x: x[1], reverse=True)
            for tool_name, total_usage in used_tools[:10]:
                print(f"[{prefix} SUMMARY]   {tool_name}: {total_usage} 次")
            
            if len(used_tools) > 10:
                print(f"[{prefix} SUMMARY]   ... 还有 {len(used_tools)-10} 个工具")
            
            print(f"[{prefix} SUMMARY] === 统计结束 ===\n")
        else:
            print(f"\n[{prefix} SUMMARY] 本批次未使用任何工具\n")
    
    def extract_tool_usage_from_responses(self, responses: List[str]) -> None:
        """
        从响应字符串中提取工具使用信息
        
        Args:
            responses: 模型响应列表
        """
        import re
        import json
        
        for i, response in enumerate(responses):
            # 查找tool_call块
            tool_call_match = re.search(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', response, re.DOTALL)
            if tool_call_match:
                try:
                    tool_calls = json.loads(tool_call_match.group(1))
                    if isinstance(tool_calls, list):
                        for tool_call in tool_calls:
                            if isinstance(tool_call, dict) and 'name' in tool_call:
                                tool_name = tool_call['name']
                                self.record_tool_usage(tool_name, i)
                except json.JSONDecodeError:
                    continue
    
    def get_tool_stats_for_batch(self, responses: List[str], target_device='cpu') -> Tuple[Dict[str, torch.Tensor], Dict[str, float]]:
        """
        为一个批次的响应生成完整的工具统计信息
        
        Args:
            responses: 模型响应列表
            target_device: 目标设备
            
        Returns:
            tuple: (tensor_stats, wandb_metrics)
        """
        # 重置统计
        self.reset_statistics()
        
        # 从响应中提取工具使用
        self.extract_tool_usage_from_responses(responses)
        
        # 生成tensor统计和wandb指标
        tensor_stats = self.get_tensor_stats(target_device)
        wandb_metrics = self.get_wandb_metrics(len(responses))
        
        # 打印摘要
        self.print_statistics_summary()
        
        return tensor_stats, wandb_metrics


# 全局工具统计管理器实例
_global_tool_stats_manager = None

def get_tool_stats_manager(device='cpu') -> ToolStatisticsManager:
    """
    获取全局工具统计管理器实例（单例模式）
    
    Args:
        device: 设备
        
    Returns:
        ToolStatisticsManager实例
    """
    global _global_tool_stats_manager
    if _global_tool_stats_manager is None:
        _global_tool_stats_manager = ToolStatisticsManager(device)
    return _global_tool_stats_manager


def reset_global_tool_stats():
    """重置全局工具统计管理器"""
    global _global_tool_stats_manager
    if _global_tool_stats_manager is not None:
        _global_tool_stats_manager.reset_statistics()


# 便捷函数
def record_tool_usage(tool_name: str, sample_index: int = None):
    """记录工具使用的便捷函数"""
    manager = get_tool_stats_manager()
    manager.record_tool_usage(tool_name, sample_index)


def get_tool_wandb_metrics() -> Dict[str, float]:
    """获取工具WandB指标的便捷函数"""
    manager = get_tool_stats_manager()
    return manager.get_wandb_metrics()


def print_tool_stats_summary():
    """打印工具统计摘要的便捷函数"""
    manager = get_tool_stats_manager()
    manager.print_statistics_summary()
