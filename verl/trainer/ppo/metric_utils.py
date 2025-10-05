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

    if use_critic:
        values = batch.batch["values"]
        valid_values = torch.masked_select(values, response_mask)
        return_diff_var = torch.var(valid_returns - valid_values)
        return_var = torch.var(valid_returns)

    metrics = {
        # score
        "critic/score/mean": torch.mean(sequence_score).detach().item(),
        "critic/score/max": torch.max(sequence_score).detach().item(),
        "critic/score/min": torch.min(sequence_score).detach().item(),
        # reward
        "critic/rewards/mean": torch.mean(sequence_reward).detach().item(),
        "critic/rewards/max": torch.max(sequence_reward).detach().item(),
        "critic/rewards/min": torch.min(sequence_reward).detach().item(),
        # adv
        "critic/advantages/mean": torch.mean(valid_adv).detach().item(),
        "critic/advantages/max": torch.max(valid_adv).detach().item(),
        "critic/advantages/min": torch.min(valid_adv).detach().item(),
        # returns
        "critic/returns/mean": torch.mean(valid_returns).detach().item(),
        "critic/returns/max": torch.max(valid_returns).detach().item(),
        "critic/returns/min": torch.min(valid_returns).detach().item(),
        **(
            {
                # values
                "critic/values/mean": torch.mean(valid_values).detach().item(),
                "critic/values/max": torch.max(valid_values).detach().item(),
                "critic/values/min": torch.min(valid_values).detach().item(),
                # vf explained var
                "critic/vf_explained_var": (1.0 - return_diff_var / (return_var + 1e-5)).detach().item(),
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
    metrics = {}
    
    print(f"[METRICS DEBUG] 开始计算agent指标，batch.batch.keys(): {list(batch.batch.keys())}")
    
    # 原有的工具调用统计
    if 'tool_cnt' in batch.batch.keys():
        tool_cnt_tensor = batch.batch.pop('tool_cnt').detach().cpu()
        metrics.update({
            "agent/tool_call_mean": torch.mean(tool_cnt_tensor).item(),
            "agent/tool_call_max": torch.max(tool_cnt_tensor).item(),
            "agent/tool_call_min": torch.min(tool_cnt_tensor).item(),
        })
        print(f"[METRICS DEBUG] 工具调用统计: mean={torch.mean(tool_cnt_tensor).item():.2f}")
    
    # 新增：是否以answer结束的统计
    if 'final_answer' in batch.batch.keys():
        final_answer_tensor = batch.batch.pop('final_answer').detach().cpu()
        answer_rate = torch.mean(final_answer_tensor).item()
        metrics.update({
            "agent/final_answer_rate": answer_rate,
            "agent/final_answer_count": torch.sum(final_answer_tensor).item(),
        })
    
    # 新增：连续重复退化统计
    if 'repeated_degradation_cnt' in batch.batch.keys():
        repeated_deg_tensor = batch.batch.pop('repeated_degradation_cnt').detach().cpu()
        metrics.update({
            "agent/repeated_degradation_mean": torch.mean(repeated_deg_tensor).item(),
            "agent/repeated_degradation_max": torch.max(repeated_deg_tensor).item(),
        })
    
    # 新增：各种退化类型统计
    degradation_types = ["rain", "haze", "dark", "motion_blur", "defocus_blur", "noise", "low_resolution", "jpeg_compression_artifact", "clean"]
    for deg_type in degradation_types:
        # 总出现次数统计
        total_key = f"degradation_{deg_type}_total"
        if total_key in batch.batch.keys():
            deg_tensor = batch.batch.pop(total_key).detach().cpu()
            total_count = torch.sum(deg_tensor).item()
            mean_count = torch.mean(deg_tensor).item()
            metrics.update({
                f"degradation_stats/{deg_type}_total": total_count,
                f"degradation_stats/{deg_type}_mean": mean_count,
            })
            if total_count > 0:
                print(f"[METRICS DEBUG] {deg_type}: total={total_count:.1f}, mean={mean_count:.3f}")
        else:
            print(f"[METRICS DEBUG] 缺少键: {total_key}")
        
        # 连续出现次数统计
        consecutive_key = f"degradation_{deg_type}_consecutive"
        if consecutive_key in batch.batch.keys():
            consecutive_tensor = batch.batch.pop(consecutive_key).detach().cpu()
            max_consecutive = torch.max(consecutive_tensor).item()
            mean_consecutive = torch.mean(consecutive_tensor).item()
            # 只统计大于0的连续次数
            non_zero_consecutive = consecutive_tensor[consecutive_tensor > 0]
            if len(non_zero_consecutive) > 0:
                avg_non_zero_consecutive = torch.mean(non_zero_consecutive).item()
            else:
                avg_non_zero_consecutive = 0.0
                
            metrics.update({
                f"degradation_stats/{deg_type}_consecutive_max": max_consecutive,
                f"degradation_stats/{deg_type}_consecutive_mean": mean_consecutive,
                f"degradation_stats/{deg_type}_consecutive_avg_nonzero": avg_non_zero_consecutive,
            })
    
    # 新增：clean准确率统计（只统计clean样本）
    if 'ir_clean_accuracy' in batch.batch.keys() and 'ir_is_clean_sample' in batch.batch.keys():
        clean_accuracy_tensor = batch.batch.pop('ir_clean_accuracy').detach().cpu()
        is_clean_sample_tensor = batch.batch.pop('ir_is_clean_sample').detach().cpu()
        
        # 过滤掉-1值（表示不适用的clean_accuracy）和非clean样本
        clean_mask = is_clean_sample_tensor > 0  # 只选择clean样本
        if torch.sum(clean_mask).item() > 0:
            clean_accuracy_values = clean_accuracy_tensor[clean_mask]
            # 确保clean_accuracy值都是有效的（不是-1）
            valid_mask = clean_accuracy_values >= 0
            if torch.sum(valid_mask).item() > 0:
                valid_clean_accuracy = clean_accuracy_values[valid_mask]
                clean_sample_count = len(valid_clean_accuracy)
                clean_correct_count = torch.sum(valid_clean_accuracy).item()
                clean_accuracy_rate = clean_correct_count / clean_sample_count
                
                metrics.update({
                    "degradation_stats/clean_accuracy_rate": clean_accuracy_rate,
                    "degradation_stats/clean_sample_count": clean_sample_count,
                    "degradation_stats/clean_correct_count": clean_correct_count,
                })
                print(f"[METRICS DEBUG] clean样本统计: 总数={clean_sample_count:.0f}, 正确={clean_correct_count:.0f}, 准确率={clean_accuracy_rate:.3f}")
            else:
                print(f"[METRICS DEBUG] clean样本存在但clean_accuracy值无效")
        else:
            print(f"[METRICS DEBUG] 本批次无clean样本")
    elif 'ir_is_clean_sample' in batch.batch.keys():
        # 只有is_clean_sample但没有clean_accuracy
        is_clean_sample_tensor = batch.batch.pop('ir_is_clean_sample').detach().cpu()
        clean_sample_count = torch.sum(is_clean_sample_tensor).item()
        print(f"[METRICS DEBUG] clean样本数量: {clean_sample_count:.0f}")
    else:
        print(f"[METRICS DEBUG] 缺少clean相关键")
    
    # 新增：工具使用统计（使用独立的工具统计管理器）
    from verl.utils.tool_statistics_manager import get_tool_stats_manager
    
    tool_stats_manager = get_tool_stats_manager()
    tool_names = tool_stats_manager.all_tool_names
    
    for tool_name in tool_names:
        usage_key = f"tool_usage_{tool_name}"
        if usage_key in batch.batch.keys():
            tool_tensor = batch.batch.pop(usage_key).detach().cpu()
            total_usage = torch.sum(tool_tensor).item()
            mean_usage = torch.mean(tool_tensor).item()
            max_usage = torch.max(tool_tensor).item()
            
            # 只统计有使用的工具
            non_zero_usage = tool_tensor[tool_tensor > 0]
            usage_rate = (len(non_zero_usage) / len(tool_tensor)) if len(tool_tensor) > 0 else 0.0
            
            metrics.update({
                f"tool_stats/{tool_name}_total": total_usage,
                f"tool_stats/{tool_name}_mean": mean_usage,
                f"tool_stats/{tool_name}_max": max_usage,
                f"tool_stats/{tool_name}_usage_rate": usage_rate,
            })
            
            # 只显示使用量较高的工具，避免日志过多
            if total_usage >= 5:  # 只显示使用5次以上的工具
                print(f"[METRICS DEBUG] {tool_name}: total={total_usage:.1f}, mean={mean_usage:.3f}, rate={usage_rate:.3f}")
    
    return metrics


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
