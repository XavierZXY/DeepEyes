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


def _parse_model_output_for_tools(action_text: str, turn_info=""):
    """
    Parse model output to extract tool calls, think blocks, and answer blocks.
    
    Args:
        action_text: The model's output text
        turn_info: Turn information for debugging
        
    Returns:
        dict: Contains 'think', 'tool_calls', 'answer', and 'is_done' fields
    """
    result = {
        'think': None,
        'tool_calls': [],
        'answer': None,
        'is_done': False
    }
    
    # Extract <think> block
    think_pattern = r'<think>(.*?)</think>'
    think_match = re.search(think_pattern, action_text, re.DOTALL)
    if think_match:
        think_content = think_match.group(1).strip()
        try:
            result['think'] = json.loads(think_content)
            # 统计时添加额外调试信息
            if "统计" in turn_info and isinstance(result['think'], dict):
                if 'diagnosis' in result['think']:
                    diagnosis = result['think']['diagnosis']
                    if isinstance(diagnosis, dict) and 'label' in diagnosis:
                        print(f"[STATS PARSING] {turn_info} 解析到退化标签: {diagnosis['label']}")
        except json.JSONDecodeError as e:
            if "统计" in turn_info:
                print(f"[STATS PARSING] {turn_info} JSON解析失败: {e}, 内容: {repr(think_content[:100])}")
            result['think'] = think_content
    
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
    
    # Extract <answer> block
    answer_pattern = r'<answer>(.*?)</answer>'
    answer_match = re.search(answer_pattern, action_text, re.DOTALL)
    if answer_match:
        result['answer'] = answer_match.group(1).strip()
        result['is_done'] = True
    
    return result


def _create_tools_from_parsed_output(parsed_output, multi_modal_data=None, origin_multi_modal_data=None, raw_prompt=None, turn_info=""):
    """
    Create tool instances from parsed model output.
    
    Args:
        parsed_output: Output from _parse_model_output_for_tools
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
            print(f"[DEBUG TOOL] tool_call: {tool_call}")
            print(f"[DEBUG TOOL] tool_name: {tool_name}, 类型: {type(tool_name)}")
        
        # 检查tool_name格式错误
        if not tool_name:
            print(f"[ERROR TOOL] {turn_info} 工具调用缺少name字段: {tool_call}")
            tools.append(None)
            continue
        elif isinstance(tool_name, dict):
            print(f"[ERROR TOOL] {turn_info} 格式错误：name字段是字典而不是字符串: {tool_name}")
            print(f"[ERROR TOOL] {turn_info} 完整tool_call: {tool_call}")
            print(f"[ERROR TOOL] {turn_info} 这说明模型输出的JSON格式不正确")
            tools.append(None)
            continue
        elif isinstance(tool_name, list):
            print(f"[ERROR TOOL] {turn_info} 格式错误：name字段是列表而不是字符串: {tool_name}")
            tools.append(None)
            continue
        elif not isinstance(tool_name, str):
            print(f"[WARNING TOOL] {turn_info} name字段类型错误，强制转换为字符串: {tool_name} ({type(tool_name)}) -> {str(tool_name)}")
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
        print(f"[ERROR MULTIMODAL] ❌ 占位符不匹配: 需要{actual_image_count}个<image>, 实际{image_placeholder_count}个")

    vllm_input_prompt = prompt_str.replace('<image>', '<|vision_start|><|image_pad|><|vision_end|>')
    
    image_info_list = []
    for img in input_mm_data["image"]:
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        png_bytes = buf.getvalue()
        buf.close()
        img_info = {"bytes": png_bytes}
        image_info_list.append(img_info)

    input_mm_data["image"] = [process_image(img) for img in image_info_list]
    
    model_inputs = processor(text=[vllm_input_prompt], images=input_mm_data["image"], return_tensors="pt")
    input_ids = model_inputs.pop("input_ids")[0]
    attention_mask = model_inputs.pop("attention_mask")[0]

    if "second_per_grid_ts" in model_inputs:
        model_inputs.pop("second_per_grid_ts")

    mm_inputs = dict(model_inputs)
    return vllm_input_prompt, input_ids, mm_inputs


def compute_tool_degradation_matching_stats(
    tool_calls_per_sample, 
    degradation_types_per_sample, 
    degradation_to_tools,
    conversation_mode,
    all_degradation_types
):
    """
    计算工具-退化类型匹配统计（批次级别，每个step的统计）
    
    Args:
        tool_calls_per_sample: List[Dict[int, List[str]]]，每个样本的每轮调用的工具
        degradation_types_per_sample: List[List[str]]，每个样本的真实退化类型
        degradation_to_tools: Dict[str, List[str]]，退化类型到工具的映射
        conversation_mode: str，对话模式
        all_degradation_types: List[str]，所有退化类型
        
    Returns:
        dict: 批次级别的统计结果，会随每个step变化
        
    统计说明:
        - unique_ratio: 当前批次中，调用了正确工具的样本比例
        - repeat_ratio: 当前批次中，任何工具被重复调用的样本比例
        - 每个step的batch数据不同，统计值会随之变化
    """
    from collections import defaultdict, Counter
    
    # 初始化统计计数器
    # 重复统计：统计有多少样本重复调用了任何工具（包括正确和错误工具，调用次数>=2）
    degradation_sample_repeat_matched = defaultdict(int)  # 每种退化有多少样本存在工具重复调用
    degradation_sample_total = defaultdict(int)  # 每种退化类型出现的总样本数
    
    # 不重复统计：每个样本只统计一次（只要调用了正确工具就算）
    degradation_sample_matched_unique = defaultdict(int)  # 每种退化有多少样本调用了正确工具
    degradation_sample_total_unique = defaultdict(int)  # 每种退化在多少个样本中出现
    
    # 新增：工具数量匹配统计（按退化数量分组）
    # 统计样本调用的工具数量是否与退化数量匹配
    tool_count_match_stats = {
        'deg2': {'less': 0, 'exact': 0, 'more': 0, 'total': 0},  # 2种退化的样本
        'deg3': {'less': 0, 'exact': 0, 'more': 0, 'total': 0},  # 3种退化的样本
    }
    
    num_samples = len(tool_calls_per_sample)
    
    print(f"[TOOL STATS] 统计模式: {conversation_mode}")
    print(f"[TOOL STATS] 样本数量: {num_samples}")
    
    for idx in range(num_samples):
        tool_calls_dict = tool_calls_per_sample[idx]  # {turn: [tools]}
        degradation_types = degradation_types_per_sample[idx]  # [deg1, deg2, ...]
        
        if not degradation_types:
            # clean样本或没有退化信息，跳过
            continue
        
        # 决定使用哪些轮次的工具调用
        if conversation_mode == 'multi_tool_planning':
            # 多工具模式：只使用最后一轮
            if tool_calls_dict:
                max_turn = max(tool_calls_dict.keys())
                tools_to_use = tool_calls_dict.get(max_turn, [])
            else:
                tools_to_use = []
        else:
            # 单工具模式：使用所有轮次
            tools_to_use = []
            for turn in sorted(tool_calls_dict.keys()):
                tools_to_use.extend(tool_calls_dict[turn])
        
        # 先统计所有工具的重复情况（用于repeat_ratio，与tool_diversity_bonus一致）
        all_tools_counter = Counter(tools_to_use)
        sample_has_any_repeat = any(count >= 2 for count in all_tools_counter.values())
        
        # 【新增】统计工具数量匹配情况
        num_degradations = len(degradation_types)
        
        # 计算调用了多少个对应退化的工具（去重）
        matched_tools_set = set()
        for tool_name in tools_to_use:
            # 检查该工具对应当前样本的哪种退化
            for deg_type in degradation_types:
                correct_tools = degradation_to_tools.get(deg_type, [])
                if tool_name in correct_tools:
                    matched_tools_set.add(tool_name)
                    break  # 一个工具只计数一次
        
        num_matched_tools = len(matched_tools_set)
        
        # 根据退化数量分类统计（只统计2种和3种退化的样本）
        if num_degradations == 2:
            tool_count_match_stats['deg2']['total'] += 1
            if num_matched_tools < num_degradations:
                tool_count_match_stats['deg2']['less'] += 1
            elif num_matched_tools == num_degradations:
                tool_count_match_stats['deg2']['exact'] += 1
            else:  # num_matched_tools > num_degradations
                tool_count_match_stats['deg2']['more'] += 1
        elif num_degradations == 3:
            tool_count_match_stats['deg3']['total'] += 1
            if num_matched_tools < num_degradations:
                tool_count_match_stats['deg3']['less'] += 1
            elif num_matched_tools == num_degradations:
                tool_count_match_stats['deg3']['exact'] += 1
            else:  # num_matched_tools > num_degradations
                tool_count_match_stats['deg3']['more'] += 1
        
        # 统计每种退化类型
        for deg_type in degradation_types:
            # 增加该退化类型的总计数
            degradation_sample_total[deg_type] += 1
            degradation_sample_total_unique[deg_type] += 1
            
            # 获取该退化类型对应的工具列表
            correct_tools = degradation_to_tools.get(deg_type, [])
            
            if not correct_tools:
                print(f"[TOOL STATS WARNING] 退化类型 '{deg_type}' 没有对应的工具映射")
                continue
            
            # 统计该样本中每个正确工具的调用次数
            correct_tool_call_counter = Counter()
            for tool_name in tools_to_use:
                if tool_name in correct_tools:
                    correct_tool_call_counter[tool_name] += 1
            
            # 不重复统计：只要调用了任何一个正确工具就算匹配
            if len(correct_tool_call_counter) > 0:
                degradation_sample_matched_unique[deg_type] += 1
            
            # 重复统计：检查该样本是否有任何工具被调用了2次或以上（所有工具，不只是正确工具）
            # 这样和tool_diversity_bonus的逻辑一致
            if sample_has_any_repeat:
                degradation_sample_repeat_matched[deg_type] += 1
    
    # 计算批次级别的匹配率（每个step的统计）
    results = {}
    
    print(f"\n[TOOL STATS] === 工具-退化匹配统计（批次级别）===")
    print(f"[TOOL STATS] 不重复统计（只要调用了对应工具就算，样本级别）:")
    for deg_type in all_degradation_types:
        if deg_type == 'clean':
            continue
        
        total_samples = degradation_sample_total_unique[deg_type]
        matched_samples = degradation_sample_matched_unique[deg_type]
        
        if total_samples > 0:
            ratio_unique = matched_samples / total_samples
            # 批次级别统计：该退化类型在当前批次的工具匹配率
            results[f'tool_match/unique_ratio/{deg_type}'] = ratio_unique
            results[f'tool_match/unique_count/{deg_type}'] = float(matched_samples)
            results[f'tool_match/unique_total/{deg_type}'] = float(total_samples)
            print(f"[TOOL STATS]   {deg_type}: {matched_samples}/{total_samples} = {ratio_unique:.3f}")
        else:
            results[f'tool_match/unique_ratio/{deg_type}'] = 0.0
            results[f'tool_match/unique_count/{deg_type}'] = 0.0
            results[f'tool_match/unique_total/{deg_type}'] = 0.0
    
    print(f"\n[TOOL STATS] 重复统计（样本中任何工具被调用≥2次）:")
    for deg_type in all_degradation_types:
        if deg_type == 'clean':
            continue
        
        total_samples = degradation_sample_total[deg_type]
        repeat_matched_samples = degradation_sample_repeat_matched[deg_type]
        
        if total_samples > 0:
            ratio_repeat = repeat_matched_samples / total_samples
            results[f'tool_match/repeat_ratio/{deg_type}'] = ratio_repeat
            results[f'tool_match/repeat_count/{deg_type}'] = float(repeat_matched_samples)
            results[f'tool_match/repeat_total/{deg_type}'] = float(total_samples)
            print(f"[TOOL STATS]   {deg_type}: {repeat_matched_samples}/{total_samples} = {ratio_repeat:.3f}")
        else:
            results[f'tool_match/repeat_ratio/{deg_type}'] = 0.0
            results[f'tool_match/repeat_count/{deg_type}'] = 0.0
            results[f'tool_match/repeat_total/{deg_type}'] = 0.0
    
    # 【新增】工具数量匹配统计
    print(f"\n[TOOL STATS] 工具数量匹配统计（样本调用的工具数 vs 退化数量）:")
    for deg_count_key, stats in tool_count_match_stats.items():
        deg_num = int(deg_count_key.replace('deg', ''))
        total = stats['total']
        
        if total > 0:
            less_ratio = stats['less'] / total
            exact_ratio = stats['exact'] / total
            more_ratio = stats['more'] / total
            
            # 添加到结果（分组统计）
            results[f'tool_count_match/{deg_count_key}_less_ratio'] = less_ratio
            results[f'tool_count_match/{deg_count_key}_less_count'] = float(stats['less'])
            results[f'tool_count_match/{deg_count_key}_exact_ratio'] = exact_ratio
            results[f'tool_count_match/{deg_count_key}_exact_count'] = float(stats['exact'])
            results[f'tool_count_match/{deg_count_key}_more_ratio'] = more_ratio
            results[f'tool_count_match/{deg_count_key}_more_count'] = float(stats['more'])
            results[f'tool_count_match/{deg_count_key}_total'] = float(total)
            
            print(f"[TOOL STATS]   {deg_num}种退化的样本 (共{total}个):")
            print(f"[TOOL STATS]     少调用: {stats['less']}/{total} = {less_ratio:.3f}")
            print(f"[TOOL STATS]     刚好: {stats['exact']}/{total} = {exact_ratio:.3f}")
            print(f"[TOOL STATS]     多调用: {stats['more']}/{total} = {more_ratio:.3f}")
        else:
            # 没有该类型样本
            results[f'tool_count_match/{deg_count_key}_less_ratio'] = 0.0
            results[f'tool_count_match/{deg_count_key}_less_count'] = 0.0
            results[f'tool_count_match/{deg_count_key}_exact_ratio'] = 0.0
            results[f'tool_count_match/{deg_count_key}_exact_count'] = 0.0
            results[f'tool_count_match/{deg_count_key}_more_ratio'] = 0.0
            results[f'tool_count_match/{deg_count_key}_more_count'] = 0.0
            results[f'tool_count_match/{deg_count_key}_total'] = 0.0
    
    print(f"[TOOL STATS] === 统计完成 ===\n")
    
    return results


def agent_rollout_loop(config, vllm_engine, vllm_inputs, prompts, multi_modal_inputs, sampling_params):
    from vllm.distributed import parallel_state as vllm_ps
    import os

    # 读取对话模式配置
    conversation_mode = os.environ.get('AGENT_CONVERSATION_MODE', 'multi_tool_planning')
    print(f"[AGENT MODE] 对话模式: {conversation_mode}")
    
    if conversation_mode not in ['multi_tool_planning', 'single_tool_iterative']:
        print(f"[AGENT MODE WARNING] 未知模式 '{conversation_mode}'，使用默认模式 'multi_tool_planning'")
        conversation_mode = 'multi_tool_planning'
    
    # 读取单轮最大工具数限制
    max_tools_per_turn = int(os.environ.get('MAX_TOOLS_PER_TURN', '0'))
    if max_tools_per_turn > 0:
        print(f"[AGENT MODE] 单轮最大工具数: {max_tools_per_turn} (超过将被截断)")
    else:
        print(f"[AGENT MODE] 单轮最大工具数: 无限制")
    
    # 定义退化类型到工具的映射关系
    DEGRADATION_TO_TOOLS = {
        'rain': ['mprnet_deraining', 'restormer_deraining', 'xrestormer_deraining', 'nerd_deraining'],
        'haze': ['dehazeformer_dehaze'],
        'dark': ['retinexformer_enhance', 'retinexformer_lol_v1', 'retinexformer_lol_v2_real', 
                'retinexformer_lol_v2_synthetic', 'retinexformer_sdsd_indoor', 'retinexformer_sdsd_outdoor',
                'retinexformer_sid', 'retinexformer_smid', 'retinexformer_fivek'],
        'motion blur': ['xrestormer_motion_deblurring', 'mprnet_motion_deblurring', 'restormer_motion_deblurring'],
        'defocus blur': ['drbnet_defocus_deblurring', 'restormer_defocus_deblurring'],
        'noise': ['swinir_denoising', 'mprnet_denoising', 'scunet_real_denoising_psnr', 'scunet_real_denoising_gan',
                 'scunet_color_denoising', 'scunet_gray_denoising'],
        'low resolution': ['swinir_super_resolution', 'hat_super_resolution'],  # 添加HAT工具
        'jpeg compression artifact': ['swinir_jpeg_artifact_removal', 'fbcnn_jpeg_artifact_removal'],
    }
    
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

    # Refer to: https://github.com/vllm-project/vllm/issues/1728
    # and https://github.com/vllm-project/vllm/issues/15976
    # def process_bad_tokens(token_ids, logits, exclude_token_ids=[]):
    #     for token_id in exclude_token_ids:
    #         logits[token_id] = -9999.999
    #     return logits

    # # NOTE: tmp for visual agent!
    # exclude_func = partial(process_bad_tokens, exclude_token_ids=[
    #     151643,    # <|endoftext|>
    #     151644,    # <|im_start|>
    # ])
    # agent_sampling_params.logits_processors = [exclude_func]
    # agent_sampling_params.bad_words = ["<|endoftext|>", "<|im_start|>"]

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
    
    # 新增统计信息
    final_answer_list = []  # 是否以answer结束
    degradation_labels_list = []  # 退化类型列表
    repeated_degradation_cnt_list = []  # 连续重复退化数量
    
    # 工具调用统计（用于计算工具-退化匹配率）
    # 格式：每个样本记录 {turn: [tool_names]}
    tool_calls_per_sample = []  # List[Dict[int, List[str]]]，每个样本的每轮调用的工具列表
    degradation_types_per_sample = []  # List[List[str]]，每个样本的真实退化类型列表
    
    # 每种退化类型的连续出现统计
    all_degradation_types = ["rain", "haze", "dark", "motion blur", "defocus blur", "noise", "low resolution", "jpeg compression artifact", "clean"]
    consecutive_degradation_stats = {}
    last_round_degradations = []  # 跟踪每个样本上一轮的退化类型
    for deg_type in all_degradation_types:
        consecutive_degradation_stats[deg_type] = []  # 每个样本的连续次数

    env = ParallelEnv(config.agent, tokenizer, processor, conversation_mode=conversation_mode, max_tools_per_turn=max_tools_per_turn)
    env.reset(prompts, vllm_inputs, n=sampling_params.n)

    # interleaving inputs if sampling_params.n > 1
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
            
            # 初始化新增统计信息
            final_answer_list.append(False)
            degradation_labels_list.append([])  # 存储每轮的退化标签
            repeated_degradation_cnt_list.append(0)
            
            # 初始化每种退化类型的连续统计
            for deg_type in all_degradation_types:
                consecutive_degradation_stats[deg_type].append(0)
            last_round_degradations.append(set())  # 初始化为空集合
            
            # 初始化工具调用统计
            tool_calls_per_sample.append({})  # 每个样本的工具调用记录 {turn: [tools]}
            degradation_types_per_sample.append([])  # 每个样本的真实退化类型

    pg = vllm_ps.get_tp_group()
    max_total_length = config.prompt_length + config.response_length
    for step in range(config.agent.max_turns):
        print(f'[DEBUG step {step + 1}] 🔄 活跃: {sum(active_mask)}/{batch_size * sampling_params.n}')
        
        if sum(active_mask) == 0:
            print(f'[DEBUG step {step + 1}] 结束: 无活跃对话')
            break

        active_indices = [idx for idx, is_active in enumerate(active_mask) if is_active]
        active_vllm_inputs = [vinput for vinput, is_active in zip(vllm_input_list, active_mask) if is_active]
        actions = vllm_engine.generate(
            prompts=active_vllm_inputs,
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
            
            # print(f'[DEBUG step {step + 1}-{active_idx:02d}] 解析: {"|".join(format_tags) if format_tags else "无有效标签"}')
            # print(f'[DEBUG step {step + 1}-{active_idx:02d}] 解析: {"|".join(format_tags) if format_tags else "无有效标签"}')
        if pg.is_first_rank:
            obs_results = env.step(active_indices, actions, current_turn=step + 1)
        else:
            obs_results = None

        obs_results = pg.broadcast_object(obs_results)
        observations, rewards, dones, info = obs_results


        for idx, obs, act, rew, done in zip(active_indices, observations, actions, rewards, dones):
            # 收集统计信息 - 解析当前动作
            action_text = act.outputs[0].text
            parsed_action = _parse_model_output_for_tools(action_text, f"统计-轮次{step + 1}")
            
            # 收集工具调用信息（用于统计工具-退化匹配率）
            if parsed_action.get('tool_calls'):
                tool_calls = parsed_action['tool_calls']
                
                # 【修复】单工具迭代模式下，统计前先截断（与execute_tool_call中的逻辑一致）
                if conversation_mode == 'single_tool_iterative' and len(tool_calls) > 1:
                    print(f"[TOOL STATS WARNING] 样本{idx} 轮次{step + 1}: 单工具模式下检测到{len(tool_calls)}个工具，截断为1个")
                    tool_calls = [tool_calls[0]]
                
                tool_names = []
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict) and 'name' in tool_call:
                        tool_names.append(tool_call['name'])
                if tool_names:
                    tool_calls_per_sample[idx][step + 1] = tool_names
                    print(f"[TOOL STATS] 样本{idx} 轮次{step + 1}: 调用工具 {tool_names} (统计数量: {len(tool_names)})")
            
            # 保存对话历史（用于wandb可视化）
            if hasattr(env, 'conversation_history') and idx < len(env.conversation_history):
                turn_record = {
                    'turn': step + 1,
                    'response': action_text,
                    'is_done': parsed_action.get('is_done', False)
                }
                # TODO: 未来可以从工具返回的info中提取错误信息
                # 目前info是字典不是列表，无法在zip中使用
                
                env.conversation_history[idx].append(turn_record)
            
            # 统计是否以answer结束
            if parsed_action.get('is_done', False):
                final_answer_list[idx] = True
                print(f"[STATS] 样本{idx} 以answer结束")
            
            # 统计退化类型
            think_data = parsed_action.get('think')
            print(f"[STATS] 样本{idx} 轮次{step + 1} 思考数据: {think_data}, 类型: {type(think_data)}")
            
            current_labels = []
            # 确保think_data是字典且包含diagnosis
            if isinstance(think_data, dict) and 'diagnosis' in think_data:
                diagnosis = think_data['diagnosis']
                print(f"[STATS] 样本{idx} diagnosis数据: {diagnosis}, 类型: {type(diagnosis)}")
                
                if isinstance(diagnosis, dict) and 'label' in diagnosis:
                    # 处理单个标签，转换为列表格式以保持一致性
                    label = diagnosis.get('label', '')
                    current_labels = [label] if label else []
                    print(f"[STATS] 样本{idx} 提取到的标签: {current_labels}")
                elif isinstance(diagnosis, dict) and 'labels' in diagnosis:
                    # 兼容多标签格式，安全处理嵌套列表
                    raw_labels = diagnosis.get('labels', [])
                    current_labels = []
                    
                    # 处理可能的嵌套列表
                    if isinstance(raw_labels, list):
                        for item in raw_labels:
                            if isinstance(item, str):
                                current_labels.append(item)
                            elif isinstance(item, list):
                                # 展平嵌套列表
                                current_labels.extend([str(x) for x in item])
                            else:
                                current_labels.append(str(item))
                    else:
                        current_labels = [str(raw_labels)]
                    
                    print(f"[STATS] 样本{idx} 提取到的标签: {current_labels}")
                else:
                    print(f"[STATS] 样本{idx} diagnosis格式错误或缺少label/labels字段")
            else:
                print(f"[STATS] 样本{idx} think数据不是字典或缺少diagnosis字段")
            
            # 安全地创建标签集合，处理可能的非哈希类型
            try:
                # 确保所有元素都是可哈希的
                hashable_labels = []
                for label in current_labels:
                    if isinstance(label, (str, int, float)):
                        hashable_labels.append(str(label))
                    elif isinstance(label, list):
                        # 如果是列表，转换为字符串
                        hashable_labels.append(str(label))
                    else:
                        hashable_labels.append(str(label))
                
                current_labels_set = set(hashable_labels)
                current_labels = hashable_labels  # 更新为可哈希的版本
                print(f"[STATS] 样本{idx} 处理后的标签: {current_labels}")
            except TypeError as e:
                print(f"[STATS ERROR] 样本{idx} 无法创建标签集合: {e}, 原始标签: {current_labels}")
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
                
                # 检查连续重复退化（只统计连续出现的相同退化）
                # 修改逻辑：只有当某个退化类型在consecutive_degradation_stats中>1时才算重复
                consecutive_repeat_count = 0
                for deg_type in all_degradation_types:
                    if consecutive_degradation_stats[deg_type][idx] > 1:
                        # 这个退化类型连续出现了，算作重复
                        consecutive_repeat_count += 1
                
                if consecutive_repeat_count > 0 and step > 0:
                    repeated_degradation_cnt_list[idx] += consecutive_repeat_count
                    consecutive_types = [deg for deg in all_degradation_types if consecutive_degradation_stats[deg][idx] > 1]
                    print(f"[STATS] 样本{idx} 连续重复退化: {consecutive_types} (计数: {consecutive_repeat_count})")
                
                print(f"[STATS] 样本{idx} 轮次{step + 1} 退化类型: {current_labels}")
                
                # 打印连续统计
                consecutive_info = []
                for deg_type in all_degradation_types:
                    if consecutive_degradation_stats[deg_type][idx] > 1:
                        consecutive_info.append(f"{deg_type}:{consecutive_degradation_stats[deg_type][idx]}")
                if consecutive_info:
                    print(f"[STATS] 样本{idx} 连续退化: {', '.join(consecutive_info)}")
            else:
                # 当前轮没有退化标签，重置所有连续计数
                for deg_type in all_degradation_types:
                    consecutive_degradation_stats[deg_type][idx] = 0
                last_round_degradations[idx] = set()
            
            # process response token ids
            response_token_ids = torch.tensor(act.outputs[0].token_ids, dtype=torch.int64, device=running_states[idx].device)
            running_states[idx] = torch.cat([running_states[idx], response_token_ids])
            vllm_input_list[idx]['prompt_token_ids'] = _concat_vllm_input(
                vllm_input_list[idx]['prompt_token_ids'], 
                response_token_ids,
                tokenizer=tokenizer,
            )

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

            # Count tool calls based on whether the action actually contains tool_calls
            # Logic differs by conversation mode:
            # - multi_tool_planning: count number of tools in current turn (overwrite, not accumulate)
            # - single_tool_iterative: accumulate tool calls across turns
            if parsed_action.get('tool_calls'):
                tool_calls = parsed_action['tool_calls']
                
                # 【修复】单工具迭代模式下，统计前先截断（与execute_tool_call和上面的统计逻辑一致）
                if conversation_mode == 'single_tool_iterative' and len(tool_calls) > 1:
                    tool_calls = [tool_calls[0]]
                
                num_tools = len(tool_calls)
                
                if conversation_mode == 'multi_tool_planning':
                    # 多工具模式：用当前轮的工具数量覆盖（统计最后一轮工具链内的工具数）
                    tool_call_cnt_list[idx] = num_tools
                    print(f"[DEBUG TOOL CNT] 样本{idx} 轮次{step + 1}: 工具调用计数 = {num_tools} (多工具模式，覆盖)")
                else:
                    # 单工具模式：累加每轮的工具调用次数（已截断为1个）
                    tool_call_cnt_list[idx] += num_tools
                    print(f"[DEBUG TOOL CNT] 样本{idx} 轮次{step + 1}: 工具调用计数 = {tool_call_cnt_list[idx]} (单工具模式，累加)")
            elif parsed_action.get('is_done', False):
                # Model generated <answer> block, no tool call
                print(f"[DEBUG TOOL CNT] 样本{idx} 轮次{step + 1}: 给出answer，无工具调用")
            else:
                # Model only generated <think> or invalid format
                print(f"[DEBUG TOOL CNT] 样本{idx} 轮次{step + 1}: 仅思考或格式错误，无工具调用")
            
            if done or step == config.agent.max_turns - 1:
                active_mask[idx] = False
                continue

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

                vllm_input_list[idx]['prompt_token_ids'] = _concat_vllm_input(
                    vllm_input_list[idx]['prompt_token_ids'], 
                    obs_token_ids_vllm,
                    tokenizer=tokenizer,
                )

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
                    mm_input_list[idx] = _merge_multi_modal_inputs(mm_input_list[idx], mm_input)

            if running_states[idx].shape[-1] >= max_total_length or len(vllm_input_list[idx]['prompt_token_ids']) >= max_total_length:
                active_mask[idx] = False

    # 提取真实退化类型（从prompts的reward_model或env_name）
    # 参考：verl/utils/reward_score/image_restoration.py 的 parse_reward_model_to_degradations_v2 和 parse_env_name_to_degradations_v2
    print(f"[TOOL STATS] 开始提取真实退化类型...")
    for i in range(batch_size):
        data_item = prompts[i]
        # 获取reward_model和env_name
        reward_model = data_item.non_tensor_batch.get("reward_model", [])
        env_name = data_item.non_tensor_batch.get("env_name", "")
        
        # 提取退化类型（优先使用reward_model，与现有代码逻辑一致）
        degradation_types = []
        
        # 方法1：从reward_model提取（优先）
        if reward_model and isinstance(reward_model, list) and len(reward_model) > 0:
            for item in reward_model:
                if isinstance(item, dict) and 'degradation_type' in item:  # 注意：字段名是 'degradation_type' 不是 'type'
                    deg_type = item['degradation_type']
                    if deg_type is not None and str(deg_type).strip() and str(deg_type).strip().lower() != 'clean':
                        # 统一转换为小写，与DEGRADATION_TO_TOOLS的键匹配
                        degradation_types.append(str(deg_type).strip().lower())
        
        # 方法2：从env_name提取（备用）
        if not degradation_types and env_name and env_name.strip().lower() != "clean":
            # env_name格式：逆序，逗号分隔，例如 "noise, haze, rain" 表示先加rain，再haze，最后noise
            parts = [p.strip() for p in env_name.split(',') if p.strip()]
            # 逆序后就是添加顺序（与reward_model一致）
            degradation_types = list(reversed(parts))
        
        # 为每个重复的样本复制退化类型
        for _ in range(sampling_params.n):
            idx = i * sampling_params.n + _
            degradation_types_per_sample[idx] = degradation_types
            if i < 3:  # 只打印前3个样本，避免日志过多
                print(f"[TOOL STATS] 样本{idx}: 真实退化类型 {degradation_types} (来源: {'reward_model' if reward_model else 'env_name'})")
    
    # 计算工具-退化匹配统计（批次级别，每个step的统计）
    print(f"[TOOL STATS] 开始计算工具-退化匹配统计...")
    tool_degradation_stats = compute_tool_degradation_matching_stats(
        tool_calls_per_sample=tool_calls_per_sample,
        degradation_types_per_sample=degradation_types_per_sample,
        degradation_to_tools=DEGRADATION_TO_TOOLS,
        conversation_mode=conversation_mode,
        all_degradation_types=all_degradation_types
    )
    
    # Save image_history_list, original_images, extra_info, and conversation_history BEFORE closing env (env.close() will clear it)
    saved_image_history_list = env.multi_modal_data_history_list.copy() if hasattr(env, 'multi_modal_data_history_list') else []
    saved_original_images = env.origin_multi_modal_data_list.copy() if hasattr(env, 'origin_multi_modal_data_list') else []
    saved_extra_info_list = env.extra_info_list.copy() if hasattr(env, 'extra_info_list') else []
    saved_conversation_history = env.conversation_history.copy() if hasattr(env, 'conversation_history') else []
    
    # 为每个extra_info添加对话模式信息（用于奖励计算中的工具多样性bonus）
    for i, extra_info in enumerate(saved_extra_info_list):
        if extra_info is not None and isinstance(extra_info, dict):
            extra_info['conversation_mode'] = conversation_mode
    
    print(f"[DEBUG EXTRA_INFO] saved_extra_info_list length: {len(saved_extra_info_list)}")
    print(f"[DEBUG EXTRA_INFO] Added conversation_mode='{conversation_mode}' to all extra_info")
    
    env.close()
    target_device = prompts.batch['input_ids'].device
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
                image_grid_thw=mm_input_list[i].get("image_grid_thw", None),
                video_grid_thw=mm_input_list[i].get("video_grid_thw", None),
                second_per_grid_ts=mm_input_list[i].get("second_per_grid_ts", None),
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
    
    # 处理新增统计信息
    final_answer_tensor = torch.tensor([1.0 if x else 0.0 for x in final_answer_list], dtype=torch.float32).to(target_device).unsqueeze(1)
    
    # 统计退化类型出现次数
    degradation_stats = {}
    for deg_type in all_degradation_types:
        # 总出现次数统计
        count_list = []
        for labels in degradation_labels_list:
            count_list.append(float(labels.count(deg_type)))
        degradation_stats[f"degradation_{deg_type.replace(' ', '_')}_total"] = torch.tensor(count_list, dtype=torch.float32).to(target_device).unsqueeze(1)
        
        # 连续出现次数统计
        consecutive_list = consecutive_degradation_stats[deg_type]
        degradation_stats[f"degradation_{deg_type.replace(' ', '_')}_consecutive"] = torch.tensor(consecutive_list, dtype=torch.float32).to(target_device).unsqueeze(1)
    
    repeated_degradation_tensor = torch.tensor(repeated_degradation_cnt_list, dtype=torch.float32).to(target_device).unsqueeze(1)
    
    # 将工具-退化匹配统计转换为tensor（批次级别，每个step会更新）
    tool_match_tensors = {}
    for key, value in tool_degradation_stats.items():
        # 该批次的所有样本使用相同的批次统计值
        # 注意：每个step的batch不同，所以统计值会随step变化
        tool_match_tensors[key] = torch.full(
            (batch_size * sampling_params.n, 1), 
            value, 
            dtype=torch.float32,
            device=target_device
        )
    
    # 打印添加的指标键（用于调试）
    print(f"[DEBUG STATS] tool_degradation_stats 返回了 {len(tool_degradation_stats)} 个指标")
    tool_count_keys = [k for k in tool_degradation_stats.keys() if k.startswith('tool_count_match/')]
    print(f"[DEBUG STATS] 其中 tool_count_match/ 指标: {len(tool_count_keys)} 个")
    if tool_count_keys:
        print(f"[DEBUG STATS] tool_count_match 指标示例: {tool_count_keys[:3]}")
    
    # 打印详细统计摘要
    print(f"\n[STATS SUMMARY] === 退化类型统计详情 ===")
    print(f"[STATS SUMMARY] 以answer结束的样本: {sum(final_answer_list)}/{len(final_answer_list)}")
    print(f"[STATS SUMMARY] 连续重复退化平均次数: {sum(repeated_degradation_cnt_list)/len(repeated_degradation_cnt_list):.2f} (只统计连续出现的相同退化)")
    
    print(f"[STATS SUMMARY] 原始数据检查:")
    print(f"[STATS SUMMARY]   degradation_labels_list长度: {len(degradation_labels_list)}")
    for i, labels in enumerate(degradation_labels_list[:3]):  # 只显示前3个样本
        print(f"[STATS SUMMARY]   样本{i}的标签: {labels}")
    
    print(f"[STATS SUMMARY] 退化类型出现统计:")
    for deg_type in all_degradation_types:
        total_count = sum([labels.count(deg_type) for labels in degradation_labels_list])
        if total_count > 0:
            print(f"[STATS SUMMARY]   {deg_type}: {total_count} 次")
            
    print(f"[STATS SUMMARY] 传递给WandB的tensor形状:")
    for key, tensor in degradation_stats.items():
        if 'total' in key:
            print(f"[STATS SUMMARY]   {key}: shape={tensor.shape}, sum={torch.sum(tensor).item():.1f}")
    
    print(f"[STATS SUMMARY] === 统计详情结束 ===\n")
    
    # Prepare non_tensors dict with image_history_list for wandb logging
    non_tensors_dict = {}
    if processor is not None:
        non_tensors_dict["multi_modal_inputs"] = mm_input_list
    
    # Add image_history_list, original_images, extra_info, and conversation_history for wandb image logging
    # Note: We saved the lists before env.close() to avoid them being cleared
    # Note: mm_input_list is already interleaved, so saved_image_history_list should match it
    # IMPORTANT: saved lists have batch_size elements, but mm_input_list has batch_size*n elements
    # We need to replicate each element n times to match the interleaved structure
    print(f"[DEBUG IMAGE_HISTORY] saved_image_history_list length: {len(saved_image_history_list)}, mm_input_list length: {len(mm_input_list)}")
    print(f"[DEBUG IMAGE_HISTORY] saved_extra_info_list length: {len(saved_extra_info_list)}")
    print(f"[DEBUG IMAGE_HISTORY] saved_conversation_history length: {len(saved_conversation_history)}")
    
    if len(saved_image_history_list) > 0:
        # IMPORTANT: saved_image_history_list is ALREADY interleaved by env.reset()
        # env.reset() receives prompts that may already be repeated (batch_size × n)
        # So saved_image_history_list already has the correct size to match mm_input_list
        # We should NOT interleave again!
        
        expected_size = len(mm_input_list)
        actual_size = len(saved_image_history_list)
        
        print(f"[DEBUG IMAGE_HISTORY] saved_image_history_list length: {actual_size}, mm_input_list length: {expected_size}")
        
        # Direct assignment - NO interleaving needed
        image_history_to_add = saved_image_history_list
        
        # 确保conversation_history的大小和结构正确
        if len(saved_conversation_history) == actual_size:
            conversation_history_to_add = saved_conversation_history
        else:
            # Fallback: 创建空的对话历史
            conversation_history_to_add = [[] for _ in range(actual_size)]
            print(f"[DEBUG IMAGE_HISTORY] conversation_history size mismatch, using empty lists. saved={len(saved_conversation_history)}, expected={actual_size}")
        
        # Extract original images from extra_info
        original_images_to_add = []
        for i in range(actual_size):
            original_img = None  # Default to None
            
            # 从saved_extra_info_list中获取真正的original_image
            if i < len(saved_extra_info_list) and saved_extra_info_list[i] is not None:
                extra_info = saved_extra_info_list[i]
                
                # 调试：查看extra_info的内容（只打印第一个）
                if i == 0:
                    print(f"[DEBUG GT] extra_info keys: {list(extra_info.keys()) if isinstance(extra_info, dict) else 'not dict'}")
                    if isinstance(extra_info, dict):
                        print(f"[DEBUG GT] original_image type: {type(extra_info.get('original_image'))}")
                        print(f"[DEBUG GT] original_image is None: {extra_info.get('original_image') is None}")
                
                # 从extra_info中提取original_image（这才是真正的GT）
                if isinstance(extra_info, dict) and extra_info.get('original_image') is not None:
                    original_img = extra_info['original_image']
                    if i == 0:
                        print(f"[DEBUG GT] ✓ Using original_image from extra_info")
            
            # Fallback to origin_multi_modal_data if extra_info doesn't have original_image
            if original_img is None and i < len(saved_original_images):
                original_img = saved_original_images[i]
                if i == 0:
                    print(f"[DEBUG GT] ⚠️  Fallback to origin_multi_modal_data (可能也是退化的)")
            
            # Append (even if None) to maintain correct list length
            original_images_to_add.append(original_img)
            
            if i == 0 and original_img is None:
                print(f"[DEBUG GT] ❌ Warning: Sample 0 has no original_image!")
        
        print(f"[DEBUG IMAGE_HISTORY] No interleaving needed - data already matches mm_input_list structure")
        print(f"[DEBUG IMAGE_HISTORY] original_images_to_add length: {len(original_images_to_add)}, conversation_history_to_add length: {len(conversation_history_to_add)}")
        
        if actual_size == expected_size:
            # 添加image_history_list（确保1维）
            # 使用np.empty + 赋值的方式，避免numpy自动推断维度
            img_hist_array = np.empty(actual_size, dtype=object)
            for i in range(actual_size):
                img_hist_array[i] = image_history_to_add[i]
            non_tensors_dict["image_history_list"] = img_hist_array
            
            # 添加conversation_history（确保1维，即使全是空列表）
            conv_hist_array = np.empty(actual_size, dtype=object)
            for i in range(actual_size):
                conv_hist_array[i] = conversation_history_to_add[i] if i < len(conversation_history_to_add) else []
            non_tensors_dict["conversation_history"] = conv_hist_array
            
            # 添加original_images（确保1维）
            if len(original_images_to_add) >= expected_size:
                orig_img_array = np.empty(expected_size, dtype=object)
                for i in range(expected_size):
                    orig_img_array[i] = original_images_to_add[i] if i < len(original_images_to_add) else None
                non_tensors_dict["original_images"] = orig_img_array
                print(f"[DEBUG IMAGE_HISTORY] ✓ Added image_history_list, original_images, and conversation_history")
            else:
                # original_images太少，用None填充
                orig_img_array = np.empty(expected_size, dtype=object)
                for i in range(expected_size):
                    orig_img_array[i] = original_images_to_add[i] if i < len(original_images_to_add) else None
                non_tensors_dict["original_images"] = orig_img_array
                print(f"[DEBUG IMAGE_HISTORY] ✓ Added all fields (original_images padded: {len(original_images_to_add)}/{expected_size})")
            
            # 添加extra_info
            # 🔥 关键修复：extra_info应该和image_history_list使用相同的索引逻辑！
            # saved_extra_info_list已经在reset中interleaved了（每个原始样本重复n次）
            # 所以和image_history_list长度相同，直接对应即可
            if saved_extra_info_list:
                extra_info_array = np.empty(expected_size, dtype=object)
                for i in range(expected_size):
                    # 🔥 直接使用i索引（与image_history_list一致，不再使用orig_idx）
                    extra_info_array[i] = saved_extra_info_list[i] if i < len(saved_extra_info_list) else None
                non_tensors_dict["extra_info"] = extra_info_array
                print(f"[DEBUG EXTRA_INFO] ✓ Added extra_info (直接对应): {len(saved_extra_info_list)} -> {expected_size}")
            else:
                # 如果没有extra_info，添加None数组
                extra_info_array = np.empty(expected_size, dtype=object)
                for i in range(expected_size):
                    extra_info_array[i] = None
                non_tensors_dict["extra_info"] = extra_info_array
                print(f"[DEBUG EXTRA_INFO] ⚠️  No extra_info, added None array")
            
            # 验证维度
            print(f"[DEBUG IMAGE_HISTORY]   Array shapes: img_hist={img_hist_array.shape} (ndim={img_hist_array.ndim}), conv_hist={conv_hist_array.shape} (ndim={conv_hist_array.ndim}), orig_img={non_tensors_dict['original_images'].shape}")
        else:
            print(f"[DEBUG IMAGE_HISTORY] ✗ Size mismatch! expected={expected_size}, actual={actual_size}, NOT adding data")
            # 即使size不匹配，也要添加空数组以保持keys一致
            empty_size = len(mm_input_list)
            non_tensors_dict["image_history_list"] = np.empty(empty_size, dtype=object)
            non_tensors_dict["conversation_history"] = np.empty(empty_size, dtype=object)
            non_tensors_dict["original_images"] = np.empty(empty_size, dtype=object)
            non_tensors_dict["extra_info"] = np.empty(empty_size, dtype=object)
            for i in range(empty_size):
                non_tensors_dict["image_history_list"][i] = []
                non_tensors_dict["conversation_history"][i] = []
                non_tensors_dict["original_images"][i] = None
                non_tensors_dict["extra_info"][i] = None
    else:
        print(f"[DEBUG IMAGE_HISTORY] ✗ saved_image_history_list is empty, adding empty arrays to maintain key consistency")
        # 即使数据为空，也要添加空数组以保持所有worker的keys一致
        empty_size = len(mm_input_list)
        non_tensors_dict["image_history_list"] = np.empty(empty_size, dtype=object)
        non_tensors_dict["conversation_history"] = np.empty(empty_size, dtype=object)
        non_tensors_dict["original_images"] = np.empty(empty_size, dtype=object)
        non_tensors_dict["extra_info"] = np.empty(empty_size, dtype=object)
        for i in range(empty_size):
            non_tensors_dict["image_history_list"][i] = []
            non_tensors_dict["conversation_history"][i] = []
            non_tensors_dict["original_images"][i] = None
            non_tensors_dict["extra_info"][i] = None
    
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
            **degradation_stats,
            **tool_match_tensors,  # 添加工具-退化匹配统计
        },
        non_tensors=non_tensors_dict
    )


def execute_tool_call(sample, tokenizer=None, processor=None, pbar=None, conversation_mode='multi_tool_planning', max_tools_per_turn=0):
    action_string = sample.get('action', '')
    tools = sample.get('tools', [])
    parsed_output = sample.get('parsed_output', {})
    turn_info = sample.get('turn_info', '')
    # print(f'[DEBUG {turn_info}] ', action_string)
    # print(f'[DEBUG {turn_info}] ', tools)
    # print(f'[DEBUG {turn_info}] ', parsed_output)

    # 工具执行开始
    valid_tools = [t for t in tools if t is not None]
    
    # 🔥 限制单轮工具数量（避免浪费时间）
    if max_tools_per_turn > 0 and len(valid_tools) > max_tools_per_turn:
        print(f'[TOOL LIMIT {turn_info}] 工具数量超限: {len(valid_tools)} > {max_tools_per_turn}，截断到前{max_tools_per_turn}个')
        tools = tools[:max_tools_per_turn]
        valid_tools = [t for t in tools if t is not None]

    # non-agent data or no tools to execute
    if action_string == '':
        return {}, 0.0, True, {}
    
    # Handle <answer> case - episode is done (CHECK THIS FIRST!)
    if parsed_output.get('is_done', False):
        return {}, 0.0, True, {"status": "success", "type": "answer"}  # Episode done, no reward here
    
    # Then check if tools is empty
    if not tools:
        # If tools is empty but action_string is not, it means parsing failed
        error_msg = "Failed to parse valid tool calls from the action string. Please check the format of your <tool_call> blocks."
        error_text = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        
        # Encode error message in the expected format
        obs_token_ids = tokenizer.encode(error_text, add_special_tokens=False)
        error_obs = {
            "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
            "prompt_token_ids_model": torch.tensor(obs_token_ids),
        }
        return error_obs, 0.0, False, {"error": error_msg, "status": "failed"}

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
            # print(f'[DEBUG {turn_info}] ', compatible_action_string)
            print(f'[DEBUG {turn_info}] 执行工具{i+1}/{len(tools)}: {tool.name}')
            tool_result, reward, done, info = tool.execute(compatible_action_string)
            # 安全检查：tool_result可能是字符串（错误信息）而不是字典
            has_multi_modal = isinstance(tool_result, dict) and tool_result.get("multi_modal_data") is not None
            print(f'[DEBUG {turn_info}] 结果: multi_modal_data={has_multi_modal}, reward={reward:.3f}, done={done}')
            print(f'[DEBUG {turn_info}] 状态: {info.get("status", "unknown")}')
            executed_count += 1
            
            # 累积结果
            final_tool_result = tool_result
            total_reward += reward
            final_done = final_done or done
            final_info.update(info)
            
            # 【关键修改】多工具链式规划模式：将当前工具的输出图像传递给下一个工具
            if conversation_mode == 'multi_tool_planning' and i < len(tools) - 1:
                # 有下一个工具，且当前工具产生了图像输出
                if final_tool_result and isinstance(final_tool_result, dict) and 'multi_modal_data' in final_tool_result:
                    next_tool = tools[i + 1]
                    if next_tool is not None:
                        # 更新下一个工具的输入图像
                        try:
                            # 使用 reset 方法更新工具的输入图像
                            next_tool.reset(
                                raw_prompt=next_tool.raw_prompt if hasattr(next_tool, 'raw_prompt') else None,
                                multi_modal_data=deepcopy(final_tool_result['multi_modal_data']),
                                origin_multi_modal_data=next_tool.origin_multi_modal_data if hasattr(next_tool, 'origin_multi_modal_data') else None,
                            )
                            print(f'[DEBUG {turn_info}] 链式传递: 工具{i+1}的输出 → 工具{i+2}的输入')
                        except Exception as reset_error:
                            print(f'[WARNING {turn_info}] 更新工具{i+2}输入图像失败: {reset_error}')
            
        except Exception as e:
            print(f'[ERROR {turn_info}] 工具{i+1}执行异常: {e}')
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

        # 🔥 关键修复：保存原始PIL图像（用于reward计算）
        # _preprocess_multi_modal_inputs会修改multi_modal_data（调用process_image/fetch_image）
        # 所以先deepcopy保存原始数据
        original_multi_modal_data_for_reward = deepcopy(final_tool_result.get("multi_modal_data", {}))

        prompt_str_vllm, obs_token_ids_model, mm_inputs = _preprocess_multi_modal_inputs(prompt_str, processor, **final_tool_result)
        obs_token_ids_vllm = tokenizer.encode(prompt_str_vllm, add_special_tokens=False, return_tensors='pt')[0]
        tool_result_info = {
            "prompt_token_ids_vllm": obs_token_ids_vllm,
            "prompt_token_ids_model": obs_token_ids_model,
            **final_tool_result   # multi_modal_data（已被fetch_image处理，用于VLLM）
        }
        if mm_inputs:
            tool_result_info["multi_modal_inputs"] = mm_inputs
        
        # 🔥 关键：添加原始multi_modal_data用于reward计算
        tool_result_info["multi_modal_data_for_reward"] = original_multi_modal_data_for_reward

    else:
        raise ValueError(f"Invalid tool_result type: {type(final_tool_result)=} -- {final_tool_result}")

    if pbar is not None:
        pbar.update(1)
    return tool_result_info, total_reward, final_done, final_info


class ParallelEnv:
    """
    The interface is designed to be the similar to : https://github.com/openai/gym
    """
    def __init__(self, env_config, tokenizer, processor, conversation_mode='multi_tool_planning', max_tools_per_turn=0, **kwargs):
        self.config = env_config
        self.tokenizer = tokenizer
        self.processor = processor
        self.conversation_mode = conversation_mode  # 对话模式：multi_tool_planning 或 single_tool_iterative
        self.max_tools_per_turn = max_tools_per_turn  # 单轮最大工具数（0=无限制）

        # type: List[ Dict[ Str, ToolBase subclasses ] ]
        self.tools = []
        
        # 初始化列表（避免reset前访问导致AttributeError）
        self.conversation_history = []
        self.multi_modal_data_history_list = []
        self.origin_multi_modal_data_list = []
        self.extra_info_list = []
        self.raw_prompts = []

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

        # 工具解析和创建
        agent_inputs = []
        
        for i, idx, action in zip(real_indices, valid_indices, valid_actions):
            turn_info = f"T{current_turn}-样本{idx}"
            
            # 解析模型输出
            parsed_output = _parse_model_output_for_tools(action, turn_info)
            
            tool_calls_count = len(parsed_output.get('tool_calls', []))
            has_answer = parsed_output.get('is_done', False)
            has_think = parsed_output.get('think') is not None
            print(f'[DEBUG step {current_turn}-{idx:02d}] 工具解析: {parsed_output.get("tool_calls", [])}')
           
            print(f'[DEBUG step {current_turn}-{idx:02d}] 思考: {parsed_output.get("think", None)}')
            # 创建工具实例
            tools = []
            if parsed_output['tool_calls']:
                # 【单工具模式验证】确保每轮只调用一个工具
                if self.conversation_mode == 'single_tool_iterative' and len(parsed_output['tool_calls']) > 1:
                    print(f'[FORMAT ERROR {turn_info}] 单工具迭代模式下，每轮只能调用一个工具，但检测到{len(parsed_output['tool_calls'])}个工具调用')
                    # 可以选择只使用第一个工具，或者返回错误
                    # 这里选择只使用第一个工具，并给出警告
                    parsed_output['tool_calls'] = [parsed_output['tool_calls'][0]]
                
                # 获取最新的图像数据（历史列表的最后一个元素）
                current_multi_modal_data = (
                    self.multi_modal_data_history_list[idx][-1] 
                    if self.multi_modal_data_history_list[idx] 
                    else None
                )
                
                # 调试：显示使用的是哪个图像
                history_len = len(self.multi_modal_data_history_list[idx]) if self.multi_modal_data_history_list[idx] else 0
                if self.conversation_mode == 'single_tool_iterative':
                    print(f'[DEBUG {turn_info}] 🔄 单工具模式: 使用历史图像[{history_len-1}] (共{history_len}张图像)')
                elif len(parsed_output['tool_calls']) > 1:
                    print(f'[DEBUG {turn_info}] 🔗 多工具模式: 使用历史图像[{history_len-1}], 将链式执行{len(parsed_output["tool_calls"])}个工具')
                
                tools = _create_tools_from_parsed_output(
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
                        tool_names.append(tool_call.get('name', 'unknown'))
                    else:
                        tool_names.append('格式错误')
                
                success_count = sum(1 for t in tools if t is not None)
                mode_indicator = "🔗" if self.conversation_mode == 'multi_tool_planning' else "🔄"
                # print(f'[DEBUG step {current_turn}-{idx:02d}] {mode_indicator} 工具: {success_count}/{len(tools)}个成功 [{", ".join(tool_names)}]')
                
            # elif has_answer:
            #     print(f'[DEBUG step {current_turn}-{idx:02d}] 答案: 任务完成')
            # else:
            #     print(f'[DEBUG step {current_turn}-{idx:02d}] 错误: 无有效工具调用或答案')
            
            agent_inputs.append(dict(
                idx=i,
                valid_idx=idx,
                action=action,
                tools=tools,
                parsed_output=parsed_output,
                turn_info=turn_info,
            ))

        # 工具执行
        num_workers = min(self.config.concurrent_workers, len(valid_actions))
        pbar = tqdm(total=len(valid_actions), desc=f'Tool calling on {num_workers} workers') if self.config.show_tqdm else None
        
        if num_workers <= 1:
            for agi in agent_inputs:
                valid_idx = agi['valid_idx']
                subidx = agi['idx']
                
                obs, reward, done, info = execute_tool_call(agi, self.tokenizer, self.processor, pbar=pbar, conversation_mode=self.conversation_mode, max_tools_per_turn=self.max_tools_per_turn)
                
                # 输出执行结果
                if info.get('status') == 'success':
                    if info.get('type') == 'answer':
                        status = "🏁"  # 答案完成
                    else:
                        status = "✅"  # 工具执行成功
                        # 更新环境中的图像数据
                        # 🔥 优先使用原始PIL图像（用于reward计算），而不是fetch后的
                        if isinstance(obs, dict):
                            if 'multi_modal_data_for_reward' in obs:
                                # 使用原始PIL图像（工具直接输出，未经fetch_image）
                                old_len = len(self.multi_modal_data_history_list[valid_idx])
                                self.multi_modal_data_history_list[valid_idx].append(deepcopy(obs['multi_modal_data_for_reward']))
                                new_len = len(self.multi_modal_data_history_list[valid_idx])
                                print(f'[DEBUG {turn_info}] 📸 更新图像历史(原始PIL): {old_len} → {new_len}张')
                            elif 'multi_modal_data' in obs:
                                # Fallback: 使用fetch后的（兼容旧逻辑）
                                old_len = len(self.multi_modal_data_history_list[valid_idx])
                                self.multi_modal_data_history_list[valid_idx].append(deepcopy(obs['multi_modal_data']))
                                new_len = len(self.multi_modal_data_history_list[valid_idx])
                                print(f'[DEBUG {turn_info}] ⚠️  更新图像历史(fetch后,fallback): {old_len} → {new_len}张')
                else:
                    status = "❌"  # 执行失败
                
                obs_list[subidx] = obs
                reward_list[subidx] = reward
                done_list[subidx] |= done
        else:
            partial_tool_func = partial(execute_tool_call, tokenizer=self.tokenizer, processor=self.processor, pbar=pbar, conversation_mode=self.conversation_mode, max_tools_per_turn=self.max_tools_per_turn)
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
                        # 🔥 优先使用原始PIL图像（用于reward计算），而不是fetch后的
                        if isinstance(obs, dict):
                            if 'multi_modal_data_for_reward' in obs:
                                # 使用原始PIL图像（工具直接输出，未经fetch_image）
                                old_len = len(self.multi_modal_data_history_list[valid_idx])
                                self.multi_modal_data_history_list[valid_idx].append(deepcopy(obs['multi_modal_data_for_reward']))
                                new_len = len(self.multi_modal_data_history_list[valid_idx])
                                print(f'[DEBUG 并行-样本{valid_idx}] 📸 更新图像历史(原始PIL): {old_len} → {new_len}张')
                            elif 'multi_modal_data' in obs:
                                # Fallback: 使用fetch后的（兼容旧逻辑）
                                old_len = len(self.multi_modal_data_history_list[valid_idx])
                                self.multi_modal_data_history_list[valid_idx].append(deepcopy(obs['multi_modal_data']))
                                new_len = len(self.multi_modal_data_history_list[valid_idx])
                                print(f'[DEBUG 并行-样本{valid_idx}] ⚠️  更新图像历史(fetch后,fallback): {old_len} → {new_len}张')
                else:
                    status = "❌"  # 执行失败
                print(f'[DEBUG step {current_turn}-{valid_idx:02d}] 执行: {status} reward={reward:.3f}, done={done}')
                
                subidx = agi['idx']
                obs_list[subidx] = obs
                reward_list[subidx] = reward
                done_list[subidx] |= done

        return obs_list, reward_list, done_list, {}

    def reset(self, prompts, vllm_inputs, n=1, **kwargs):
        self.tools = []
        self.raw_prompts = []
        self.multi_modal_data_history_list = []  # 每个样本的图像历史：List[List[Dict]]
        self.origin_multi_modal_data_list = []
        self.extra_info_list = []  # 保存每个样本的extra_info（包含original_image）
        self.conversation_history = []  # 保存每个样本的对话历史
        reset_output_list = []
        assert len(prompts) == len(vllm_inputs), f"{len(prompts)=}, {len(vllm_inputs)=}"

        num_agent, num_non_agent = 0, 0
        for i in range(len(prompts)):
            data_item = prompts[i]  # DataProtoItem
            # We no longer use tool_name from dataset, but still extract other data
            tool_name = data_item.non_tensor_batch.pop(self.config.tool_name_key, '')
            raw_prompt = data_item.non_tensor_batch.pop('raw_prompt', None)
            extra_info = data_item.non_tensor_batch.get("extra_info", None)  # 获取extra_info
          
            vllm_input_item = vllm_inputs[i]   # {"prompt_token_ids": ..., "multi_modal_data": ...}
            multi_modal_data = vllm_input_item.get("multi_modal_data", None)
            origin_multi_modal_data = data_item.non_tensor_batch.pop("origin_multi_modal_data", None)
            
            for _ in range(n):
                # Store context data for later tool creation
                self.raw_prompts.append(raw_prompt)
                # 🔥 关键修复：初始化图像历史时使用origin_multi_modal_data（原始PIL，未fetch）
                # 不应该使用multi_modal_data（已经fetch_image处理过，可能padding）
                image_history = [deepcopy(origin_multi_modal_data)] if origin_multi_modal_data else []
                self.multi_modal_data_history_list.append(image_history)
                self.origin_multi_modal_data_list.append(deepcopy(origin_multi_modal_data))
                
                # 保存extra_info（包含真正的original_image）
                if extra_info:
                    self.extra_info_list.append(deepcopy(extra_info))
                else:
                    # 如果extra_info为None，打印警告
                    if i == 0:  # 只打印第一个
                        print(f"[DEBUG RESET] ⚠️  Prompt {i} has no extra_info, original_image will fallback")
                    self.extra_info_list.append(None)
                
                self.conversation_history.append([])  # 初始化对话历史为空列表
                
                # Initialize with None - tools will be created dynamically from model output
                self.tools.append(None)
                reset_output_list.append(None)
                
                # Count as agent data if we have a raw prompt (indicating this could be an agent task)
                if raw_prompt is not None:
                    num_agent += 1
                else:
                    num_non_agent += 1
        
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
            print(f'[ROLLBACK] 样本{idx} 回退到第{step+1}轮')
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
        self.extra_info_list = []
        self.conversation_history = []
