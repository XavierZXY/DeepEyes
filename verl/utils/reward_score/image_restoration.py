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

import re
import json
import numpy as np
from typing import List, Dict, Union

# Define allowed tools list (unified for all format checking functions)
ALLOWED_TOOLS = {
    # Dehazing
    "dehazeformer_dehaze",
    # Deblurring
    "drbnet_defocus_deblurring", 
    "xrestormer_motion_deblurring", 
    "mprnet_motion_deblurring",
    "restormer_motion_deblurring",
    "restormer_defocus_deblurring",
    "nafnet_deblur",
    # Deraining
    "mprnet_deraining",
    "restormer_deraining",
    "xrestormer_deraining",
    "nerd_deraining",
    # JPEG artifact removal
    "swinir_jpeg_artifact_removal", 
    "fbcnn_jpeg_artifact_removal",
    # Quality assessment
    "fbcnn_blind_quality_assessment",
    # Super resolution
    "swinir_super_resolution",
    "hat_super_resolution",  # HAT工具
    # Denoising
    "swinir_denoising", 
    "mprnet_denoising",
    "scunet_real_denoising_psnr",
    "scunet_real_denoising_gan",
    "scunet_color_denoising",
    "scunet_gray_denoising",
    # Low-light enhancement (Retinexformer系列)
    "retinexformer_enhance",
    "retinexformer_lol_v1",
    "retinexformer_lol_v2_real",
    "retinexformer_lol_v2_synthetic",
    "retinexformer_sdsd_indoor",
    "retinexformer_sdsd_outdoor",
    "retinexformer_sid",
    "retinexformer_smid",
    "retinexformer_fivek",
    # Basic adjustments
    "histogram_equalization",
    "gamma_correction",
    "constant_shift",
    # Visual toolboxes
    "visual_toolbox",
    "visual_toolbox_v2",
    "visual_toolbox_v3", 
    "visual_toolbox_v4",
    "visual_toolbox_v5",
    # RAG tools
    "rag",
    "rag_v2",
    # VL Agent tools
    "vl_agent",
    "vl_agent_v2",
    "vl_agent_v3",
}

# Import image quality metrics
try:
    from .image_quality_metrics import ImageQualityMetrics, compute_image_restoration_reward, compute_no_reference_image_restoration_reward
    HAS_IMAGE_QUALITY = True
except ImportError:
    HAS_IMAGE_QUALITY = False
    print("[WARNING] image_quality_metrics module not found. Image quality reward will not be available.")


def extract_restoration_log_from_response_v2(response_str: str) -> List[str]:
    """
    Extract restoration log from model response (v2 format).
    The response should contain an <answer> block with a JSON object containing restoration_log.
    """
    # Look for <answer> block
    answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', response_str, re.DOTALL)
    if not answer_match:
        return []
    
    try:
        answer_json = json.loads(answer_match.group(1))
        restoration_log = answer_json.get('restoration_log', [])
        # Ensure all elements are strings
        if isinstance(restoration_log, list):
            return [str(item) for item in restoration_log if item is not None]
        else:
            return []
    except (json.JSONDecodeError, AttributeError):
        return []


def check_multiturn_format_v2(response_str: str, is_clean_sample: bool = False) -> float:
    """
    Strict binary format checking for multi-turn conversation.
    
    Format requirements (ALL must be satisfied):
    1. Each turn must have <think> block with meaningful content (>=10 chars)
    2. Each turn must have either <tool_call> OR <answer> (NOT both, and at least one is REQUIRED)
    3. All JSON formats must be valid (if present)
    4. All tool names must be in the allowed list (if present)
    5. Answer must have valid restoration_log field (only field) if present
    
    Returns:
        1.0: Perfect format (all requirements met)
        -1.0: Any format violation
    """
    # Use unified allowed tools list
    allowed_tools = ALLOWED_TOOLS
    
    # Split response into turns (assuming each turn starts with <think>)
    think_pattern = r'<think>(.*?)</think>'
    think_matches = list(re.finditer(think_pattern, response_str, re.DOTALL))
    
    if not think_matches:
        print(f' [STRICT FORMAT] 缺少think块')
        return -1.0
    
    turns = []
    for i, think_match in enumerate(think_matches):
        start_pos = think_match.start()
        end_pos = think_matches[i + 1].start() if i + 1 < len(think_matches) else len(response_str)
        turn_content = response_str[start_pos:end_pos]
        turns.append(turn_content)
    
    if not turns:
        print(f' [STRICT FORMAT] 没有有效的回合')
        return -1.0
    
    # Check global requirements first
    has_any_tool_call = bool(re.search(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', response_str, re.DOTALL))
    has_any_answer = bool(re.search(r'<answer>\s*(\{.*?\})\s*</answer>', response_str, re.DOTALL))
    
    # Check each turn strictly
    for i, turn in enumerate(turns):
        is_final_turn = (i == len(turns) - 1)
        
        # 1. Must have think block with meaningful content
        think_match = re.search(r'<think>(.*?)</think>', turn, re.DOTALL)
        if not think_match:
            print(f' [STRICT FORMAT] 第{i+1}轮缺少think块')
            return -1.0
        
        think_content = think_match.group(1).strip()
        if len(think_content) < 10:
            print(f' [STRICT FORMAT] 第{i+1}轮think内容太短 (< 10字符)')
            return -1.0
        
        # 2. Check tool_call and answer
        tool_call_match = re.search(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', turn, re.DOTALL)
        answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', turn, re.DOTALL)
        
        # 3. Cannot have both tool_call and answer in same turn
        if tool_call_match and answer_match:
            print(f' [STRICT FORMAT] 第{i+1}轮同时包含tool_call和answer')
            return -1.0
        
        # 4. Must have either tool_call or answer (at least one is REQUIRED)
        if not tool_call_match and not answer_match:
            print(f' [STRICT FORMAT] 第{i+1}轮既没有tool_call也没有answer（必须至少有一个）')
            return -1.0
        
        # 5. Validate tool_call format if present
        if tool_call_match:
            try:
                tool_calls = json.loads(tool_call_match.group(1))
                if not isinstance(tool_calls, list) or len(tool_calls) == 0:
                    print(f' [STRICT FORMAT] 第{i+1}轮tool_call格式错误（不是非空列表）')
                    return -1.0
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        print(f' [STRICT FORMAT] 第{i+1}轮tool_call包含非字典元素')
                        return -1.0
                    if 'name' not in tool_call or 'arguments' not in tool_call:
                        print(f' [STRICT FORMAT] 第{i+1}轮tool_call缺少name或arguments字段')
                        return -1.0
                    # Check if tool name is in allowed list
                    if tool_call['name'] not in allowed_tools:
                        print(f' [STRICT FORMAT] 第{i+1}轮使用了未允许的工具: {tool_call["name"]}')
                        return -1.0
            except json.JSONDecodeError:
                print(f' [STRICT FORMAT] 第{i+1}轮tool_call JSON解析失败')
                return -1.0
        
        # 5. Validate answer format if present
        if answer_match:
            try:
                answer_json = json.loads(answer_match.group(1))
                if 'restoration_log' not in answer_json:
                    print(f' [STRICT FORMAT] 第{i+1}轮answer缺少restoration_log字段')
                    return -1.0
                if not isinstance(answer_json['restoration_log'], list):
                    print(f' [STRICT FORMAT] 第{i+1}轮restoration_log不是列表')
                    return -1.0
                # Strict: only restoration_log field
                if len(answer_json.keys()) != 1:
                    print(f' [STRICT FORMAT] 第{i+1}轮answer包含额外字段（应该只有restoration_log）')
                    return -1.0
            except json.JSONDecodeError:
                print(f' [STRICT FORMAT] 第{i+1}轮answer JSON解析失败')
                return -1.0
    
    # All checks passed
    return 1.0


def check_multiturn_format_v3_enhanced(response_str: str, degradation_count: int = 0, is_clean_sample: bool = False, max_tools_per_turn: int = 0, enable_total_tools_upper_limit: bool = False) -> float:
    """
    Enhanced multi-turn format checking with additional constraints.
    
    Inherits all requirements from check_multiturn_format_v2, plus:
    6. Answer must be in the FINAL turn only (if present)
    7. Total tool_call count must be >= 1 (for non-clean samples)
       注：原规则"≥退化数量"已放宽，现在只要求至少调用1个工具
    8. Single turn tool_call count must be <= max_tools_per_turn (if max_tools_per_turn > 0)
    9. Total tool_call count must be <= degradation_count + 1 (if enable_total_tools_upper_limit=True)
       注：此约束主要用于单工具迭代模式，防止过度调用工具
    
    Args:
        response_str: The model's response string
        degradation_count: Number of degradations in the image (for validation, currently not strictly enforced)
        is_clean_sample: Whether this is a clean image sample
        max_tools_per_turn: Maximum number of tools allowed per turn (0 = no limit)
        enable_total_tools_upper_limit: Whether to enable total tools upper limit check (default: False)
    
    Returns:
        1.0: Perfect format (all requirements met including new constraints)
        -1.0: Any format violation
    """
    # Use unified allowed tools list
    allowed_tools = ALLOWED_TOOLS
    
    # Split response into turns (assuming each turn starts with <think>)
    think_pattern = r'<think>(.*?)</think>'
    think_matches = list(re.finditer(think_pattern, response_str, re.DOTALL))
    
    if not think_matches:
        print(f' [ENHANCED FORMAT] 缺少think块')
        return -1.0
    
    turns = []
    for i, think_match in enumerate(think_matches):
        start_pos = think_match.start()
        end_pos = think_matches[i + 1].start() if i + 1 < len(think_matches) else len(response_str)
        turn_content = response_str[start_pos:end_pos]
        turns.append(turn_content)
    
    if not turns:
        print(f' [ENHANCED FORMAT] 没有有效的回合')
        return -1.0
    
    # Track tool_call and answer positions
    total_tool_calls = 0
    answer_turns = []  # Track which turns have answers
    
    # Check each turn strictly (inherit all checks from v2)
    for i, turn in enumerate(turns):
        is_final_turn = (i == len(turns) - 1)
        
        # 1. Must have think block with meaningful content
        think_match = re.search(r'<think>(.*?)</think>', turn, re.DOTALL)
        if not think_match:
            print(f' [ENHANCED FORMAT] 第{i+1}轮缺少think块')
            return -1.0
        
        think_content = think_match.group(1).strip()
        if len(think_content) < 10:
            print(f' [ENHANCED FORMAT] 第{i+1}轮think内容太短 (< 10字符)')
            return -1.0
        
        # 2. Check tool_call and answer
        tool_call_match = re.search(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', turn, re.DOTALL)
        answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', turn, re.DOTALL)
        
        # 3. Cannot have both tool_call and answer in same turn
        if tool_call_match and answer_match:
            print(f' [ENHANCED FORMAT] 第{i+1}轮同时包含tool_call和answer')
            return -1.0
        
        # 4. Must have either tool_call or answer (at least one is REQUIRED)
        if not tool_call_match and not answer_match:
            print(f' [ENHANCED FORMAT] 第{i+1}轮既没有tool_call也没有answer（必须至少有一个）')
            return -1.0
        
        # 5. Validate tool_call format if present
        if tool_call_match:
            try:
                tool_calls = json.loads(tool_call_match.group(1))
                if not isinstance(tool_calls, list) or len(tool_calls) == 0:
                    print(f' [ENHANCED FORMAT] 第{i+1}轮tool_call格式错误（不是非空列表）')
                    return -1.0
                
                # NEW CONSTRAINT 3: Check single turn tool count limit
                turn_tool_count = len(tool_calls)
                if max_tools_per_turn > 0 and turn_tool_count > max_tools_per_turn:
                    print(f' [ENHANCED FORMAT] 第{i+1}轮工具数量超限: {turn_tool_count} > {max_tools_per_turn}（单轮最大工具数）')
                    return -1.0
                
                # Count total tool calls
                total_tool_calls += turn_tool_count
                
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict):
                        print(f' [ENHANCED FORMAT] 第{i+1}轮tool_call包含非字典元素')
                        return -1.0
                    if 'name' not in tool_call or 'arguments' not in tool_call:
                        print(f' [ENHANCED FORMAT] 第{i+1}轮tool_call缺少name或arguments字段')
                        return -1.0
                    # Check if tool name is in allowed list
                    if tool_call['name'] not in allowed_tools:
                        print(f' [ENHANCED FORMAT] 第{i+1}轮使用了未允许的工具: {tool_call["name"]}')
                        return -1.0
            except json.JSONDecodeError:
                print(f' [ENHANCED FORMAT] 第{i+1}轮tool_call JSON解析失败')
                return -1.0
        
        # 6. Validate answer format if present
        if answer_match:
            answer_turns.append(i + 1)  # Track which turn has answer (1-indexed)
            
            try:
                answer_json = json.loads(answer_match.group(1))
                if 'restoration_log' not in answer_json:
                    print(f' [ENHANCED FORMAT] 第{i+1}轮answer缺少restoration_log字段')
                    return -1.0
                if not isinstance(answer_json['restoration_log'], list):
                    print(f' [ENHANCED FORMAT] 第{i+1}轮restoration_log不是列表')
                    return -1.0
                # Strict: only restoration_log field
                if len(answer_json.keys()) != 1:
                    print(f' [ENHANCED FORMAT] 第{i+1}轮answer包含额外字段（应该只有restoration_log）')
                    return -1.0
            except json.JSONDecodeError:
                print(f' [ENHANCED FORMAT] 第{i+1}轮answer JSON解析失败')
                return -1.0
    
    # NEW CONSTRAINT 1: Answer must be in the FINAL turn only
    if answer_turns:
        if len(answer_turns) > 1:
            print(f' [ENHANCED FORMAT] Answer出现在多个轮次: {answer_turns}，只能在最后一轮')
            return -1.0
        if answer_turns[0] != len(turns):
            print(f' [ENHANCED FORMAT] Answer出现在第{answer_turns[0]}轮，但应该在最后一轮（第{len(turns)}轮）')
            return -1.0
    
    # NEW CONSTRAINT 2: Tool_call count validation (for non-clean samples)
    # 修改：要求至少调用1个工具，而不是≥退化数量
    # 原因：模型可能需要尝试，不强制必须为每个退化都调用工具
    if not is_clean_sample:
        if total_tool_calls < 1:
            print(f' [ENHANCED FORMAT] Tool_call数量不足: {total_tool_calls} < 1（至少需要1个工具）')
            return -1.0
        print(f' [ENHANCED FORMAT] Tool_call数量下限验证通过: {total_tool_calls} >= 1')
    
    # NEW CONSTRAINT 4: Total tool_call count upper limit validation (for non-clean samples in single-tool-iterative mode)
    # 防止模型过度调用工具：总工具数 <= 退化数量 + 1
    if enable_total_tools_upper_limit and not is_clean_sample and degradation_count > 0:
        max_allowed_tools = degradation_count + 1
        if total_tool_calls > max_allowed_tools:
            print(f' [ENHANCED FORMAT] Tool_call数量超过上限: {total_tool_calls} > {max_allowed_tools}（退化数量{degradation_count}+1）')
            return -1.0
        print(f' [ENHANCED FORMAT] Tool_call数量上限验证通过: {total_tool_calls} <= {max_allowed_tools}（退化数量{degradation_count}+1）')
    
    # 【原规则保留，可恢复】注释掉的是原来的严格规则：总工具数≥退化数量
    # if not is_clean_sample and degradation_count > 0:
    #     if total_tool_calls < degradation_count:
    #         print(f' [ENHANCED FORMAT] Tool_call数量不足: {total_tool_calls} < {degradation_count}（退化数量）')
    #         return -1.0
    #     print(f' [ENHANCED FORMAT] Tool_call数量验证通过: {total_tool_calls} >= {degradation_count}')
    
    # All checks passed (including enhanced constraints)
    print(f' [ENHANCED FORMAT] 所有检查通过: 轮次={len(turns)}, tool_calls={total_tool_calls}, answer_turns={answer_turns}')
    return 1.0


def check_response_format_strict_v2(response_str: str, content_aware: bool = False) -> float:
    """
    Strict format checking for v2 format: only give reward if format is completely correct.
    
    Args:
        content_aware: If True, apply content-based rules (clean->answer, degraded->tool_call).
                      If False (DEFAULT), only check pure format without content judgment.
    
    Format rules (for single response):
    1. 每轮对话都必须有<think>块，包含简短推理
    2. 必须有<tool_call>或<answer>之一（至少一个是必需的）
    3. <tool_call>和<answer>不能在同一个回合中同时出现
    4. <answer>必须包含valid JSON with restoration_log (only field) if present
    5. tool_call中的工具名称必须是system prompt中允许的工具 if present
    
    Content-aware rules (only when content_aware=True):
    6. 如果检测到退化，必须有<tool_call>
    7. 如果图像干净，必须有<answer>
    
    Returns 1.0 if perfect, 0.0 if any format violation.
    """
    # Use unified allowed tools list
    allowed_tools = ALLOWED_TOOLS
    
    format_score = 0.0
    
    # 1. Check for <think> block with meaningful content (0.3 points)
    think_match = re.search(r'<think>(.*?)</think>', response_str, re.DOTALL)
    if not think_match:
        return 0.0
    
    think_content = think_match.group(1).strip()
    if len(think_content) < 10:  # Must have meaningful reasoning
        return 0.0
    
    # 2. Check for <tool_call> and <answer> blocks
    tool_call_match = re.search(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', response_str, re.DOTALL)
    answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', response_str, re.DOTALL)
    
    # 3. Rule: answer and tool_call cannot coexist in single response
    if tool_call_match and answer_match:
        return 0.0
    
    # 4. Must have either tool_call or answer (at least one is REQUIRED)
    if not tool_call_match and not answer_match:
        return 0.0
    
    # 5. Validate tool_call format if present
    if tool_call_match:
        try:
            tool_calls = json.loads(tool_call_match.group(1))
            if not isinstance(tool_calls, list) or len(tool_calls) == 0:
                return 0.0
            # Each tool call must have name and arguments, and name must be allowed
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    return 0.0
                if 'name' not in tool_call or 'arguments' not in tool_call:
                    return 0.0
                # Check if tool name is in allowed list
                if tool_call['name'] not in allowed_tools:
                    return 0.0
        except json.JSONDecodeError:
            return 0.0
    
    # 6. Validate answer format if present
    if answer_match:
        try:
            answer_json = json.loads(answer_match.group(1))
            # According to system prompt, answer should ONLY contain restoration_log field
            if 'restoration_log' not in answer_json:
                return 0.0
            if not isinstance(answer_json['restoration_log'], list):
                return 0.0
            # Check that ONLY restoration_log field is present (strict format compliance)
            if len(answer_json.keys()) != 1:
                return 0.0
        except json.JSONDecodeError:
            return 0.0
    
    # Content-aware rules (only applied when content_aware=True)
    if content_aware:
        # TODO: Add content-aware logic here if needed
        # For now, we'll implement this in the main compute_score_v2 function
        # to avoid duplicating the clean/degraded detection logic
        pass
    
    return 1.0


def check_response_format_v2(response_str: str) -> float:
    """
    Gradual format checking for v2: give partial credit for partial compliance.
    Returns a score between 0 and 1 based on format compliance.
    
    Format rules:
    1. Must have <think> block with meaningful content
    2. Must have either <tool_call> OR <answer> (at least one is REQUIRED)
    3. <tool_call> and <answer> cannot coexist in same response
    """
    # Use unified allowed tools list
    allowed_tools = ALLOWED_TOOLS
    
    format_score = 0.0
    
    # 1. Check for <think> block with meaningful content (0.3 points)
    think_match = re.search(r'<think>(.*?)</think>', response_str, re.DOTALL)
    if think_match:
        think_content = think_match.group(1).strip()
        if len(think_content) >= 10:  # Meaningful reasoning
            format_score += 0.3
            
            # Bonus for quality reasoning keywords
            quality_keywords = [
                "artifact", "blur", "noise", "haze", "rain", "dark", "compression",
                "clean", "priority", "lifo", "degradation", "highest", "fix"
            ]
            if any(keyword in think_content.lower() for keyword in quality_keywords):
                format_score += 0.1  # Total 0.4 for think
        elif len(think_content) > 0:
            format_score += 0.1  # Partial credit for having some content
    
    # 2. Check for <tool_call> and <answer> blocks
    tool_call_match = re.search(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', response_str, re.DOTALL)
    answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', response_str, re.DOTALL)
    
    # 3. Check for format conflict (tool_call and answer coexist) - major penalty
    if tool_call_match and answer_match:
        format_score -= 0.8  # Heavy penalty for format violation
        return max(format_score, 0.0)
    
    # 4. Must have either tool_call or answer (at least one is REQUIRED)
    if not tool_call_match and not answer_match:
        format_score -= 0.6  # Major penalty for missing action
        return max(format_score, 0.0)
    
    # 5. Validate and score tool_call if present (0.4 points)
    if tool_call_match:
        format_score += 0.2  # Basic tool_call presence
        try:
            tool_calls = json.loads(tool_call_match.group(1))
            if isinstance(tool_calls, list) and len(tool_calls) > 0:
                format_score += 0.1  # Valid list format
                # Check if tool calls have required fields and valid names
                valid_tools = True
                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict) or 'name' not in tool_call or 'arguments' not in tool_call:
                        valid_tools = False
                        break
                    # Check if tool name is allowed
                    if tool_call['name'] not in allowed_tools:
                        valid_tools = False
                        break
                if valid_tools:
                    format_score += 0.1  # Valid tool structure
        except json.JSONDecodeError:
            format_score -= 0.2  # Penalty for invalid JSON
    
    # 6. Validate and score answer if present (0.4 points)
    if answer_match:
        format_score += 0.2  # Basic answer presence
        try:
            answer_json = json.loads(answer_match.group(1))
            format_score += 0.1  # Valid JSON format
            if 'restoration_log' in answer_json:
                format_score += 0.1  # Has restoration_log field
                if isinstance(answer_json['restoration_log'], list):
                    format_score += 0.1  # Valid list format
                    # Bonus for strict format compliance (only restoration_log field)
                    if len(answer_json.keys()) == 1:
                        format_score += 0.1  # Perfect format compliance (total 0.6 for answer)
                    else:
                        format_score -= 0.1  # Penalty for extra fields
        except json.JSONDecodeError:
            format_score -= 0.2  # Penalty for invalid JSON
    
    return min(format_score, 1.0)


def check_step_logic_v2(response_str: str) -> float:
    """
    Check if the step logic follows LIFO principle and makes sense.
    
    Returns:
        Score between 0 and 1 based on logic quality
    """
    logic_score = 0.0
    
    # Extract components
    think_match = re.search(r'<think>(.*?)</think>', response_str, re.DOTALL)
    tool_call_match = re.search(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', response_str, re.DOTALL)
    answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', response_str, re.DOTALL)
    
    if not think_match:
        return 0.0
    
    think_content = think_match.group(1).strip().lower()
    
    # LIFO Priority detection
    priority_keywords = {
        1: ["jpeg", "compression", "artifact", "blockiness", "block"],  # Highest priority
        2: ["motion blur", "defocus blur", "noise", "low resolution", "blur", "pixelated"],
        3: ["haze", "rain", "dark", "fog", "atmospheric", "weather", "brightness"]
    }
    
    detected_priority = None
    degradation_detected = False
    clean_detected = False
    
    # Check for degradation detection
    for priority, keywords in priority_keywords.items():
        if any(keyword in think_content for keyword in keywords):
            detected_priority = priority
            degradation_detected = True
            break
    
    # Check for clean detection
    clean_indicators = ["clean", "no degradation", "artifact-free", "fully restored", "no significant"]
    if any(indicator in think_content for indicator in clean_indicators):
        clean_detected = True
    
    # Logic consistency scoring
    if degradation_detected and tool_call_match and not answer_match:
        logic_score += 0.5  # Correct action for degradation
        
        # LIFO priority bonus
        if detected_priority == 1:  # Compression - highest priority
            logic_score += 0.3
        elif detected_priority == 2:  # Imaging degradation
            logic_score += 0.2
        elif detected_priority == 3:  # Scene degradation
            logic_score += 0.1
        
        # Check for LIFO reasoning
        lifo_keywords = ["priority", "highest", "first", "lifo", "reverse", "order"]
        if any(keyword in think_content for keyword in lifo_keywords):
            logic_score += 0.2
            
    elif clean_detected and answer_match and not tool_call_match:
        logic_score += 0.5  # Correct action for clean image
        
        # Check if restoration_log makes sense
        try:
            if answer_match:
                answer_json = json.loads(answer_match.group(1))
                restoration_log = answer_json.get('restoration_log', [])
                if isinstance(restoration_log, list) and len(restoration_log) > 0:
                    logic_score += 0.3  # Has restoration history
        except:
            pass
    else:
        # Logic inconsistency penalties
        if degradation_detected and answer_match:
            logic_score -= 0.3  # Detected degradation but gave final answer
        elif clean_detected and tool_call_match:
            logic_score -= 0.3  # Detected clean but still using tools
        elif not degradation_detected and not clean_detected:
            logic_score -= 0.2  # Unclear reasoning
    
    return max(logic_score, 0.0)


def parse_env_name_to_degradations_v2(env_name: str) -> List[str]:
    """
    Parse env_name string to extract degradation types (same as v1).
    Note: env_name is in reverse order of degradation addition.
    """
    if not env_name:
        return []
    
    # Split by comma and strip whitespace
    degradations = [deg.strip() for deg in env_name.split(',')]
    return [str(deg) for deg in degradations if deg and deg.strip()]


def extract_image_from_multimodal_data(multimodal_data: Dict) -> Union[str, bytes, None]:
    """
    Extract image from multimodal data structure.
    
    Args:
        multimodal_data: Dictionary containing image data in various formats
        
    Returns:
        Image data (bytes, base64 string, or PIL Image)
    """
    if not isinstance(multimodal_data, dict):
        return None
    
    # Check for image list
    images = multimodal_data.get('image', [])
    if images and len(images) > 0:
        # Take the first image from the list
        image_data = images[0]
        
        # Handle PIL Image objects
        if hasattr(image_data, 'save'):
            # It's a PIL Image, convert to bytes
            import io
            buf = io.BytesIO()
            image_data.save(buf, format='PNG')
            return buf.getvalue()
        
        # Handle dict with bytes
        if isinstance(image_data, dict) and 'bytes' in image_data:
            return image_data['bytes']
        
        # Handle direct bytes
        if isinstance(image_data, bytes):
            return image_data
        
        # Handle base64 string
        if isinstance(image_data, str):
            return image_data
    
    return None


def extract_restored_image_from_response_v2(response_str: str) -> str:
    """
    Extract restored image from model response (v2 format).
    The response should contain an <answer> block with a JSON object containing restored_image.
    """
    # Look for <answer> block
    answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', response_str, re.DOTALL)
    if not answer_match:
        return None
    
    try:
        answer_json = json.loads(answer_match.group(1))
        restored_image = answer_json.get('restored_image', None)
        return restored_image
    except (json.JSONDecodeError, AttributeError):
        return None


def parse_reward_model_to_degradations_v2(reward_model: List[Dict]) -> List[str]:
    """
    Parse reward_model list to extract degradation types in addition order (same as v1).
    """
    if reward_model is None or len(reward_model) == 0:
        return []
    
    degradations = []
    for item in reward_model:
        if isinstance(item, dict) and 'degradation_type' in item:
            deg_type = item['degradation_type']
            if deg_type is not None:
                degradations.append(str(deg_type))
    
    return degradations


def discretize_quality_reward(continuous_reward: float, 
                             discretize_levels: int = 0,
                             smooth_boundary: bool = True) -> float:
    """
    将连续的图像质量奖励离散化为固定等级
    
    Args:
        continuous_reward: 连续奖励值 [0, 1]
        discretize_levels: 离散化等级数量
            - 0: 不离散化，保持连续（默认）
            - 10: 每10%一个档 (0.0, 0.1, 0.2, ..., 1.0)
            - 20: 每5%一个档 (0.0, 0.05, 0.10, ..., 1.0)
        smooth_boundary: 是否在边界附近平滑过渡（仅在discretize_levels>0时有效）
            
    Returns:
        离散化后的奖励值 [0, 1]
        
    Examples:
        >>> discretize_quality_reward(0.8234, discretize_levels=0)
        0.8234  # 不离散化
        
        >>> discretize_quality_reward(0.8234, discretize_levels=10)
        0.8  # 离散化到最近的0.1
        
        >>> discretize_quality_reward(0.8234, discretize_levels=20)
        0.8  # 离散化到最近的0.05
    """
    if discretize_levels <= 0:
        # 不离散化，返回原值
        return continuous_reward
    
    if not smooth_boundary:
        # 硬边界：直接四舍五入到最近的等级
        discrete_reward = round(continuous_reward * discretize_levels) / discretize_levels
        return max(0.0, min(1.0, discrete_reward))
    
    # 平滑边界：在阈值附近线性插值
    level_size = 1.0 / discretize_levels
    smooth_width = level_size * 0.1  # 平滑区域为等级宽度的10%
    
    # 找到最近的下界等级
    lower_level_idx = int(continuous_reward * discretize_levels)
    lower_level_value = lower_level_idx / discretize_levels
    upper_level_value = (lower_level_idx + 1) / discretize_levels
    
    # 计算在当前等级中的位置
    position_in_level = continuous_reward - lower_level_value
    
    # 判断是否在平滑区域
    if position_in_level <= level_size - smooth_width:
        # 在等级中心区域，直接返回该等级值
        return lower_level_value
    elif position_in_level >= level_size:
        # 超出上界，返回上界值
        return min(upper_level_value, 1.0)
    else:
        # 在平滑区域，线性插值
        progress = (position_in_level - (level_size - smooth_width)) / smooth_width
        interpolated = lower_level_value + progress * level_size
        return max(0.0, min(1.0, interpolated))


def compute_image_quality_reward_v2(solution_str: str, extra_info: Dict = None, 
                                    discretize_levels: int = 0, 
                                    use_no_reference: bool = True) -> float:
    """
    Compute image quality reward using reference or no-reference metrics.
    
    Args:
        solution_str: The model's response string
        extra_info: Dictionary containing image history and other data
        discretize_levels: 离散化等级数量（0=不离散化，10=每10%，20=每5%）
        use_no_reference: 是否使用无参考指标 (NIQE, BRISQUE, CPBD, CLIP-IQA, Hyper-IQA)
                         False时使用有参考指标 (SSIM, LPIPS, PSNR)
        
    Returns:
        Image quality reward score between 0 and 1
    """
    if not HAS_IMAGE_QUALITY:
        print("[WARNING] Image quality metrics not available, falling back to 0.5")
        return 0.5
    
    def return_negative_quality_result(reason: str):
        """返回-1分的详细结果（没有工具处理的情况）"""
        print(f"[WARNING] {reason}")
        return 0.0  # 没有工具处理直接返回-1

    if extra_info is None:
        print("[ERROR IMAGE QUALITY] extra_info is None - 请检查数据流!")
        return return_negative_quality_result("extra_info is None")
    
    print(f"[DEBUG IMAGE QUALITY] extra_info keys: {list(extra_info.keys())}")
    
    # 1. 获取原图（来自parquet数据集）- 仅有参考模式需要
    original_image_data = None
    if not use_no_reference:
        original_image_data = extra_info.get('original_image', None)
        if original_image_data is None:
            print("[ERROR IMAGE QUALITY] 缺少 original_image - 请检查数据集!")
            return return_negative_quality_result("No original image found in extra_info['original_image'] (from parquet dataset)")
        print(f"[DEBUG IMAGE QUALITY] original_image 类型: {type(original_image_data)}")
    else:
        print(f"[DEBUG IMAGE QUALITY] 使用无参考模式，不需要原图")
    
    # 2. 获取图像历史（训练过程中动态生成的）
    image_history = extra_info.get('image_history', [])
    print(f"[DEBUG IMAGE QUALITY] image_history 类型: {type(image_history)}, 长度: {len(image_history) if hasattr(image_history, '__len__') else 'N/A'}")
    
    # 检查image_history是否为空（兼容numpy数组和Python列表）
    import numpy as np
    if isinstance(image_history, np.ndarray):
        if image_history.size == 0:
            return return_negative_quality_result("No image history found (empty numpy array) - no tools were executed")
    else:
        if not image_history:
            return return_negative_quality_result("No image history found (empty list) - no tools were executed")
    
    # 3. 获取最后一个被工具处理的图像
    if len(image_history) < 2:
        return return_negative_quality_result(f"No processed image found (only input image), history length: {len(image_history)} - tools did not generate new images")
    
    print(f"[DEBUG] 图像历史总长度: {len(image_history)}")
    print(f"[DEBUG] 原图来源: extra_info['original_image'] (未退化的真实原图)")
    print(f"[DEBUG] 复原图来源: image_history[{len(image_history)-1}] (最后一个被工具处理的图像)")
    print(f"[DEBUG] 输入图像: image_history[0] (退化后的输入图像，不用于质量评估)")
    
    # 使用最后一个图像作为复原后的图像
    restored_image_data = image_history[-1]
    
    # 详细检查原图和复原图的来源
    print(f"[DEBUG] ====== 图像数据详细分析 ======")
    print(f"[DEBUG] 原图数据类型: {type(original_image_data)}")
    if hasattr(original_image_data, '__len__'):
        print(f"[DEBUG] 原图数据长度: {len(original_image_data)}")
    
    print(f"[DEBUG] 复原图数据结构: {type(restored_image_data)}")
    if isinstance(restored_image_data, dict):
        print(f"[DEBUG] 复原图字典键: {list(restored_image_data.keys())}")
        if 'image' in restored_image_data:
            images = restored_image_data['image']
            print(f"[DEBUG] 复原图列表长度: {len(images)}")
            if len(images) > 0 and hasattr(images[0], 'size'):
                print(f"[DEBUG] 复原图实际尺寸: {images[0].size}")
    
    # 验证最后一个图像的内容
    if isinstance(restored_image_data, dict) and 'image' in restored_image_data:
        restored_images = restored_image_data['image']
        print(f"[DEBUG] 复原图像数量: {len(restored_images)}")
        if len(restored_images) > 0 and hasattr(restored_images[0], 'size'):
            print(f"[DEBUG] 复原图像尺寸: {restored_images[0].size}")
    else:
        print(f"[DEBUG] 复原图像数据格式: {type(restored_image_data)}")
    
    try:
        print(f"[DEBUG] 开始图像质量计算... 模式: {'无参考' if use_no_reference else '有参考'}")
        
        # 复原图从图像历史中提取
        restored_image_raw = extract_image_from_multimodal_data(restored_image_data)
        print(f"[DEBUG] 复原图(raw) 类型: {type(restored_image_raw)}")
        
        if restored_image_raw is None:
            return return_negative_quality_result("Failed to extract restored image from multimodal data")
        
        # 将复原图转为PIL.Image（如果是bytes）
        from PIL import Image
        import io
        if isinstance(restored_image_raw, bytes):
            restored_image_pil = Image.open(io.BytesIO(restored_image_raw))
            print(f"[DEBUG] 复原图从bytes转PIL后尺寸: {restored_image_pil.size}")
        elif hasattr(restored_image_raw, 'size'):
            restored_image_pil = restored_image_raw
            print(f"[DEBUG] 复原图已是PIL.Image，尺寸: {restored_image_pil.size}")
        else:
            print(f"[DEBUG] 复原图格式未知: {type(restored_image_raw)}")
            return return_negative_quality_result(f"Unsupported restored image format: {type(restored_image_raw)}")
        
        # 直接使用PIL图像，不做fetch_image处理
        # （fetch_image是为vision transformer准备的，reward计算不需要）
        restored_image = restored_image_pil
        print(f"[DEBUG] 复原图尺寸（直接使用PIL）: {restored_image.size}")
        
        if use_no_reference:
            # 使用无参考指标计算图像质量奖励
            print(f"[DEBUG] 使用无参考指标计算...")
            final_reward = compute_no_reference_image_restoration_reward(restored_image)
            
            # 应用离散化（如果配置了）
            if discretize_levels > 0:
                discrete_reward = discretize_quality_reward(final_reward, discretize_levels)
                print(f' [DEBUG no_ref_image_quality] continuous_reward={final_reward:.4f} → discrete_reward={discrete_reward:.4f} (levels={discretize_levels})')
                final_reward = discrete_reward
            
            # 返回详细信息字典（无参考模式）
            return {
                "image_quality_reward": final_reward,
                "image_quality_reward_continuous": final_reward,  # 保留连续值用于分析
                "discretize_levels": discretize_levels,
                "mode": "no_reference",
                "success": True
            }
        else:
            # 使用有参考指标计算图像质量奖励
            print(f"[DEBUG] 使用有参考指标计算...")
            
            # Convert image data to consistent format
            # 原图需要经过与复原图相同的预处理流程
            print(f"[DEBUG] 处理原图数据...")
            if isinstance(original_image_data, dict):
                print(f"[DEBUG] 原图是字典格式，使用extract_image_from_multimodal_data")
                original_image = extract_image_from_multimodal_data(original_image_data)
            else:
                print(f"[DEBUG] 原图是直接数据格式，转换为PIL图像")
                # 直接是图像数据（base64、bytes等），转换为PIL图像
                if isinstance(original_image_data, bytes):
                    from PIL import Image
                    import io
                    original_image = Image.open(io.BytesIO(original_image_data))
                    print(f"[DEBUG] 原图从bytes转换后尺寸: {original_image.size}")
                elif isinstance(original_image_data, str):
                    # base64格式
                    import base64
                    from PIL import Image
                    import io
                    image_bytes = base64.b64decode(original_image_data)
                    original_image = Image.open(io.BytesIO(image_bytes))
                    print(f"[DEBUG] 原图从base64转换后尺寸: {original_image.size}")
                else:
                    print(f"[DEBUG] 原图格式未知: {type(original_image_data)}")
                    return return_negative_quality_result(f"Unsupported original image format: {type(original_image_data)}")
            
            # 直接使用PIL图像，不做fetch_image处理
            if hasattr(original_image, 'size'):
                print(f"[DEBUG] 原图尺寸（直接使用PIL）: {original_image.size}")
            elif hasattr(original_image, 'shape'):
                print(f"[DEBUG] 原图是numpy数组，shape: {original_image.shape}")
                # 如果是numpy数组，转换为PIL图像
                from PIL import Image
                if len(original_image.shape) == 3:
                    original_image = Image.fromarray(original_image.astype('uint8'))
                else:
                    original_image = Image.fromarray(original_image.astype('uint8'), mode='L')
                print(f"[DEBUG] 原图numpy转PIL后尺寸: {original_image.size}")
            else:
                print(f"[DEBUG] 原图格式异常: {type(original_image)}, 无法获取尺寸")
                
            if original_image is None:
                return return_negative_quality_result("Failed to extract original image from multimodal data")
            
            # 确保尺寸一致（处理super_resolution等改变尺寸的工具）
            # 原则：将复原图resize到原图尺寸（GT是标准，待评估图像需要对齐）
            if restored_image.size != original_image.size:
                print(f"[DEBUG] 尺寸不匹配: restored={restored_image.size} vs original={original_image.size}")
                # 将复原图resize到原图的尺寸（GT是参考标准）
                restored_image = restored_image.resize(original_image.size, Image.Resampling.LANCZOS)
                print(f"[DEBUG] 复原图已resize到: {restored_image.size}")
            
            # Compute image quality reward with detailed metrics
            from .image_quality_metrics import get_image_quality_metrics, normalize_metrics
            
            metrics_calculator = get_image_quality_metrics()
            metrics = metrics_calculator.calculate_all_metrics(restored_image, original_image)
            
            # 获取原始指标值
            ssim_val = metrics['ssim']
            lpips_val = metrics['lpips']
            psnr_val = metrics['psnr']
            
            # 归一化指标
            norm_ssim, norm_lpips, norm_psnr = normalize_metrics(ssim_val, lpips_val, psnr_val)
            
            # 计算最终奖励（优化权重）
            # LPIPS权重最高(0.50): 基于深度特征，最接近人类感知
            # SSIM权重中等(0.35): 结构相似性，对纹理和边缘敏感
            # PSNR权重较低(0.15): 像素级误差，辅助指标
            alpha, beta, gamma = 0.35, 0.50, 0.15
            continuous_reward = alpha * norm_ssim + beta * (1.0 - norm_lpips) + gamma * norm_psnr
            continuous_reward = max(0.0, min(1.0, continuous_reward))
            
            # 应用离散化（如果配置了）
            if discretize_levels > 0:
                discrete_reward = discretize_quality_reward(continuous_reward, discretize_levels)
                print(f' [DEBUG image_quality] continuous_reward={continuous_reward:.4f} → discrete_reward={discrete_reward:.4f} (levels={discretize_levels})')
                final_reward = discrete_reward
            else:
                final_reward = continuous_reward
            
            print(f' [DEBUG image_quality] ssim={ssim_val:.4f}(norm={norm_ssim:.4f}), '
                  f'lpips={lpips_val:.4f}(norm={norm_lpips:.4f}), '
                  f'psnr={psnr_val:.4f}(norm={norm_psnr:.4f})')
            print(f' [DEBUG image_quality] weights: α={alpha}(SSIM), β={beta}(LPIPS), γ={gamma}(PSNR)')
            print(f' [DEBUG image_quality] reward={final_reward:.4f} (越接近1表示复原质量越好)')
            
            # 返回详细信息字典（有参考模式）
            return {
                "image_quality_reward": final_reward,
                "image_quality_reward_continuous": continuous_reward,  # 保留连续值用于分析
                "ssim_score": ssim_val,
                "lpips_score": lpips_val, 
                "psnr_score": psnr_val,
                "ssim_normalized": norm_ssim,
                "lpips_normalized": norm_lpips,
                "psnr_normalized": norm_psnr,
                "discretize_levels": discretize_levels,
                "mode": "reference",
                "success": True
            }
    except Exception as e:
        print(f"[WARNING] Image quality computation failed: {e}")
        # 返回简单的失败分数，保持类型一致性
        return 0.0


def compute_intermediate_image_quality_reward(image_history: List, include_last: bool = False) -> float:
    """
    计算中间被工具处理的图片的无参考质量奖励
    
    Args:
        image_history: 图像历史列表，包含原始图和所有工具处理后的图像
        include_last: 是否包含最后一张图像（默认False，最后一张用于主质量奖励）
    
    Returns:
        归一化的中间图像质量奖励，范围[0, 1]
        
    逻辑说明：
        - image_history[0]: 原始退化图（不计入）
        - image_history[1:-1]: 中间工具处理的图像（计入中间奖励）
        - image_history[-1]: 最后工具处理的图像（通常不计入，除非include_last=True）
        - 特殊情况：如果只有一个工具（len(image_history)==2），则该图像既算主奖励也算中间奖励
    """
    if not HAS_IMAGE_QUALITY:
        print("[WARNING INTERMEDIATE] Image quality metrics not available")
        return 0.0
    
    if not image_history or len(image_history) < 2:
        print("[DEBUG INTERMEDIATE] No intermediate images to evaluate")
        return 0.0
    
    # 确定要评估的图像范围
    # image_history[0] 是原始退化图，跳过
    # 从 image_history[1] 开始是第一个工具处理后的图像
    start_idx = 1
    
    if include_last:
        # 包含最后一张：评估所有工具处理后的图像
        end_idx = len(image_history)
    else:
        # 不包含最后一张：只评估中间的图像
        end_idx = len(image_history) - 1
    
    # 特殊情况：只有一个工具（len=2: 原图+结果图）
    # 这种情况下，结果图既算主奖励也算中间奖励
    if len(image_history) == 2:
        end_idx = len(image_history)  # 包含唯一的工具处理结果
        print("[DEBUG INTERMEDIATE] 只有一个工具，结果图既算主奖励也算中间奖励")
    
    intermediate_images = image_history[start_idx:end_idx]
    
    if not intermediate_images:
        print(f"[DEBUG INTERMEDIATE] No intermediate images (history_len={len(image_history)}, range=[{start_idx}:{end_idx}])")
        return 0.0
    
    print(f"[DEBUG INTERMEDIATE] 评估中间图像: 总历史长度={len(image_history)}, 评估范围=[{start_idx}:{end_idx}], 数量={len(intermediate_images)}")
    
    # 计算每个中间图像的无参考质量分数
    intermediate_scores = []
    
    from .image_quality_metrics import get_image_quality_metrics, compute_no_reference_image_restoration_reward
    from PIL import Image
    import io
    
    for idx, img_data in enumerate(intermediate_images):
        try:
            # 提取图像
            img_raw = extract_image_from_multimodal_data(img_data)
            
            if img_raw is None:
                print(f"[WARNING INTERMEDIATE] 第{idx+1}个中间图像提取失败")
                continue
            
            # 转换为PIL.Image
            if isinstance(img_raw, bytes):
                img_pil = Image.open(io.BytesIO(img_raw))
            elif hasattr(img_raw, 'size'):
                img_pil = img_raw
            else:
                print(f"[WARNING INTERMEDIATE] 第{idx+1}个中间图像格式不支持: {type(img_raw)}")
                continue
            
            # 计算无参考质量分数
            score = compute_no_reference_image_restoration_reward(img_pil)
            intermediate_scores.append(score)
            
            print(f"[DEBUG INTERMEDIATE] 第{idx+1}/{len(intermediate_images)}个中间图像质量={score:.4f}")
            
        except Exception as e:
            print(f"[WARNING INTERMEDIATE] 第{idx+1}个中间图像评估失败: {e}")
            continue
    
    if not intermediate_scores:
        print("[WARNING INTERMEDIATE] 所有中间图像评估都失败")
        return 0.0
    
    # 求和并归一化
    total_score = sum(intermediate_scores)
    normalized_score = total_score / len(intermediate_scores)  # 平均分
    
    print(f"[DEBUG INTERMEDIATE] 中间图像奖励: 总分={total_score:.4f}, 平均分={normalized_score:.4f} (评估了{len(intermediate_scores)}/{len(intermediate_images)}张)")
    
    return max(0.0, min(1.0, normalized_score))


def merge_consecutive_duplicates_v2(restoration_log: List[str]) -> List[str]:
    """
    Merge consecutive duplicate degradation types (same as v1).
    """
    if not restoration_log:
        return []
    
    merged_log = []
    for item in restoration_log:
        # Only add if it's different from the last item
        if not merged_log or merged_log[-1] != item:
            merged_log.append(item)
    
    return merged_log


def check_restoration_order_v2(predicted_log: List[str], reward_model_order: List[str]) -> float:
    """
    Check if the restoration order is correct (LIFO principle).
    Same logic as v1 but adapted for v2 format.
    """
    if not predicted_log or not reward_model_order:
        return 0.0
    
    # Correct restoration order is the reverse of reward_model order (LIFO)
    correct_restoration_order = list(reversed(reward_model_order))
    
    # Exact match gets full score
    if predicted_log == correct_restoration_order:
        return 1.0
    
    # Partial credit for partially correct order
    score = 0.0
    min_len = min(len(predicted_log), len(correct_restoration_order))
    
    # Check how many positions are correct
    correct_positions = 0
    for i in range(min_len):
        if predicted_log[i] == correct_restoration_order[i]:
            correct_positions += 1
    
    if min_len > 0:
        score = correct_positions / len(correct_restoration_order)
    
    # Bonus for having all the right degradations (even if order is wrong)
    try:
        predicted_set = set(str(item) for item in predicted_log if item is not None)
        expected_set = set(str(item) for item in correct_restoration_order if item is not None)
        
        if predicted_set == expected_set:
            score = max(score, 0.1)  # At least 10% if all degradations are present
    except (TypeError, AttributeError) as e:
        print(f" [WARNING image_restoration_v2] Set comparison failed: {e}")
    
    return score


def check_restoration_order_with_partial_credit_v2(predicted_log: List[str], reward_model_order: List[str]) -> float:
    """
    Check restoration order with partial credit.
    
    改进点：
    1. 自动过滤预测中的 "clean" 标签（因为ground truth中没有）
    2. 合并连续重复的退化类型（一个退化可能需要多次处理）
    3. 使用递进式奖励：
       - 1个退化：100% 正确才给分
       - 2个退化：第1个=60%，全部=100%
       - 3个退化：第1个=50%，前2个=80%，全部=100%
    4. 必须按照正确的LIFO顺序，否则为0
    """
    if not reward_model_order:
        return 0.0
    
    # 过滤掉 "clean" 标签（因为ground truth中没有，只是模型表达"完成恢复"的方式）
    if predicted_log:
        filtered_predicted_log = [
            item for item in predicted_log 
            if item is not None and str(item).strip().lower() != "clean"
        ]
    else:
        filtered_predicted_log = []
    
    # 如果过滤后没有预测，返回0
    if not filtered_predicted_log:
        print(f' [DEBUG degradation_reward] 过滤clean后预测为空，返回0分')
        return 0.0
    
    # 合并连续重复的退化类型（一个退化可能需要多次调用工具才能去除）
    merged_predicted_log = merge_consecutive_duplicates_v2(filtered_predicted_log)
    
    expected_count = len(reward_model_order)
    predicted_count = len(merged_predicted_log)
    correct_restoration_order = list(reversed(reward_model_order))
    
    print(f' [DEBUG degradation_reward] 原始log: {predicted_log}')
    print(f' [DEBUG degradation_reward] 过滤clean: {filtered_predicted_log}')
    print(f' [DEBUG degradation_reward] 合并重复: {merged_predicted_log}')
    print(f' [DEBUG degradation_reward] 期望顺序: {correct_restoration_order}')
    
    # Check if predicted degradation types are valid
    try:
        predicted_set = set(str(item) for item in merged_predicted_log if item is not None)
        expected_set = set(str(item) for item in reward_model_order if item is not None)
        
        # If predicted invalid types, return 0
        if not predicted_set.issubset(expected_set):
            print(f' [DEBUG degradation_reward] 预测了无效的退化类型: {predicted_set - expected_set}')
            return 0.0
    except (TypeError, AttributeError):
        return 0.0
    
    # Check if order is correct for the predicted portion
    if predicted_count > expected_count:
        print(f' [DEBUG degradation_reward] 预测数量过多: {predicted_count} > {expected_count}')
        return 0.0  # Predicted too many
    
    # Check if predicted order matches expected order (must be in correct LIFO order)
    for i in range(predicted_count):
        if i >= len(correct_restoration_order) or merged_predicted_log[i] != correct_restoration_order[i]:
            print(f' [DEBUG degradation_reward] 顺序错误: 位置{i} 预测={merged_predicted_log[i]}, 期望={correct_restoration_order[i] if i < len(correct_restoration_order) else "N/A"}')
            return 0.0  # Wrong order
    
    # Give partial credit based on predicted count (更激进的递进式奖励，避免奖励过于稀疏)
    if expected_count == 1:
        # 只有1个退化：必须完全正确
        partial_score = 1.0 if predicted_count == expected_count else 0.0
    elif expected_count == 2:
        # 2个退化：第1个=60%，全部=100%（更激进，避免稀疏）
        if predicted_count == 1:
            partial_score = 0.6
        elif predicted_count == 2:
            partial_score = 1.0
        else:
            partial_score = 0.0
    elif expected_count == 3:
        # 3个退化：第1个=50%，前2个=80%，全部=100%（平滑梯度）
        if predicted_count == 1:
            partial_score = 0.5
        elif predicted_count == 2:
            partial_score = 0.8
        elif predicted_count == 3:
            partial_score = 1.0
        else:
            partial_score = 0.0
    else:
        # 更多退化：使用平方根奖励（介于线性和稀疏之间）
        import math
        partial_score = math.sqrt(predicted_count / expected_count)
    
    print(f' [DEBUG degradation_reward] 正确数量={predicted_count}/{expected_count}, 奖励={partial_score:.3f}')
    
    return partial_score


def check_degradation_type_match_v2(predicted_log: List[str], reward_model_order: List[str]) -> float:
    """
    Check if predicted degradation types match expected types (不考虑顺序，只看集合匹配).
    
    This function only checks if the predicted degradation types are correct,
    regardless of order. Useful as a bonus reward.
    
    Args:
        predicted_log: List of predicted degradation types
        reward_model_order: List of expected degradation types (in addition order)
        
    Returns:
        Float score between 0 and 1:
        - 1.0: All expected types predicted (exact match)
        - Partial: predicted_count / expected_count (only valid types)
        - 0.0: No match or invalid types predicted
    """
    if not reward_model_order:
        return 0.0
    
    # 过滤掉 "clean" 标签
    if predicted_log:
        filtered_predicted_log = [
            item for item in predicted_log 
            if item is not None and str(item).strip().lower() != "clean"
        ]
    else:
        filtered_predicted_log = []
    
    # 如果过滤后没有预测，返回0
    if not filtered_predicted_log:
        print(f' [DEBUG degradation_type_match] 过滤clean后预测为空，返回0分')
        return 0.0
    
    # 合并连续重复的退化类型
    merged_predicted_log = merge_consecutive_duplicates_v2(filtered_predicted_log)
    
    # 转换为集合
    try:
        predicted_set = set(str(item) for item in merged_predicted_log if item is not None)
        expected_set = set(str(item) for item in reward_model_order if item is not None)
    except (TypeError, AttributeError) as e:
        print(f' [DEBUG degradation_type_match] 集合转换失败: {e}')
        return 0.0
    
    print(f' [DEBUG degradation_type_match] 预测集合: {predicted_set}')
    print(f' [DEBUG degradation_type_match] 期望集合: {expected_set}')
    
    # Check if predicted types are valid (must be subset of expected)
    if not predicted_set.issubset(expected_set):
        invalid_types = predicted_set - expected_set
        print(f' [DEBUG degradation_type_match] 预测了无效的退化类型: {invalid_types}')
        return 0.0
    
    # Calculate match score
    if predicted_set == expected_set:
        # Perfect match: all types predicted
        score = 1.0
        print(f' [DEBUG degradation_type_match] 完全匹配，奖励=1.0')
    elif len(predicted_set) > 0:
        # Partial match: give credit for predicted valid types
        score = len(predicted_set) / len(expected_set)
        print(f' [DEBUG degradation_type_match] 部分匹配: {len(predicted_set)}/{len(expected_set)}, 奖励={score:.3f}')
    else:
        score = 0.0
        print(f' [DEBUG degradation_type_match] 无匹配，奖励=0.0')
    
    return score


def check_clean_image_response_v2(response_str: str) -> bool:
    """
    Check if the response correctly identifies a clean image.
    Returns True ONLY if the response has an answer block with:
    1. Empty restoration_log (indicating no processing was needed), OR
    2. restoration_log containing ONLY "clean" (and no other degradation types)
    
    This is strict: if the model predicts any degradation types along with clean, it's considered incorrect.
    """
    # Look for <answer> block
    answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', response_str, re.DOTALL)
    if not answer_match:
        return False
    
    try:
        answer_json = json.loads(answer_match.group(1))
        restoration_log = answer_json.get('restoration_log', [])
        
        # Check if restoration_log indicates clean image
        if isinstance(restoration_log, list):
            # Case 1: Empty restoration_log (no processing needed - image is clean)
            if len(restoration_log) == 0:
                return True
            
            # Case 2: Contains only "clean" and nothing else
            if len(restoration_log) == 1:
                single_item = str(restoration_log[0]).strip().lower()
                # Only accept explicit "clean" - be very strict
                if single_item == "clean":
                    return True
            
            # Case 3: Multiple items or non-clean items = incorrect for clean images
            # This includes cases where model predicts both "clean" and degradation types
            return False
            
    except (json.JSONDecodeError, AttributeError):
        return False
    
    return False


def compute_tool_diversity_bonus_v2(solution_str: str, conversation_mode: str = 'multi_tool_planning') -> float:
    """
    计算工具多样性bonus奖励
    
    Args:
        solution_str: 模型的响应字符串
        conversation_mode: 对话模式 ('multi_tool_planning' 或 'single_tool_iterative')
        
    Returns:
        0.1 如果满足多样性条件，否则 0.0
    """
    import re
    import json
    
    # 提取所有轮次的工具调用
    tool_call_matches = list(re.finditer(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', solution_str, re.DOTALL))
    
    if not tool_call_matches:
        # 没有工具调用，不给bonus
        return 0.0
    
    if conversation_mode == 'multi_tool_planning':
        # 多工具模式：只检查最后一轮的工具链
        if len(tool_call_matches) == 0:
            return 0.0
        
        try:
            # 获取最后一轮的工具调用
            last_tool_call = tool_call_matches[-1]
            tools = json.loads(last_tool_call.group(1))
            
            if not isinstance(tools, list) or len(tools) == 0:
                return 0.0
            
            # 提取工具名称
            tool_names = []
            for tool_dict in tools:
                if isinstance(tool_dict, dict) and 'name' in tool_dict:
                    tool_names.append(tool_dict['name'])
            
            if len(tool_names) == 0:
                return 0.0
            
            # 检查是否所有工具都不重复
            if len(tool_names) == len(set(tool_names)):
                print(f' [DEBUG tool_diversity_bonus] 多工具模式: 最后一轮{len(tool_names)}个工具都不重复，获得bonus=0.1')
                return 0.1
            else:
                print(f' [DEBUG tool_diversity_bonus] 多工具模式: 最后一轮有重复工具，不给bonus')
                return 0.0
                
        except Exception as e:
            print(f' [DEBUG tool_diversity_bonus] 解析工具调用失败: {e}')
            return 0.0
    
    else:  # single_tool_iterative
        # 单工具模式：检查每一轮的工具是否都不一样
        try:
            all_tool_names = []
            for match in tool_call_matches:
                tools = json.loads(match.group(1))
                if isinstance(tools, list):
                    for tool_dict in tools:
                        if isinstance(tool_dict, dict) and 'name' in tool_dict:
                            all_tool_names.append(tool_dict['name'])
            
            if len(all_tool_names) == 0:
                return 0.0
            
            # 检查所有轮次的工具是否都不重复
            if len(all_tool_names) == len(set(all_tool_names)):
                print(f' [DEBUG tool_diversity_bonus] 单工具模式: {len(all_tool_names)}轮工具都不重复，获得bonus=0.1')
                return 0.1
            else:
                print(f' [DEBUG tool_diversity_bonus] 单工具模式: 有重复工具，不给bonus')
                return 0.0
                
        except Exception as e:
            print(f' [DEBUG tool_diversity_bonus] 解析工具调用失败: {e}')
            return 0.0


def compute_score_v2(solution_str: str, ground_truth: Union[str, Dict], extra_info: Dict = None, 
                     strict_format: bool = True, accuracy_mode: str = "image_quality", 
                     format_content_aware: bool = False, discretize_levels: int = 0,
                     use_no_reference: bool = True, enable_degradation_type_reward: bool = False,
                     degradation_type_reward_weight: float = 1.0,
                     format_reward_weight: float = 0.3,
                     quality_reward_weight: float = 0.7,
                     use_enhanced_format: bool = False,
                     max_tools_per_turn: int = 0,
                     enable_total_tools_upper_limit: bool = False,
                     enable_intermediate_reward: bool = False,
                     intermediate_reward_weight: float = 0.5) -> float:
    """
    Compute reward score for image restoration task (v2 format).
    
    Args:
        solution_str: The model's response string
        ground_truth: Dictionary containing reward_model and env_name
        extra_info: Additional information containing 'original_image' key with original image data (仅有参考模式需要)
        strict_format: If True, use strict format checking. If False, use gradual format checking.
        accuracy_mode: Accuracy checking mode:
            - "image_quality": Use image quality metrics (默认无参考: NIQE+BRISQUE+CPBD+CLIP-IQA+Hyper-IQA, 有参考: SSIM+LPIPS+PSNR)
            - "partial_credit": Degradation type order reward with partial credit (递进式奖励: 50%->80%->100%, 自动过滤clean)
            - "order_only": Original order-only checking
            - "order_with_dedup": Order checking with consecutive duplicate merging
        format_content_aware: If True, apply content-based format rules (clean->answer, degraded->tool_call).
                             If False (DEFAULT), only check pure format without content judgment.
        discretize_levels: 图像质量奖励离散化等级数量（0=连续，10=每10%，20=每5%）
        use_no_reference: 是否使用无参考图像质量指标 (默认True，使用NIQE+BRISQUE+CPBD+CLIP-IQA+Hyper-IQA)
                         False时使用有参考指标 (SSIM+LPIPS+PSNR)
        enable_degradation_type_reward: 是否启用退化类型奖励（不考虑顺序，只看集合匹配）
        degradation_type_reward_weight: 退化类型奖励的权重系数（默认1.0）
        format_reward_weight: 格式奖励的权重系数（默认0.3）
        quality_reward_weight: 图像质量奖励的权重系数（默认0.7）
        use_enhanced_format: 是否使用增强格式检查（默认False）
                           - True: 使用check_multiturn_format_v3_enhanced，增加answer必须在最后一轮、tool_call数量>=退化数量的约束
                           - False: 使用原有的check_multiturn_format_v2
        max_tools_per_turn: 单轮最大工具数限制（默认0=无限制）
                           - >0: 每轮最多允许调用的工具数量，超过则格式违规（-1.0）
                           - 0: 不限制单轮工具数量
                           - 只在use_enhanced_format=True时生效
        enable_total_tools_upper_limit: 是否启用总工具调用数上限检查（默认False）
                           - True: 总工具数必须 <= 退化数量+1（防止过度调用工具）
                           - False: 不限制总工具数上限
                           - 只在use_enhanced_format=True且非clean样本时生效
                           - 主要用于单工具迭代模式
        enable_intermediate_reward: 是否启用中间图像质量奖励（默认False）
                           - True: 计算所有中间工具处理图像的无参考质量奖励
                           - False: 只计算最终图像质量
                           - 中间奖励鼓励模型在多步处理中保持每一步的质量
        intermediate_reward_weight: 中间图像质量奖励的权重系数（默认0.5）
                           - 控制中间奖励在总奖励中的占比
                           - 只在enable_intermediate_reward=True时生效
    
    奖励结构说明:
        默认奖励 = FORMAT_WEIGHT × format_score + QUALITY_WEIGHT × quality_score
        如果启用退化类型奖励:
            total = FORMAT_WEIGHT × format_score 
                  + QUALITY_WEIGHT × quality_score 
                  + DEGRADATION_TYPE_WEIGHT × degradation_type_score
        如果启用中间图像质量奖励:
            total = FORMAT_WEIGHT × format_score 
                  + QUALITY_WEIGHT × quality_score 
                  + INTERMEDIATE_WEIGHT × intermediate_quality_score
        如果全部启用:
            total = FORMAT_WEIGHT × format_score 
                  + QUALITY_WEIGHT × quality_score 
                  + DEGRADATION_TYPE_WEIGHT × degradation_type_score
                  + INTERMEDIATE_WEIGHT × intermediate_quality_score
    
    Returns:
        Float score (can be negative due to format violations)
    """
    # Parse ground truth
    if isinstance(ground_truth, str):
        try:
            ground_truth = json.loads(ground_truth)
        except json.JSONDecodeError:
            ground_truth = {}
    
    if not isinstance(ground_truth, dict):
        ground_truth = {}
    
    # Extract expected degradation order from reward_model or env_name
    reward_model = ground_truth.get('reward_model', [])
    env_name = ground_truth.get('env_name', '')
    
    # Check if this is a clean image sample
    is_clean_sample = env_name.strip().lower() == "clean"
    
    # Get expected degradation addition order
    if reward_model is not None and len(reward_model) > 0:
        degradation_addition_order = parse_reward_model_to_degradations_v2(reward_model)
    elif env_name and not is_clean_sample:
        env_degradations = parse_env_name_to_degradations_v2(env_name)
        degradation_addition_order = list(reversed(env_degradations))
    else:
        degradation_addition_order = []
    
    # Extract predicted restoration log
    # 单轮对话模式：直接从 <tool_call> 提取退化类型（避免依赖 <answer> 块）
    predicted_log = []
    try:
        import re
        import json
        # 从 tool_call 提取退化类型
        tool_call_matches = re.finditer(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', solution_str, re.DOTALL)
        for tool_call_match in tool_call_matches:
            tools = json.loads(tool_call_match.group(1))
            if isinstance(tools, list):
                for tool_dict in tools:
                    if isinstance(tool_dict, dict):
                        # 优先使用 degradation 字段（新格式）
                        if 'degradation' in tool_dict:
                            deg_type = tool_dict['degradation']
                            if deg_type and deg_type not in predicted_log:
                                predicted_log.append(deg_type)
                        # 如果没有 degradation 字段，不添加（避免用工具名称推断）
    except Exception as e:
        print(f' [DEBUG] 从 tool_call 提取退化类型失败: {e}')
    
    # 如果 tool_call 中没有提取到，尝试从 <answer> 块的 restoration_log 提取（兼容旧格式）
    if not predicted_log:
        predicted_log = extract_restoration_log_from_response_v2(solution_str)
        if predicted_log:
            print(f' [DEBUG] 从 restoration_log 提取到退化类型: {predicted_log} (兼容旧格式)')
    
    # Compute format score with content-aware checking for non-clean samples
    if strict_format:
        if use_enhanced_format:
            # Use enhanced multi-turn format checking with additional constraints
            degradation_count = len(degradation_addition_order)
            format_score = check_multiturn_format_v3_enhanced(
                solution_str, 
                degradation_count=degradation_count, 
                is_clean_sample=is_clean_sample,
                max_tools_per_turn=max_tools_per_turn,
                enable_total_tools_upper_limit=enable_total_tools_upper_limit
            )
        else:
            # Use standard multi-turn format checking for strict mode (已经内置了clean/non-clean判断)
            format_score = check_multiturn_format_v2(solution_str, is_clean_sample=is_clean_sample)
    else:
        format_score = check_response_format_v2(solution_str)
        
        # For non-clean samples, no additional requirements beyond format checking
        # (格式检查已经包含了tool_call和answer不能同时出现的规则)
    
    # Compute step logic score (temporarily disabled)
    logic_score = 0.0  # check_step_logic_v2(solution_str)  # 暂时关闭逻辑奖励
    
    # Compute accuracy score based on mode and whether it's a clean sample
    image_quality_details = {}
    
    # Special handling for clean image samples
    if is_clean_sample:
        # For clean samples, use accuracy reward instead of image quality reward
        # Only give score of 1 if response correctly identifies image as clean
        if check_clean_image_response_v2(solution_str):
            # 降低clean样本的奖励，避免模型过度倾向于"不用工具"
            # 0.8 vs 1.0：让正确使用工具恢复的样本更有吸引力
            accuracy_score = 0.5  # 从1.0降低到0.8
            print(f' [DEBUG clean_sample] Correctly identified clean image, accuracy_score=0.5 (降低以平衡工具使用)')
        else:
            accuracy_score = 0.0
            print(f' [DEBUG clean_sample] Failed to identify clean image, accuracy_score=0.0')
    else:
        # Normal processing for non-clean samples
        if accuracy_mode == "image_quality":
            # Use image quality metrics (SSIM + LPIPS + PSNR)
            print(f' [DEBUG] 调用 compute_image_quality_reward_v2... 模式: {"无参考" if use_no_reference else "有参考"}')
            quality_result = compute_image_quality_reward_v2(solution_str, extra_info, discretize_levels=discretize_levels, use_no_reference=use_no_reference)
            print(f' [DEBUG] compute_image_quality_reward_v2 返回类型: {type(quality_result)}')
            print(f' [DEBUG] compute_image_quality_reward_v2 返回值: {quality_result}')
            
            if isinstance(quality_result, dict):
                accuracy_score = quality_result["image_quality_reward"]
                image_quality_details = quality_result
                print(f' [DEBUG] 从字典中提取 accuracy_score={accuracy_score}')
            else:
                accuracy_score = quality_result
                print(f' [DEBUG] 直接使用返回值 accuracy_score={accuracy_score}')
        elif accuracy_mode == "partial_credit":
            # Use degradation order checking with partial credit (新的递进式奖励)
            accuracy_score = check_restoration_order_with_partial_credit_v2(predicted_log, degradation_addition_order)
        elif accuracy_mode == "order_with_dedup":
            merged_predicted_log = merge_consecutive_duplicates_v2(predicted_log)
            accuracy_score = check_restoration_order_v2(merged_predicted_log, degradation_addition_order)
        elif accuracy_mode == "order_only":
            accuracy_score = check_restoration_order_v2(predicted_log, degradation_addition_order)
        else:
            raise ValueError(f"Unknown accuracy_mode: {accuracy_mode}")
    
    # Debug output - 显示预测和期望的顺序
    format_mode = "strict" if strict_format else "gradual"
    
    print(f' [DEBUG image_restoration_v2] format_mode={format_mode}, accuracy_mode={accuracy_mode}, is_clean_sample={is_clean_sample}')
    
    if is_clean_sample:
        print(f' [DEBUG image_restoration_v2] clean sample detected, using clean detection reward')
        print(f' [DEBUG image_restoration_v2] format_score={format_score:.3f}, logic_score={logic_score:.3f}, accuracy_score={accuracy_score:.3f}')
    elif accuracy_mode == "image_quality":
        print(f' [DEBUG image_restoration_v2] using image quality metrics (SSIM + LPIPS + PSNR)')
        print(f' [DEBUG image_restoration_v2] format_score={format_score:.3f}, logic_score={logic_score:.3f}, quality_score={accuracy_score:.3f}')
    else:
        # 显示预测和期望的退化类型顺序（用于 partial_credit, order_only, order_with_dedup 模式）
        predicted_log_str = ', '.join(predicted_log) if predicted_log else ''
        degradation_addition_order_str = ', '.join(degradation_addition_order) if degradation_addition_order else ''
        correct_restoration_order_str = ', '.join(reversed(degradation_addition_order)) if degradation_addition_order else ''
        print(f' [DEBUG image_restoration_v2] using degradation order reward ({accuracy_mode})')
        print(f' [DEBUG image_restoration_v2] predicted_log="{predicted_log_str}" (count={len(predicted_log)})')
        print(f' [DEBUG image_restoration_v2] expected_order="{degradation_addition_order_str}" (count={len(degradation_addition_order)})')
        print(f' [DEBUG image_restoration_v2] correct_restoration="{correct_restoration_order_str}"')
        print(f' [DEBUG image_restoration_v2] format_score={format_score:.3f}, logic_score={logic_score:.3f}, accuracy_score={accuracy_score:.3f}')
    
    # Combined score with weights
    # 奖励结构：格式奖励 + 图像质量奖励 + (可选)退化类型奖励
    format_weight = format_reward_weight    # 格式奖励权重（从环境变量读取，默认0.3）
    quality_weight = quality_reward_weight  # 图像质量奖励权重（从环境变量读取，默认0.7）
    logic_weight = 0.0  # 当前逻辑奖励被禁用
    
    # accuracy_score实际是图像质量分数，重命名为quality_score更清晰
    quality_score = accuracy_score
    
    # Format score处理：
    # - format_score = 1.0: 完美格式
    # - format_score = -1.0: 格式违规（任何不符合要求的情况）
    
    # 对于格式违规，总分应该是负数
    if format_score == -1.0:
        # 格式违规，总分为负（不给图像质量奖励）
        total_score = format_weight * format_score + logic_weight * logic_score
        print(f' [DEBUG image_restoration_v2] 格式违规，不计算图像质量奖励')
    else:
        # 格式正确，计算基础奖励 = 格式 + 图像质量
        total_score = format_weight * format_score + logic_weight * logic_score + quality_weight * quality_score
    
    print(f' [DEBUG image_restoration_v2] weights: format={format_weight}, quality={quality_weight}, logic={logic_weight}')
    print(f' [DEBUG image_restoration_v2] base_reward={total_score:.3f} (format + quality)')
    
    # 计算退化类型奖励（可选，不考虑顺序）
    degradation_type_score = 0.0
    if enable_degradation_type_reward and not is_clean_sample:
        degradation_type_score = check_degradation_type_match_v2(predicted_log, degradation_addition_order)
        degradation_type_contribution = degradation_type_reward_weight * degradation_type_score
        
        # 只有格式正确时才给退化类型奖励
        if format_score > 0:
            total_score += degradation_type_contribution
            print(f' [DEBUG degradation_type_reward] enabled, degradation_type_score={degradation_type_score:.3f}, weight={degradation_type_reward_weight:.1f}, contribution={degradation_type_contribution:.3f}')
        else:
            print(f' [DEBUG degradation_type_reward] skipped due to format error')
    elif enable_degradation_type_reward and is_clean_sample:
        print(f' [DEBUG degradation_type_reward] skipped for clean sample')
    
    print(f' [DEBUG image_restoration_v2] total_score={total_score:.3f} (包含退化类型奖励)' if enable_degradation_type_reward and format_score > 0 else f' [DEBUG image_restoration_v2] total_score={total_score:.3f}')
    
    # 计算中间图像质量奖励（只有格式正确且非clean样本时才给）
    intermediate_quality_score = 0.0
    if enable_intermediate_reward and format_score > 0 and not is_clean_sample:
        # 从extra_info获取图像历史
        if extra_info is not None and 'image_history' in extra_info:
            image_history = extra_info.get('image_history', [])
            if len(image_history) >= 2:
                # 计算中间图像质量奖励
                intermediate_quality_score = compute_intermediate_image_quality_reward(image_history, include_last=False)
                intermediate_contribution = intermediate_reward_weight * intermediate_quality_score
                
                total_score += intermediate_contribution
                print(f' [DEBUG intermediate_reward] enabled, intermediate_quality_score={intermediate_quality_score:.3f}, weight={intermediate_reward_weight:.1f}, contribution={intermediate_contribution:.3f}')
                print(f' [DEBUG intermediate_reward] new total_score={total_score:.3f} (包含中间图像质量奖励)')
            else:
                print(f' [DEBUG intermediate_reward] 图像历史不足，跳过中间奖励计算 (history_len={len(image_history)})')
        else:
            print(f' [DEBUG intermediate_reward] extra_info中没有image_history，跳过中间奖励计算')
    elif enable_intermediate_reward and is_clean_sample:
        print(f' [DEBUG intermediate_reward] clean样本跳过中间奖励计算')
    elif enable_intermediate_reward and format_score <= 0:
        print(f' [DEBUG intermediate_reward] 格式错误，跳过中间奖励计算')
    
    # 计算工具多样性bonus（只有格式正确且非clean样本时才给）
    tool_diversity_bonus = 0.0
    if format_score > 0 and not is_clean_sample:
        # 从extra_info获取对话模式
        conversation_mode = 'multi_tool_planning'  # 默认值
        if extra_info is not None and 'conversation_mode' in extra_info:
            conversation_mode = extra_info['conversation_mode']
        
        tool_diversity_bonus = compute_tool_diversity_bonus_v2(solution_str, conversation_mode)
        
        if tool_diversity_bonus > 0:
            total_score += tool_diversity_bonus
            print(f' [DEBUG tool_diversity_bonus] bonus={tool_diversity_bonus:.3f} added, new total_score={total_score:.3f}')
    elif is_clean_sample:
        print(f' [DEBUG tool_diversity_bonus] skipped for clean sample')
    elif format_score <= 0:
        print(f' [DEBUG tool_diversity_bonus] skipped due to format error')
    
    # 返回包含各项分数的字典（用于监控）
    result_dict = {
        "score": total_score,                           # 总分（格式+质量+可选的退化类型+中间奖励+工具多样性bonus）
        "format_score": format_score,                   # 格式分数（1.0或-1.0）
        "quality_score": quality_score,                 # 图像质量分数（0.0~1.0）
        "degradation_type_score": degradation_type_score,  # 退化类型分数（0.0~1.0，仅在启用时计算）
        "intermediate_quality_score": intermediate_quality_score,  # 中间图像质量分数（0.0~1.0，仅在启用时计算）
        "tool_diversity_bonus": tool_diversity_bonus,   # 工具多样性bonus（0.0或0.1）
        # 保留旧字段以兼容
        "accuracy_score": quality_score,                # 兼容旧代码，实际是图像质量分数
        "degradation_order_score": quality_score,       # 兼容旧代码
    }
    
    # 添加退化类型信息（直接从数据集的reward_model获取）
    degradation_type = "unknown"
    degradation_types_all = ""  # 确保每个样本都有这个字段
    
    if is_clean_sample:
        degradation_type = "clean"
        degradation_types_all = "clean"
    elif reward_model is not None and len(reward_model) > 0:
        # 直接从reward_model的第一个元素中获取degradation_type
        if isinstance(reward_model[0], dict) and 'degradation_type' in reward_model[0]:
            degradation_type = reward_model[0]['degradation_type']
            
            # 总是生成完整的退化类型列表（无论单个还是多个）
            all_types = [item.get('degradation_type', '') for item in reward_model if isinstance(item, dict) and 'degradation_type' in item]
            if all_types:
                degradation_types_all = ", ".join(all_types)
            else:
                degradation_types_all = degradation_type  # 单个退化类型的情况
    
    result_dict["degradation_type"] = degradation_type
    result_dict["degradation_types_all"] = degradation_types_all  # 确保每个样本都有此字段
    
    # 添加clean准确率统计（对所有模式都添加is_clean_sample标记）
    if is_clean_sample:
        clean_accuracy = 1.0 if check_clean_image_response_v2(solution_str) else 0.0
        result_dict["clean_accuracy"] = clean_accuracy
        result_dict["is_clean_sample"] = 1.0  # 标记这是clean样本
        print(f' [DEBUG clean_accuracy] clean_accuracy={clean_accuracy:.3f} (仅用于监控)')
    else:
        # 对于非clean样本，标记不是clean样本（不设置clean_accuracy）
        result_dict["is_clean_sample"] = 0.0
    
    # 所有模式都返回字典，确保reward manager能正确获取is_clean_sample信息
    return result_dict


# Test function for v2 format
def test_v2_format():
    """Test the v2 format checking with examples"""
    
    # Test case 1: Correct format - degradation detected + tool call
    test1 = """<think>Image exhibits blocky artifacts typical of JPEG compression, which is the highest priority to fix based on the LIFO principle.</think>
<tool_call>
[
  {"name": "swinir_jpeg_artifact_removal", "arguments": {"jpeg": 40}}
]
</tool_call>"""
    
    print("Test 1 - Correct format (degradation + tool):")
    format_score = check_response_format_v2(test1)
    logic_score = check_step_logic_v2(test1)
    print(f"  Format score: {format_score:.3f}")
    print(f"  Logic score: {logic_score:.3f}")
    print()
    
    # Test case 2: Correct format - clean image + answer
    test2 = """<think>No significant artifacts remain.</think>
<answer>
{
  "restoration_log": [
    "jpeg compression artifact",
    "motion blur"
  ]
}
</answer>"""
    
    print("Test 2 - Correct format (clean + answer):")
    format_score = check_response_format_v2(test2)
    logic_score = check_step_logic_v2(test2)
    print(f"  Format score: {format_score:.3f}")
    print(f"  Logic score: {logic_score:.3f}")
    print()
    
    # Test case 3: Format violation - both tool_call and answer
    test3 = """<think>Image exhibits blocky artifacts typical of JPEG compression.</think>
<tool_call>
[
  {"name": "tool_name", "arguments": {}}
]
</tool_call>
<answer>
{
  "restoration_log": ["jpeg compression artifact"]
}
</answer>"""
    
    print("Test 3 - Format violation (both tool_call and answer):")
    format_score = check_response_format_v2(test3)
    logic_score = check_step_logic_v2(test3)
    print(f"  Format score: {format_score:.3f}")
    print(f"  Logic score: {logic_score:.3f}")
    print()
    
    # Test case 4: Missing think
    test4 = """<tool_call>
[
  {"name": "swinir_jpeg_artifact_removal", "arguments": {"jpeg": 40}}
]
</tool_call>"""
    
    print("Test 4 - Missing think:")
    format_score = check_response_format_v2(test4)
    logic_score = check_step_logic_v2(test4)
    print(f"  Format score: {format_score:.3f}")
    print(f"  Logic score: {logic_score:.3f}")
    print()
    
    # Test case 5: Clean image response
    test5 = """<think>The image appears clean with no significant artifacts or degradation visible.</think>
<answer>
{
  "restoration_log": []
}
</answer>"""
    
    print("Test 5 - Clean image response:")
    is_clean_response = check_clean_image_response_v2(test5)
    print(f"  Clean response detected: {is_clean_response}")
    
    # Test clean sample scoring
    ground_truth_clean = {"env_name": "clean"}
    score_clean = compute_score_v2(test5, ground_truth_clean, extra_info=None, accuracy_mode="image_quality")
    if isinstance(score_clean, dict):
        print(f"  Clean sample score: {score_clean['score']:.3f}")
        print(f"  Clean accuracy: {score_clean['clean_accuracy']:.3f}")
    else:
        print(f"  Clean sample score: {score_clean:.3f}")
    print()
    
    # Test case 6: Clean sample with wrong response (using tool instead of answer)
    test6 = """<think>Image exhibits blocky artifacts typical of JPEG compression.</think>
<tool_call>
[
  {"name": "swinir_jpeg_artifact_removal", "arguments": {"jpeg": 40}}
]
</tool_call>"""
    
    print("Test 6 - Clean sample with wrong response (tool instead of answer):")
    is_clean_response6 = check_clean_image_response_v2(test6)
    print(f"  Clean response detected: {is_clean_response6}")
    
    # Test with format-only mode (default)
    score_clean_wrong = compute_score_v2(test6, ground_truth_clean, extra_info=None, accuracy_mode="image_quality")
    if isinstance(score_clean_wrong, dict):
        print(f"  Clean sample score (format-only): {score_clean_wrong['score']:.3f}")
        print(f"  Clean accuracy (wrong response): {score_clean_wrong['clean_accuracy']:.3f}")
    else:
        print(f"  Clean sample score (format-only): {score_clean_wrong:.3f}")
    
    # Test with content-aware format mode  
    score_clean_content_format = compute_score_v2(test6, ground_truth_clean, extra_info=None, accuracy_mode="image_quality", format_content_aware=True)
    if isinstance(score_clean_content_format, dict):
        print(f"  Clean sample score (content-aware format): {score_clean_content_format['score']:.3f}")
        print(f"  Clean accuracy (should be same): {score_clean_content_format['clean_accuracy']:.3f}")
    else:
        print(f"  Clean sample score (content-aware format): {score_clean_content_format:.3f}")
    print()
    
    # Test case 7: Clean sample with mixed prediction (should be incorrect)
    test7_mixed = """<think>The image appears mostly clean but might have some minor artifacts.</think>
<answer>
{
  "restoration_log": ["clean", "noise"]
}
</answer>"""
    
    print("Test 7 - Clean sample with mixed prediction (clean + noise):")
    is_clean_response7 = check_clean_image_response_v2(test7_mixed)
    print(f"  Clean response detected: {is_clean_response7}")
    
    score_clean_mixed = compute_score_v2(test7_mixed, ground_truth_clean, extra_info=None, accuracy_mode="image_quality")
    if isinstance(score_clean_mixed, dict):
        print(f"  Clean sample score (mixed prediction): {score_clean_mixed['score']:.3f}")
        print(f"  Clean accuracy (should be 0): {score_clean_mixed['clean_accuracy']:.3f}")
    else:
        print(f"  Clean sample score (mixed prediction): {score_clean_mixed:.3f}")
    print()
    
    # Test case 8: Clean sample with only "clean" in restoration_log (should be correct)
    test8_clean_only = """<think>The image is clean with no degradation.</think>
<answer>
{
  "restoration_log": ["clean"]
}
</answer>"""
    
    print("Test 8 - Clean sample with only 'clean' in restoration_log:")
    is_clean_response8 = check_clean_image_response_v2(test8_clean_only)
    print(f"  Clean response detected: {is_clean_response8}")
    
    score_clean_only = compute_score_v2(test8_clean_only, ground_truth_clean, extra_info=None, accuracy_mode="image_quality")
    if isinstance(score_clean_only, dict):
        print(f"  Clean sample score (clean only): {score_clean_only['score']:.3f}")
        print(f"  Clean accuracy (should be 1): {score_clean_only['clean_accuracy']:.3f}")
    else:
        print(f"  Clean sample score (clean only): {score_clean_only:.3f}")
    print()
    
    # Test case 9: Non-clean sample (should have clean_accuracy = 0)
    test9 = """<think>Image exhibits blocky artifacts typical of JPEG compression, which is the highest priority to fix.</think>
<tool_call>
[
  {"name": "swinir_jpeg_artifact_removal", "arguments": {"jpeg": 40}}
]
</tool_call>"""
    
    print("Test 9 - Non-clean sample:")
    ground_truth_non_clean = {"env_name": "jpeg_compression_artifact"}
    score_non_clean = compute_score_v2(test9, ground_truth_non_clean, extra_info=None, accuracy_mode="image_quality")
    if isinstance(score_non_clean, dict):
        print(f"  Non-clean sample score: {score_non_clean['score']:.3f}")
        print(f"  Is clean sample: {score_non_clean.get('is_clean_sample', 'N/A')}")
        print(f"  Clean accuracy (should not exist): {score_non_clean.get('clean_accuracy', 'N/A')}")
    else:
        print(f"  Non-clean sample score: {score_non_clean:.3f}")
    print()


if __name__ == "__main__":
    test_v2_format()
