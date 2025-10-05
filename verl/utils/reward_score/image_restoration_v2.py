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

# Import image quality metrics
try:
    from .image_quality_metrics import ImageQualityMetrics, compute_image_restoration_reward
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


def check_response_format_strict_v2(response_str: str) -> float:
    """
    Strict format checking for v2 format: only give reward if format is completely correct.
    Based on the new system prompt rules:
    1. 每轮对话都必须有<think>块，包含简短推理
    2. <tool_call>和<answer>不能同时出现
    3. 如果检测到退化，必须有<tool_call>
    4. 如果图像干净，必须有<answer>
    5. <answer>必须包含valid JSON with restoration_log (only field)
    6. tool_call中的工具名称必须是system prompt中允许的工具
    
    Returns 1.0 if perfect, 0.0 if any format violation.
    """
    # Define allowed tools from system prompt
    allowed_tools = {
        "dehazeformer_dehaze", "drbnet_defocus_deblurring", "histogram_equalization",
        "gamma_correction", "xrestormer_motion_deblurring", "mprnet_motion_deblurring",
        "mprnet_deraining", "swinir_jpeg_artifact_removal", "fbcnn_jpeg_artifact_removal",
        "swinir_super_resolution", "swinir_denoising", "mprnet_denoising"
    }
    # 1. Check for <think> block with brief reasoning (text, not JSON)
    think_match = re.search(r'<think>(.*?)</think>', response_str, re.DOTALL)
    if not think_match:
        return 0.0
    
    think_content = think_match.group(1).strip()
    if len(think_content) < 10:  # Must have meaningful reasoning
        return 0.0
    
    # 2. Check for <tool_call> and <answer> blocks
    tool_call_match = re.search(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', response_str, re.DOTALL)
    answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', response_str, re.DOTALL)
    
    # 3. Rule: answer and tool_call cannot coexist
    if tool_call_match and answer_match:
        return 0.0
    
    # 4. Must have exactly one of tool_call or answer
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
    
    return 1.0


def check_response_format_v2(response_str: str) -> float:
    """
    Gradual format checking for v2: give partial credit for partial compliance.
    Returns a score between 0 and 1 based on format compliance.
    """
    # Define allowed tools from system prompt
    allowed_tools = {
        "dehazeformer_dehaze", "drbnet_defocus_deblurring", "histogram_equalization",
        "gamma_correction", "xrestormer_motion_deblurring", "mprnet_motion_deblurring",
        "mprnet_deraining", "swinir_jpeg_artifact_removal", "fbcnn_jpeg_artifact_removal",
        "swinir_super_resolution", "swinir_denoising", "mprnet_denoising"
    }
    
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
    
    # 4. Must have exactly one action
    if not tool_call_match and not answer_match:
        format_score -= 0.5  # Penalty for no action
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
    if not reward_model:
        return []
    
    degradations = []
    for item in reward_model:
        if isinstance(item, dict) and 'degradation_type' in item:
            deg_type = item['degradation_type']
            if deg_type is not None:
                degradations.append(str(deg_type))
    
    return degradations


def compute_image_quality_reward_v2(solution_str: str, extra_info: Dict = None) -> float:
    """
    Compute image quality reward using SSIM, LPIPS, and PSNR metrics.
    
    Args:
        solution_str: The model's response string
        extra_info: Dictionary containing image history and other data
        
    Returns:
        Image quality reward score between 0 and 1
    """
    if not HAS_IMAGE_QUALITY:
        print("[WARNING] Image quality metrics not available, falling back to 0.5")
        return 0.5
    
    def return_zero_quality_result(reason: str):
        """返回0分的详细结果（确保字段结构一致）"""
        print(f"[WARNING] {reason}")
        return 0.0  # 统一返回float类型，保持一致性

    if extra_info is None:
        return return_zero_quality_result("extra_info is None")
    
    # 1. 获取原图（来自parquet数据集）
    original_image_data = extra_info.get('original_image', None)
    if original_image_data is None:
        return return_zero_quality_result("No original image found in extra_info['original_image'] (from parquet dataset)")
    
    # 2. 获取图像历史（训练过程中动态生成的）
    image_history = extra_info.get('image_history', [])
    
    # 检查image_history是否为空（兼容numpy数组和Python列表）
    import numpy as np
    if isinstance(image_history, np.ndarray):
        if image_history.size == 0:
            return return_zero_quality_result("No image history found (empty numpy array) - no tools were executed")
    else:
        if not image_history:
            return return_zero_quality_result("No image history found (empty list) - no tools were executed")
    
    # 3. 获取最后一个被工具处理的图像
    if len(image_history) < 2:
        return return_zero_quality_result(f"No processed image found (only input image), history length: {len(image_history)} - tools did not generate new images")
    
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
        print(f"[DEBUG] 开始图像质量计算...")
        
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
                return return_zero_quality_result(f"Unsupported original image format: {type(original_image_data)}")
        
        # 对原图也应用fetch_image预处理，确保与复原图一致
        if hasattr(original_image, 'size'):
            print(f"[DEBUG] 原图预处理前尺寸: {original_image.size}")
            
            # 将原图也通过相同的预处理流程
            from qwen_vl_utils import fetch_image
            # 创建与复原图相同的数据结构
            original_dict = {"image": original_image}
            original_image_processed = fetch_image(original_dict, size_factor=28)
            print(f"[DEBUG] 原图预处理后尺寸: {original_image_processed.size}")
            original_image = original_image_processed
        elif hasattr(original_image, 'shape'):
            print(f"[DEBUG] 原图是numpy数组，shape: {original_image.shape}")
            # 如果是numpy数组，转换为PIL图像
            from PIL import Image
            if len(original_image.shape) == 3:
                original_pil = Image.fromarray(original_image.astype('uint8'))
            else:
                original_pil = Image.fromarray(original_image.astype('uint8'), mode='L')
            print(f"[DEBUG] 原图numpy转PIL后尺寸: {original_pil.size}")
            
            # 应用fetch_image
            from qwen_vl_utils import fetch_image
            original_dict = {"image": original_pil}
            original_image_processed = fetch_image(original_dict, size_factor=28)
            print(f"[DEBUG] 原图预处理后尺寸: {original_image_processed.size}")
            original_image = original_image_processed
        else:
            print(f"[DEBUG] 原图格式异常: {type(original_image)}, 无法获取尺寸")
            
        # 复原图从图像历史中提取（已经经过了fetch_image处理）
        restored_image = extract_image_from_multimodal_data(restored_image_data)
        print(f"[DEBUG] 复原图尺寸: {restored_image.size if hasattr(restored_image, 'size') else 'N/A'}")
        
        if original_image is None or restored_image is None:
            return return_zero_quality_result("Failed to extract images from multimodal data")
        
        # Compute image quality reward with detailed metrics
        from .image_quality_metrics import ImageQualityMetrics, normalize_metrics
        
        metrics_calculator = ImageQualityMetrics()
        metrics = metrics_calculator.calculate_all_metrics(restored_image, original_image)
        
        # 获取原始指标值
        ssim_val = metrics['ssim']
        lpips_val = metrics['lpips']
        psnr_val = metrics['psnr']
        
        # 归一化指标
        norm_ssim, norm_lpips, norm_psnr = normalize_metrics(ssim_val, lpips_val, psnr_val)
        
        # 计算最终奖励
        alpha, beta, gamma = 0.4, 0.4, 0.2
        reward = alpha * norm_ssim + beta * (1.0 - norm_lpips) + gamma * norm_psnr
        reward = max(0.0, min(1.0, reward))
        
        print(f' [DEBUG image_quality] ssim={ssim_val:.4f}(norm={norm_ssim:.4f}), '
              f'lpips={lpips_val:.4f}(norm={norm_lpips:.4f}), '
              f'psnr={psnr_val:.4f}(norm={norm_psnr:.4f})')
        print(f' [DEBUG image_quality] weights: α={alpha}, β={beta}, γ={gamma}')
        print(f' [DEBUG image_quality] reward={reward:.4f}')
        
        # 返回详细信息字典（成功情况）
        return {
            "image_quality_reward": reward,
            "ssim_score": ssim_val,
            "lpips_score": lpips_val, 
            "psnr_score": psnr_val,
            "ssim_normalized": norm_ssim,
            "lpips_normalized": norm_lpips,
            "psnr_normalized": norm_psnr,
            "success": True
        }
    except Exception as e:
        print(f"[WARNING] Image quality computation failed: {e}")
        # 返回简单的失败分数，保持类型一致性
        return 0.0


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
    Check restoration order with partial credit (adapted from v1).
    """
    if not predicted_log or not reward_model_order:
        return 0.0
    
    expected_count = len(reward_model_order)
    predicted_count = len(predicted_log)
    correct_restoration_order = list(reversed(reward_model_order))
    
    # Check if predicted degradation types are valid
    try:
        predicted_set = set(str(item) for item in predicted_log if item is not None)
        expected_set = set(str(item) for item in reward_model_order if item is not None)
        
        # If predicted invalid types, return 0
        if not predicted_set.issubset(expected_set):
            return 0.0
    except (TypeError, AttributeError):
        return 0.0
    
    # Check if order is correct for the predicted portion
    if predicted_count > expected_count:
        return 0.0  # Predicted too many
    
    # Check if predicted order matches expected order
    for i in range(predicted_count):
        if i >= len(correct_restoration_order) or predicted_log[i] != correct_restoration_order[i]:
            return 0.0  # Wrong order
    
    # Give partial credit based on predicted count
    if expected_count == 1:
        partial_score = 1.0 if predicted_count == expected_count else 0.0
    elif expected_count == 2:
        partial_score = predicted_count / expected_count
    elif expected_count == 3:
        if predicted_count == 1:
            partial_score = 1.0 / 3.0
        elif predicted_count == 2:
            partial_score = 0.5
        elif predicted_count == 3:
            partial_score = 1.0
        else:
            partial_score = 0.0
    else:
        partial_score = predicted_count / expected_count
    
    return partial_score


def compute_score_v2(solution_str: str, ground_truth: Union[str, Dict], extra_info: Dict = None, 
                     strict_format: bool = True, accuracy_mode: str = "image_quality") -> float:
    """
    Compute reward score for image restoration task (v2 format).
    
    Args:
        solution_str: The model's response string
        ground_truth: Dictionary containing reward_model and env_name
        extra_info: Additional information containing 'original_image' key with original image data
        strict_format: If True, use strict format checking. If False, use gradual format checking.
        accuracy_mode: Accuracy checking mode:
            - "image_quality": Use image quality metrics (SSIM + LPIPS + PSNR) (DEFAULT)
            - "partial_credit": Partial credit based on correct count
            - "order_only": Original order-only checking
            - "order_with_dedup": Order checking with consecutive duplicate merging
    
    Returns:
        Float score between -1 and 1 (can be negative due to format violations)
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
    
    # Get expected degradation addition order
    if reward_model:
        degradation_addition_order = parse_reward_model_to_degradations_v2(reward_model)
    elif env_name:
        env_degradations = parse_env_name_to_degradations_v2(env_name)
        degradation_addition_order = list(reversed(env_degradations))
    else:
        degradation_addition_order = []
    
    # Extract predicted restoration log
    predicted_log = extract_restoration_log_from_response_v2(solution_str)
    
    # Compute format score
    if strict_format:
        format_score = check_response_format_strict_v2(solution_str)
    else:
        format_score = check_response_format_v2(solution_str)
    
    # Compute step logic score (temporarily disabled)
    logic_score = 0.0  # check_step_logic_v2(solution_str)  # 暂时关闭逻辑奖励
    
    # Compute accuracy score based on mode
    image_quality_details = {}
    if accuracy_mode == "image_quality":
        # Use image quality metrics (SSIM + LPIPS + PSNR)
        quality_result = compute_image_quality_reward_v2(solution_str, extra_info)
        if isinstance(quality_result, dict):
            accuracy_score = quality_result["image_quality_reward"]
            image_quality_details = quality_result
        else:
            accuracy_score = quality_result
    
    # 根据accuracy_mode计算不同的accuracy_score
    if accuracy_mode == "partial_credit":
        accuracy_score = check_restoration_order_with_partial_credit_v2(predicted_log, degradation_addition_order)
    elif accuracy_mode == "order_with_dedup":
        merged_predicted_log = merge_consecutive_duplicates_v2(predicted_log)
        accuracy_score = check_restoration_order_v2(merged_predicted_log, degradation_addition_order)
    elif accuracy_mode == "order_only":
        accuracy_score = check_restoration_order_v2(predicted_log, degradation_addition_order)
    elif accuracy_mode == "image_quality":
        # accuracy_score已经在上面计算过了，这里不需要重复
        pass
    else:
        raise ValueError(f"Unknown accuracy_mode: {accuracy_mode}")
    
    # 计算退化类型奖励（仅用于监控，不加到总奖励中）
    degradation_order_score = 0.0
    if predicted_log and degradation_addition_order:
        degradation_order_score = check_restoration_order_with_partial_credit_v2(predicted_log, degradation_addition_order)
        print(f' [DEBUG degradation_order] predicted_log="{", ".join(predicted_log)}"')
        print(f' [DEBUG degradation_order] expected_order="{", ".join(degradation_addition_order)}"')
        print(f' [DEBUG degradation_order] order_score={degradation_order_score:.3f} (仅用于监控)')
    
    # Debug output
    format_mode = "strict" if strict_format else "gradual"
    
    print(f' [DEBUG image_restoration_v2] format_mode={format_mode}, accuracy_mode={accuracy_mode}')
    
    if accuracy_mode == "image_quality":
        print(f' [DEBUG image_restoration_v2] using image quality metrics (SSIM + LPIPS + PSNR)')
        print(f' [DEBUG image_restoration_v2] format_score={format_score:.3f}, logic_score={logic_score:.3f}, quality_score={accuracy_score:.3f}')
    else:
        predicted_log_str = ', '.join(predicted_log) if predicted_log else ''
        degradation_addition_order_str = ', '.join(degradation_addition_order) if degradation_addition_order else ''
        correct_restoration_order_str = ', '.join(reversed(degradation_addition_order)) if degradation_addition_order else ''
        print(f' [DEBUG image_restoration_v2] predicted_log="{predicted_log_str}" (count={len(predicted_log)})')
        print(f' [DEBUG image_restoration_v2] expected_order="{degradation_addition_order_str}" (count={len(degradation_addition_order)})')
        print(f' [DEBUG image_restoration_v2] correct_restoration="{correct_restoration_order_str}"')
        print(f' [DEBUG image_restoration_v2] format_score={format_score:.3f}, logic_score={logic_score:.3f}, accuracy_score={accuracy_score:.3f}')
    
    # Combined score with weights
    format_weight = 0.4
    logic_weight = 0.0  # 当前逻辑奖励被禁用
    accuracy_weight = 0.6
    
    # Convert format score: 0 -> -1 for strict penalty
    if strict_format and format_score == 0:
        format_score = -1
    
    total_score = format_weight * format_score + logic_weight * logic_score + accuracy_weight * accuracy_score
    
    if accuracy_mode == "image_quality":
        print(f' [DEBUG image_restoration_v2] weights: format={format_weight}, logic={logic_weight}, quality={accuracy_weight}')
    else:
        print(f' [DEBUG image_restoration_v2] weights: format={format_weight}, logic={logic_weight}, accuracy={accuracy_weight}')
    print(f' [DEBUG image_restoration_v2] total_score={total_score:.3f}')
    
    # 返回包含退化类型奖励的字典（仅用于监控）
    if accuracy_mode == "image_quality":
        return {
            "score": total_score,
            "degradation_order_score": degradation_order_score  # 仅用于wandb监控
        }
    else:
        return total_score


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


if __name__ == "__main__":
    test_v2_format()
