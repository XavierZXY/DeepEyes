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
Reward computation for visual_toolbox_v2 (defect detection task)
"""

import os
import re
import json
import random
import logging
from typing import Dict, Any
import requests
from openai import OpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client for LLM judge
openai_api_key = "EMPTY"
openai_api_base = os.environ.get("LLM_AS_A_JUDGE_BASE", "http://10.1.100.71:18901/v1")

client = None
model_name = ""

if openai_api_base:
    try:
        client = OpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base,
        )
        response = requests.get(f"{openai_api_base}/models")
        response.raise_for_status()
        models = response.json()
        if models.get("data"):
            model_name = models["data"][0]["id"]
        else:
            logger.warning("No models found at the specified API base for reward scoring.")
    except (requests.exceptions.RequestException, KeyError, IndexError) as e:
        logger.warning(f"Failed to get model from {openai_api_base}: {e}. Reward scoring will be disabled.")


def extract_answer(text):
    """Extract content from <answer></answer> tags."""
    pattern = r"<answer>(.*?)</answer>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def extract_location(text):
    """Extract content from <location></location> tags."""
    pattern = r"<location>(.*?)</location>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def extract_type(text):
    """Extract content from <type></type> tags."""
    pattern = r"<type>(.*?)</type>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _validate_tool_call_json(solution_str):
    """
    Validate that tool_call tags contain valid JSON.
    
    Returns:
        bool: True if all tool_call contents are valid JSON (or no tool_calls), False otherwise
    """
    tool_call_pattern = r"<tool_call>(.*?)</tool_call>"
    tool_calls = re.findall(tool_call_pattern, solution_str, re.DOTALL)
    
    if not tool_calls:
        return True  # No tool calls is valid
    
    for tool_call_content in tool_calls:
        try:
            json.loads(tool_call_content.strip())
        except (json.JSONDecodeError, ValueError):
            return False
    
    return True


def _extract_ground_truth_answer(ground_truth, extra_info):
    """Return the textual ground truth answer if available."""
    answer = None
    
    if isinstance(ground_truth, dict):
        answer = ground_truth.get("answer")
    elif isinstance(ground_truth, str):
        answer = ground_truth
    elif ground_truth is not None:
        answer = str(ground_truth)
    
    if answer is None and extra_info is not None:
        answer_info = extra_info.get("answer")
        if isinstance(answer_info, dict):
            answer = answer_info.get("answer")
        elif isinstance(answer_info, str):
            answer = answer_info
    
    return (answer or "").strip()


def compute_visual_toolbox_v2_score(data_source: str, solution_str: str, ground_truth: str, extra_info=None) -> float:
    """
    Compute reward score for visual_toolbox_v2 defect detection task.
    
    Simplified reward: format + accuracy only
    - format: -1 (has errors) or 1 (no errors)
    - accuracy: 1 (match yes/no) or 0 (mismatch)
    
    Args:
        data_source: Source of the data (not used currently)
        solution_str: Model's solution string
        ground_truth: Ground truth answer (can be dict or string)
        extra_info: Additional information including question, bboxes, etc.
    
    Returns:
        float: Final reward score
    """
    format_errors_count = 0
    
    # Detect if this is a tool request turn (Format 1) or final answer turn (Format 2/3)
    has_answer_tag = "<answer>" in solution_str
    has_tool_call = "<tool_call>" in solution_str
    
    # Count tool calls
    count_tool_call_1 = solution_str.count("<tool_call>")
    count_tool_call_2 = solution_str.count("</tool_call>")
    
    # 1. Format checking
    count_think_1 = solution_str.count("<think>")
    count_think_2 = solution_str.count("</think>")
    if count_think_1 != count_think_2 or count_think_1 == 0:
        format_errors_count += 1
    
    # If this is a tool request turn (Format 1)
    if has_tool_call and not has_answer_tag:
        # Format 1: Should ONLY have <think> and <tool_call>
        if count_tool_call_1 != count_tool_call_2 or count_tool_call_1 == 0:
            format_errors_count += 1
        
        # Validate tool call JSON format
        if not _validate_tool_call_json(solution_str):
            format_errors_count += 1
        
        # Should NOT have answer, location, type tags in Format 1
        if "<answer>" in solution_str or "<location>" in solution_str or "<type>" in solution_str:
            format_errors_count += 1
        
        # For Format 1, we don't compute answer/bbox rewards, only format
        format_reward = 1.0 if format_errors_count == 0 else -1.0
        return format_reward
    
    # If this is a final answer turn (Format 2 or 3)
    if has_answer_tag:
        # Extract the final answer section (after last </think>)
        predict_no_think = solution_str.split("</think>")[-1].strip() if "</think>" in solution_str else solution_str
        
        # Check that final answer section does NOT contain <tool_call>
        if "<tool_call>" in predict_no_think:
            format_errors_count += 1
        
        # Check required tags in final answer section
        count_answer_1 = predict_no_think.count("<answer>")
        count_answer_2 = predict_no_think.count("</answer>")
        if count_answer_1 != count_answer_2 or count_answer_1 == 0:
            format_errors_count += 1
        
        count_location_1 = predict_no_think.count("<location>")
        count_location_2 = predict_no_think.count("</location>")
        if count_location_1 != count_location_2 or count_location_1 == 0:
            format_errors_count += 1
        
        count_type_1 = predict_no_think.count("<type>")
        count_type_2 = predict_no_think.count("</type>")
        if count_type_1 != count_type_2 or count_type_1 == 0:
            format_errors_count += 1
        
        # Validate tool call JSON format in earlier turns (if present)
        if count_tool_call_1 > 0 and not _validate_tool_call_json(solution_str):
            format_errors_count += 1
        
        # Extract answer
        answer_text = extract_answer(predict_no_think)
        
        # Check if answer exists
        if not answer_text:
            format_errors_count += 1
            answer_text = ""
    else:
        # No answer tag and no tool call - invalid format
        format_errors_count += 3
        answer_text = ""
    
    # Format reward: -1 or 1
    format_reward = 1.0 if format_errors_count == 0 else -1.0
    
    # 2. Answer correctness using direct yes/no matching
    # Extract ground truth answer
    ground_truth_answer = _extract_ground_truth_answer(ground_truth, extra_info)
    
    # Simple yes/no matching (case insensitive)
    acc_reward = 0.0
    if answer_text:
        answer_lower = answer_text.lower().strip()
        gt_lower = ground_truth_answer.lower().strip()
        
        # Check if both contain "yes" or both contain "no"
        answer_has_yes = "yes" in answer_lower
        answer_has_no = "no" in answer_lower
        gt_has_yes = "yes" in gt_lower
        gt_has_no = "no" in gt_lower
        
        # Match if both say yes OR both say no
        if (answer_has_yes and gt_has_yes and not answer_has_no) or \
           (answer_has_no and gt_has_no and not answer_has_yes):
            acc_reward = 1.0
        else:
            acc_reward = 0.0
    
    # Final score: format + accuracy
    final_score = format_reward + acc_reward
    
    # Log for debugging
    logger.debug(
        f"Score breakdown: format={format_reward:.2f}, acc={acc_reward:.2f}, "
        f"final={final_score:.2f}, format_errors={format_errors_count}"
    )
    print(
        f"[visual_toolbox_v2] Score breakdown: format={format_reward:.2f}, acc={acc_reward:.2f}, "
        f"final={final_score:.2f}, format_errors={format_errors_count}, "
        f"answer_text='{answer_text}', gt='{ground_truth_answer}'"
    )
    
    # Return as dict for wandb component tracking
    return {
        "score": final_score,
        "format_reward": format_reward,
        "acc_reward": acc_reward,
        "format_errors_count": format_errors_count,
    }


if __name__ == "__main__":
    # Test case 1: Well-formatted response with correct answer
    test_case_1 = """<think>
I need to examine the image carefully for any defects. Let me zoom in on a specific region.
</think>
<tool_call>
[{"name": "image_zoom_in_tool", "arguments": {"bbox_2d": [100, 150, 200, 250], "label": "surface area"}}]
</tool_call>
<tool_response>
Zoomed in on the image to the region [100, 150, 200, 250] with label surface area.
</tool_response>
<think>
After zooming in, I can see a crack in the surface.
</think>
<location>[{"bbox2d": [105, 155, 195, 245]}]</location>
<type>crack</type>
<answer>yes</answer>"""
    
    ground_truth_1 = {"answer": "yes", "bboxes": [{"bbox2d": [100, 150, 200, 250]}]}
    extra_info_1 = {
        "question": "Does this image contain any defects?",
        "bboxes": [{"bbox2d": [100, 150, 200, 250]}],
    }
    
    print("=== Test Case 1: Well-formatted with correct answer (yes) ===")
    score = compute_visual_toolbox_v2_score("defect_detection", test_case_1, ground_truth_1, extra_info_1)
    print(f"Score: {score}")
    print(f"Expected: 2.0 (format=1.0 + acc=1.0)\n")
    
    # Test case 2: Well-formatted with correct answer (no)
    test_case_2 = """<think>
After examining the image, I can see the surface is clean and smooth with no visible defects.
</think>
<location>[]</location>
<type>good</type>
<answer>no</answer>"""
    
    ground_truth_2 = {"answer": "no", "bboxes": []}
    extra_info_2 = {
        "question": "Does this image contain any defects?",
        "bboxes": [],
    }
    
    print("=== Test Case 2: Well-formatted with correct answer (no) ===")
    score2 = compute_visual_toolbox_v2_score("defect_detection", test_case_2, ground_truth_2, extra_info_2)
    print(f"Score: {score2}")
    print(f"Expected: 2.0 (format=1.0 + acc=1.0)\n")
    
    # Test case 3: Format error (mismatched think tags)
    test_case_3 = """<think>
Let me check for defects.
<location>[]</location>
<type>good</type>
<answer>no</answer>"""
    
    print("=== Test Case 3: Format error (mismatched think tags) ===")
    score3 = compute_visual_toolbox_v2_score("defect_detection", test_case_3, ground_truth_2, extra_info_2)
    print(f"Score: {score3}")
    print(f"Expected: 0.0 (format=-1.0 + acc=1.0)\n")
    
    # Test case 4: Wrong answer
    test_case_4 = """<think>
I see some anomalies.
</think>
<location>[{"bbox2d": [100, 100, 200, 200]}]</location>
<type>crack</type>
<answer>yes</answer>"""
    
    print("=== Test Case 4: Correct format but wrong answer ===")
    score4 = compute_visual_toolbox_v2_score("defect_detection", test_case_4, ground_truth_2, extra_info_2)
    print(f"Score: {score4}")
    print(f"Expected: 1.0 (format=1.0 + acc=0.0)\n")
    
    # Test case 5: Tool request turn (should only check format)
    test_case_5 = """<think>
I need to zoom in to check for defects.
</think>
<tool_call>
[{"name": "image_zoom_in_tool", "arguments": {"bbox_2d": [100, 150, 200, 250]}}]
</tool_call>"""
    
    print("=== Test Case 5: Tool request turn (Format 1) ===")
    score5 = compute_visual_toolbox_v2_score("defect_detection", test_case_5, ground_truth_2, extra_info_2)
    print(f"Score: {score5}")
    print(f"Expected: 1.0 (format=1.0, no acc reward for tool request turn)\n")

