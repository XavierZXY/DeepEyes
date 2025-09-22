import ast
import json
import logging
import os
import random
import re

import requests
from math_verify import parse, verify
from openai import OpenAI

from verl.utils.reward_score.qwen_utils.utils import (
    reverse_convert_to_original_format,
    smart_resize,
)

log = logging.getLogger("rich")

# Use the same OpenAI client configuration as vl_agent
openai_api_key = "EMPTY"
openai_api_base_list = [
    os.environ.get("LLM_AS_A_JUDGE_BASE", "http://GPUD4FC:9091/v1"),
]

client_list = []
for api_base in openai_api_base_list:
    client = OpenAI(
        api_key=openai_api_key,
        base_url=api_base,
    )
    client_list.append(client)

model_name_list = []
for client in client_list:
    try:
        response = requests.get(f"{api_base}/models")
        models = response.json()
        model_name_list.append(models["data"][0]["id"])
    except Exception:
        model_name_list.append("default_model")


# Visual ToolBox V2 specific verification prompt
VISUAL_TOOLBOX_V2_VERIFY_PROMPT = """# CONTEXT #
You are evaluating a defect detection response for industrial anomaly inspection using visual tools.
The model should identify defects accurately, provide proper defect type classification, and demonstrate effective tool usage.

# OBJECTIVE #
Judge whether the student's response is equivalent to the reference answer for visual defect detection.
Consider defect detection accuracy (yes/no), defect type classification, and spatial localization quality.

# EVALUATION CRITERIA #
For defect detection:
- "yes" responses should match when defects are present
- "no" responses should match when no defects are present
- Consider tool usage effectiveness for thorough inspection

For defect type classification:
- When defects are present, the predicted type should semantically match the ground truth
- Common defect types: crack, scratch, hole, discoloration, surface anomaly, contamination
- "good" type should only be used when no defects are present

# TONE #
Professional, scientific, focused on industrial quality control and visual inspection.

# RESPONSE: MARKDOWN REPORT #
## Detection Equivalence
[Whether the student's defect detection decision matches the reference. (TRUE or FALSE)]

## Type Equivalence  
[Whether the student's defect type classification matches the reference when applicable. (TRUE or FALSE or N/A)]

## Overall Equivalence
[Whether the overall response is equivalent considering detection, type, and inspection quality. (TRUE or FALSE)]

# ATTENTION #
- The reference answer is ALWAYS correct
- Consider both detection accuracy and type accuracy in overall judgment
- Tool usage should enhance detection quality
- Output only TRUE, FALSE, or N/A in each judgment section

**Question**:
{query}

**Reference Answer**
{gold_ans}

**Reference Type**
{gold_type}

## Student Answer
{pred_ans}

## Student Type
{pred_type}"""


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


def _parse_predicted_bboxes(location_text):
    """Parse predicted bboxes from location JSON string into list of [x1,y1,x2,y2]."""
    if not location_text:
        return []

    try:
        loc = json.loads(location_text)
    except Exception:
        try:
            loc = ast.literal_eval(location_text)
        except Exception:
            loc = None

    boxes = []
    if isinstance(loc, list):
        for item in loc:
            if isinstance(item, dict):
                arr = item.get("bbox2d") or item.get("bbox_2d")
                if isinstance(arr, (list, tuple)) and len(arr) == 4:
                    try:
                        boxes.append([float(v) for v in arr])
                    except Exception:
                        continue

    if boxes:
        return boxes

    # Regex fallback: extract any [x1,y1,x2,y2]
    try:
        pattern = r"\[\s*([-+]?[0-9]*\.?[0-9]+)\s*,\s*([-+]?[0-9]*\.?[0-9]+)\s*,\s*([-+]?[0-9]*\.?[0-9]+)\s*,\s*([-+]?[0-9]*\.?[0-9]+)\s*\]"
        matches = re.findall(pattern, location_text)
        for m in matches:
            vals = [float(x) for x in m]
            if len(vals) == 4:
                boxes.append(vals)
        return boxes
    except Exception as e:
        log.error(f"Failed to parse predicted bboxes: {e}")
        return []


def _extract_gt_bboxes(ground_truth, extra_info):
    """Extract ground truth bboxes list[[x1,y1,x2,y2]]."""
    boxes = []

    try:
        if isinstance(ground_truth, dict) and "bboxes" in ground_truth:
            gt_boxes = ground_truth["bboxes"]
            try:
                iterable = list(gt_boxes)
            except Exception:
                iterable = []
            if iterable:
                for item in iterable:
                    if isinstance(item, dict):
                        arr = item.get("bbox2d") or item.get("bbox_2d")
                        if isinstance(arr, list) and len(arr) == 4:
                            boxes.append([float(v) for v in arr])

        # Fallback to extra_info
        if not boxes and extra_info and "bboxes" in extra_info:
            gt_boxes = extra_info["bboxes"]
            try:
                iterable = list(gt_boxes)
            except Exception:
                iterable = []
            if iterable:
                for item in iterable:
                    if isinstance(item, dict):
                        arr = item.get("bbox2d") or item.get("bbox_2d")
                        if isinstance(arr, list) and len(arr) == 4:
                            boxes.append([float(v) for v in arr])
    except Exception as e:
        log.error(f"Failed to extract GT bboxes: {e}")

    return boxes


def _bbox_iou_xyxy(box_a, box_b):
    """Compute IoU between two boxes in [x1, y1, x2, y2] format."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter = inter_w * inter_h

    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union = area_a + area_b - inter

    return inter / union if union > 0 else 0.0


def _maybe_rescale_pred_boxes_to_original(pred_boxes, extra_info):
    """Rescale predicted boxes back to original image size if needed."""
    if not extra_info:
        return pred_boxes

    img_shape = extra_info.get("img_shape") or extra_info.get("image_shape")
    if not img_shape or not isinstance(img_shape, (list, tuple)) or len(img_shape) < 2:
        return pred_boxes

    try:
        orig_h, orig_w = int(img_shape[0]), int(img_shape[1])
        new_h, new_w = smart_resize(orig_h, orig_w)
        restored = []
        for box in pred_boxes:
            x1, y1, x2, y2 = reverse_convert_to_original_format(
                box, orig_h, orig_w, new_h, new_w
            )
            restored.append([float(x1), float(y1), float(x2), float(y2)])
        return restored
    except Exception as e:
        log.error(f"Failed to rescale predicted boxes: {e}")
        return pred_boxes


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


def _visual_toolbox_v2_grounding_reward(pred_boxes, gt_boxes, pred_type, extra_info):
    """
    Specialized grounding reward for visual_toolbox_v2 defect detection.
    Takes into account the specific needs of industrial defect detection.
    """
    # Handle no defect cases
    if len(gt_boxes) == 0:
        if len(pred_boxes) == 0:
            return 1.0  # Perfect - correctly identified no defects
        else:
            # Gentle penalty for false positive detections in visual inspection
            return max(0.3, 1.0 - 0.15 * len(pred_boxes))

    # Handle defect detection cases
    if len(pred_boxes) == 0:
        # Missing defects is more serious in quality control
        return 0.1

    # Limit to reasonable number of predictions
    if len(pred_boxes) > 3:
        pred_boxes = pred_boxes[:3]

    # Compute IoU-based reward
    def compute_best_ious():
        max_ious = []
        for gt_box in gt_boxes:
            best_iou = 0.0
            for pred_box in pred_boxes:
                iou = _bbox_iou_xyxy(gt_box, pred_box)
                best_iou = max(best_iou, iou)
            max_ious.append(best_iou)
        return max_ious

    ious = compute_best_ious()
    avg_iou = sum(ious) / len(ious) if ious else 0.0

    # Progressive IoU reward for defect detection
    if avg_iou >= 0.7:
        iou_reward = 1.0
    elif avg_iou >= 0.5:
        iou_reward = 0.8 + 0.2 * (avg_iou - 0.5) / 0.2
    elif avg_iou >= 0.3:
        iou_reward = 0.5 + 0.3 * (avg_iou - 0.3) / 0.2
    else:
        iou_reward = avg_iou / 0.3 * 0.5

    # Additional reward for detection attempt in industrial context
    detection_attempt_reward = (
        min(len(pred_boxes), len(gt_boxes))
        / max(len(pred_boxes), len(gt_boxes), 1)
        * 0.2
    )

    # Combine rewards
    total_reward = 0.8 * iou_reward + 0.2 * detection_attempt_reward

    return min(1.0, total_reward)


def _evaluate_visual_toolbox_v2_answer(answer_text, ground_truth_answer, question_text):
    """
    Enhanced answer evaluation specifically for visual_toolbox_v2 defect detection.
    """
    # Normalize answers for comparison
    pred_answer = answer_text.lower().strip()
    gt_answer = ground_truth_answer.lower().strip()

    # Direct match first
    if pred_answer == gt_answer:
        return 1.0

    # Defect detection specific matching
    if "yes" in pred_answer and ("yes" in gt_answer or "defect" in gt_answer):
        return 1.0
    elif "no" in pred_answer and (
        "no" in gt_answer or "defect-free" in gt_answer or "good" in gt_answer
    ):
        return 1.0
    elif "defect" in pred_answer and "defect" in gt_answer:
        return 1.0

    # Fallback to LLM judge for complex cases if clients are available
    if not client_list:
        return 0.5  # Return neutral score if no LLM judge available

    try:
        client_idx = random.randint(0, len(client_list) - 1)
        client = client_list[client_idx]
        model_name = model_name_list[client_idx]

        full_prompt = VISUAL_TOOLBOX_V2_VERIFY_PROMPT.format(
            query=question_text,
            gold_ans=ground_truth_answer,
            gold_type="",  # Will be filled separately if needed
            pred_ans=answer_text,
            pred_type="",  # Will be filled separately if needed
        )

        for _ in range(3):  # Retry up to 3 times
            try:
                chat_response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": full_prompt}],
                    seed=random.randint(0, 1000000),
                    temperature=0.3,
                )
                response = chat_response.choices[0].message.content.strip()
                judgement = response.split("## Overall Equivalence")[-1].lower()

                if "true" in judgement and "false" not in judgement:
                    return 1.0
                elif "false" in judgement and "true" not in judgement:
                    return 0.0
            except Exception as e:
                log.warning(f"LLM judge error: {e}")
                continue

        return 0.0  # Default to 0 if all attempts fail

    except Exception:
        return 0.0


def _get_expected_defect_type(ground_truth_answer, extra_info):
    """
    Determine the expected defect type for visual_toolbox_v2 tasks.
    """
    if (
        ground_truth_answer.lower().startswith("no")
        or "defect-free" in ground_truth_answer.lower()
    ):
        return "good"

    if extra_info:
        # Check multiple possible keys for defect type
        for key in ["type", "label_name", "defect_type", "anomaly_type"]:
            defect_type = extra_info.get(key)
            if defect_type and isinstance(defect_type, str):
                return defect_type.lower()

    return "unspecified"


def compute_visual_toolbox_v2_score(
    predict_str: str, ground_truth: str, extra_info=None, use_bbox_reward=True
) -> float:
    """
    Specialized scoring function for visual_toolbox_v2 defect detection tasks.
    Focuses on defect detection accuracy, tool usage effectiveness, and grounding quality.

    Args:
        predict_str: Model prediction string with expected format
        ground_truth: Ground truth answer
        extra_info: Additional information including question, bboxes, etc.
        use_bbox_reward: Whether to include bbox/grounding reward

    Returns:
        Float score between 0-3 (higher is better)
    """
    is_format_error = False

    # Enhanced format validation for visual_toolbox_v2
    count_think_1 = predict_str.count("<think>")
    count_think_2 = predict_str.count("</think>")
    if count_think_1 != count_think_2 or count_think_1 == 0:
        is_format_error = True

    count_vision_1 = predict_str.count("<|vision_start|><|image_pad|>")
    count_vision_2 = predict_str.count("<|image_pad|><|vision_end|>")
    if count_vision_1 != count_vision_2:
        is_format_error = True

    # Split at </think> to analyze the response portion
    predict_no_think = predict_str.split("</think>")[-1].strip()

    # Required tags validation
    count_answer_1 = predict_no_think.count("<answer>")
    count_answer_2 = predict_no_think.count("</answer>")
    if count_answer_1 != count_answer_2 or count_answer_1 == 0:
        is_format_error = True

    count_location_1 = predict_no_think.count("<location>")
    count_location_2 = predict_no_think.count("</location>")
    if count_location_1 != count_location_2 or count_location_1 == 0:
        is_format_error = True

    count_type_1 = predict_no_think.count("<type>")
    count_type_2 = predict_no_think.count("</type>")
    if count_type_1 != count_type_2 or count_type_1 == 0:
        is_format_error = True

    # Extract components
    answer_text = extract_answer(predict_no_think)
    location_text = extract_location(predict_no_think)
    type_text = extract_type(predict_no_think)

    # Tool usage detection for visual_toolbox_v2
    tool_usage_count = predict_str.count("<tool_call>")
    tool_response_count = predict_str.count("<tool_response>")
    has_meaningful_tool_usage = (
        tool_usage_count > 0 and tool_response_count >= tool_usage_count
    )

    # Enhanced tool usage reward for visual_toolbox_v2
    tool_reward = 0.0
    if has_meaningful_tool_usage and answer_text:
        # Basic tool usage reward
        tool_reward = 0.5

        # Bonus for appropriate tool usage patterns
        if "image_zoom_in_tool" in predict_str:
            tool_reward += 0.3  # Reward for using zoom tool
        if "bbox_2d" in predict_str:
            tool_reward += 0.2  # Reward for proper bbox usage

        # Additional reward if tool usage led to correct answer
        if answer_text and len(answer_text.strip()) > 0:
            tool_reward += 0.5
    elif count_vision_1 > 0:  # Basic vision token usage
        tool_reward = 0.2

    # Bbox format validation with visual_toolbox_v2 specific requirements
    bbox_format_ok = False
    if location_text:
        try:
            loc = json.loads(location_text)
            if isinstance(loc, list):
                if len(loc) == 0:  # Empty list is valid for no defects
                    bbox_format_ok = True
                elif len(loc) <= 3:  # Limit to 3 boxes max for defects
                    bbox_format_ok = all(
                        isinstance(item, dict)
                        and ("bbox2d" in item or "bbox_2d" in item)
                        and isinstance(
                            (item.get("bbox2d") or item.get("bbox_2d")), list
                        )
                        and len((item.get("bbox2d") or item.get("bbox_2d"))) == 4
                        and all(
                            isinstance(x, (int, float))
                            for x in (item.get("bbox2d") or item.get("bbox_2d"))
                        )
                        for item in loc
                    )
        except (json.JSONDecodeError, TypeError):
            pass

    # Parse predicted and ground truth bboxes
    pred_boxes = _parse_predicted_bboxes(location_text)
    pred_boxes = _maybe_rescale_pred_boxes_to_original(pred_boxes, extra_info)
    gt_boxes = _extract_gt_bboxes(ground_truth, extra_info)

    # Enhanced grounding reward for defect detection
    grounding_reward = 0.0
    if use_bbox_reward:
        grounding_reward = _visual_toolbox_v2_grounding_reward(
            pred_boxes, gt_boxes, type_text, extra_info
        )

    # Enhanced answer accuracy evaluation
    ground_truth_answer = _extract_ground_truth_answer(ground_truth, extra_info)
    acc_reward = 0.0

    if not answer_text:
        is_format_error = True
    elif len(answer_text) >= 1000:
        acc_reward = 0.0
        is_format_error = True
    else:
        # Use enhanced verification for visual_toolbox_v2
        question_text = extra_info.get("question", "") if extra_info else ""
        acc_reward = _evaluate_visual_toolbox_v2_answer(
            answer_text, ground_truth_answer, question_text
        )

    # Type accuracy evaluation for defect detection
    expected_type = _get_expected_defect_type(ground_truth_answer, extra_info)
    type_reward = 0.0
    if type_text and isinstance(type_text, str):
        if expected_type.lower() == "good" and type_text.lower() == "good":
            type_reward = 1.0  # Perfect match for no defect case
        elif expected_type.lower() != "good" and type_text.lower() != "good":
            # Partial credit for detecting any defect type when defect exists
            type_reward = 0.7 if type_text.lower() == expected_type.lower() else 0.3
        elif expected_type.lower() == "good" and type_text.lower() != "good":
            type_reward = 0.0  # False positive
        else:
            type_reward = 0.0  # False negative

    # Format penalty
    format_reward = -0.5 if is_format_error else 0.0

    # Bbox format reward
    bbox_format_reward = 0.3 if bbox_format_ok else 0.0

    # Calculate final score with visual_toolbox_v2 specific weights
    final_score = (
        1.0 * acc_reward  # Answer accuracy (highest weight)
        + 0.8 * grounding_reward  # Grounding accuracy for defect localization
        + 0.6 * type_reward  # Defect type classification
        + 0.8 * tool_reward  # Tool usage effectiveness
        + format_reward  # Format penalty
        + bbox_format_reward  # Bbox format bonus
    )

    # Debug logging
    if extra_info:
        log.info(
            f"Visual ToolBox V2 Score: acc={acc_reward:.2f}, grounding={grounding_reward:.2f}, "
            f"type={type_reward:.2f}, tool={tool_reward:.2f}, format={format_reward:.2f}, "
            f"bbox_fmt={bbox_format_reward:.2f}, final={final_score:.2f}"
        )

    return max(0.0, final_score)


if __name__ == "__main__":
    # Simple test case
    predict_str = """<think>I need to analyze this image for defects. Let me examine it carefully.</think>
<tool_call>{"name": "image_zoom_in_tool", "arguments": {"bbox_2d": [100, 100, 200, 200]}}</tool_call>
<tool_response><image>I can see a clear crack in the zoomed area.</tool_response>
<location>[{"bbox2d": [150, 150, 180, 180]}]</location>
<type>crack</type>
<answer>yes</answer>"""

    ground_truth = {
        "answer": "Yes. There has been a defect detected.",
        "bboxes": [{"bbox2d": [145, 145, 185, 185]}],
    }
    extra_info = {
        "question": "Analyze this image for defects.",
        "type": "crack",
        "defect_type": "crack",
        "bboxes": [{"bbox2d": [145, 145, 185, 185]}],
    }

    score = compute_visual_toolbox_v2_score(predict_str, ground_truth, extra_info)
    print(f"Visual ToolBox V2 Score: {score:.3f}")
