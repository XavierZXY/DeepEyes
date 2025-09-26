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
from typing import List, Dict, Union


def extract_restoration_log_from_response(response_str: str) -> List[str]:
    """
    Extract restoration log from model response.
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


def merge_consecutive_duplicates(restoration_log: List[str]) -> List[str]:
    """
    Merge consecutive duplicate degradation types.
    Example: ["rain", "rain", "motion blur", "rain"] -> ["rain", "motion blur", "rain"]
    Only consecutive duplicates are merged.
    """
    if not restoration_log:
        return []
    
    merged_log = []
    for item in restoration_log:
        # Only add if it's different from the last item (consecutive deduplication)
        if not merged_log or merged_log[-1] != item:
            merged_log.append(item)
    
    return merged_log


def check_response_format_strict(response_str: str) -> float:
    """
    Strict format checking: only give reward if format is completely correct.
    Based on the system prompt rules.
    Returns 1.0 if perfect, 0.0 if any format violation.
    """
    # Check for <think> block with required fields
    think_match = re.search(r'<think>\s*(\{.*?\})\s*</think>', response_str, re.DOTALL)
    if not think_match:
        return 0.0
    
    try:
        think_json = json.loads(think_match.group(1))
        # Must have all required fields
        if not ('reasoning' in think_json and think_json['reasoning'].strip()):
            return 0.0
        if not ('diagnosis' in think_json and 'label' in think_json['diagnosis']):
            return 0.0
        if not ('pass' in think_json and isinstance(think_json['pass'], bool)):
            return 0.0
    except json.JSONDecodeError:
        return 0.0
    
    # Check mutual exclusivity and correct action based on pass value
    tool_call_match = re.search(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', response_str, re.DOTALL)
    answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', response_str, re.DOTALL)
    
    # Rule: answer and tool_call cannot coexist
    if tool_call_match and answer_match:
        return 0.0
    
    pass_value = think_json.get('pass', None)
    
    if pass_value is False:
        # Must have tool_call, must NOT have answer
        if not tool_call_match or answer_match:
            return 0.0
        # Validate tool_call JSON format
        try:
            tool_calls = json.loads(tool_call_match.group(1))
            if not isinstance(tool_calls, list) or len(tool_calls) == 0:
                return 0.0
            # Each tool call must have name and arguments
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    return 0.0
                if 'name' not in tool_call or 'arguments' not in tool_call:
                    return 0.0
        except json.JSONDecodeError:
            return 0.0
            
    elif pass_value is True:
        # Must have answer, must NOT have tool_call
        if not answer_match or tool_call_match:
            return 0.0
        # Validate answer JSON format
        try:
            answer_json = json.loads(answer_match.group(1))
            if 'status' not in answer_json or 'restoration_log' not in answer_json:
                return 0.0
        except json.JSONDecodeError:
            return 0.0
    else:
        return 0.0
    
    return 1.0


def check_response_format(response_str: str) -> float:
    """
    Gradual format checking: give partial credit for partial compliance.
    Returns a score between 0 and 1 based on format compliance.
    """
    format_score = 0.0
    
    # Check for <think> block with required fields
    think_match = re.search(r'<think>\s*(\{.*?\})\s*</think>', response_str, re.DOTALL)
    if think_match:
        try:
            think_json = json.loads(think_match.group(1))
            # Check required fields
            if 'reasoning' in think_json and think_json['reasoning'].strip():
                format_score += 0.2
            if 'diagnosis' in think_json and 'label' in think_json['diagnosis']:
                format_score += 0.2
            if 'pass' in think_json and isinstance(think_json['pass'], bool):
                format_score += 0.1
        except json.JSONDecodeError:
            pass
    
    # Check for appropriate action based on pass value and mutual exclusivity
    tool_call_match = re.search(r'<tool_call>\s*(\[.*?\])\s*</tool_call>', response_str, re.DOTALL)
    answer_match = re.search(r'<answer>\s*(\{.*?\})\s*</answer>', response_str, re.DOTALL)
    
    # Check for invalid simultaneous presence of both tool_call and answer
    if tool_call_match and answer_match:
        # Penalty for having both tool_call and answer (invalid format)
        format_score -= 0.5
        return max(format_score, 0.0)
    
    if think_match:
        try:
            think_json = json.loads(think_match.group(1))
            pass_value = think_json.get('pass', None)
            
            if pass_value is False:
                # Should have <tool_call> block and NOT have <answer>
                if tool_call_match and not answer_match:
                    format_score += 0.3
                    try:
                        tool_calls = json.loads(tool_call_match.group(1))
                        if isinstance(tool_calls, list) and len(tool_calls) > 0:
                            # Check if tool calls have name and arguments
                            for tool_call in tool_calls:
                                if 'name' in tool_call and 'arguments' in tool_call:
                                    format_score += 0.1
                                    break
                    except json.JSONDecodeError:
                        pass
                elif answer_match:
                    # Penalty for having answer when pass=false
                    format_score -= 0.2
                        
            elif pass_value is True:
                # Should have <answer> block and NOT have <tool_call>
                if answer_match and not tool_call_match:
                    format_score += 0.3
                    try:
                        answer_json = json.loads(answer_match.group(1))
                        if 'status' in answer_json and 'restoration_log' in answer_json:
                            format_score += 0.1
                    except json.JSONDecodeError:
                        pass
                elif tool_call_match:
                    # Penalty for having tool_call when pass=true
                    format_score -= 0.2
        except json.JSONDecodeError:
            pass
    
    return min(format_score, 1.0)


def parse_env_name_to_degradations(env_name: str) -> List[str]:
    """
    Parse env_name string to extract degradation types.
    Note: env_name is in reverse order of degradation addition.
    Example: "jpeg compression artifact, motion blur, haze" -> ["jpeg compression artifact", "motion blur", "haze"]
    """
    if not env_name:
        return []
    
    # Split by comma and strip whitespace
    degradations = [deg.strip() for deg in env_name.split(',')]
    return [str(deg) for deg in degradations if deg and deg.strip()]


def parse_reward_model_to_degradations(reward_model: List[Dict]) -> List[str]:
    """
    Parse reward_model list to extract degradation types in addition order.
    Example: [{'degradation_type': 'haze', 'degradation_level': 'low'}, 
              {'degradation_type': 'motion blur', 'degradation_level': 'medium'}, ...] 
    -> ["haze", "motion blur", ...]
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


def check_restoration_accuracy_with_penalties(predicted_log: List[str], reward_model_order: List[str]) -> Dict[str, float]:
    """
    Check restoration accuracy with negative penalties for wrong predictions.
    
    Args:
        predicted_log: The restoration order from model response
        reward_model_order: The degradation order from reward_model (addition order)
    
    Returns:
        Dict with detailed scores including penalties
    """
    if not reward_model_order:
        return {"type_score": 0.0, "count_penalty": 0.0, "order_score": 0.0, "combined_score": 0.0}
    
    expected_count = len(reward_model_order)
    predicted_count = len(predicted_log) if predicted_log else 0
    correct_restoration_order = list(reversed(reward_model_order))
    
    # 1. Count penalty (数量不匹配的惩罚)
    if predicted_count == expected_count:
        count_penalty = 0.0  # 数量正确，无惩罚
    else:
        # 数量错误的惩罚：差距越大惩罚越重
        count_diff = abs(predicted_count - expected_count)
        count_penalty = -0.2 * count_diff  # 每个错误数量 -0.2分
        count_penalty = max(count_penalty, -1.0)  # 最大惩罚不超过 -1.0
    
    # 2. Type accuracy score (类型准确性)
    type_score = 0.0
    wrong_type_penalty = 0.0
    
    if predicted_log:
        try:
            predicted_set = set(str(item) for item in predicted_log if item is not None)
            expected_set = set(str(item) for item in reward_model_order if item is not None)
            
            correct_types = predicted_set.intersection(expected_set)
            wrong_types = predicted_set - expected_set
            
            # 正确类型的奖励
            if len(correct_types) > 0:
                type_score = len(correct_types) / len(expected_set)
            
            # 错误类型的惩罚
            if len(wrong_types) > 0:
                wrong_type_penalty = -0.3 * len(wrong_types)  # 每个错误类型 -0.3分
                
        except (TypeError, AttributeError) as e:
            print(f" [WARNING image_restoration] Type comparison failed: {e}")
            type_score = 0.0
            wrong_type_penalty = 0.0
    
    # 3. Order score (顺序检查，只有在数量和类型完全正确时才给分)
    order_score = 0.0
    order_penalty = 0.0
    
    if predicted_count == expected_count and type_score > 0.99:
        if predicted_log == correct_restoration_order:
            order_score = 1.0
        else:
            # 顺序错误的惩罚
            min_len = min(len(predicted_log), len(correct_restoration_order))
            wrong_positions = 0
            for i in range(min_len):
                if predicted_log[i] != correct_restoration_order[i]:
                    wrong_positions += 1
            
            if wrong_positions > 0:
                order_penalty = -0.1 * wrong_positions  # 每个错位 -0.1分
    
    # 4. Combined score with penalties
    base_score = max(0.0, type_score)  # 基础分数（类型正确的比例）
    total_penalty = count_penalty + wrong_type_penalty + order_penalty
    combined_score = base_score + total_penalty
    
    # 只有完全正确才给满分奖励
    if (predicted_count == expected_count and 
        type_score > 0.99 and 
        predicted_log == correct_restoration_order):
        combined_score = 1.0  # 完美预测奖励
    
    # 确保分数在合理范围内
    combined_score = max(combined_score, -1.0)  # 最低 -1.0
    combined_score = min(combined_score, 1.0)   # 最高 1.0
    
    return {
        "type_score": type_score,
        "count_penalty": count_penalty,
        "wrong_type_penalty": wrong_type_penalty,
        "order_penalty": order_penalty,
        "combined_score": combined_score,
        "expected_count": expected_count,
        "predicted_count": predicted_count
    }


def check_restoration_accuracy(predicted_log: List[str], reward_model_order: List[str]) -> Dict[str, float]:
    """
    Original accuracy checking (for backward compatibility).
    """
    if not reward_model_order:
        return {"type_score": 0.0, "count_score": 0.0, "order_score": 0.0, "combined_score": 0.0}
    
    if not predicted_log:
        return {"type_score": 0.0, "count_score": 0.0, "order_score": 0.0, "combined_score": 0.0}
    
    expected_count = len(reward_model_order)
    predicted_count = len(predicted_log)
    correct_restoration_order = list(reversed(reward_model_order))
    
    # 1. Count matching score (必须数量完全匹配)
    count_score = 1.0 if predicted_count == expected_count else 0.0
    
    # 2. Type matching score (预测的类型是否都在期望类型中)
    try:
        predicted_set = set(str(item) for item in predicted_log if item is not None)
        expected_set = set(str(item) for item in reward_model_order if item is not None)
        
        if predicted_set == expected_set:
            type_score = 1.0
        elif predicted_set.issubset(expected_set):
            # 部分匹配：预测的都是正确的，但可能缺少一些
            type_score = len(predicted_set) / len(expected_set)
        else:
            # 有错误的预测类型
            correct_predictions = len(predicted_set.intersection(expected_set))
            type_score = correct_predictions / max(len(predicted_set), len(expected_set))
    except (TypeError, AttributeError) as e:
        print(f" [WARNING image_restoration] Type comparison failed: {e}")
        type_score = 0.0
    
    # 3. Order score (只有在数量和类型都正确时才检查顺序)
    if count_score > 0 and type_score > 0.99:  # 类型基本完全匹配
        if predicted_log == correct_restoration_order:
            order_score = 1.0
        else:
            # 部分顺序正确
            min_len = min(len(predicted_log), len(correct_restoration_order))
            correct_positions = 0
            for i in range(min_len):
                if predicted_log[i] == correct_restoration_order[i]:
                    correct_positions += 1
            order_score = correct_positions / len(correct_restoration_order) if len(correct_restoration_order) > 0 else 0.0
    else:
        order_score = 0.0  # 数量或类型不对，顺序分数为0
    
    # 4. Combined score (只有所有维度都正确才给满分)
    if count_score > 0 and type_score > 0.99 and order_score > 0.99:
        combined_score = 1.0
    else:
        combined_score = 0.0  # 任何一个维度不完美都是0分
    
    return {
        "type_score": type_score,
        "count_score": count_score, 
        "order_score": order_score,
        "combined_score": combined_score
    }


def check_restoration_order_with_dedup(predicted_log: List[str], reward_model_order: List[str]) -> float:
    """
    Check restoration order with consecutive duplicate merging.
    连续相同的退化类型会被合并为一个进行判断。
    
    Args:
        predicted_log: The restoration order from model response
        reward_model_order: The degradation order from reward_model (addition order)
    
    Returns:
        Score between 0 and 1
    """
    if not predicted_log or not reward_model_order:
        return 0.0
    
    # 合并连续重复的退化类型
    merged_predicted_log = merge_consecutive_duplicates(predicted_log)
    
    # 正确的修复顺序是reward_model的逆序
    correct_restoration_order = list(reversed(reward_model_order))
    
    # 精确匹配获得满分
    if merged_predicted_log == correct_restoration_order:
        return 1.0
    
    # 部分匹配的分数计算
    score = 0.0
    min_len = min(len(merged_predicted_log), len(correct_restoration_order))
    
    # 检查有多少位置是正确的
    correct_positions = 0
    for i in range(min_len):
        if merged_predicted_log[i] == correct_restoration_order[i]:
            correct_positions += 1
    
    if min_len > 0:
        score = correct_positions / len(correct_restoration_order)
    
    # 如果包含所有正确的退化类型（即使顺序错误），给予最低50%分数
    try:
        merged_predicted_set = set(str(item) for item in merged_predicted_log if item is not None)
        expected_set = set(str(item) for item in correct_restoration_order if item is not None)
        
        if merged_predicted_set == expected_set:
            score = max(score, 0.5)  # 至少50%如果所有退化类型都存在
    except (TypeError, AttributeError) as e:
        print(f" [WARNING image_restoration] Set comparison failed: {e}")
    
    return score


def check_restoration_order_with_partial_credit(predicted_log: List[str], reward_model_order: List[str]) -> float:
    """
    Check restoration order with partial credit based on correct count and order.
    
    奖励规则:
    - 如果期望N种退化:
      - 预测1个且正确且位置对: 1/N 奖励
      - 预测2个且都正确且顺序对: 2/N 奖励
      - 预测N个且都正确且顺序对: 满分奖励
    - 任何数量错误、类型错误、顺序错误都不给分
    
    Args:
        predicted_log: The restoration order from model response
        reward_model_order: The degradation order from reward_model (addition order)
    
    Returns:
        Score between 0 and 1
    """
    if not predicted_log or not reward_model_order:
        return 0.0
    
    expected_count = len(reward_model_order)
    predicted_count = len(predicted_log)
    correct_restoration_order = list(reversed(reward_model_order))
    
    # 检查预测的退化类型是否都在期望类型中
    try:
        predicted_set = set(str(item) for item in predicted_log if item is not None)
        expected_set = set(str(item) for item in reward_model_order if item is not None)
        
        # 如果预测了不存在的类型，直接0分
        if not predicted_set.issubset(expected_set):
            return 0.0
            
    except (TypeError, AttributeError):
        return 0.0
    
    # 检查顺序是否正确（预测的部分必须与期望顺序的前N个匹配）
    if predicted_count > expected_count:
        return 0.0  # 预测数量超过期望，直接0分
    
    # 检查预测的顺序是否与期望顺序的前predicted_count个匹配
    for i in range(predicted_count):
        if i >= len(correct_restoration_order) or predicted_log[i] != correct_restoration_order[i]:
            return 0.0  # 顺序错误，直接0分
    
    # 如果到这里，说明预测的都是正确的且顺序正确
    # 根据预测数量给予相应比例的奖励，对3种退化的情况更严格
    if expected_count == 1:
        # 1种退化：只有全对才给分
        partial_score = 1.0 if predicted_count == expected_count else 0.0
    elif expected_count == 2:
        # 2种退化：1个对=0.5，2个对=1.0
        partial_score = predicted_count / expected_count
    elif expected_count == 3:
        # 3种退化：更严格的奖励
        if predicted_count == 1:
            partial_score = 1.0 / 3.0  # 1/3奖励
        elif predicted_count == 2:
            partial_score = 0.5        # 一半奖励（而不是2/3）
        elif predicted_count == 3:
            partial_score = 1.0        # 满分奖励
        else:
            partial_score = 0.0
    else:
        # 更多种退化：使用原始比例
        partial_score = predicted_count / expected_count
    
    return partial_score


def check_restoration_order(predicted_log: List[str], reward_model_order: List[str]) -> float:
    """
    Check if the restoration order is correct.
    According to user specification:
    - Model's restoration_log should match reward_model's reverse order (LIFO principle)
    - Or equivalently, match env_name's forward order
    
    Args:
        predicted_log: The restoration order from model response
        reward_model_order: The degradation order from reward_model (addition order)
    
    Returns:
        Score between 0 and 1
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
        # Ensure all elements are hashable (strings)
        predicted_set = set(str(item) for item in predicted_log if item is not None)
        expected_set = set(str(item) for item in correct_restoration_order if item is not None)
        
        if predicted_set == expected_set:
            score = max(score, 0.1)  # At least 50% if all degradations are present
    except (TypeError, AttributeError) as e:
        # If there's still a type error, just skip the bonus
        print(f" [WARNING image_restoration] Set comparison failed: {e}")
    
    return score


def compute_score(solution_str: str, ground_truth: Union[str, Dict], extra_info: Dict = None, strict_format: bool = True, accuracy_mode: str = "partial_credit") -> float:
    """
    Compute reward score for image restoration task.
    
    Args:
        solution_str: The model's response string
        ground_truth: Dictionary containing reward_model and env_name
        extra_info: Additional information (not used currently)
        strict_format: If True, use strict format checking (all-or-nothing). If False, use gradual format checking.
        accuracy_mode: Accuracy checking mode:
            - "order_only": Original order-only checking (no penalties, no deduplication)
            - "order_with_dedup": Order checking with consecutive duplicate merging
            - "partial_credit": Partial credit based on correct count (1/N, 2/N, etc.) (DEFAULT)
            - "strict": Strict checking (type+count+order all correct, but no negative penalties)
            - "strict_with_penalties": Strict checking with negative penalties for errors
    
    Returns:
        Float score between 0 and 1
    """
    # accuracy_mode = "order_with_dedup"

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
        # reward_model is in addition order
        degradation_addition_order = parse_reward_model_to_degradations(reward_model)
    elif env_name:
        # env_name is in reverse order of addition, so we need to reverse it to get addition order
        env_degradations = parse_env_name_to_degradations(env_name)
        degradation_addition_order = list(reversed(env_degradations))
    else:
        degradation_addition_order = []
    
    # Extract predicted restoration log
    predicted_log = extract_restoration_log_from_response(solution_str)
    
    # Compute format score (use strict mode by default)
    if strict_format:
        format_score = check_response_format_strict(solution_str)
    else:
        format_score = check_response_format(solution_str)
    
    # Compute accuracy score based on mode
    predicted_log_str = ', '.join(predicted_log) if predicted_log else ''
    degradation_addition_order_str = ', '.join(degradation_addition_order) if degradation_addition_order else ''
    correct_restoration_order_str = ', '.join(reversed(degradation_addition_order)) if degradation_addition_order else ''
    format_mode = "strict" if strict_format else "gradual"
    
    if accuracy_mode == "partial_credit":
        # 新的默认模式：基于预测数量的部分奖励
        accuracy_score = check_restoration_order_with_partial_credit(predicted_log, degradation_addition_order)
        
        print(f' [DEBUG image_restoration] format_mode={format_mode}, accuracy_mode={accuracy_mode}')
        print(f' [DEBUG image_restoration] predicted_log="{predicted_log_str}" (count={len(predicted_log)})')
        print(f' [DEBUG image_restoration] expected_order="{degradation_addition_order_str}" (count={len(degradation_addition_order)})')
        print(f' [DEBUG image_restoration] correct_restoration="{correct_restoration_order_str}"')
        print(f' [DEBUG image_restoration] format_score={format_score:.3f}, order_score={accuracy_score:.3f}')
        
    elif accuracy_mode == "order_with_dedup":
        # 原始顺序检查 + 连续去重
        merged_predicted_log = merge_consecutive_duplicates(predicted_log)
        accuracy_score = check_restoration_order(merged_predicted_log, degradation_addition_order)
        
        merged_predicted_log_str = ', '.join(merged_predicted_log) if merged_predicted_log else ''
        
        print(f' [DEBUG image_restoration] format_mode={format_mode}, accuracy_mode={accuracy_mode}')
        print(f' [DEBUG image_restoration] original_log="{predicted_log_str}" -> merged_log="{merged_predicted_log_str}"')
        print(f' [DEBUG image_restoration] expected_order="{degradation_addition_order_str}"')
        print(f' [DEBUG image_restoration] correct_restoration="{correct_restoration_order_str}"')
        print(f' [DEBUG image_restoration] format_score={format_score:.3f}, order_score={accuracy_score:.3f}')
        
    elif accuracy_mode == "strict_with_penalties":
        # 带惩罚的严格准确性检查
        merged_predicted_log = merge_consecutive_duplicates(predicted_log)
        accuracy_result = check_restoration_accuracy_with_penalties(merged_predicted_log, degradation_addition_order)
        accuracy_score = accuracy_result["combined_score"]
        
        print(f' [DEBUG image_restoration] format_mode={format_mode}, accuracy_mode={accuracy_mode}')
        print(f' [DEBUG image_restoration] predicted_log="{predicted_log_str}" (count={accuracy_result["predicted_count"]})')
        print(f' [DEBUG image_restoration] expected_order="{degradation_addition_order_str}" (count={accuracy_result["expected_count"]})')
        print(f' [DEBUG image_restoration] correct_restoration="{correct_restoration_order_str}"')
        print(f' [DEBUG image_restoration] type_score={accuracy_result["type_score"]:.3f}, count_penalty={accuracy_result["count_penalty"]:.3f}')
        print(f' [DEBUG image_restoration] wrong_type_penalty={accuracy_result["wrong_type_penalty"]:.3f}, order_penalty={accuracy_result["order_penalty"]:.3f}')
        print(f' [DEBUG image_restoration] format_score={format_score:.3f}, accuracy_score={accuracy_score:.3f}')
        
    elif accuracy_mode == "strict":
        # 严格检查但无负惩罚（0分最低）
        accuracy_result = check_restoration_accuracy(predicted_log, degradation_addition_order)
        accuracy_score = accuracy_result["combined_score"]
        
        print(f' [DEBUG image_restoration] format_mode={format_mode}, accuracy_mode={accuracy_mode}')
        print(f' [DEBUG image_restoration] predicted_log="{predicted_log_str}" (count={len(predicted_log)})')
        print(f' [DEBUG image_restoration] expected_order="{degradation_addition_order_str}" (count={len(degradation_addition_order)})')
        print(f' [DEBUG image_restoration] correct_restoration="{correct_restoration_order_str}"')
        print(f' [DEBUG image_restoration] type_score={accuracy_result["type_score"]:.3f}, count_score={accuracy_result["count_score"]:.3f}, order_score={accuracy_result["order_score"]:.3f}')
        print(f' [DEBUG image_restoration] format_score={format_score:.3f}, accuracy_score={accuracy_score:.3f}')
        
    elif accuracy_mode == "order_only":
        # 原来的顺序检查（向后兼容）
        accuracy_score = check_restoration_order(predicted_log, degradation_addition_order)
        
        print(f' [DEBUG image_restoration] format_mode={format_mode}, accuracy_mode={accuracy_mode}')
        print(f' [DEBUG image_restoration] predicted_log="{predicted_log_str}", '
              f'expected_order="{degradation_addition_order_str}", '
              f'correct_restoration="{correct_restoration_order_str}"')
        print(f' [DEBUG image_restoration] format_score={format_score:.3f}, order_score={accuracy_score:.3f}')
        
    else:
        raise ValueError(f"Unknown accuracy_mode: {accuracy_mode}. Must be one of: 'order_only', 'order_with_dedup', 'partial_credit', 'strict', 'strict_with_penalties'")
    
    # Combined score with weights (following vl_agent.py pattern)
    format_weight = 0.2
    accuracy_weight = 0.8
    format_score = -1 if format_score == 0 else format_score
    total_score = format_weight * format_score + accuracy_weight * accuracy_score
    
    print(f' [DEBUG image_restoration] total_score={total_score:.3f}')
    
    return total_score
