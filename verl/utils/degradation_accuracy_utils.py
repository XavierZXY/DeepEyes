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
退化类型预测准确率计算工具
"""

import json
import re
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


def extract_predicted_degradation_types_from_conversation(conversation_history: list) -> List[str]:
    """
    从conversation_history中提取预测的退化类型
    
    Args:
        conversation_history: 对话历史列表
        
    Returns:
        预测的退化类型列表（去重）
    """
    # 工具到退化类型的映射（与tracking_image_utils.py中保持一致）
    tool_to_degradation = {
        "swinir_denoising": "noise", "mprnet_denoising": "noise",
        "restormer_motion_deblurring": "motion blur", "mprnet_motion_deblurring": "motion blur",
        "xrestormer_motion_deblurring": "motion blur", "restormer_defocus_deblurring": "defocus blur",
        "drbnet_defocus_deblurring": "defocus blur", "restormer_deraining": "rain",
        "mprnet_deraining": "rain", "xrestormer_deraining": "rain",
        "swinir_jpeg_artifact_removal": "jpeg compression artifact",
        "fbcnn_jpeg_artifact_removal": "jpeg compression artifact",
        "swinir_super_resolution": "low resolution", "dehazeformer_dehaze": "haze",
        "constant_shift": "dark", "gamma_correction": "dark", "histogram_equalization": "dark",
    }
    
    predicted_types = []
    
    if not conversation_history or not isinstance(conversation_history, list):
        return predicted_types
    
    for turn in conversation_history:
        if not isinstance(turn, dict):
            continue
            
        response = turn.get('response', '')
        if '<tool_call>' in response and '</tool_call>' in response:
            try:
                tool_match = re.search(r'<tool_call>(.*?)</tool_call>', response, re.DOTALL)
                if tool_match:
                    tools = json.loads(tool_match.group(1).strip())
                    if isinstance(tools, list):
                        for tool_dict in tools:
                            if isinstance(tool_dict, dict):
                                tool_name = tool_dict.get('name', '')
                                deg_type = tool_to_degradation.get(tool_name, None)
                                if deg_type and deg_type not in predicted_types:
                                    predicted_types.append(deg_type)
                    elif isinstance(tools, dict):
                        tool_name = tools.get('name', '')
                        deg_type = tool_to_degradation.get(tool_name, None)
                        if deg_type and deg_type not in predicted_types:
                            predicted_types.append(deg_type)
            except:
                pass
    
    return predicted_types


def extract_ground_truth_degradation_info(reward_model: list) -> Tuple[List[str], List[str]]:
    """
    从reward_model中提取GT退化类型和等级
    
    Args:
        reward_model: reward_model数组，格式如：
            [
                {"degradation_type": "dark", "degradation_level": "high"},
                {"degradation_type": "noise", "degradation_level": "low"}
            ]
            
    Returns:
        (degradation_types, degradation_levels)
    """
    degradation_types = []
    degradation_levels = []
    
    if not reward_model or not isinstance(reward_model, list):
        return degradation_types, degradation_levels
    
    for item in reward_model:
        if isinstance(item, dict):
            deg_type = item.get('degradation_type', '')
            deg_level = item.get('degradation_level', '')
            if deg_type:
                degradation_types.append(deg_type)
            if deg_level:
                degradation_levels.append(deg_level)
    
    return degradation_types, degradation_levels


def compute_degradation_accuracy(
    conversation_histories: List,
    reward_models: List,
    env_names: List
) -> Dict[str, float]:
    """
    计算退化类型预测准确率
    
    Args:
        conversation_histories: 对话历史列表
        reward_models: reward_model列表（从数据集获取）
        env_names: 环境名称列表
        
    Returns:
        包含各种准确率指标的字典
    """
    metrics = {}
    
    # 收集所有样本的预测和GT
    samples = []
    for idx in range(len(conversation_histories)):
        # 跳过clean样本（env_name为"clean"）
        env_name = env_names[idx] if idx < len(env_names) else ""
        if env_name and env_name.strip().lower() == "clean":
            continue
        
        # 提取预测的退化类型
        conv_hist = conversation_histories[idx] if idx < len(conversation_histories) else None
        predicted_types = extract_predicted_degradation_types_from_conversation(conv_hist)
        
        # 提取GT退化类型和等级
        reward_model = reward_models[idx] if idx < len(reward_models) else []
        gt_types, gt_levels = extract_ground_truth_degradation_info(reward_model)
        
        if not gt_types:
            continue
        
        # 记录样本信息
        samples.append({
            'predicted': set(predicted_types),
            'gt': set(gt_types),
            'gt_types': gt_types,
            'gt_levels': gt_levels
        })
    
    if not samples:
        print("[WARNING] No valid samples for accuracy computation")
        return metrics
    
    # 1. 计算总体准确率
    total_correct = sum(1 for s in samples if s['predicted'] == s['gt'])
    metrics['val-acc/overall_accuracy'] = total_correct / len(samples)
    metrics['val-acc/total_samples'] = len(samples)
    
    # 2. 按退化类型统计准确率（不考虑等级）
    type_stats = defaultdict(lambda: {'correct': 0, 'total': 0})
    
    for sample in samples:
        for gt_type in sample['gt']:
            type_stats[gt_type]['total'] += 1
            if gt_type in sample['predicted']:
                type_stats[gt_type]['correct'] += 1
    
    for deg_type, stats in type_stats.items():
        if stats['total'] > 0:
            accuracy = stats['correct'] / stats['total']
            # 替换特殊字符，确保wandb可以显示
            safe_type_name = deg_type.replace(' ', '_').replace('/', '_')
            metrics[f'val-acc/by_type/{safe_type_name}'] = accuracy
            metrics[f'val-acc/by_type/{safe_type_name}_samples'] = stats['total']
    
    # 3. 按退化等级和类型统计准确率
    level_type_stats = defaultdict(lambda: {'correct': 0, 'total': 0})
    
    for sample in samples:
        # 为每个GT类型创建(type, level)对
        for i, gt_type in enumerate(sample['gt_types']):
            gt_level = sample['gt_levels'][i] if i < len(sample['gt_levels']) else 'unknown'
            key = f"{gt_type}_{gt_level}"
            
            level_type_stats[key]['total'] += 1
            if gt_type in sample['predicted']:
                level_type_stats[key]['correct'] += 1
    
    for key, stats in level_type_stats.items():
        if stats['total'] > 0:
            accuracy = stats['correct'] / stats['total']
            # 替换特殊字符
            safe_key = key.replace(' ', '_').replace('/', '_')
            metrics[f'val-acc/by_level_and_type/{safe_key}'] = accuracy
            metrics[f'val-acc/by_level_and_type/{safe_key}_samples'] = stats['total']
    
    # 4. 按等级统计准确率（汇总所有类型）
    level_stats = defaultdict(lambda: {'correct': 0, 'total': 0})
    
    for sample in samples:
        for i, gt_type in enumerate(sample['gt_types']):
            gt_level = sample['gt_levels'][i] if i < len(sample['gt_levels']) else 'unknown'
            
            level_stats[gt_level]['total'] += 1
            if gt_type in sample['predicted']:
                level_stats[gt_level]['correct'] += 1
    
    for level, stats in level_stats.items():
        if stats['total'] > 0:
            accuracy = stats['correct'] / stats['total']
            metrics[f'val-acc/by_level/{level}'] = accuracy
            metrics[f'val-acc/by_level/{level}_samples'] = stats['total']
    
    # 打印调试信息
    print(f"\n[VAL ACC] Computed accuracy metrics for {len(samples)} samples:")
    print(f"  Overall Accuracy: {metrics['val-acc/overall_accuracy']:.3f}")
    print(f"  By Type:")
    for deg_type in sorted(type_stats.keys()):
        safe_type = deg_type.replace(' ', '_').replace('/', '_')
        acc = metrics.get(f'val-acc/by_type/{safe_type}', 0)
        print(f"    {deg_type}: {acc:.3f} ({type_stats[deg_type]['correct']}/{type_stats[deg_type]['total']})")
    
    return metrics


# 测试代码
if __name__ == "__main__":
    print("=" * 80)
    print("退化类型准确率计算测试")
    print("=" * 80)
    
    # 测试数据
    test_conversation_histories = [
        # Sample 0: 正确预测
        [
            {'response': '<tool_call>[{"name": "swinir_denoising"}]</tool_call>'}
        ],
        # Sample 1: 正确预测（brightening）
        [
            {'response': '<tool_call>[{"name": "constant_shift", "arguments": {"shift": 40}}]</tool_call>'}
        ],
        # Sample 2: 未预测
        [
            {'response': '<answer>{"restoration_log": []}</answer>'}
        ],
        # Sample 3: 预测错误
        [
            {'response': '<tool_call>[{"name": "restormer_deraining"}]</tool_call>'}
        ],
        # Sample 4: 多退化类型，正确
        [
            {'response': '<tool_call>[{"name": "swinir_denoising"}]</tool_call>'},
            {'response': '<tool_call>[{"name": "histogram_equalization"}]</tool_call>'}
        ],
    ]
    
    test_reward_models = [
        [{"degradation_type": "noise", "degradation_level": "high"}],
        [{"degradation_type": "dark", "degradation_level": "low"}],
        [{"degradation_type": "motion blur", "degradation_level": "medium"}],
        [{"degradation_type": "noise", "degradation_level": "low"}],
        [
            {"degradation_type": "noise", "degradation_level": "high"},
            {"degradation_type": "dark", "degradation_level": "medium"}
        ],
    ]
    
    test_env_names = ["", "", "", "", ""]
    
    # 计算准确率
    metrics = compute_degradation_accuracy(
        conversation_histories=test_conversation_histories,
        reward_models=test_reward_models,
        env_names=test_env_names
    )
    
    print("\n返回的指标:")
    for key, value in sorted(metrics.items()):
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 80)

