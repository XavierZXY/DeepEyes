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

from collections import defaultdict

import torch

from verl import DataProto
from verl.utils.reward_score import _default_compute_score

import json
import datetime

class NaiveRewardManager:
    """The reward manager."""

    def __init__(self, tokenizer, num_examine, compute_score=None, reward_fn_key="data_source") -> None:
        self.tokenizer = tokenizer
        self.num_examine = num_examine  # the number of batches of decoded responses to print to the console
        self.compute_score = compute_score or _default_compute_score
        self.reward_fn_key = reward_fn_key

        self.step_cnt = 0

    def __call__(self, data: DataProto, return_dict=False):
        """We will expand this function gradually based on the available datasets"""

        # If there is rm score, we directly return rm score. Otherwise, we compute via rm_score_fn
        if "rm_scores" in data.batch.keys():
            if return_dict:
                return {"reward_tensor": data.batch["rm_scores"]}
            else:
                return data.batch["rm_scores"]

        reward_tensor = torch.zeros_like(data.batch["responses"], dtype=torch.float32)
        reward_extra_info = defaultdict(list)
        
        # 统计图像处理和奖励相关指标
        image_processing_stats = {
            'total_samples': 0,
            'samples_with_image_history': 0,
            'samples_with_processed_images': 0,
            'image_quality_reward_zero_count': 0,
            'image_quality_reward_positive_count': 0,
            'image_restoration_v2_samples': 0
        }

        action_or_attn_mask = data.batch['action_mask'] if 'action_mask' in data.batch.keys() else data.batch['attention_mask']
        if 'env_reward' in data.batch.keys():
            reward_tensor += data.batch['env_reward']
            print(f' [DEBUG reward] mean={reward_tensor.mean().item()}, min={reward_tensor.min().item()}, max={reward_tensor.max().item()}')

        already_print_data_sources = {}

        for i in range(len(data)):
            data_item = data[i]  # DataProtoItem
            image_processing_stats['total_samples'] += 1

            prompt_ids = data_item.batch["prompts"]

            prompt_length = prompt_ids.shape[-1]

            valid_prompt_length = data_item.batch["attention_mask"][:prompt_length].sum()
            valid_prompt_ids = prompt_ids[-valid_prompt_length:]

            response_ids = data_item.batch["responses"]
            valid_response_length = data_item.batch["attention_mask"][prompt_length:].sum()
            valid_response_ids = response_ids[:valid_response_length]

            # decode
            prompt_str = self.tokenizer.decode(valid_prompt_ids)
            response_str = self.tokenizer.decode(valid_response_ids)

            # Handle different ground truth formats
            if "reward_model" in data_item.non_tensor_batch and isinstance(data_item.non_tensor_batch["reward_model"], dict):
                ground_truth = data_item.non_tensor_batch["reward_model"]["ground_truth"]
            else:
                # For image restoration task, construct ground truth from available data
                ground_truth = {
                    "reward_model": data_item.non_tensor_batch.get("reward_model", []),
                    "env_name": data_item.non_tensor_batch.get("env_name", "")
                }

            data_source = data_item.non_tensor_batch[self.reward_fn_key]

            extra_info = data_item.non_tensor_batch.get("extra_info", None)
            
            # 初始化样本级别的统计标志
            has_processed_image = False
            
            # 统计图像复原任务相关指标  
            if data_source in ["image_restoration_v2"]:
                
                # 检查是否有图像历史信息
                if "image_history_list" in data.non_tensor_batch:
                    image_history_list = data.non_tensor_batch["image_history_list"]
                    
                    if i < len(image_history_list):
                        image_history = image_history_list[i]
                        image_processing_stats['samples_with_image_history'] += 1
                        
                        # 检查是否有被工具处理的图像（长度>1表示有处理后的图像）
                        if isinstance(image_history, (list, tuple)) and len(image_history) > 1:
                            image_processing_stats['samples_with_processed_images'] += 1
                            has_processed_image = True
                        elif hasattr(image_history, 'size') and image_history.size > 1:  # numpy数组
                            image_processing_stats['samples_with_processed_images'] += 1
                            has_processed_image = True
                        
                        # 将图像历史信息添加到extra_info中
                        if extra_info is None:
                            extra_info = {}
                        extra_info["image_history"] = image_history

            score = self.compute_score(
                data_source=data_source,
                solution_str=response_str,
                ground_truth=ground_truth,
                extra_info=extra_info,
            )
            
            # 为所有样本添加统计标志（确保批次大小一致性）
            reward_value = score if isinstance(score, (int, float)) else score.get("score", 0.0)
            
            # 为图像复原任务设置特殊标志，其他任务设置默认值
            if data_source in ["image_restoration_v2"]:
                image_processing_stats['image_restoration_v2_samples'] += 1
                reward_extra_info['ir_has_processed_image'].append(1.0 if has_processed_image else 0.0)
                reward_extra_info['ir_quality_reward_zero'].append(1.0 if reward_value == 0.0 else 0.0)
                reward_extra_info['ir_quality_reward_positive'].append(1.0 if reward_value > 0.0 else 0.0)
                reward_extra_info['ir_total_reward_value'].append(reward_value)
                
                # 添加退化类型奖励（从score字典中提取，仅用于监控）
                if isinstance(score, dict):
                    degradation_score = score.get("degradation_order_score", 0.0)
                    format_score = score.get("format_score", 0.0)
                    accuracy_score = score.get("accuracy_score", 0.0)
                    
                    # 检查是否为clean样本
                    is_clean_sample = score.get("is_clean_sample", 0.0)
                    reward_extra_info['ir_is_clean_sample'].append(is_clean_sample)
                    
                    # 只对clean样本收集clean_accuracy，但为了保持数组长度一致，
                    # 我们需要为所有样本都添加clean_accuracy（非clean样本设为-1表示不适用）
                    if is_clean_sample > 0:
                        clean_accuracy = score.get("clean_accuracy", 0.0)
                        reward_extra_info['ir_clean_accuracy'].append(clean_accuracy)
                    else:
                        # 非clean样本设为-1，表示不适用（在metric_utils中会被过滤掉）
                        reward_extra_info['ir_clean_accuracy'].append(-1.0)
                        
                    # 添加格式奖励和准确性奖励的单独统计
                    reward_extra_info['ir_format_score'].append(format_score)
                    reward_extra_info['ir_accuracy_score'].append(accuracy_score)
                    
                    # 添加图像质量分数（新字段名，与accuracy_score相同但语义更清晰）
                    quality_score = score.get("quality_score", accuracy_score)
                    reward_extra_info['ir_quality_score'].append(quality_score)
                    
                    # 添加退化类型分数（用于统计mean/min/max/std）
                    degradation_type_score = score.get("degradation_type_score", 0.0)
                    reward_extra_info['ir_degradation_type_score'].append(degradation_type_score)
                    
                    # 添加退化类型信息（用于wandb展示）
                    degradation_type = score.get("degradation_type", "unknown")
                    reward_extra_info['degradation_type'].append(degradation_type)
                    # 如果有完整的退化类型列表也保存
                    if "degradation_types_all" in score:
                        reward_extra_info['degradation_types_all'].append(score.get("degradation_types_all"))
                else:
                    degradation_score = 0.0
                    reward_extra_info['ir_is_clean_sample'].append(0.0)
                    reward_extra_info['ir_clean_accuracy'].append(-1.0)
                    reward_extra_info['ir_format_score'].append(0.0)
                    reward_extra_info['ir_accuracy_score'].append(0.0)
                    reward_extra_info['ir_quality_score'].append(0.0)
                    reward_extra_info['ir_degradation_type_score'].append(0.0)
                    reward_extra_info['degradation_type'].append("unknown")
                reward_extra_info['ir_degradation_order_score'].append(degradation_score)
                
                # 统计总奖励分数（包含格式+图像质量）
                if reward_value == 0.0:
                    image_processing_stats['image_quality_reward_zero_count'] += 1
                else:
                    image_processing_stats['image_quality_reward_positive_count'] += 1
            else:
                # 为非图像复原任务添加默认值，确保批次大小一致
                reward_extra_info['ir_has_processed_image'].append(0.0)
                reward_extra_info['ir_quality_reward_zero'].append(0.0)
                reward_extra_info['ir_quality_reward_positive'].append(0.0)
                reward_extra_info['ir_total_reward_value'].append(0.0)
                reward_extra_info['ir_degradation_order_score'].append(0.0)
                reward_extra_info['ir_is_clean_sample'].append(0.0)
                reward_extra_info['ir_clean_accuracy'].append(-1.0)  # 非图像复原任务也需要添加以保持数组长度一致
                reward_extra_info['ir_format_score'].append(0.0)
                reward_extra_info['ir_accuracy_score'].append(0.0)
                reward_extra_info['ir_quality_score'].append(0.0)
                reward_extra_info['ir_degradation_type_score'].append(0.0)

            if isinstance(score, dict):
                reward = score["score"]
                # Store the information including original reward
                # 跳过已经在图像复原任务中特殊处理过的键，避免重复添加
                skip_keys = {'degradation_type', 'degradation_types_all', 'degradation_order_score', 
                            'format_score', 'accuracy_score', 'is_clean_sample', 'clean_accuracy'} if data_source in ["image_restoration_v2"] else set()
                for key, value in score.items():
                    if key not in skip_keys:
                        reward_extra_info[key].append(value)
                # 调试：检查字典中的键
                if i < 3:  # 只打印前3个样本
                    print(f"[DEBUG] 样本{i} score字典键: {list(score.keys())}")
            else:
                reward = score
                if i < 3:
                    print(f"[DEBUG] 样本{i} score类型: {type(score)}, 值: {score}")
                
                # 为了确保batch size一致性，当score不是字典时，也需要为可能的字典键添加默认值
                # 但这需要知道所有可能的键，这在当前设计下很困难
                # 最好的方法是确保所有奖励函数都返回一致的格式

            reward_tensor[i, valid_response_length - 1] += reward

            # eos_idx = torch.nonzero(action_or_attn_mask[i, prompt_length: prompt_length + valid_response_length])[-1]
            # reward_tensor[i, eos_idx] = score

            if data_source not in already_print_data_sources:
                already_print_data_sources[data_source] = 0

            if already_print_data_sources[data_source] < self.num_examine:
                already_print_data_sources[data_source] += 1
                print("[prompt]", prompt_str)
                print("[response]", response_str)
                print("[ground_truth]", ground_truth)
                if isinstance(score, dict):
                    for key, value in score.items():
                        print(f"[{key}]", value)
                else:
                    print("[score]", score)

            self.step_cnt += 1

        # 检查reward_extra_info中各数组的长度一致性
        total_len = len(data)
        print(f"[DEBUG] 检查reward_extra_info数组长度一致性 (期望长度: {total_len}):")
        for key, values in reward_extra_info.items():
            actual_len = len(values)
            if actual_len != total_len:
                print(f"[ERROR] {key}: 长度{actual_len} != 期望{total_len}")
            elif total_len <= 5:  # 只在小批次时显示详细信息
                print(f"[DEBUG] {key}: 长度{actual_len} ✓")
        
        # 计算和输出图像处理统计信息
        if image_processing_stats['total_samples'] > 0:
            processed_ratio = image_processing_stats['samples_with_processed_images'] / max(image_processing_stats['image_restoration_v2_samples'], 1)
            zero_reward_ratio = image_processing_stats['image_quality_reward_zero_count'] / max(image_processing_stats['image_restoration_v2_samples'], 1)
            
            print(f"[STATS] 图像处理统计:")
            print(f"[STATS]   总样本数: {image_processing_stats['total_samples']}")
            print(f"[STATS]   图像复原任务样本数: {image_processing_stats['image_restoration_v2_samples']}")
            print(f"[STATS]   有图像历史的样本数: {image_processing_stats['samples_with_image_history']}")
            print(f"[STATS]   有被工具处理图像的样本数: {image_processing_stats['samples_with_processed_images']}")
            print(f"[STATS]   被工具处理的样本比率: {processed_ratio:.3f}")
            print(f"[STATS]   总奖励为0的样本数: {image_processing_stats['image_quality_reward_zero_count']}")
            print(f"[STATS]   总奖励>0的样本数: {image_processing_stats['image_quality_reward_positive_count']}")
            print(f"[STATS]   总奖励为0的比例: {zero_reward_ratio:.3f}")
            print(f"[STATS]   说明: 总奖励 = 格式奖励(30%) + 图像质量奖励(70%)")
            
            # 注意：不将统计信息添加到reward_extra_info中，因为这些是全局统计，不是按样本的
            # 这些统计信息会在日志中显示，不需要传递给wandb
            # 如果需要wandb记录，应该在训练器层面处理这些全局统计

        if return_dict:
            return {
                "reward_tensor": reward_tensor,
                "reward_extra_info": reward_extra_info,
            }
        else:
            return reward_tensor
