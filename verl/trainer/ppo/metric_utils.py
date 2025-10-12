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
Metrics related to the PPO trainer.
"""

from collections import defaultdict
from functools import partial
from typing import Any, Callable, Dict, List

import numpy as np
import torch

from verl import DataProto


def reduce_metrics(metrics: Dict[str, List[Any]]) -> Dict[str, Any]:
    for key, val in metrics.items():
        metrics[key] = np.mean(val)
    return metrics


def _compute_response_info(batch: DataProto) -> Dict[str, Any]:
    response_length = batch.batch["responses"].shape[-1]

    prompt_mask = batch.batch["attention_mask"][:, :-response_length]
    response_mask = batch.batch["attention_mask"][:, -response_length:]

    prompt_length = prompt_mask.sum(-1).float()
    response_length = response_mask.sum(-1).float()  # (batch_size,)

    if 'action_mask' in batch.batch:
        action_mask = batch.batch['action_mask'][:, -batch.batch['responses'].shape[-1]:]
        obs_mask = response_mask * (1 - action_mask)
        obs_length = obs_mask.sum(-1).float()
    else:
        obs_length = torch.zeros_like(response_length)
    response_length -= obs_length

    return dict(
        response_mask=response_mask,
        prompt_length=prompt_length,
        response_length=response_length,
        obs_length=obs_length,
    )


def compute_data_metrics(batch: DataProto, use_critic: bool = True) -> Dict[str, Any]:
    # TODO: add response length
    sequence_score = batch.batch["token_level_scores"].sum(-1)
    sequence_reward = batch.batch["token_level_rewards"].sum(-1)

    advantages = batch.batch["advantages"]
    returns = batch.batch["returns"]

    max_response_length = batch.batch["responses"].shape[-1]
    prompt_mask = batch.batch['attention_mask'][:, :-max_response_length].bool()
    action_or_attn_mask = batch.batch['action_mask'] if 'action_mask' in batch.batch else batch.batch['attention_mask']
    response_mask = action_or_attn_mask[:, -max_response_length:].bool()

    max_prompt_length = prompt_mask.size(-1)

    response_info = _compute_response_info(batch)
    prompt_length = response_info["prompt_length"]
    response_length = response_info["response_length"]
    obs_length = response_info["obs_length"]

    valid_adv = torch.masked_select(advantages, response_mask)
    valid_returns = torch.masked_select(returns, response_mask)

    # 检查是否有有效的response（边界情况保护）
    has_valid_responses = valid_adv.numel() > 0
    
    if not has_valid_responses:
        print(f"[WARNING] No valid responses in batch! response_mask sum: {response_mask.sum().item()}")
        print(f"[WARNING] advantages shape: {advantages.shape}, response_mask shape: {response_mask.shape}")

    if use_critic:
        values = batch.batch["values"]
        valid_values = torch.masked_select(values, response_mask)
        if has_valid_responses:
            return_diff_var = torch.var(valid_returns - valid_values)
            return_var = torch.var(valid_returns)
        else:
            return_diff_var = torch.tensor(0.0)
            return_var = torch.tensor(1.0)

    metrics = {
        # score
        "critic/score/mean": torch.mean(sequence_score).detach().item(),
        "critic/score/max": torch.max(sequence_score).detach().item(),
        "critic/score/min": torch.min(sequence_score).detach().item(),
        # reward
        "critic/rewards/mean": torch.mean(sequence_reward).detach().item(),
        "critic/rewards/max": torch.max(sequence_reward).detach().item(),
        "critic/rewards/min": torch.min(sequence_reward).detach().item(),
        # adv (添加空tensor保护)
        "critic/advantages/mean": torch.mean(valid_adv).detach().item() if has_valid_responses else 0.0,
        "critic/advantages/max": torch.max(valid_adv).detach().item() if has_valid_responses else 0.0,
        "critic/advantages/min": torch.min(valid_adv).detach().item() if has_valid_responses else 0.0,
        # returns (添加空tensor保护)
        "critic/returns/mean": torch.mean(valid_returns).detach().item() if has_valid_responses else 0.0,
        "critic/returns/max": torch.max(valid_returns).detach().item() if has_valid_responses else 0.0,
        "critic/returns/min": torch.min(valid_returns).detach().item() if has_valid_responses else 0.0,
        **(
            {
                # values (添加空tensor保护)
                "critic/values/mean": torch.mean(valid_values).detach().item() if has_valid_responses else 0.0,
                "critic/values/max": torch.max(valid_values).detach().item() if has_valid_responses else 0.0,
                "critic/values/min": torch.min(valid_values).detach().item() if has_valid_responses else 0.0,
                # vf explained var
                "critic/vf_explained_var": (1.0 - return_diff_var / (return_var + 1e-5)).detach().item() if has_valid_responses else 0.0,
            }
            if use_critic
            else {}
        ),
        # response length

        "response_length/mean": torch.mean(response_length).detach().item(),
        "response_length/max": torch.max(response_length).detach().item(),
        "response_length/min": torch.min(response_length).detach().item(),
        "response_length/clip_ratio": torch.mean(torch.eq(response_length, max_response_length).float())
        .detach()
        .item(),

        # obs length
        'obs_length/mean': torch.mean(obs_length).detach().item(),
        'obs_length/min': torch.min(obs_length).detach().item(),
        'obs_length/max': torch.max(obs_length).detach().item(),

        # prompt length
        "prompt_length/mean": torch.mean(prompt_length).detach().item(),
        "prompt_length/max": torch.max(prompt_length).detach().item(),
        "prompt_length/min": torch.min(prompt_length).detach().item(),
        "prompt_length/clip_ratio": torch.mean(torch.eq(prompt_length, max_prompt_length).float()).detach().item(),
    }
    return metrics


def compute_timing_metrics(batch: DataProto, timing_raw: Dict[str, float]) -> Dict[str, Any]:
    response_info = _compute_response_info(batch)
    num_prompt_tokens = torch.sum(response_info["prompt_length"]).item()
    num_response_tokens = torch.sum(response_info["response_length"]).item()
    num_overall_tokens = num_prompt_tokens + num_response_tokens

    num_tokens_of_section = {
        "gen": num_response_tokens,
        **{name: num_overall_tokens for name in ["ref", "values", "adv", "update_critic", "update_actor"]},
    }

    return {
        **{f"timing_s/{name}": value for name, value in timing_raw.items()},
        **{
            f"timing_per_token_ms/{name}": timing_raw[name] * 1000 / num_tokens_of_section[name]
            for name in set(num_tokens_of_section.keys()) & set(timing_raw.keys())
        },
    }


def compute_throughout_metrics(batch: DataProto, timing_raw: Dict[str, float], n_gpus: int) -> Dict[str, Any]:
    total_num_tokens = sum(batch.meta_info["global_token_num"])
    time = timing_raw["step"]
    # estimated_flops, promised_flops = flops_function.estimate_flops(num_tokens, time)
    # f'Actual TFLOPs/s/GPU​': estimated_flops/(n_gpus),
    # f'Theoretical TFLOPs/s/GPU​': promised_flops,
    return {
        "perf/total_num_tokens": total_num_tokens,
        "perf/time_per_step": time,
        "perf/throughput": total_num_tokens / (time * n_gpus),
    }


def compute_agent_metrics(batch: DataProto):
    if 'tool_cnt' not in batch.batch.keys():
        return {}

    tool_cnt_tensor = batch.batch.pop('tool_cnt').detach().cpu()
    return {
        "agent/tool_call_mean": torch.mean(tool_cnt_tensor).item(),
        "agent/tool_call_max": torch.max(tool_cnt_tensor).item(),
        "agent/tool_call_min": torch.min(tool_cnt_tensor).item(),
    }


def bootstrap_metric(
    data: list[Any],
    subset_size: int,
    reduce_fns: list[Callable[[np.ndarray], float]],
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> list[tuple[float, float]]:
    np.random.seed(seed)

    bootstrap_metric_lsts = [[] for _ in range(len(reduce_fns))]
    for _ in range(n_bootstrap):
        bootstrap_idxs = np.random.choice(len(data), size=subset_size, replace=True)
        bootstrap_data = [data[i] for i in bootstrap_idxs]
        for i, reduce_fn in enumerate(reduce_fns):
            bootstrap_metric_lsts[i].append(reduce_fn(bootstrap_data))
    return [(np.mean(lst), np.std(lst)) for lst in bootstrap_metric_lsts]


def calc_maj_val(data: list[dict[str, Any]], vote_key: str, val_key: str) -> float:
    """
    Calculate the majority voting metric
    """
    vote2vals = defaultdict(list)
    for d in data:
        vote2vals[d[vote_key]].append(d[val_key])

    vote2cnt = {k: len(v) for k, v in vote2vals.items()}
    maj_vote = max(vote2cnt, key=vote2cnt.get)

    maj_val = vote2vals[maj_vote][0]

    return maj_val


def compute_reward_component_metrics(reward_extra_infos_dict: dict[str, list]) -> dict[str, float]:
    """
    计算奖励组成部分的统计指标（格式奖励、图像质量奖励、退化类型奖励）
    支持数据集1 (image_restoration) 和数据集2 (visual_toolbox_v2)
    
    Args:
        reward_extra_infos_dict: 包含各种奖励信息的字典
        
    Returns:
        包含统计指标的字典
    """
    metrics = {}
    
    # 格式奖励统计 - 支持数据集1 (ir_format_score) 和数据集2 (format_reward)
    format_score_key = None
    if 'ir_format_score' in reward_extra_infos_dict:
        format_score_key = 'ir_format_score'  # 数据集1
    elif 'format_reward' in reward_extra_infos_dict:
        format_score_key = 'format_reward'  # 数据集2
    
    if format_score_key:
        format_scores = reward_extra_infos_dict[format_score_key]
        if len(format_scores) > 0:
            # 计算格式正确率（format_score = 1.0 的比例）
            format_correct_count = sum(1 for s in format_scores if s == 1.0)
            format_violation_count = sum(1 for s in format_scores if s == -1.0)
            metrics['reward/format_correct_ratio'] = format_correct_count / len(format_scores)
            metrics['reward/format_violation_ratio'] = format_violation_count / len(format_scores)
            metrics['reward/format_score_mean'] = np.mean(format_scores)
    
    # 准确性奖励统计 - 支持数据集1 (quality_score) 和数据集2 (acc_reward)
    # 数据集1: ir_quality_score / ir_accuracy_score (图像质量: 0.0 - 1.0)
    # 数据集2: acc_reward (答案准确性: 0.0 或 1.0)
    quality_score_key = None
    if 'ir_quality_score' in reward_extra_infos_dict:
        quality_score_key = 'ir_quality_score'  # 数据集1
    elif 'ir_accuracy_score' in reward_extra_infos_dict:
        quality_score_key = 'ir_accuracy_score'  # 数据集1 (向后兼容)
    elif 'acc_reward' in reward_extra_infos_dict:
        quality_score_key = 'acc_reward'  # 数据集2
    
    if quality_score_key:
        quality_scores = reward_extra_infos_dict[quality_score_key]
        if len(quality_scores) > 0:
            metrics['reward/accuracy_mean'] = np.mean(quality_scores)
            metrics['reward/accuracy_max'] = np.max(quality_scores)
            metrics['reward/accuracy_min'] = np.min(quality_scores)
            metrics['reward/accuracy_std'] = np.std(quality_scores)
            # 添加准确率（对于数据集2特别重要）
            if quality_score_key == 'acc_reward':
                correct_count = sum(1 for s in quality_scores if s == 1.0)
                metrics['reward/accuracy_ratio'] = correct_count / len(quality_scores)
    
    # 退化类型奖励统计 (degradation_type_score: 0.0 - 1.0)
    if 'ir_degradation_type_score' in reward_extra_infos_dict:
        degradation_type_scores = reward_extra_infos_dict['ir_degradation_type_score']
        if len(degradation_type_scores) > 0:
            # 过滤掉0.0的分数（这些是clean样本或未启用时的默认值）
            non_zero_scores = [s for s in degradation_type_scores if s > 0.0]
            
            if len(non_zero_scores) > 0:
                # 只对有效样本统计（退化类型奖励启用且非clean样本）
                metrics['reward/degradation_type_score_mean'] = np.mean(non_zero_scores)
                metrics['reward/degradation_type_score_max'] = np.max(non_zero_scores)
                metrics['reward/degradation_type_score_min'] = np.min(non_zero_scores)
                metrics['reward/degradation_type_score_std'] = np.std(non_zero_scores)
                metrics['reward/degradation_type_valid_samples'] = len(non_zero_scores)
                metrics['reward/degradation_type_valid_ratio'] = len(non_zero_scores) / len(degradation_type_scores)
            
            # 也记录包含所有样本的统计（包括0分）
            metrics['reward/degradation_type_score_mean_all'] = np.mean(degradation_type_scores)
    
    # 有参考图像质量指标统计 (SSIM, LPIPS, PSNR)
    # 这些指标从reward_extra_infos_dict中提取（如果有的话）
    # 注意：只统计>0的值（0表示工具未执行或计算失败）
    
    # SSIM统计 (0.0 - 1.0, 越高越好)
    if 'ssim_score_ref' in reward_extra_infos_dict:
        ssim_scores = reward_extra_infos_dict['ssim_score_ref']
        if len(ssim_scores) > 0:
            valid_ssim = [s for s in ssim_scores if s > 0.0]
            if len(valid_ssim) > 0:
                metrics['reward/ssim_mean'] = np.mean(valid_ssim)
                metrics['reward/ssim_max'] = np.max(valid_ssim)
                metrics['reward/ssim_min'] = np.min(valid_ssim)
                metrics['reward/ssim_std'] = np.std(valid_ssim)
                metrics['reward/ssim_valid_samples'] = len(valid_ssim)
    
    # LPIPS统计 (0.0 - 1.0, 越低越好)
    if 'lpips_score_ref' in reward_extra_infos_dict:
        lpips_scores = reward_extra_infos_dict['lpips_score_ref']
        if len(lpips_scores) > 0:
            valid_lpips = [s for s in lpips_scores if s > 0.0]
            if len(valid_lpips) > 0:
                metrics['reward/lpips_mean'] = np.mean(valid_lpips)
                metrics['reward/lpips_max'] = np.max(valid_lpips)
                metrics['reward/lpips_min'] = np.min(valid_lpips)
                metrics['reward/lpips_std'] = np.std(valid_lpips)
                metrics['reward/lpips_valid_samples'] = len(valid_lpips)
    
    # PSNR统计 (通常10-50, 越高越好)
    if 'psnr_score_ref' in reward_extra_infos_dict:
        psnr_scores = reward_extra_infos_dict['psnr_score_ref']
        if len(psnr_scores) > 0:
            valid_psnr = [s for s in psnr_scores if s > 0.0]
            if len(valid_psnr) > 0:
                metrics['reward/psnr_mean'] = np.mean(valid_psnr)
                metrics['reward/psnr_max'] = np.max(valid_psnr)
                metrics['reward/psnr_min'] = np.min(valid_psnr)
                metrics['reward/psnr_std'] = np.std(valid_psnr)
                metrics['reward/psnr_valid_samples'] = len(valid_psnr)
    
    return metrics


def process_validation_metrics(
    data_sources: list[str], sample_inputs: list[str], infos_dict: dict[str, list[Any]], seed: int = 42
) -> dict[str, dict[str, dict[str, float]]]:
    """Process validation metrics into a structured format.

    Args:
        data_sources: Array of data source identifiers for each sample
        sample_inputs: List of input prompts
        infos_dict: variable name -> list of values for each sample

    Returns:
        dict[str, dict[str, dict[str, float]]]: data source -> variable name -> metric value
    """
    # Group metrics by data source, prompt and variable
    data_src2prompt2var2vals = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for sample_idx, data_source in enumerate(data_sources):
        prompt = sample_inputs[sample_idx]
        var2vals = data_src2prompt2var2vals[data_source][prompt]
        for var_name, var_vals in infos_dict.items():
            var2vals[var_name].append(var_vals[sample_idx])

    # Calculate metrics for each group
    data_src2prompt2var2metric = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for data_source, prompt2var2vals in data_src2prompt2var2vals.items():
        for prompt, var2vals in prompt2var2vals.items():
            for var_name, var_vals in var2vals.items():
                if isinstance(var_vals[0], str):
                    continue
                metric = {}
                n_resps = len(var_vals)
                metric[f"mean@{n_resps}"] = np.mean(var_vals)
                metric[f"std@{n_resps}"] = np.std(var_vals)

                ns = []
                n = 2
                while n < n_resps:
                    ns.append(n)
                    n *= 2
                ns.append(n_resps)

                for n in ns:
                    # Best/Worst-of-N
                    [(bon_mean, bon_std), (won_mean, won_std)] = bootstrap_metric(
                        data=var_vals, subset_size=n, reduce_fns=[np.max, np.min], seed=seed
                    )
                    metric[f"best@{n}/mean"], metric[f"best@{n}/std"] = bon_mean, bon_std
                    metric[f"worst@{n}/mean"], metric[f"worst@{n}/std"] = won_mean, won_std
                    # Majority voting
                    if var2vals.get("pred", None) is not None:
                        vote_data = [{"val": val, "pred": pred} for val, pred in zip(var_vals, var2vals["pred"])]
                        [(maj_n_mean, maj_n_std)] = bootstrap_metric(
                            data=vote_data,
                            subset_size=n,
                            reduce_fns=[partial(calc_maj_val, vote_key="pred", val_key="val")],
                            seed=seed,
                        )
                        metric[f"maj@{n}/mean"], metric[f"maj@{n}/std"] = maj_n_mean, maj_n_std

                data_src2prompt2var2metric[data_source][prompt][var_name] = metric

    # Aggregate metrics across prompts
    data_src2var2metric2prompt_vals = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for data_source, prompt2var2metric in data_src2prompt2var2metric.items():
        for prompt, var2metric in prompt2var2metric.items():
            for var_name, metric in var2metric.items():
                for metric_name, metric_val in metric.items():
                    data_src2var2metric2prompt_vals[data_source][var_name][metric_name].append(metric_val)

    data_src2var2metric2val = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for data_source, var2metric2prompt_vals in data_src2var2metric2prompt_vals.items():
        for var_name, metric2prompt_vals in var2metric2prompt_vals.items():
            for metric_name, prompt_vals in metric2prompt_vals.items():
                data_src2var2metric2val[data_source][var_name][metric_name] = np.mean(prompt_vals)

    return data_src2var2metric2val
