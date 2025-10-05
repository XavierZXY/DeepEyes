"""Minimal rollout sanity check for DeepEyes agents."""

import json
import math
import os
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

import hydra
import torch
import torch.distributed as dist
from omegaconf import DictConfig, OmegaConf, open_dict
from transformers import AutoConfig

from verl import DataProto
from verl.utils.dataset.rl_dataset import RLHFDataset, collate_fn
from verl.utils.distributed import initialize_global_process_group
from verl.utils.tokenizer import hf_processor, hf_tokenizer
from verl.utils.torch_functional import pad_2d_list_to_length
from verl.workers.rollout.vllm_rollout import vLLMRollout

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def _bootstrap_distributed() -> Tuple[int, int, int]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the VLLM rollout test.")

    defaults = {
        "MASTER_ADDR": "127.0.0.1",
        "MASTER_PORT": "29500",
        "RANK": "0",
        "LOCAL_RANK": "0",
        "WORLD_SIZE": "1",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)

    if not dist.is_initialized():
        local_rank, rank, world_size = initialize_global_process_group()
    else:
        local_rank = int(os.environ.get("LOCAL_RANK", 0))
        rank = dist.get_rank()
        world_size = dist.get_world_size()

    torch.cuda.set_device(local_rank)
    return local_rank, rank, world_size


def _prepare_generation_batch(batch: DataProto, agent_cfg: DictConfig) -> DataProto:
    tensor_keys = ["input_ids", "attention_mask", "position_ids"]
    optional_non_tensor = ["raw_prompt_ids", "multi_modal_data", "origin_multi_modal_data", "multi_modal_inputs", "raw_prompt"]
    non_tensor_keys: List[str] = []
    for key in optional_non_tensor:
        if key in batch.non_tensor_batch:
            non_tensor_keys.append(key)
    gen_batch = batch.pop(batch_keys=tensor_keys, non_tensor_batch_keys=non_tensor_keys)

    if agent_cfg.activate_agent:
        tool_key = agent_cfg.tool_name_key
        if tool_key and tool_key in batch.non_tensor_batch:
            gen_batch.non_tensor_batch[tool_key] = batch.non_tensor_batch.pop(tool_key)
    return gen_batch


def _strip_pad(token_ids: List[int], pad_id: int) -> List[int]:
    return [tid for tid in token_ids if tid != pad_id]


def _decode_prompt(tokenizer, token_ids: List[int]) -> str:
    cleaned = _strip_pad(token_ids, tokenizer.pad_token_id)
    return tokenizer.decode(cleaned, skip_special_tokens=True).strip()


def _decode_response(tokenizer, token_ids: List[int]) -> str:
    pad_id = tokenizer.pad_token_id
    eos_id = tokenizer.eos_token_id
    cleaned: List[int] = []
    for tid in token_ids:
        if tid == eos_id:
            break
        if tid == pad_id:
            continue
        cleaned.append(tid)
    if not cleaned:
        cleaned = _strip_pad(token_ids, pad_id)
    return tokenizer.decode(cleaned, skip_special_tokens=True).strip()


def _compress_media_tokens(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'(?:<\|image_pad\|>\s*)+', '<|image_pad|>', text)
    text = re.sub(r'(?:<image>\s*)+', '<image>', text)
    text = re.sub(r'(?:<\|vision_start\|>\s*)+', '<|vision_start|>', text)
    text = re.sub(r'(?:<\|vision_end\|>\s*)+', '<|vision_end|>', text)
    return text


def _extract_chat_turns(raw_text: str) -> List[Tuple[str, str]]:
    pattern = r"<\|im_start\|>(.*?)\n(.*?)(?=<\|im_end\|>)"
    turns = []
    for match in re.finditer(pattern, raw_text, flags=re.DOTALL):
        role = match.group(1).strip()
        content = _compress_media_tokens(match.group(2).strip())
        turns.append((role, content))
    return turns


def _prettify_content(text: str) -> str:
    text = _compress_media_tokens(text)
    replacements = {
        '<|image_pad|>': '[image_pad]',
        '<image>': '[image]',
        '<|vision_start|>': '[vision_start]',
        '<|vision_end|>': '[vision_end]',
        '<|image_pad_1|>': '[image_pad]',
    }
    for src, tgt in replacements.items():
        text = text.replace(src, tgt)
    return text


def _safe_json_dumps(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)


def _extract_tool_calls(text: str):
    calls = []
    if not text:
        return calls
    for raw_call in re.findall(r"<tool_call>(.*?)</tool_call>", text, flags=re.DOTALL):
        payload = raw_call.strip()
        info = {"raw": payload, "name": None, "arguments": None, "error": None}
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                info["name"] = parsed.get("name")
                info["arguments"] = parsed.get("arguments")
        except Exception as exc:
            info["error"] = str(exc)
        calls.append(info)
    return calls


def _extract_tool_responses(text: str):
    if not text:
        return []
    blocks = re.findall(r"<tool_response>(.*?)</tool_response>", text, flags=re.DOTALL)
    return [block.strip() for block in blocks]


def _patch_agent_rollout_logging():
    import types
    from verl.workers.agent import parallel_env as pe_module
    import verl.workers.agent as agent_module
    from verl.workers.agent.parallel_env_v2 import ParallelEnv
    from verl.models.transformers.qwen2_vl import get_rope_index

    if getattr(pe_module, "_debug_rollout_patched", False):
        return

    base_concat = pe_module._concat_vllm_input
    base_merge = pe_module._merge_multi_modal_inputs
    logging.getLogger("agent.rollout").setLevel(logging.INFO)
    logging.getLogger("agent.rollout").propagate = True

    def decode_tokens(tokenizer, token_ids):
        if token_ids is None:
            return ""
        if isinstance(token_ids, torch.Tensor):
            tensor = token_ids
        else:
            tensor = torch.tensor(token_ids, dtype=torch.long)
        tensor = tensor.to("cpu")
        return tokenizer.decode(tensor.tolist(), skip_special_tokens=True)

    def debug_agent_rollout_loop(config, vllm_engine, vllm_inputs, prompts, multi_modal_inputs, sampling_params):
        logger = logging.getLogger("agent.rollout")

        agent_sampling_params = sampling_params.clone()
        agent_sampling_params.detokenize = True
        agent_sampling_params.skip_special_tokens = False
        agent_sampling_params.spaces_between_special_tokens = False
        agent_sampling_params.n = 1
        agent_sampling_params.include_stop_str_in_output = True
        max_generated_tokens = min(config.agent.single_response_max_tokens, config.response_length)
        agent_sampling_params.max_tokens = max_generated_tokens

        custom_stop = list(config.agent.custom_stop)
        if custom_stop:
            prev_stop = sampling_params.stop if sampling_params.stop else []
            agent_sampling_params.stop = prev_stop + custom_stop

        tokenizer = hf_tokenizer(config.agent.vl_model_path)
        processor = hf_processor(config.agent.vl_model_path)

        if multi_modal_inputs is not None:
            multi_modal_inputs = multi_modal_inputs.tolist()
        else:
            multi_modal_inputs = [{}] * len(vllm_inputs)

        batch_size = len(vllm_inputs)
        vllm_input_list = []
        running_states = []
        running_action_masks = []
        running_attn_masks = []
        reward_tensor_list = []
        active_mask = []
        mm_input_list = []
        tool_call_cnt_list = []
        slot_logs = [[] for _ in range(batch_size * sampling_params.n)]
        step_entry_map: dict[int, dict] = {}

        env = ParallelEnv(config.agent, tokenizer, processor)
        env.reset(prompts, vllm_inputs, n=sampling_params.n)

        for i in range(batch_size):
            for _ in range(sampling_params.n):
                vllm_input_list.append(deepcopy(vllm_inputs[i]))
                prompt_ids = prompts.batch['input_ids'][i, :].clone()
                running_states.append(prompt_ids)
                prompt_mask = prompts.batch['attention_mask'][i, :].clone()
                running_action_masks.append(prompt_mask)
                running_attn_masks.append(prompt_mask)
                reward_tensor = torch.zeros_like(prompt_ids, dtype=torch.float)
                reward_tensor_list.append(reward_tensor)
                active_mask.append(True)
                mm_input_list.append(deepcopy(multi_modal_inputs[i]))
                tool_call_cnt_list.append(0)

        from vllm.distributed import parallel_state as vllm_ps
        pg = vllm_ps.get_tp_group()
        max_total_length = config.prompt_length + config.response_length

        for step in range(config.agent.max_turns):
            if sum(active_mask) == 0:
                break

            logger.info("===== Agent Step %d =====", step + 1)

            active_indices = [idx for idx, is_active in enumerate(active_mask) if is_active]
            active_vllm_inputs = [vinput for vinput, is_active in zip(vllm_input_list, active_mask) if is_active]
            actions = vllm_engine.generate(
                prompts=active_vllm_inputs,
                sampling_params=agent_sampling_params,
                use_tqdm=False,
            )

            step_actions_text = []
            for idx_slot, action_output in zip(active_indices, actions):
                text = action_output.outputs[0].text
                step_actions_text.append((idx_slot, text))
                pretty_action = _prettify_content(text)
                logger.info(
                    "Step %d | Model Slot %d Action (model -> tool):\n%s",
                    step + 1,
                    idx_slot,
                    pretty_action.strip() or "<empty>",
                )

                tool_calls = _extract_tool_calls(text)
                if tool_calls:
                    for call_idx, call_info in enumerate(tool_calls, 1):
                        logger.info(
                            "    Tool Call %d | name=%s",
                            call_idx,
                            call_info["name"] if call_info["name"] else "<unknown>",
                        )
                        if call_info["arguments"] is not None:
                            logger.info(
                                "      arguments=%s",
                                _safe_json_dumps(call_info["arguments"]),
                            )
                        if call_info["error"]:
                            logger.info("      (JSON parse error: %s)", call_info["error"])
                        logger.info(
                            "      raw payload:\n%s",
                            _prettify_content(call_info["raw"]),
                        )
                else:
                    logger.info("    (No <tool_call> block detected in model output)")

                entry = {
                    "step": step + 1,
                    "model_action": text.strip(),
                    "model_action_pretty": pretty_action.strip(),
                    "tool_calls": tool_calls,
                }
                slot_logs[idx_slot].append(entry)
                step_entry_map[idx_slot] = entry

            if pg.is_first_rank:
               
                obs_results = env.step(active_indices, actions)
            else:
                obs_results = None

            obs_results = pg.broadcast_object(obs_results)
            observations, rewards, dones, info = obs_results

            for idx_slot, obs, reward, done_flag in zip(active_indices, observations, rewards, dones):
                tool = env.tools[idx_slot]
                tool_name = getattr(tool, "name", "unknown") if tool is not None else "no-tool"
                raw_obs_text = ""
                if isinstance(obs, dict):
                    if 'prompt_token_ids_model' in obs:
                        raw_obs_text = decode_tokens(tokenizer, obs['prompt_token_ids_model'])
                    elif 'prompt' in obs:
                        raw_obs_text = obs['prompt']
                    else:
                        raw_obs_text = str(obs)
                else:
                    raw_obs_text = str(obs)

                obs_text = _prettify_content(raw_obs_text)
                logger.info(
                    "Step %d | Tool Slot %d (%s) → reward=%.3f | done=%s",
                    step + 1,
                    idx_slot,
                    tool_name,
                    reward,
                    done_flag,
                )
                if obs_text.strip():
                    logger.info("    Environment observation:\n%s", obs_text.strip())
                else:
                    logger.info("    Environment observation: <empty>")

                tool_responses = _extract_tool_responses(raw_obs_text)
                if tool_responses:
                    for resp_idx, resp in enumerate(tool_responses, 1):
                        logger.info(
                            "    Tool Response %d:\n%s",
                            resp_idx,
                            _prettify_content(resp),
                        )
                mm_data = {}
                if isinstance(obs, dict):
                    mm_data = obs.get('multi_modal_data', {}) or {}
                mm_summary = {}
                if mm_data:
                    mm_summary = {
                        key: len(value) if isinstance(value, (list, tuple)) else "?"
                        for key, value in mm_data.items()
                    }
                    logger.info("    Attached multimodal data: %s", mm_summary)

                entry = step_entry_map.get(idx_slot)
                if entry is not None:
                    entry.update(
                        {
                            "tool_name": tool_name,
                            "reward": float(reward),
                            "done": bool(done_flag),
                            "env_observation": raw_obs_text.strip(),
                            "env_observation_pretty": obs_text.strip(),
                            "tool_responses": [_prettify_content(resp) for resp in tool_responses],
                            "multimodal_summary": mm_summary,
                        }
                    )
                    if done_flag:
                        entry["terminated"] = True

            for i, (idx, obs_item, action_item, reward_item, done_flag) in enumerate(
                zip(active_indices, observations, actions, rewards, dones)
            ):
                response_token_ids = torch.tensor(
                    action_item.outputs[0].token_ids,
                    dtype=torch.int64,
                    device=running_states[idx].device,
                )
                running_states[idx] = torch.cat([running_states[idx], response_token_ids])
                vllm_input_list[idx]['prompt_token_ids'] = base_concat(
                    vllm_input_list[idx]['prompt_token_ids'],
                    response_token_ids,
                    tokenizer=tokenizer,
                )

                action_reward = torch.zeros_like(
                    response_token_ids,
                    dtype=torch.float,
                    device=reward_tensor_list[idx].device,
                )
                reward_tensor_list[idx] = torch.cat([reward_tensor_list[idx], action_reward])
                reward_tensor_list[idx][-1] += reward_item

                action_mask = torch.ones_like(
                    response_token_ids,
                    dtype=torch.int64,
                    device=running_action_masks[idx].device,
                )
                running_action_masks[idx] = torch.cat([running_action_masks[idx], action_mask])
                running_attn_masks[idx] = torch.cat([running_attn_masks[idx], action_mask])

                if running_states[idx].shape[-1] >= max_total_length or len(vllm_input_list[idx]['prompt_token_ids']) >= max_total_length:
                    active_mask[idx] = False
                    continue

                if done_flag or step == config.agent.max_turns - 1:
                    active_mask[idx] = False
                    continue

                tool_call_cnt_list[idx] += 1

                obs = obs_item
                if isinstance(obs, dict) and 'prompt_token_ids_vllm' in obs and 'prompt_token_ids_model' in obs:
                    obs_token_ids_vllm = obs['prompt_token_ids_vllm']
                    obs_token_ids_model = obs['prompt_token_ids_model'].to(running_states[idx].device)

                    if len(vllm_input_list[idx]['prompt_token_ids']) + len(obs_token_ids_vllm) >= max_total_length:
                        active_mask[idx] = False
                        continue
                    if running_states[idx].shape[-1] + len(obs_token_ids_model) >= max_total_length:
                        active_mask[idx] = False
                        continue

                    vllm_input_list[idx]['prompt_token_ids'] = base_concat(
                        vllm_input_list[idx]['prompt_token_ids'],
                        obs_token_ids_vllm,
                        tokenizer=tokenizer,
                    )

                    running_states[idx] = torch.cat([running_states[idx], obs_token_ids_model])
                    obs_reward = torch.zeros(
                        len(obs_token_ids_model),
                        dtype=torch.float,
                        device=reward_tensor_list[idx].device,
                    )
                    reward_tensor_list[idx] = torch.cat([reward_tensor_list[idx], obs_reward], dim=-1)

                    obs_mask = torch.zeros(
                        len(obs_token_ids_model),
                        dtype=torch.int64,
                        device=running_action_masks[idx].device,
                    )
                    running_action_masks[idx] = torch.cat([running_action_masks[idx], obs_mask])
                    attn_mask = torch.ones(
                        len(obs_token_ids_model),
                        dtype=torch.int64,
                        device=running_attn_masks[idx].device,
                    )
                    running_attn_masks[idx] = torch.cat([running_attn_masks[idx], attn_mask])

                    mm_data = obs.get('multi_modal_data', {})
                    if 'image' in mm_data.keys():
                        if 'multi_modal_data' not in vllm_input_list[idx].keys():
                            vllm_input_list[idx]['multi_modal_data'] = {"image": []}
                        vllm_input_list[idx]['multi_modal_data']['image'] += mm_data['image']

                    mm_input = obs.get('multi_modal_inputs', {})
                    if mm_input:
                        mm_input_list[idx] = base_merge(mm_input_list[idx], mm_input)

                if running_states[idx].shape[-1] >= max_total_length or len(vllm_input_list[idx]['prompt_token_ids']) >= max_total_length:
                    active_mask[idx] = False

        env.close()
        target_device = prompts.batch['input_ids'].device
        running_states = [state[: max_total_length] for state in running_states]
        state_tensor = pad_2d_list_to_length(running_states, tokenizer.pad_token_id, max_total_length).to(target_device)

        running_action_masks = [mask[: max_total_length] for mask in running_action_masks]
        action_mask_tensor = pad_2d_list_to_length(running_action_masks, 0, max_total_length).to(target_device)

        running_attn_masks = [mask[: max_total_length] for mask in running_attn_masks]
        attn_mask_tensor = pad_2d_list_to_length(running_attn_masks, 0, max_total_length).to(target_device)

        if processor is not None and processor.image_processor.__class__.__name__ == "Qwen2VLImageProcessor":
            position_ids_list = [
                get_rope_index(
                    processor,
                    input_ids=state_tensor[i, :],
                    image_grid_thw=mm_input_list[i].get("image_grid_thw", None),
                    video_grid_thw=mm_input_list[i].get("video_grid_thw", None),
                    second_per_grid_ts=mm_input_list[i].get("second_per_grid_ts", None),
                    attention_mask=attn_mask_tensor[i, :],
                )
                for i in range(batch_size * sampling_params.n)
            ]
            position_ids_tensor = torch.stack(position_ids_list, dim=0)
        else:
            position_ids_tensor = compute_position_id_with_mask(attn_mask_tensor)

        reward_tensor_list = [reward[: max_total_length] for reward in reward_tensor_list]
        reward_tensor = pad_2d_list_to_length(reward_tensor_list, 0.0, max_total_length).to(target_device)

        tool_call_tensor = torch.tensor(tool_call_cnt_list, dtype=torch.float32).to(target_device).unsqueeze(1)

        from verl import DataProto

        return DataProto.from_dict(
            tensors={
                "response": state_tensor[:, -config.response_length :],
                "action_mask": action_mask_tensor,
                "attention_mask": attn_mask_tensor,
                "position_ids": position_ids_tensor,
                "env_reward": reward_tensor[:, -config.response_length :],
                "tool_cnt": tool_call_tensor,
            },
            non_tensors={"multi_modal_inputs": mm_input_list} if processor is not None else None,
            meta_info={"agent_logs": slot_logs},
        )

    pe_module.agent_rollout_loop = debug_agent_rollout_loop
    agent_module.agent_rollout_loop = debug_agent_rollout_loop
    pe_module._debug_rollout_patched = True


try:
    from verl.utils.model import compute_position_id_with_mask
except ImportError:  # defensive fallback
    from verl.utils.model import compute_position_id_with_mask

@hydra.main(version_base=None, config_path=".", config_name="test_rollout_config")
def run_rollout(cfg: DictConfig) -> None:
    logger.info("Hydra config:\n%s", OmegaConf.to_yaml(cfg))

    _patch_agent_rollout_logging()

    local_rank, rank, world_size = _bootstrap_distributed()
    device = torch.device("cuda", local_rank)
    logger.info("Distributed initialized | rank=%d | world_size=%d", rank, world_size)

    tokenizer = hf_tokenizer(cfg.model.model_path, trust_remote_code=True)
    tokenizer.padding_side = "left"
    processor = hf_processor(cfg.model.model_path)

    data_cfg = cfg.data
    dataset = RLHFDataset(
        data_files=data_cfg.train_data_path,
        tokenizer=tokenizer,
        config=data_cfg,
        processor=processor,
    )
    sampler = None
    if world_size > 1:
        sampler = torch.utils.data.distributed.DistributedSampler(
            dataset,
            num_replicas=world_size,
            rank=rank,
            shuffle=False,
            drop_last=False,
        )

    dataloader_kwargs = dict(
        dataset=dataset,
        batch_size=data_cfg.batch_size,
        collate_fn=collate_fn,
    )
    if sampler is not None:
        dataloader_kwargs["sampler"] = sampler
    else:
        dataloader_kwargs["shuffle"] = False

    dataloader = torch.utils.data.DataLoader(**dataloader_kwargs)

    if data_cfg.max_samples is None:
        sample_cap = len(dataset)
    else:
        sample_cap = min(int(data_cfg.max_samples), len(dataset))

    if sample_cap == 0:
        logger.warning("Nothing to process: max_samples is 0.")
        return

    logger.info("Dataset loaded (%d rows); testing first %d samples.", len(dataset), sample_cap)

    with open_dict(cfg.rollout):
        if "max_model_len" not in cfg.rollout:
            cfg.rollout.max_model_len = None
        if "agent" not in cfg.rollout:
            cfg.rollout.agent = {}

    with open_dict(cfg.rollout.agent):
        cfg.rollout.agent.setdefault("max_vllm_images", 0)
        cfg.rollout.agent.setdefault("max_vllm_videos", 0)
        cfg.rollout.agent.setdefault("activate_agent", True)

    with open_dict(cfg):
        if "output" not in cfg:
            cfg.output = {}
        output_cfg = cfg.output
        if "save_path" in output_cfg and "save_all_path" not in output_cfg:
            output_cfg["save_all_path"] = output_cfg.pop("save_path")
        output_cfg.setdefault("save_all_path", "outputs/rollout_trace_all.json")
        output_cfg.setdefault("save_tool_path", "outputs/rollout_trace_tool.json")
        output_cfg.setdefault("save_plain_path", "outputs/rollout_trace_plain.json")
        output_cfg.setdefault("only_with_tool", False)

    hf_config = AutoConfig.from_pretrained(cfg.model.model_path, trust_remote_code=True)
    total_seq_len = cfg.rollout.prompt_length + cfg.rollout.response_length
    if getattr(hf_config, "max_position_embeddings", 0) < total_seq_len:
        hf_config.max_position_embeddings = total_seq_len

    rollout_worker = vLLMRollout(
        cfg.model.model_path,
        config=cfg.rollout,
        tokenizer=tokenizer,
        model_hf_config=hf_config,
    )
    logger.info("vLLM engine ready with sampling params: %s", rollout_worker.sampling_params)

    processed = 0
    sample_index = 0
    samples_per_prompt = rollout_worker.sampling_params.n
    records: List[Dict] = []
    local_sample_cap = sample_cap
    if world_size > 1:
        local_sample_cap = max(1, math.ceil(sample_cap / world_size))

    if sampler is not None:
        sampler.set_epoch(0)

    for batch_dict in dataloader:
        batch_proto = DataProto.from_single_dict(batch_dict)
        remaining = local_sample_cap - processed
        if remaining <= 0:
            break
        if len(batch_proto) > remaining:
            batch_proto = batch_proto.slice(0, remaining)

        gen_batch = _prepare_generation_batch(batch_proto, cfg.rollout.agent)
        gen_batch.meta_info["eos_token_id"] = tokenizer.eos_token_id
        gen_batch.meta_info["pad_token_id"] = tokenizer.pad_token_id
        gen_batch.meta_info.setdefault("do_sample", True)
        gen_batch = gen_batch.to(device)

        rollout_output = rollout_worker.generate_sequences(gen_batch)
        rollout_output = rollout_output.to("cpu")
        batch_td = rollout_output.batch
        agent_logs: List[List[Dict]] = []
        if rollout_output.meta_info is not None:
            agent_logs = rollout_output.meta_info.get("agent_logs", [])

        responses = batch_td["responses"].cpu()
        response_count = responses.size(0)
        expected = len(gen_batch) * (samples_per_prompt if gen_batch.meta_info.get("do_sample", True) else 1)
        if response_count != expected:
            samples_per_prompt = max(1, response_count // max(len(gen_batch), 1))

        env_key = cfg.rollout.agent.tool_name_key if cfg.rollout.agent.activate_agent else None
        env_names = []
        if env_key and env_key in gen_batch.non_tensor_batch:
            env_names = gen_batch.non_tensor_batch[env_key].tolist()
        else:
            env_names = [""] * len(gen_batch)

        env_names_resolved: List[str] = []
        for env_name in env_names:
            for _ in range(samples_per_prompt):
                env_names_resolved.append(env_name)

        prompt_tokens_tensor = batch_td["prompts"].cpu()
        full_tokens_tensor = batch_td["input_ids"].cpu()
        full_attention_tensor = batch_td["attention_mask"].cpu()

        if "env_reward" in batch_td.keys():
            env_reward = batch_td["env_reward"].cpu()
        else:
            env_reward = None
        if "tool_cnt" in batch_td.keys():
            tool_cnt = batch_td["tool_cnt"].cpu()
        else:
            tool_cnt = None

        for idx in range(response_count):
            prompt_tokens = prompt_tokens_tensor[idx].tolist()
            prompt_text = _decode_prompt(tokenizer, prompt_tokens)

            full_tokens = full_tokens_tensor[idx].tolist()
            full_attn = full_attention_tensor[idx].tolist()
            effective_len = sum(full_attn)
            full_tokens = full_tokens[:effective_len]

            prompt_len = len(_strip_pad(prompt_tokens, tokenizer.pad_token_id))
            response_slice = full_tokens[prompt_len:]
            response_text = _decode_response(tokenizer, response_slice if response_slice else responses[idx].tolist())

            conversation_raw = tokenizer.decode(full_tokens, skip_special_tokens=False)
            chat_turns = _extract_chat_turns(conversation_raw)

            reward_value = 0.0
            if env_reward is not None:
                reward_value = float(env_reward[idx].sum().item())

            tool_calls = 0.0
            if tool_cnt is not None:
                tool_calls = float(tool_cnt[idx].item())

            tool_calls_count_value = tool_calls

            sample_index += 1
            if rank == 0:
                logger.info(
                    "Sample %d | tool=%s | reward=%.3f | tool_calls=%.0f",
                    sample_index,
                    env_names_resolved[idx],
                    reward_value,
                    tool_calls,
                )
                logger.info("Prompt:\n%s", prompt_text)
                logger.info("Response:\n%s", response_text)
                if chat_turns:
                    logger.info("Conversation Timeline:")
                    for turn_idx, (role, content) in enumerate(chat_turns, 1):
                        role_lower = role.lower()
                        if role_lower == "assistant":
                            origin = "model"
                        elif role_lower == "tool":
                            origin = "tool-env"
                        elif role_lower in {"system", "user"}:
                            origin = "dataset"
                        else:
                            origin = "unknown"

                        pretty_content = _prettify_content(content)
                        logger.info("  Step %02d [%s | %s]:\n%s", turn_idx, role, origin, pretty_content)

                        call_blocks = re.findall(r"<tool_call>(.*?)</tool_call>", content, flags=re.DOTALL)
                        for call_idx, call in enumerate(call_blocks, 1):
                            logger.info(
                                "    └─ Tool Call %d Payload:\n%s",
                                call_idx,
                                _prettify_content(call.strip()),
                            )

                        tool_responses = re.findall(r"<tool_response>(.*?)</tool_response>", content, flags=re.DOTALL)
                        for resp_idx, resp in enumerate(tool_responses, 1):
                            summary = _prettify_content(resp.strip())
                            logger.info("    └─ Tool Response %d:\n%s", resp_idx, summary)

            timeline_entries = []
            for turn_idx, (role, content) in enumerate(chat_turns, 1):
                role_lower = role.lower()
                if role_lower == "assistant":
                    origin = "model"
                elif role_lower == "tool":
                    origin = "tool-env"
                elif role_lower in {"system", "user"}:
                    origin = "dataset"
                else:
                    origin = "unknown"

                pretty_content = _prettify_content(content)
                timeline_entries.append(
                    {
                        "step": turn_idx,
                        "role": role,
                        "origin": origin,
                        "content": pretty_content,
                        "tool_calls": _extract_tool_calls(content),
                        "tool_responses": [_prettify_content(resp) for resp in _extract_tool_responses(content)],
                    }
                )

            agent_step_logs = agent_logs[idx] if idx < len(agent_logs) else []
            has_tool_call = any(entry.get("tool_calls") for entry in agent_step_logs if entry)

            record = {
                "sample_index": sample_index,
                "env_name": env_names_resolved[idx],
                "prompt": prompt_text,
                "response": response_text,
                "reward": reward_value,
                "tool_calls_count": tool_calls_count_value,
                "timeline": timeline_entries,
                "agent_steps": agent_step_logs,
                "has_tool_call": bool(has_tool_call or tool_calls_count_value),
            }

            records.append(record)

        processed += len(gen_batch)
        if processed >= local_sample_cap:
            break

    if dist.is_initialized():
        if rank == 0:
            gathered_records: List[List[Dict]] = [None for _ in range(world_size)]  # type: ignore
            dist.gather_object(records, gathered_records, dst=0)
            merged_records: List[Dict] = []
            for part in gathered_records:
                if part:
                    merged_records.extend(part)
        else:
            dist.gather_object(records, None, dst=0)
            merged_records = []
        dist.barrier()
    else:
        merged_records = records

    if rank == 0:
        output_cfg = cfg.output
        all_path = Path(output_cfg.save_all_path)
        tool_path = Path(output_cfg.save_tool_path) if output_cfg.save_tool_path else None
        plain_path = Path(output_cfg.save_plain_path) if output_cfg.save_plain_path else None

        all_path.parent.mkdir(parents=True, exist_ok=True)
        if tool_path:
            tool_path.parent.mkdir(parents=True, exist_ok=True)
        if plain_path:
            plain_path.parent.mkdir(parents=True, exist_ok=True)

        tool_records = [rec for rec in merged_records if rec.get("has_tool_call")]
        plain_records = [rec for rec in merged_records if not rec.get("has_tool_call")]

        if output_cfg.only_with_tool:
            target_records = tool_records
        else:
            target_records = merged_records

        with all_path.open("w", encoding="utf-8") as f:
            json.dump(target_records, f, ensure_ascii=False, indent=2)
        logger.info("Saved %d conversation records to %s", len(target_records), all_path.resolve())

        if tool_path:
            with tool_path.open("w", encoding="utf-8") as f:
                json.dump(tool_records, f, ensure_ascii=False, indent=2)
            logger.info("Saved %d tool-call records to %s", len(tool_records), tool_path.resolve())

        if plain_path:
            with plain_path.open("w", encoding="utf-8") as f:
                json.dump(plain_records, f, ensure_ascii=False, indent=2)
            logger.info("Saved %d plain records to %s", len(plain_records), plain_path.resolve())

    if dist.is_initialized():
        dist.barrier()
        dist.destroy_process_group()
    logger.info("Rollout test finished.")


if __name__ == "__main__":
    run_rollout()
