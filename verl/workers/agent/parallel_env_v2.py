import re
import io
import json
import torch
import numpy as np
from copy import deepcopy
from tqdm import tqdm
from functools import partial
from concurrent.futures import ThreadPoolExecutor

from verl import DataProto
from verl.models.transformers.qwen2_vl import get_rope_index
from verl.utils.model import compute_position_id_with_mask
from verl.utils import hf_tokenizer, hf_processor
from verl.utils.dataset.vision_utils import process_image, process_raw_image, process_video
from verl.utils.torch_functional import pad_2d_list_to_length
from verl.workers.agent.tool_envs import ToolBase

# 创建工具调用专用日志记录器
def setup_tool_call_logger():
    """设置工具调用专用的日志记录器"""
    import logging
    import datetime
    import os
    
    logger = logging.getLogger('tool_call_tracker')
    logger.setLevel(logging.INFO)
    
    # 避免重复添加handler
    if not logger.handlers:
        # 创建日志文件
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"tool_call_tracker_{timestamp}.log")
        
        # 创建文件handler
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter('%(asctime)s | %(message)s', datefmt='%H:%M:%S')
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
    
    return logger

# 全局日志记录器
tool_call_logger = setup_tool_call_logger()

def _strip_system_block(text: str) -> str:
    """
    删除 text 中第一个 <|im_start|>system ... <|im_end|> 区块（含标签），
    并返回删除后的字符串。
    如果找不到匹配的开始或结束标签，则返回原文。
    """
    # 非贪婪匹配，匹配跨行
    pattern = r"<\|im_start\|>system.*?<\|im_end\|>"
    # 替换为空
    result = re.sub(pattern, "", text, flags=re.S)
    return result


def _concat_vllm_input(prompt_token_ids, response_token_ids, tokenizer=None):
    # NOTE: temporarily fix qwen-base oov issue
    if tokenizer is not None:
        max_token_id = max(tokenizer.get_vocab().values())
        tokenizer_size = len(tokenizer)
        max_token_id = max(max_token_id, tokenizer_size)
        valid_token_mask = torch.le(response_token_ids, max_token_id)
        response_token_ids = torch.masked_select(response_token_ids, valid_token_mask)

    if isinstance(prompt_token_ids, torch.Tensor):
        output_tensor = torch.cat([
            prompt_token_ids,
            response_token_ids.to(prompt_token_ids.device),
        ], dim=-1)
        return output_tensor.cpu().numpy().flatten().tolist()
    else:
        output_array = np.concatenate([
            prompt_token_ids,
            response_token_ids.cpu().numpy(),
        ], axis=-1)
        return output_array.flatten().tolist()


def _ensure_images_on_cpu(multi_modal_data):
    """
    确保图像数据在CPU上，避免GPU显存累积
    
    Args:
        multi_modal_data: 包含图像数据的字典
        
    Returns:
        修改后的multi_modal_data，图像数据在CPU上
    """
    if not isinstance(multi_modal_data, dict) or 'image' not in multi_modal_data:
        return multi_modal_data
    
    cpu_images = []
    for img in multi_modal_data['image']:
        if hasattr(img, 'cpu'):  # 如果是tensor，移到CPU
            cpu_images.append(img.cpu())
        elif hasattr(img, 'device') and 'cuda' in str(img.device):
            # 其他GPU tensor类型
            cpu_images.append(img.cpu())
        else:  # PIL图像或其他格式，保持不变
            cpu_images.append(img)
    
    # 创建新的字典避免修改原始数据
    result = dict(multi_modal_data)
    result['image'] = cpu_images
    return result


def _merge_multi_modal_inputs(mm_input, other):
    if not mm_input and not other:
        return {}
    elif len(mm_input) == 0 and len(other) > 0:
        return other
    elif len(mm_input) > 0 and len(other) == 0:
        return mm_input

    output_dict = {}
    for key in mm_input.keys():
        if key not in other.keys():
            output_dict[key] = mm_input[key]
            continue

        mm_value = mm_input[key]
        other_value = other.pop(key)
        if isinstance(mm_value, np.ndarray) and isinstance(other_value, np.ndarray):
            merged_value = np.concatenate([mm_value, other_value], axis=0)
        elif isinstance(mm_value, torch.Tensor) and isinstance(other_value, torch.Tensor):
            merged_value = torch.cat([mm_value, other_value], dim=0)
        else:
            raise ValueError(f"Invalid {type(mm_value)=}, {type(other_value)=}")

        output_dict[key] = merged_value
    return dict(**output_dict, **other)


def _parse_model_output_for_tools_v2(action_text: str, turn_info=""):
    """
    Parse model output to extract tool calls, think blocks, and answer blocks.
    Updated for v2 format where <think> contains brief reasoning text and <answer> contains JSON.
    
    Args:
        action_text: The model's output text
        turn_info: Turn information for debugging
        
    Returns:
        dict: Contains 'think', 'tool_calls', 'answer', 'restoration_log', and 'is_done' fields
    """
    result = {
        'think': None,
        'tool_calls': [],
        'answer': None,
        'restoration_log': [],
        'is_done': False
    }
    
    # Extract <think> block - now contains brief reasoning text (not JSON)
    think_pattern = r'<think>(.*?)</think>'
    think_match = re.search(think_pattern, action_text, re.DOTALL)
    if think_match:
        think_content = think_match.group(1).strip()
        result['think'] = think_content  # Store as text, not JSON
        
        # For compatibility with existing statistics, try to extract degradation info from the reasoning text
        # Look for common degradation keywords in the reasoning
        degradation_keywords = {
            "jpeg compression artifact": ["jpeg", "compression", "blockiness", "artifact", "block"],
            "motion blur": ["motion blur", "camera shake", "directional blur", "movement"],
            "defocus blur": ["defocus", "out of focus", "depth blur", "bokeh"],
            "noise": ["noise", "grain", "speckle"],
            "low resolution": ["low resolution", "pixelated", "upscale"],
            "haze": ["haze", "fog", "atmospheric", "visibility"],
            "rain": ["rain", "water drops", "precipitation"],
            "dark": ["dark", "underexposed", "low light", "brightness"],
            "clean": ["clean", "no degradation", "artifact-free"]
        }
        
        detected_degradations = []
        think_lower = think_content.lower()
        for degradation, keywords in degradation_keywords.items():
            if any(keyword in think_lower for keyword in keywords):
                detected_degradations.append(degradation)
        
        # Create compatibility structure for statistics
        if detected_degradations:
            result['diagnosis'] = {'labels': detected_degradations}
        elif "clean" in think_lower or "no" in think_lower:
            result['diagnosis'] = {'labels': ["clean"]}
    
    # Extract <tool_call> block
    tool_call_pattern = r'<tool_call>(.*?)</tool_call>'
    tool_call_match = re.search(tool_call_pattern, action_text, re.DOTALL)
    if tool_call_match:
        tool_call_content = tool_call_match.group(1).strip()
        try:
            tool_calls_json = json.loads(tool_call_content)
            if isinstance(tool_calls_json, list):
                result['tool_calls'] = tool_calls_json
            else:
                result['tool_calls'] = [tool_calls_json]
                
        except json.JSONDecodeError as e:
            result['tool_calls'] = []
    
    # Extract <answer> block - now contains JSON with restoration_log
    answer_pattern = r'<answer>(.*?)</answer>'
    answer_match = re.search(answer_pattern, action_text, re.DOTALL)
    if answer_match:
        answer_content = answer_match.group(1).strip()
        try:
            answer_json = json.loads(answer_content)
            result['answer'] = answer_json
            # 解析answer内容，但不在这里做严格格式检查（交给格式奖励处理）
            if isinstance(answer_json, dict):
                result['restoration_log'] = answer_json.get('restoration_log', [])
                print(f"[DEBUG {turn_info}] Answer包含字段: {list(answer_json.keys())}")
            elif isinstance(answer_json, list):
                # 错误格式：但保持原始数据，让格式奖励来惩罚
                result['restoration_log'] = answer_json
                print(f"[WARNING {turn_info}] Answer是数组格式（格式错误）: {answer_json}")
            else:
                # 其他错误格式：保持数据，让格式奖励来惩罚
                result['restoration_log'] = []
                print(f"[WARNING {turn_info}] Answer是{type(answer_json).__name__}类型（格式错误）: {answer_json}")
            
            result['is_done'] = True  # 都标记为完成，让格式奖励系统负责评分
        except json.JSONDecodeError as e:
            # JSON解析失败：保持原始内容，让格式奖励来惩罚
            result['answer'] = answer_content
            result['restoration_log'] = []
            result['is_done'] = True  # 标记为完成，格式奖励会给0分
            print(f"[WARNING {turn_info}] Answer JSON解析失败（格式错误）: {e}")
    
    return result


def _create_tools_from_parsed_output_v2(parsed_output, multi_modal_data=None, origin_multi_modal_data=None, raw_prompt=None, turn_info=""):
    """
    Create tool instances from parsed model output (v2).
    
    Args:
        parsed_output: Output from _parse_model_output_for_tools_v2
        multi_modal_data: Multi-modal data for tool initialization
        origin_multi_modal_data: Original multi-modal data
        raw_prompt: Raw prompt for tool initialization
        turn_info: Turn information for debugging
        
    Returns:
        list: List of tool instances corresponding to each tool call
    """
    tools = []
    
    for i, tool_call in enumerate(parsed_output['tool_calls']):
        # Handle case where tool_call might be a string instead of dict
        if isinstance(tool_call, str):
            tools.append(None)
            continue
        elif not isinstance(tool_call, dict):
            tools.append(None)
            continue
            
        tool_name = tool_call.get('name', '')
        tool_args = tool_call.get('arguments', {})
        
        # 调试信息：检查tool_name的类型
        if "统计" not in turn_info:  # 避免统计时的重复日志
            print(f"[DEBUG TOOL V2] tool_call: {tool_call}")
            print(f"[DEBUG TOOL V2] tool_name: {tool_name}, 类型: {type(tool_name)}")
        
        # 检查tool_name格式错误
        if not tool_name:
            print(f"[ERROR TOOL V2] {turn_info} 工具调用缺少name字段: {tool_call}")
            tools.append(None)
            continue
        elif isinstance(tool_name, dict):
            print(f"[ERROR TOOL V2] {turn_info} 格式错误：name字段是字典而不是字符串: {tool_name}")
            print(f"[ERROR TOOL V2] {turn_info} 完整tool_call: {tool_call}")
            print(f"[ERROR TOOL V2] {turn_info} 这说明模型输出的JSON格式不正确")
            tools.append(None)
            continue
        elif isinstance(tool_name, list):
            print(f"[ERROR TOOL V2] {turn_info} 格式错误：name字段是列表而不是字符串: {tool_name}")
            tools.append(None)
            continue
        elif not isinstance(tool_name, str):
            print(f"[WARNING TOOL V2] {turn_info} name字段类型错误，强制转换为字符串: {tool_name} ({type(tool_name)}) -> {str(tool_name)}")
            tool_name = str(tool_name)
            
        if tool_name not in ToolBase.registry:
            tools.append(None)
            continue
            
        try:
            tool_instance = ToolBase.create(tool_name)
            try:
                tool_instance.reset(
                    raw_prompt=raw_prompt,
                    multi_modal_data=deepcopy(multi_modal_data) if multi_modal_data else None,
                    origin_multi_modal_data=deepcopy(origin_multi_modal_data) if origin_multi_modal_data else None,
                )
                tools.append(tool_instance)
            except Exception as reset_error:
                tools.append(tool_instance)  # 仍然尝试使用未重置的工具
                
        except Exception as e:
            tools.append(None)
    
    return tools


def _preprocess_multi_modal_inputs(prompt_str, processor, **kwargs):
    if processor is None or "multi_modal_data" not in kwargs:
        return prompt_str, prompt_str, {}

    # 计算原始提示中的 <image> 占位符数量
    image_placeholder_count = prompt_str.count('<image>')
    input_mm_data = kwargs.get("multi_modal_data", {"image": []})
    actual_image_count = len(input_mm_data["image"])
    
    if image_placeholder_count != actual_image_count:
        print(f"[ERROR MULTIMODAL V2] ❌ 占位符不匹配: 需要{actual_image_count}个<image>, 实际{image_placeholder_count}个")

    vllm_input_prompt = prompt_str.replace('<image>', '<|vision_start|><|image_pad|><|vision_end|>')
    
    image_info_list = []
    for img in input_mm_data["image"]:
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        png_bytes = buf.getvalue()
        buf.close()
        img_info = {"bytes": png_bytes}
        image_info_list.append(img_info)

    # 处理图像并添加调试信息
    processed_images = [process_image(img) for img in image_info_list]
    input_mm_data["image"] = processed_images
    
    # 添加processor前的图像调试信息
    if processed_images:
        for i, img in enumerate(processed_images):
            if hasattr(img, 'size'):
                print(f"[PROCESSOR DEBUG] 处理前图像{i}: 尺寸={img.size}", flush=True)
                
                # 详细检查图像数据
                import numpy as np
                img_array = np.array(img)
                img_mean = np.mean(img_array)
                print(f"[PROCESSOR DEBUG] 处理前图像{i}: shape={img_array.shape}, mean={img_mean:.2f}", flush=True)
    
    # ⚠️ 关键检查点：processor可能会修改图像！
    print(f"[PROCESSOR DEBUG] 调用processor: text长度={len(vllm_input_prompt)}, 图像数量={len(input_mm_data['image'])}", flush=True)
    model_inputs = processor(text=[vllm_input_prompt], images=input_mm_data["image"], return_tensors="pt")
    
    # 检查processor是否改变了图像tensor的尺寸
    if "pixel_values" in model_inputs:
        pixel_values = model_inputs["pixel_values"]
        print(f"[PROCESSOR DEBUG] processor输出tensor: pixel_values.shape={pixel_values.shape}", flush=True)
        print(f"[PROCESSOR DEBUG] ⚠️ 注意：processor将PIL图像转换为tensor，这是正常的模型输入格式", flush=True)
    elif "image" in model_inputs:
        image_tensor = model_inputs["image"]
        print(f"[PROCESSOR DEBUG] processor输出tensor: image.shape={image_tensor.shape}", flush=True)
    
    # ⚠️ 重要：检查processor是否修改了原始PIL图像列表
    print(f"[PROCESSOR DEBUG] 检查原始图像是否被修改:", flush=True)
    for i, img in enumerate(input_mm_data["image"]):
        if hasattr(img, 'size'):
            print(f"[PROCESSOR DEBUG] processor后图像{i}: 尺寸={img.size}", flush=True)
    input_ids = model_inputs.pop("input_ids")[0]
    attention_mask = model_inputs.pop("attention_mask")[0]

    if "second_per_grid_ts" in model_inputs:
        model_inputs.pop("second_per_grid_ts")

    mm_inputs = dict(model_inputs)
    return vllm_input_prompt, input_ids, mm_inputs


def agent_rollout_loop_v2(config, vllm_engine, vllm_inputs, prompts, multi_modal_inputs, sampling_params):
    from vllm.distributed import parallel_state as vllm_ps

    agent_sampling_params = sampling_params.clone()
    agent_sampling_params.detokenize = True
    agent_sampling_params.skip_special_tokens = False
    agent_sampling_params.spaces_between_special_tokens = False
    agent_sampling_params.n = 1
    agent_sampling_params.include_stop_str_in_output = True
    max_generated_tokens = min(config.agent.single_response_max_tokens, config.response_length)
    agent_sampling_params.max_tokens = max_generated_tokens

    # support custom stop specified in dataset, like </search>, ```, etc.
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
    
    # 新增统计信息 - 适配v2格式
    final_answer_list = []  # 是否以answer结束
    restoration_logs_list = []  # 修复日志列表
    think_reasoning_list = []  # 思考推理过程
    degradation_labels_list = []  # 退化类型列表
    repeated_degradation_cnt_list = []  # 连续重复退化数量
    
    # 每种退化类型的连续出现统计
    all_degradation_types = ["rain", "haze", "dark", "motion blur", "defocus blur", "noise", "low resolution", "jpeg compression artifact", "clean"]
    consecutive_degradation_stats = {}
    last_round_degradations = []  # 跟踪每个样本上一轮的退化类型
    for deg_type in all_degradation_types:
        consecutive_degradation_stats[deg_type] = []  # 每个样本的连续次数
    
    # 使用独立的工具统计管理器
    from verl.utils.tool_statistics_manager import get_tool_stats_manager, reset_global_tool_stats
    
    # 重置工具统计管理器以开始新的批次（暂时不指定设备）
    reset_global_tool_stats()
    tool_stats_manager = get_tool_stats_manager()  # 稍后会设置正确的设备
    all_tool_names = tool_stats_manager.all_tool_names

    env = ParallelEnvV2(config.agent, tokenizer, processor)
    env.reset(prompts, vllm_inputs, n=sampling_params.n)

    # interleaving inputs if sampling_params.n > 1
    sample_idx = 0  # 跟踪样本索引
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
            # 确保mm_input_list的元素是字典格式
            mm_input_item = multi_modal_inputs[i] if i < len(multi_modal_inputs) else {}
            if not isinstance(mm_input_item, dict):
                mm_input_item = {}
            mm_input_list.append(deepcopy(mm_input_item))
            tool_call_cnt_list.append(0)
            
            # 初始化新增统计信息
            final_answer_list.append(False)
            restoration_logs_list.append([])
            think_reasoning_list.append([])
            degradation_labels_list.append([])  # 存储每轮的退化标签
            repeated_degradation_cnt_list.append(0)
            
            # 初始化每种退化类型的连续统计
            for deg_type in all_degradation_types:
                consecutive_degradation_stats[deg_type].append(0)
            last_round_degradations.append(set())  # 初始化为空集合
            
            # 确保工具统计管理器初始化了当前样本
            tool_stats_manager.ensure_sample_count(sample_idx + 1)
            sample_idx += 1

    pg = vllm_ps.get_tp_group()
    max_total_length = config.prompt_length + config.response_length
    for step in range(config.agent.max_turns):
        print(f'[DEBUG V2 step {step + 1}] 🔄 活跃: {sum(active_mask)}/{batch_size * sampling_params.n}')
        
        if sum(active_mask) == 0:
            print(f'[DEBUG V2 step {step + 1}] 结束: 无活跃对话')
            break

        active_indices = [idx for idx, is_active in enumerate(active_mask) if is_active]
        active_vllm_inputs = [vinput for vinput, is_active in zip(vllm_input_list, active_mask) if is_active]
        
        # 准备VLLM输入：如果输入包含'prompt'键，则提取字符串和多模态数据
        vllm_prompts = []
        vllm_multi_modal_data = []
        
        for vinput in active_vllm_inputs:
            if 'prompt' in vinput:
                vllm_prompts.append(vinput['prompt'])
                if 'multi_modal_data' in vinput:
                    vllm_multi_modal_data.append(vinput['multi_modal_data'])
                else:
                    vllm_multi_modal_data.append({})
            else:
                # 兼容旧格式
                vllm_prompts.append(vinput)
                vllm_multi_modal_data.append({})
        
        # VLLM的generate方法需要将多模态数据嵌入到输入中
        # 我们需要使用正确的输入格式
        if any(vllm_multi_modal_data):
            # 对于多模态输入，需要创建特殊的输入格式
            inputs = []
            for prompt, mm_data in zip(vllm_prompts, vllm_multi_modal_data):
                if mm_data and 'image' in mm_data:
                    # 创建包含图像的输入
                    inputs.append({
                        'prompt': prompt,
                        'multi_modal_data': mm_data
                    })
                else:
                    inputs.append(prompt)
            actions = vllm_engine.generate(
                prompts=inputs,
                sampling_params=agent_sampling_params,
                use_tqdm=False
            )
        else:
            actions = vllm_engine.generate(
                prompts=vllm_prompts,
                sampling_params=agent_sampling_params,
                use_tqdm=False
            )
        
        # 模型输出解析检查
        for idx, a in enumerate(actions):
            action_text = a.outputs[0].text
            active_idx = active_indices[idx]
            
            has_think = '<think>' in action_text and '</think>' in action_text
            has_tool_call = '<tool_call>' in action_text and '</tool_call>' in action_text
            has_answer = '<answer>' in action_text and '</answer>' in action_text
            
            format_tags = []
            if has_think: format_tags.append("think")
            if has_tool_call: format_tags.append("tool_call")
            if has_answer: format_tags.append("answer")
            
        if pg.is_first_rank:
            obs_results = env.step(active_indices, actions, current_turn=step + 1)
        else:
            obs_results = None

        obs_results = pg.broadcast_object(obs_results)
        observations, rewards, dones, info = obs_results

        for idx, obs, act, rew, done in zip(active_indices, observations, actions, rewards, dones):
            # 收集统计信息 - 解析当前动作 (v2格式)
            action_text = act.outputs[0].text
            parsed_action = _parse_model_output_for_tools_v2(action_text, f"统计-轮次{step + 1}")
            print('-*'*50)
            # 统计是否以answer结束
            if parsed_action.get('is_done', False):
                final_answer_list[idx] = True
                # 收集restoration_log
                restoration_log = parsed_action.get('restoration_log', [])
                restoration_logs_list[idx] = restoration_log
                print(f"[STATS V2] 样本{idx} 以answer结束，修复日志: {restoration_log}")
            
            # 收集思考推理过程
            think_content = parsed_action.get('think')
            if think_content:
                think_reasoning_list[idx].append(think_content)
                print(f"[STATS V2] 样本{idx} 轮次{step + 1} 思考: {think_content[:100]}...")
            
            # 统计工具调用
            tool_calls = parsed_action.get('tool_calls', [])
            if tool_calls:
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get('name', 'unknown')
                        if tool_name in all_tool_names:
                            tool_stats_manager.record_tool_usage(tool_name, idx)
                            # 减少实时日志输出，只在调试时显示
                            # print(f'[TOOL STATS V2] 样本{idx} 轮次{step + 1} 使用工具: {tool_name}')
            
            # 统计退化类型 (从兼容性diagnosis中提取)
            current_labels = []
            if 'diagnosis' in parsed_action:
                diagnosis = parsed_action['diagnosis']
                if isinstance(diagnosis, dict) and 'labels' in diagnosis:
                    current_labels = diagnosis.get('labels', [])
                    print(f"[STATS V2] 样本{idx} 轮次{step + 1} 检测到退化: {current_labels}")
            
            # 安全地创建标签集合，处理可能的非哈希类型
            try:
                hashable_labels = []
                for label in current_labels:
                    if isinstance(label, (str, int, float)):
                        hashable_labels.append(str(label))
                    elif isinstance(label, list):
                        hashable_labels.append(str(label))
                    else:
                        hashable_labels.append(str(label))
                
                current_labels_set = set(hashable_labels)
                current_labels = hashable_labels
                print(f"[STATS V2] 样本{idx} 处理后的标签: {current_labels}")
            except TypeError as e:
                print(f"[STATS V2 ERROR] 样本{idx} 无法创建标签集合: {e}, 原始标签: {current_labels}")
                current_labels_set = set()
                current_labels = []
            
            if current_labels:
                degradation_labels_list[idx].extend(current_labels)
                
                # 计算每种退化类型的连续出现次数
                prev_labels_set = last_round_degradations[idx]
                
                for deg_type in all_degradation_types:
                    if deg_type in current_labels_set:
                        if deg_type in prev_labels_set:
                            # 连续出现，增加计数
                            consecutive_degradation_stats[deg_type][idx] += 1
                        else:
                            # 新出现，重置为1
                            consecutive_degradation_stats[deg_type][idx] = 1
                    else:
                        # 未出现，重置为0
                        consecutive_degradation_stats[deg_type][idx] = 0
                
                # 更新上一轮的退化类型记录
                last_round_degradations[idx] = current_labels_set
                
                # 检查总体重复退化（任意类型重复）
                overlap = prev_labels_set & current_labels_set
                if overlap and step > 0:
                    repeated_degradation_cnt_list[idx] += len(overlap)
                    print(f"[STATS V2] 样本{idx} 重复退化: {overlap}")
                
                print(f"[STATS V2] 样本{idx} 轮次{step + 1} 退化类型: {current_labels}")
                
                # 打印连续统计
                consecutive_info = []
                for deg_type in all_degradation_types:
                    if consecutive_degradation_stats[deg_type][idx] > 1:
                        consecutive_info.append(f"{deg_type}:{consecutive_degradation_stats[deg_type][idx]}")
                if consecutive_info:
                    print(f"[STATS V2] 样本{idx} 连续退化: {', '.join(consecutive_info)}")
            else:
                # 当前轮没有退化标签，重置所有连续计数
                for deg_type in all_degradation_types:
                    consecutive_degradation_stats[deg_type][idx] = 0
                last_round_degradations[idx] = set()
            
            # process response token ids
            response_token_ids = torch.tensor(act.outputs[0].token_ids, dtype=torch.int64, device=running_states[idx].device)
            running_states[idx] = torch.cat([running_states[idx], response_token_ids])
            # 检查是否使用新的prompt格式
            if 'prompt_token_ids' in vllm_input_list[idx]:
                vllm_input_list[idx]['prompt_token_ids'] = _concat_vllm_input(
                    vllm_input_list[idx]['prompt_token_ids'], 
                    response_token_ids,
                    tokenizer=tokenizer,
                )
            elif 'prompt' in vllm_input_list[idx]:
                # 对于使用prompt格式的，需要更新prompt字符串
                response_text = tokenizer.decode(response_token_ids, skip_special_tokens=False)
                vllm_input_list[idx]['prompt'] += response_text

            action_reward = torch.zeros_like(response_token_ids, dtype=torch.float, device=reward_tensor_list[idx].device)
            reward_tensor_list[idx] = torch.cat([reward_tensor_list[idx], action_reward])
            reward_tensor_list[idx][-1] += rew

            action_mask = torch.ones_like(response_token_ids, dtype=torch.int64, device=running_action_masks[idx].device)
            running_action_masks[idx] = torch.cat([running_action_masks[idx], action_mask])
            running_attn_masks[idx] = torch.cat([running_attn_masks[idx], action_mask])

            # Ensure the last token is not obs
            if running_states[idx].shape[-1] >= max_total_length or len(vllm_input_list[idx]['prompt_token_ids']) >= max_total_length:
                active_mask[idx] = False
                continue

            if done or step == config.agent.max_turns - 1:
                active_mask[idx] = False
                continue
            tool_call_cnt_list[idx] += 1

            # process obs tokens and images
            if 'prompt_token_ids_vllm' in obs.keys() and 'prompt_token_ids_model' in obs.keys():
                obs_token_ids_vllm = obs['prompt_token_ids_vllm']
                obs_token_ids_model = obs['prompt_token_ids_model'].to(running_states[idx].device)
                

                if len(vllm_input_list[idx]['prompt_token_ids']) + len(obs_token_ids_vllm) >= max_total_length:
                    active_mask[idx] = False
                    continue
                if running_states[idx].shape[-1] + len(obs_token_ids_model) >= max_total_length:
                    active_mask[idx] = False
                    continue

                # 检查是否使用新的prompt格式
                if 'prompt_token_ids' in vllm_input_list[idx]:
                    vllm_input_list[idx]['prompt_token_ids'] = _concat_vllm_input(
                        vllm_input_list[idx]['prompt_token_ids'], 
                        obs_token_ids_vllm,
                        tokenizer=tokenizer,
                    )
                elif 'prompt' in vllm_input_list[idx]:
                    # 对于使用prompt格式的，需要更新prompt字符串
                    obs_text = tokenizer.decode(obs_token_ids_vllm, skip_special_tokens=False)
                    vllm_input_list[idx]['prompt'] += obs_text

                running_states[idx] = torch.cat([running_states[idx], obs_token_ids_model])
                obs_reward = torch.zeros(len(obs_token_ids_model), dtype=torch.float, device=reward_tensor_list[idx].device)
                reward_tensor_list[idx] = torch.cat([reward_tensor_list[idx], obs_reward], dim=-1)

                obs_mask = torch.zeros(len(obs_token_ids_model), dtype=torch.int64, device=running_action_masks[idx].device)
                running_action_masks[idx] = torch.cat([running_action_masks[idx], obs_mask])
                attn_mask = torch.ones(len(obs_token_ids_model), dtype=torch.int64, device=running_attn_masks[idx].device)
                running_attn_masks[idx] = torch.cat([running_attn_masks[idx], attn_mask])

                mm_data = obs.get('multi_modal_data', {})
                if 'image' in mm_data.keys():
                    if 'multi_modal_data' not in vllm_input_list[idx].keys():
                        vllm_input_list[idx]['multi_modal_data'] = {"image": []}
                    
                    vllm_input_list[idx]['multi_modal_data']['image'] += mm_data['image']

                mm_input = obs.get('multi_modal_inputs', {})
                if mm_input:
                    # 确保mm_input_list[idx]是字典格式
                    if not isinstance(mm_input_list[idx], dict):
                        mm_input_list[idx] = {}
                    # 确保mm_input也是字典格式
                    if isinstance(mm_input, dict):
                        mm_input_list[idx] = _merge_multi_modal_inputs(mm_input_list[idx], mm_input)
                    else:
                        print(f"[WARNING] mm_input不是字典格式: {type(mm_input)}, 跳过合并")

            # 检查长度限制，兼容不同的输入格式
            state_length = running_states[idx].shape[-1]
            if 'prompt_token_ids' in vllm_input_list[idx]:
                vllm_length = len(vllm_input_list[idx]['prompt_token_ids'])
            elif 'prompt' in vllm_input_list[idx]:
                # 对于prompt格式，估算长度
                vllm_length = len(vllm_input_list[idx]['prompt']) // 4  # 粗略估计
            else:
                vllm_length = 0
            
            if state_length >= max_total_length or vllm_length >= max_total_length:
                active_mask[idx] = False

    # 在env.close()之前收集图像历史信息
    print(f"[DEBUG] 开始收集图像历史: batch_size={batch_size}, sampling_params.n={sampling_params.n}, total_samples={batch_size * sampling_params.n}")
    
    image_history_list = []
    total_samples = batch_size * sampling_params.n
    
    # 边界情况检查
    if total_samples <= 0:
        print(f"[ERROR] total_samples={total_samples} <= 0, 这是不正常的!")
        # 即使在异常情况下，也不添加image_history_list，避免DataProto验证错误
        print(f"[DEBUG] 跳过图像历史收集，避免DataProto验证错误")
        collected_image_history = False
    else:
        # 检查环境是否有图像历史列表
        if hasattr(env, 'multi_modal_data_history_list'):
            env_history_length = len(env.multi_modal_data_history_list)
            print(f"[DEBUG] 环境图像历史长度: {env_history_length}, 期望总样本数: {total_samples}")
            
            for idx in range(total_samples):
                if idx < env_history_length:
                    image_history = env.get_all_images(idx)
                    image_history_list.append(image_history)
                    if idx < 3:  # 只打印前3个样本的详细信息
                        print(f"[DEBUG] 样本{idx}图像历史长度: {len(image_history)}")
                        # 检查每一步的图像信息
                        for step_idx, step_data in enumerate(image_history):
                            if isinstance(step_data, dict) and 'image' in step_data:
                                step_image_count = len(step_data['image'])
                                print(f"[DEBUG]   步骤{step_idx}: {step_image_count}张图像")
                            else:
                                print(f"[DEBUG]   步骤{step_idx}: 无图像数据 ({type(step_data)})")
                else:
                    # 如果没有图像历史，添加空列表
                    image_history_list.append([])
                    if idx < 3:
                        print(f"[DEBUG] 样本{idx}没有图像历史，使用空列表")
        else:
            print("[DEBUG] 环境没有multi_modal_data_history_list属性")
            # 如果环境没有图像历史列表，为所有样本添加空列表
            for idx in range(total_samples):
                image_history_list.append([])
        
        # 将图像历史列表转换为numpy兼容的格式
        # 由于不同样本的图像历史长度可能不同，我们需要将其转换为统一的格式
        if len(image_history_list) == total_samples:
            # 转换为numpy object数组，每个元素是一个图像历史列表
            image_history_array = np.empty(total_samples, dtype=object)
            for idx, history in enumerate(image_history_list):
                image_history_array[idx] = history
            
            print(f"[DEBUG] 成功收集图像历史列表，长度: {len(image_history_list)}")
            collected_image_history = True
            final_image_history_data = image_history_array
        else:
            print(f"[ERROR] 图像历史列表长度不匹配: {len(image_history_list)} != {total_samples}, 跳过添加")
            collected_image_history = False
            final_image_history_data = None

    env.close()
    target_device = prompts.batch['input_ids'].device
    
    # 更新工具统计管理器的设备设置
    tool_stats_manager.device = target_device
    
    running_states = [state[: max_total_length] for state in running_states]
    state_tensor = pad_2d_list_to_length(running_states, tokenizer.pad_token_id, max_total_length).to(target_device)

    running_action_masks = [mask[: max_total_length] for mask in running_action_masks]
    action_mask_tensor = pad_2d_list_to_length(running_action_masks, 0, max_total_length).to(target_device)

    running_attn_masks = [mask[: max_total_length] for mask in running_attn_masks]
    attn_mask_tensor = pad_2d_list_to_length(running_attn_masks, 0, max_total_length).to(target_device)

    if processor is not None and processor.image_processor.__class__.__name__ == "Qwen2VLImageProcessor":
        # For Qwen-VL: (n*bs, 3, seq_len)
        position_ids_list = [
            get_rope_index(
                processor,
                input_ids=state_tensor[i, :],
                image_grid_thw=mm_input_list[i].get("image_grid_thw", None) if isinstance(mm_input_list[i], dict) else None,
                video_grid_thw=mm_input_list[i].get("video_grid_thw", None) if isinstance(mm_input_list[i], dict) else None,
                second_per_grid_ts=mm_input_list[i].get("second_per_grid_ts", None) if isinstance(mm_input_list[i], dict) else None,
                attention_mask=attn_mask_tensor[i, :],
            ) for i in range(batch_size * sampling_params.n)
        ]
        position_ids_tensor = torch.stack(position_ids_list, dim=0)
    else:
        # For LM: (n*bs, seq_len)
        position_ids_tensor = compute_position_id_with_mask(attn_mask_tensor)

    reward_tensor_list = [reward[: max_total_length] for reward in reward_tensor_list]
    reward_tensor = pad_2d_list_to_length(reward_tensor_list, 0.0, max_total_length).to(target_device)

    tool_call_tensor = torch.tensor(tool_call_cnt_list, dtype=torch.float32).to(target_device).unsqueeze(1)
    
    # 处理新增统计信息 (v2)
    final_answer_tensor = torch.tensor([1.0 if x else 0.0 for x in final_answer_list], dtype=torch.float32).to(target_device).unsqueeze(1)

    # 统计退化类型出现次数
    degradation_stats = {}
    for deg_type in all_degradation_types:
        # 总出现次数统计（添加容错机制）
        count_list = []
        for labels in degradation_labels_list:
            if labels is not None and hasattr(labels, 'count'):
                count_list.append(float(labels.count(deg_type)))
            else:
                count_list.append(0.0)  # None或无效值默认为0
        degradation_stats[f"degradation_{deg_type.replace(' ', '_')}_total"] = torch.tensor(count_list, dtype=torch.float32).to(target_device).unsqueeze(1)
        
        # 连续出现次数统计
        consecutive_list = consecutive_degradation_stats[deg_type]
        degradation_stats[f"degradation_{deg_type.replace(' ', '_')}_consecutive"] = torch.tensor(consecutive_list, dtype=torch.float32).to(target_device).unsqueeze(1)
    
    repeated_degradation_tensor = torch.tensor(repeated_degradation_cnt_list, dtype=torch.float32).to(target_device).unsqueeze(1)
    
    # 使用工具统计管理器生成tensor统计
    tool_stats = tool_stats_manager.get_tensor_stats(target_device)
    
    # 统计restoration_log长度（添加容错机制）
    restoration_log_lengths = []
    for log in restoration_logs_list:
        if log is not None and hasattr(log, '__len__'):
            restoration_log_lengths.append(len(log))
        else:
            restoration_log_lengths.append(0)  # None或无效值默认为0
    restoration_log_length_tensor = torch.tensor(restoration_log_lengths, dtype=torch.float32).to(target_device).unsqueeze(1)
    
    # 打印详细统计摘要 (v2)
    print(f"\n[STATS V2 SUMMARY] === 统计详情 ===")
    print(f"[STATS V2 SUMMARY] 以answer结束的样本: {sum(final_answer_list)}/{len(final_answer_list)}")
    print(f"[STATS V2 SUMMARY] 连续重复退化平均次数: {sum(repeated_degradation_cnt_list)/len(repeated_degradation_cnt_list):.2f}")
    
    # 使用工具统计管理器打印摘要
    tool_stats_manager.print_statistics_summary("STATS V2")
    print(f"[STATS V2 SUMMARY] 平均修复步骤数: {sum(restoration_log_lengths)/len(restoration_log_lengths):.2f}")
    
    print(f"[STATS V2 SUMMARY] 原始数据检查:")
    print(f"[STATS V2 SUMMARY]   degradation_labels_list长度: {len(degradation_labels_list)}")
    for i, labels in enumerate(degradation_labels_list[:3]):  # 只显示前3个样本
        print(f"[STATS V2 SUMMARY]   样本{i}的标签: {labels}")
    for i, log in enumerate(restoration_logs_list[:3]):  # 只显示前3个样本
        print(f"[STATS V2 SUMMARY]   样本{i}的修复日志: {log}")
    
    print(f"[STATS V2 SUMMARY] 退化类型出现统计:")
    for deg_type in all_degradation_types:
        # 添加容错机制，处理None值
        total_count = 0
        for labels in degradation_labels_list:
            if labels is not None and hasattr(labels, 'count'):
                total_count += labels.count(deg_type)
        if total_count > 0:
            print(f"[STATS V2 SUMMARY]   {deg_type}: {total_count} 次")
            
    print(f"[STATS V2 SUMMARY] 传递给WandB的tensor形状:")
    for key, tensor in degradation_stats.items():
        if 'total' in key:
            print(f"[STATS V2 SUMMARY]   {key}: shape={tensor.shape}, sum={torch.sum(tensor).item():.1f}")
    
    print(f"[STATS V2 SUMMARY] === 统计详情结束 ===\n")
    
    non_tensor_data = {"multi_modal_inputs": mm_input_list} if processor is not None else {}
    
    # 使用之前收集的图像历史信息
    if collected_image_history and final_image_history_data is not None:
        non_tensor_data["image_history_list"] = final_image_history_data
        print(f"[DEBUG] 添加图像历史到返回数据，数组形状: {final_image_history_data.shape}")
    else:
        print(f"[DEBUG] 未收集到有效的图像历史信息，跳过添加")
    
    return DataProto.from_dict(
        tensors={
            "response": state_tensor[:, -config.response_length: ],
            "action_mask": action_mask_tensor,
            "attention_mask": attn_mask_tensor,
            "position_ids": position_ids_tensor,
            "env_reward": reward_tensor[:, -config.response_length: ],
            "tool_cnt": tool_call_tensor,
            "final_answer": final_answer_tensor,
            "repeated_degradation_cnt": repeated_degradation_tensor,
            "restoration_log_length": restoration_log_length_tensor,
            **degradation_stats,
            **tool_stats,
        },
        non_tensors=non_tensor_data
    )


def execute_tool_call_v2(sample, tokenizer=None, processor=None, pbar=None):
    action_string = sample.get('action', '')
    tools = sample.get('tools', [])
    parsed_output = sample.get('parsed_output', {})
    turn_info = sample.get('turn_info', '')

    # parallel_env只负责环境执行，不计算最终奖励分数

    # 工具执行开始
    valid_tools = [t for t in tools if t is not None]

    # non-agent data or no tools to execute
    if action_string == '':
        return {}, 0.0, True, {}
    elif not tools:
        # If tools is empty but action_string is not, it means parsing failed
        error_msg = "Failed to parse valid tool calls from the action string. Please check the format of your <tool_call> blocks."
        error_text = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        
        # Encode error message in the expected format
        obs_token_ids = tokenizer.encode(error_text, add_special_tokens=False)
        error_obs = {
            "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
            "prompt_token_ids_model": torch.tensor(obs_token_ids),
        }
        return error_obs, -0.1, False, {"error": error_msg, "status": "failed"}

    # Handle <answer> case - episode is done
    if parsed_output.get('is_done', False):
        return {}, 0.0, True, {"status": "success", "type": "answer"}

    # Execute tools sequentially
    final_tool_result = None
    total_reward = 0.0
    final_done = False
    final_info = {}

    # 逐个执行工具
    executed_count = 0
    for i, tool in enumerate(tools):
        if tool is None:
            continue
            
        try:
            tool_call = parsed_output['tool_calls'][i] if i < len(parsed_output['tool_calls']) else {}
            
            if isinstance(tool_call, dict):
                compatible_action_string = f"<tool_call>{json.dumps(tool_call)}</tool_call>"
            else:
                compatible_action_string = f"<tool_call>{json.dumps({'name': str(tool_call), 'arguments': {}})}</tool_call>"
            
            print(f'[DEBUG V2 {turn_info}] 执行工具: {tool.name}')
            tool_result, reward, done, info = tool.execute(compatible_action_string)
            print(f'[DEBUG V2 {turn_info}] 结果: multi_modal_data={tool_result.get("multi_modal_data") is not None}, reward={reward:.3f}, done={done}')
            print(f'[DEBUG V2 {turn_info}] 状态: {info.get("status", "unknown")}')
            executed_count += 1
            
            # 累积结果
            final_tool_result = tool_result
            total_reward += reward
            final_done = final_done or done
            final_info.update(info)
            
        except Exception as e:
            total_reward -= 0.1
            continue

    # If no tools were executed successfully, return error message to model
    if final_tool_result is None:
        error_msg = "The tool executions failed. Please check your tool call format and arguments."
        error_text = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        
        # Encode error message in the expected format
        obs_token_ids = tokenizer.encode(error_text, add_special_tokens=False)
        error_obs = {
            "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
            "prompt_token_ids_model": torch.tensor(obs_token_ids),
        }
        return error_obs, total_reward, False, {"error": error_msg, "status": "failed"}

    # post-process the final tool result
    if not final_tool_result:
        tool_result_info = {}

    elif isinstance(final_tool_result, str):
        # Format 1: text output
        obs_token_ids = tokenizer.encode(final_tool_result, add_special_tokens=False)
        tool_result_info = {
            "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
            "prompt_token_ids_model": torch.tensor(obs_token_ids),
        }

    elif isinstance(final_tool_result, list) and isinstance(final_tool_result[0], dict):
        # Format 2: [{"role": "...", "content": "..."}, ...]
        obs_token_ids = tokenizer.apply_chat_template(final_tool_result, add_generation_prompt=True, return_tensors='pt')[0]

        # NOTE: skip the sp (and the \n token that comes after it) added by Qwen tokenizer
        eos_start_idx = torch.nonzero(obs_token_ids == tokenizer.eos_token_id)
        if eos_start_idx.shape[0] > 0:
            eos_start_idx = eos_start_idx[0].item()
            obs_token_ids = obs_token_ids[eos_start_idx + 1 : ]
        else:
            raise ValueError(f"tool returned type List[str] output must be in openai/qwen format : {final_tool_result}")

        tool_result_info = {
            "prompt_token_ids_vllm": obs_token_ids,
            "prompt_token_ids_model": obs_token_ids,
        }

    elif isinstance(final_tool_result, dict):
        # Format 3: {"prompt": "...", "chat": [{"role": "...", "content": "..."}, ...], "multi_modal_data": ...}
        prompt_str = final_tool_result.pop("prompt", "")
        chat_list = final_tool_result.pop("chat", [])

        if len(prompt_str) == 0 and len(chat_list) == 0:
            raise ValueError("Both prompt_str and chat_list are invalid")
        elif len(prompt_str) == 0 and len(chat_list) > 0:
            prompt_str = tokenizer.apply_chat_template(chat_list, add_generation_prompt=True, tokenize=False)
            prompt_str = _strip_system_block(prompt_str)

        prompt_str_vllm, obs_token_ids_model, mm_inputs = _preprocess_multi_modal_inputs(prompt_str, processor, **final_tool_result)
        obs_token_ids_vllm = tokenizer.encode(prompt_str_vllm, add_special_tokens=False, return_tensors='pt')[0]
        tool_result_info = {
            "prompt_token_ids_vllm": obs_token_ids_vllm,
            "prompt_token_ids_model": obs_token_ids_model,
            **final_tool_result   # multi_modal_data
        }
        if mm_inputs:
            tool_result_info["multi_modal_inputs"] = mm_inputs

    else:
        raise ValueError(f"Invalid tool_result type: {type(final_tool_result)=} -- {final_tool_result}")

    # final_info already contains tool execution info

    if pbar is not None:
        pbar.update(1)
    return tool_result_info, total_reward, final_done, final_info


class ParallelEnvV2:
    """
    V2 version of ParallelEnv with support for the new conversation format.
    The interface is designed to be similar to: https://github.com/openai/gym
    """
    
    # 定义所有需要统计的工具名称
    ALL_TOOL_NAMES = [
        "fbcnn_jpeg_artifact_removal", "fbcnn_blind_quality_assessment",
        "swinir_denoising", "swinir_jpeg_artifact_removal", "swinir_super_resolution",
        "mprnet_denoising", "mprnet_deraining", "mprnet_motion_deblurring",
        "xrestormer_deraining", "xrestormer_motion_deblurring",
        "dehazeformer_dehaze", "drbnet_defocus_deblurring",
        "visual_toolbox", "visual_toolbox_v2", "visual_toolbox_v3", "visual_toolbox_v4", "visual_toolbox_v5"
    ]
    
    def __init__(self, env_config, tokenizer, processor, **kwargs):
        self.config = env_config
        self.tokenizer = tokenizer
        self.processor = processor

        # type: List[ Dict[ Str, ToolBase subclasses ] ]
        self.tools = []

    def step(self, active_indices, actions, current_turn=1):
        """
        Input:
        - actions: vllm.RequestOutput
        - current_turn: Current turn number for debugging

        Output:
        - observations: List[Dict], content like {"prompt_token_ids": ..., "multi_modal_data": ...}, 
                multi_modal_data only appears when there are images/videos in obs
        - rewards: List[ float ].
                each time after an action being executed, procedure rewards can be assigned to 
                the last valid token of model outputs. This might be useful for ..., 
                e.g., invalid action, code execution error, format error,
                or video game envs where immediate feedback is available.
        - dones: List[ Boolean ]
        - infos: Dict, for debugging only
        """
        obs_list = [{}] * len(actions)
        reward_list = [0.0] * len(actions)
        done_list = []
        valid_indices = []
        real_indices = []
        valid_actions = []
        
        # 1. filtering valid actions
        for i, (idx, act) in enumerate(zip(active_indices, actions)):
            if act.outputs[0].finish_reason == 'length':
                done_list.append(True)
                continue

            if len(act.outputs[0].token_ids) == 0:
                done_list.append(True)
                continue

            done_list.append(False)
            real_indices.append(i)
            valid_indices.append(idx)
            valid_actions.append(act.outputs[0].text)

        # 工具解析和创建 (v2)
        agent_inputs = []
        
        for i, idx, action in zip(real_indices, valid_indices, valid_actions):
            turn_info = f"T{current_turn}-样本{idx}"
            
            # 解析模型输出 (v2)
            parsed_output = _parse_model_output_for_tools_v2(action, turn_info)
            
            tool_calls_count = len(parsed_output.get('tool_calls', []))
            has_answer = parsed_output.get('is_done', False)
            has_think = parsed_output.get('think') is not None
            print(f'[DEBUG V2 step {current_turn}-{idx:02d}] 工具解析: {parsed_output.get("tool_calls", [])}')
           
            print(f'[DEBUG V2 step {current_turn}-{idx:02d}] 思考: {parsed_output.get("think", None)}')
            # 创建工具实例
            tools = []
            if parsed_output['tool_calls']:
                # 获取最新的图像数据（历史列表的最后一个元素）
                current_multi_modal_data = (
                    self.multi_modal_data_history_list[idx][-1] 
                    if self.multi_modal_data_history_list[idx] 
                    else None
                )
                tools = _create_tools_from_parsed_output_v2(
                    parsed_output,
                    multi_modal_data=current_multi_modal_data,
                    origin_multi_modal_data=self.origin_multi_modal_data_list[idx],
                    raw_prompt=self.raw_prompts[idx],
                    turn_info=turn_info
                )
                
                # 输出工具创建结果
                tool_names = []
                for j, tool_call in enumerate(parsed_output['tool_calls']):
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get('name', 'unknown')
                        tool_names.append(tool_name)
                    else:
                        tool_names.append('格式错误')
                
                success_count = sum(1 for t in tools if t is not None)
                
            agent_inputs.append(dict(
                idx=i,
                valid_idx=idx,
                action=action,
                tools=tools,
                parsed_output=parsed_output,
                turn_info=turn_info,
            ))

        # 工具执行 (v2)
        num_workers = min(self.config.concurrent_workers, len(valid_actions))
        pbar = tqdm(total=len(valid_actions), desc=f'Tool calling on {num_workers} workers') if self.config.show_tqdm else None
        
        if num_workers <= 1:
            for agi in agent_inputs:
                valid_idx = agi['valid_idx']
                subidx = agi['idx']
                
                obs, reward, done, info = execute_tool_call_v2(agi, self.tokenizer, self.processor, pbar=pbar)
                
                # 输出执行结果
                if info.get('status') == 'success':
                    if info.get('type') == 'answer':
                        status = "🏁"  # 答案完成
                    else:
                        status = "✅"  # 工具执行成功
                        # 更新环境中的图像数据
                        if isinstance(obs, dict) and 'multi_modal_data' in obs:
                            # 确保图像数据在CPU上，避免GPU显存累积
                            new_multi_modal_data = _ensure_images_on_cpu(obs['multi_modal_data'])
                            self.multi_modal_data_history_list[valid_idx].append(new_multi_modal_data)
                            history_len = len(self.multi_modal_data_history_list[valid_idx])
                            image_count = len(obs["multi_modal_data"].get("image", []))
                            print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 图像历史更新: 第{history_len}轮, {image_count}张图片')
                            
                            # 验证图像数据完整性并检查尺寸变化
                            if image_count > 0 and 'image' in new_multi_modal_data:
                                first_image = new_multi_modal_data['image'][0]
                                original_image = obs['multi_modal_data']['image'][0] if 'image' in obs['multi_modal_data'] and obs['multi_modal_data']['image'] else None
                                
                                if hasattr(first_image, 'size'):
                                    print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 最终保存图像尺寸: {first_image.size}')
                                    
                                    # 检查图像在保存过程中是否发生变化
                                    if original_image and hasattr(original_image, 'size'):
                                        size_changed = original_image.size != first_image.size
                                        print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 保存过程检查: 工具输出尺寸={original_image.size}, 保存后尺寸={first_image.size}, 尺寸变化={size_changed}')
                                        
                                        # 检查对象是否相同
                                        is_same_object = original_image is first_image
                                        print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 对象检查: 是否同一对象={is_same_object}')
                                else:
                                    print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 保存图像类型: {type(first_image)}')
                else:
                    status = "❌"  # 执行失败
                
                obs_list[subidx] = obs
                reward_list[subidx] = reward
                done_list[subidx] |= done
        else:
            partial_tool_func = partial(execute_tool_call_v2, tokenizer=self.tokenizer, processor=self.processor, pbar=pbar)
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                raw_outputs = list(executor.map(partial_tool_func, agent_inputs))
            for agi, raw in zip(agent_inputs, raw_outputs):
                obs, reward, done = raw[0], raw[1], raw[2]
                info = raw[3] if len(raw) > 3 else {}
                
                valid_idx = agi['valid_idx']
                if info.get('status') == 'success':
                    if info.get('type') == 'answer':
                        status = "🏁"  # 答案完成
                    else:
                        status = "✅"  # 工具执行成功
                        # 更新环境中的图像数据
                        if isinstance(obs, dict) and 'multi_modal_data' in obs:
                            # 确保图像数据在CPU上，避免GPU显存累积
                            new_multi_modal_data = _ensure_images_on_cpu(obs['multi_modal_data'])
                            self.multi_modal_data_history_list[valid_idx].append(new_multi_modal_data)
                            history_len = len(self.multi_modal_data_history_list[valid_idx])
                            image_count = len(obs["multi_modal_data"].get("image", []))
                            print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 图像历史更新: 第{history_len}轮, {image_count}张图片')
                            
                            # 验证图像数据完整性并检查尺寸变化
                            if image_count > 0 and 'image' in new_multi_modal_data:
                                first_image = new_multi_modal_data['image'][0]
                                original_image = obs['multi_modal_data']['image'][0] if 'image' in obs['multi_modal_data'] and obs['multi_modal_data']['image'] else None
                                
                                if hasattr(first_image, 'size'):
                                    print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 最终保存图像尺寸: {first_image.size}')
                                    
                                    # 检查图像在保存过程中是否发生变化
                                    if original_image and hasattr(original_image, 'size'):
                                        size_changed = original_image.size != first_image.size
                                        print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 保存过程检查: 工具输出尺寸={original_image.size}, 保存后尺寸={first_image.size}, 尺寸变化={size_changed}')
                                        
                                        # 检查对象是否相同
                                        is_same_object = original_image is first_image
                                        print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 对象检查: 是否同一对象={is_same_object}')
                                else:
                                    print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 保存图像类型: {type(first_image)}')
                else:
                    status = "❌"  # 执行失败
                print(f'[DEBUG V2 step {current_turn}-{valid_idx:02d}] 执行: {status} reward={reward:.3f}, done={done}')
                
                subidx = agi['idx']
                obs_list[subidx] = obs
                reward_list[subidx] = reward
                done_list[subidx] |= done

        return obs_list, reward_list, done_list, {}

    def reset(self, prompts, vllm_inputs, n=1, **kwargs):
        print(f"[DEBUG RESET] 环境重置: len(prompts)={len(prompts)}, len(vllm_inputs)={len(vllm_inputs)}, n={n}")
        
        self.tools = []
        self.raw_prompts = []
        self.multi_modal_data_history_list = []  # 每个样本的图像历史：List[List[Dict]]
        self.origin_multi_modal_data_list = []
        reset_output_list = []
        assert len(prompts) == len(vllm_inputs), f"{len(prompts)=}, {len(vllm_inputs)=}"

        num_agent, num_non_agent = 0, 0
        for i in range(len(prompts)):
            data_item = prompts[i]  # DataProtoItem
            # We no longer use tool_name from dataset, but still extract other data
            tool_name = data_item.non_tensor_batch.pop(self.config.tool_name_key, '')
            raw_prompt = data_item.non_tensor_batch.pop('raw_prompt', None)
          
            vllm_input_item = vllm_inputs[i]   # {"prompt_token_ids": ..., "multi_modal_data": ...}
            multi_modal_data = vllm_input_item.get("multi_modal_data", None)
            origin_multi_modal_data = data_item.non_tensor_batch.pop("origin_multi_modal_data", None)
            
            for j in range(n):
                # Store context data for later tool creation
                self.raw_prompts.append(raw_prompt)
                # 初始化图像历史，第一个元素是原始图像（确保在CPU上）
                #image_history = [deepcopy(multi_modal_data)] if multi_modal_data else []
                if multi_modal_data:
                    cpu_multi_modal_data = _ensure_images_on_cpu(multi_modal_data)
                    image_history = [cpu_multi_modal_data]
                else:
                    image_history = []
                self.multi_modal_data_history_list.append(image_history)
                self.origin_multi_modal_data_list.append(deepcopy(origin_multi_modal_data))
                
                # 调试信息
                if i < 3 and j == 0:  # 只打印前3个样本的第一个副本
                    has_image = multi_modal_data is not None and 'image' in multi_modal_data if multi_modal_data else False
                    image_count = len(multi_modal_data.get('image', [])) if has_image else 0
                    print(f"[DEBUG RESET] 样本{i}: multi_modal_data={'有' if multi_modal_data else '无'}, 图像数量={image_count}")
                
                # Initialize with None - tools will be created dynamically from model output
                self.tools.append(None)
                reset_output_list.append(None)
                
                # Count as agent data if we have a raw prompt (indicating this could be an agent task)
                if raw_prompt is not None:
                    num_agent += 1
                else:
                    num_non_agent += 1
        
        print(f"[DEBUG RESET] 重置完成: multi_modal_data_history_list长度={len(self.multi_modal_data_history_list)}, 期望长度={len(prompts) * n}")
        return reset_output_list

    def get_image_history_length(self, idx: int) -> int:
        """获取指定样本的图像历史长度"""
        return len(self.multi_modal_data_history_list[idx]) if idx < len(self.multi_modal_data_history_list) else 0
    
    def get_current_image(self, idx: int):
        """获取指定样本的当前（最新）图像"""
        if idx < len(self.multi_modal_data_history_list) and self.multi_modal_data_history_list[idx]:
            return self.multi_modal_data_history_list[idx][-1]
        return None
    
    def get_image_at_step(self, idx: int, step: int):
        """获取指定样本在指定步骤的图像"""
        if (idx < len(self.multi_modal_data_history_list) and 
            0 <= step < len(self.multi_modal_data_history_list[idx])):
            return self.multi_modal_data_history_list[idx][step]
        return None
    
    def rollback_to_step(self, idx: int, step: int) -> bool:
        """回退到指定步骤（预留接口，未来实现）"""
        if (idx < len(self.multi_modal_data_history_list) and 
            0 <= step < len(self.multi_modal_data_history_list[idx])):
            # 截断历史到指定步骤
            self.multi_modal_data_history_list[idx] = self.multi_modal_data_history_list[idx][:step+1]
            print(f'[ROLLBACK V2] 样本{idx} 回退到第{step+1}轮')
            return True
        return False
    
    def get_all_images(self, idx: int):
        """获取指定样本的所有图像历史"""
        if idx < len(self.multi_modal_data_history_list):
            return self.multi_modal_data_history_list[idx].copy()
        return []

    def close(self):
        self.tools = []
        self.raw_prompts = []
        self.multi_modal_data_history_list = []
        self.origin_multi_modal_data_list = []

# Backward compatibility - expose v2 functions with original names
_parse_model_output_for_tools = _parse_model_output_for_tools_v2
_create_tools_from_parsed_output = _create_tools_from_parsed_output_v2
agent_rollout_loop = agent_rollout_loop_v2
execute_tool_call = execute_tool_call_v2
ParallelEnv = ParallelEnvV2
