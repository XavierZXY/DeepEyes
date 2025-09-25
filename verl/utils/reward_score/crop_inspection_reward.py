import ast
import json
import logging
import os
import random
import re
from math import sqrt
from typing import Any, Dict, List, Optional, Tuple

import requests

# from math_verify import parse, verify
from openai import OpenAI

# Configure rich logging
from rich.logging import RichHandler

from verl.utils.reward_score.qwen_utils.utils import (
    reverse_convert_to_original_format,
    smart_resize,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

log = logging.getLogger("rich")


def _maybe_rescale_pred_boxes_to_original(pred_boxes, extra_info):
    """If original image shape is available in extra_info (img_shape=(H,W)),
    assume model used smart_resize(H,W) and rescale predicted boxes back to original.
    """
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


# OpenAI client setup (reuse from vl_agent.py)
openai_api_key = "EMPTY"
openai_api_base_list = [
    os.environ.get("LLM_AS_A_JUDGE_BASE", "http://gpud4fc:9091/v1"),
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
    except Exception as e:
        log.error(f"Failed to get model name: {e}")
        model_name_list.append("default_model")


CROP_INSPECTION_VERIFY_PROMPT = """# CONTEXT #
You are evaluating a defect detection response that uses crop inspection tools for detailed analysis.
The model can perform multi-round cropping to inspect specific regions more closely before making final decisions.

# OBJECTIVE #
Evaluate the student's response on multiple dimensions:
1. Defect detection accuracy (yes/no decision)
2. Tool usage effectiveness (appropriate cropping decisions)
3. Defect localization accuracy (bbox precision)
4. Defect type classification accuracy
5. Overall inspection quality

# EVALUATION CRITERIA #
For defect detection:
- "yes" responses should match when defects are present
- "no" responses should match when no defects are present

For tool usage:
- Appropriate use of cropping for detailed inspection
- Reasonable crop regions that focus on potential defects
- Not excessive cropping (diminishing returns)

For localization:
- Bounding boxes should accurately locate defects
- Multiple crops should lead to better localization

For type classification:
- Predicted type should match ground truth when defects present
- "good" type should only be used when no defects present

# TONE #
Professional, scientific, focused on industrial quality control and tool-assisted inspection.

# RESPONSE: MARKDOWN REPORT #
## Detection Accuracy
[Whether the student's defect detection decision (yes/no) matches the reference. (TRUE or FALSE)]

## Tool Usage Quality
[Whether the student used cropping tools appropriately for inspection. (EXCELLENT/GOOD/FAIR/POOR)]

## Localization Accuracy
[Whether the student's defect localization is accurate. (TRUE or FALSE or N/A)]

## Type Accuracy  
[Whether the student's defect type classification matches the reference. (TRUE or FALSE or N/A)]

## Overall Equivalence
[Whether the overall response demonstrates effective crop-assisted inspection. (TRUE or FALSE)]

# ATTENTION #
- The reference answer is ALWAYS correct
- Consider both final accuracy and inspection methodology
- Multi-round cropping should improve precision
- Output only the specified values in each judgment section

**Question**:
{query}

**Reference Answer**
{gold_ans}

**Reference Type**
{gold_type}

**Reference Bboxes**
{gold_bboxes}

## Student Answer
{pred_ans}

## Student Type
{pred_type}

## Student Bboxes
{pred_bboxes}

## Crop History
{crop_history}"""


def extract_answer(text: str) -> Optional[str]:
    """Extract content from <answer></answer> tags"""
    pattern = r"<answer>(.*?)</answer>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


def extract_location(text: str) -> Optional[str]:
    """Extract content from <location></location> tags"""
    pattern = r"<location>(.*?)</location>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


def extract_type(text: str) -> Optional[str]:
    """Extract content from <type></type> tags"""
    pattern = r"<type>(.*?)</type>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else None


def parse_predicted_bboxes(location_text: str) -> List[List[float]]:
    """Parse predicted bboxes from location JSON string into list of [x1,y1,x2,y2]"""
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

    # Regex fallback
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


def extract_gt_bboxes(
    ground_truth: Any, extra_info: Optional[Dict]
) -> List[List[float]]:
    """Extract ground truth bboxes"""
    boxes = []

    try:
        if isinstance(ground_truth, dict) and "bboxes" in ground_truth:
            gt_boxes = ground_truth["bboxes"]
            for item in gt_boxes:
                if isinstance(item, dict):
                    arr = item.get("bbox2d") or item.get("bbox_2d")
                    if isinstance(arr, list) and len(arr) == 4:
                        boxes.append([float(v) for v in arr])

        if not boxes and extra_info and "bboxes" in extra_info:
            gt_boxes = extra_info["bboxes"]
            for item in gt_boxes:
                if isinstance(item, dict):
                    arr = item.get("bbox2d") or item.get("bbox_2d")
                    if isinstance(arr, list) and len(arr) == 4:
                        boxes.append([float(v) for v in arr])
    except Exception as e:
        log.error(f"Failed to extract GT bboxes: {e}")

    return boxes


def bbox_iou_xyxy(box_a: List[float], box_b: List[float]) -> float:
    """Calculate IoU between two bounding boxes"""
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


def evaluate_crop_tool_usage(
    crop_history: List[Dict],
    pred_boxes: List[List[float]],
    gt_boxes: List[List[float]],
) -> Tuple[float, str]:
    """
    Evaluate the effectiveness of crop tool usage.

    Returns:
        (score, quality_rating)
    """
    if not crop_history:
        return 0.0, "POOR"  # No tool usage

    num_crops = len(crop_history)
    score = 0.0

    # Base score for using the tool
    score += 0.2

    # Evaluate number of crops
    if num_crops == 1:
        crop_count_score = 0.3  # Good single crop
    elif num_crops == 2:
        crop_count_score = 0.4  # Excellent - two-stage inspection
    elif num_crops == 3:
        crop_count_score = 0.3  # Still good but getting excessive
    else:
        crop_count_score = 0.1  # Too many crops

    score += crop_count_score

    # Evaluate crop progression (sizes should generally decrease)
    progression_score = 0.0
    if num_crops > 1:
        sizes = []
        for crop_info in crop_history:
            crop_size = crop_info.get("crop_size", (0, 0))
            sizes.append(crop_size[0] * crop_size[1])

        # Check if sizes generally decrease (focusing in)
        decreasing = all(sizes[i] >= sizes[i + 1] for i in range(len(sizes) - 1))
        if decreasing:
            progression_score = 0.2
        else:
            progression_score = 0.1

    score += progression_score

    # Evaluate crop quality (reasonable sizes)
    crop_quality_score = 0.0
    for crop_info in crop_history:
        crop_size = crop_info.get("crop_size", (0, 0))
        parent_size = crop_info.get("parent_size", (1, 1))

        crop_area = crop_size[0] * crop_size[1]
        parent_area = parent_size[0] * parent_size[1]
        ratio = crop_area / parent_area if parent_area > 0 else 0

        # Optimal ratio between 0.1 and 0.6
        if 0.1 <= ratio <= 0.6:
            crop_quality_score += 0.1
        elif 0.05 <= ratio < 0.1 or 0.6 < ratio <= 0.8:
            crop_quality_score += 0.05

    score += crop_quality_score

    # Bonus for improved localization (if final boxes are more precise)
    if pred_boxes and gt_boxes:
        # Calculate average IoU
        total_iou = 0.0
        for gt_box in gt_boxes:
            best_iou = 0.0
            for pred_box in pred_boxes:
                iou = bbox_iou_xyxy(gt_box, pred_box)
                best_iou = max(best_iou, iou)
            total_iou += best_iou

        avg_iou = total_iou / len(gt_boxes) if gt_boxes else 0.0

        # Bonus for high IoU (suggests effective cropping)
        if avg_iou >= 0.7:
            score += 0.2
        elif avg_iou >= 0.5:
            score += 0.1

    # Determine quality rating
    if score >= 0.8:
        quality = "EXCELLENT"
    elif score >= 0.6:
        quality = "GOOD"
    elif score >= 0.4:
        quality = "FAIR"
    else:
        quality = "POOR"

    return min(1.0, score), quality


def extract_ground_truth_answer(ground_truth: Any, extra_info: Optional[Dict]) -> str:
    """Extract the textual ground truth answer"""
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


def compute_crop_inspection_score(
    predict_str: str,
    ground_truth: str,
    extra_info: Optional[Dict] = None,
    crop_history: Optional[List[Dict]] = None,
    use_enhanced_evaluation: bool = True,
) -> float:
    """
    Compute reward score for crop inspection tool usage.

    Args:
        predict_str: Model's prediction string
        ground_truth: Ground truth answer
        extra_info: Additional information including question, bboxes, etc.
        crop_history: History of crop operations performed
        use_enhanced_evaluation: Whether to use enhanced LLM-based evaluation

    Returns:
        Final reward score
    """
    is_format_error = False
    crop_history = crop_history or []

    # Format validation
    count_think_1 = predict_str.count("<think>")
    count_think_2 = predict_str.count("</think>")
    if count_think_1 != count_think_2:
        is_format_error = True

    count_vision_1 = predict_str.count("<|vision_start|><|image_pad|>")
    count_vision_2 = predict_str.count("<|image_pad|><|vision_end|>")
    if count_vision_1 != count_vision_2:
        is_format_error = True

    predict_no_think = predict_str.split("</think>")[-1].strip()
    count_answer_1 = predict_no_think.count("<answer>")
    count_answer_2 = predict_no_think.count("</answer>")
    if count_answer_1 != count_answer_2:
        is_format_error = True

    count_location_1 = predict_no_think.count("<location>")
    count_location_2 = predict_no_think.count("</location>")
    if count_location_1 != count_location_2:
        is_format_error = True

    count_type_1 = predict_no_think.count("<type>")
    count_type_2 = predict_no_think.count("</type>")
    if count_type_1 != count_type_2:
        is_format_error = True

    # Extract components
    answer_text = extract_answer(predict_no_think)
    location_text = extract_location(predict_no_think)
    type_text = extract_type(predict_no_think)

    # Parse bounding boxes
    pred_boxes = parse_predicted_bboxes(location_text)
    gt_boxes = extract_gt_bboxes(ground_truth, extra_info)

    # Rescale predicted boxes to original coordinates if needed
    pred_boxes = _maybe_rescale_pred_boxes_to_original(pred_boxes, extra_info)

    # Get ground truth information
    ground_truth_answer = extract_ground_truth_answer(ground_truth, extra_info)
    expected_type = (
        "good"
        if ground_truth_answer.lower().startswith("no")
        else (extra_info.get("type", "unspecified") if extra_info else "unspecified")
    )

    # Evaluate crop tool usage
    crop_tool_score, crop_quality = evaluate_crop_tool_usage(
        crop_history, pred_boxes, gt_boxes
    )

    # Evaluate bbox format
    bbox_format_ok = False
    if location_text:
        try:
            loc = json.loads(location_text)
            if (
                isinstance(loc, list) and len(loc) <= 5
            ):  # Allow more boxes due to cropping
                bbox_format_ok = all(
                    isinstance(item, dict)
                    and ("bbox2d" in item or "bbox_2d" in item)
                    and isinstance((item.get("bbox2d") or item.get("bbox_2d")), list)
                    and len((item.get("bbox2d") or item.get("bbox_2d"))) == 4
                    for item in loc
                )
        except (json.JSONDecodeError, TypeError):
            pass

    # Enhanced LLM evaluation
    if use_enhanced_evaluation and answer_text and len(answer_text) < 1000:
        try:
            question_text = extra_info.get("question", "") if extra_info else ""
            client_idx = random.randint(0, len(client_list) - 1)
            client = client_list[client_idx]
            model_name = model_name_list[client_idx]

            # Format crop history for prompt
            crop_history_str = (
                json.dumps(crop_history, indent=2)
                if crop_history
                else "No crops performed"
            )

            full_prompt = CROP_INSPECTION_VERIFY_PROMPT.format(
                query=question_text,
                gold_ans=ground_truth_answer,
                gold_type=expected_type,
                gold_bboxes=json.dumps(gt_boxes),
                pred_ans=answer_text,
                pred_type=type_text or "N/A",
                pred_bboxes=json.dumps(pred_boxes),
                crop_history=crop_history_str,
            )

            # Get LLM evaluation
            chat_response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": full_prompt},
                ],
                seed=random.randint(0, 1000000),
                temperature=0.3,
            )
            response = chat_response.choices[0].message.content.strip()

            # Parse response
            acc_reward = 0.0
            tool_usage_reward = 0.0
            localization_reward = 0.0
            type_reward = 0.0

            # Detection accuracy
            detection_part = (
                response.split("## Detection Accuracy")[-1]
                .split("## Tool Usage Quality")[0]
                .lower()
            )
            if "true" in detection_part and "false" not in detection_part:
                acc_reward = 1.0

            # Tool usage quality
            tool_part = (
                response.split("## Tool Usage Quality")[-1]
                .split("## Localization Accuracy")[0]
                .upper()
            )
            if "EXCELLENT" in tool_part:
                tool_usage_reward = 1.0
            elif "GOOD" in tool_part:
                tool_usage_reward = 0.8
            elif "FAIR" in tool_part:
                tool_usage_reward = 0.6
            elif "POOR" in tool_part:
                tool_usage_reward = 0.2

            # Localization accuracy
            loc_part = (
                response.split("## Localization Accuracy")[-1]
                .split("## Type Accuracy")[0]
                .lower()
            )
            if "true" in loc_part and "false" not in loc_part:
                localization_reward = 1.0
            elif "n/a" in loc_part:
                localization_reward = 0.5

            # Type accuracy
            type_part = (
                response.split("## Type Accuracy")[-1]
                .split("## Overall Equivalence")[0]
                .lower()
            )
            if "true" in type_part and "false" not in type_part:
                type_reward = 1.0
            elif "n/a" in type_part:
                type_reward = 0.5

        except Exception as e:
            log.error(f"Enhanced evaluation failed: {e}")
            # Fallback to basic evaluation
            acc_reward = (
                1.0
                if answer_text.lower().strip() == ground_truth_answer.lower().strip()
                else 0.0
            )
            tool_usage_reward = crop_tool_score
            localization_reward = 0.5  # Neutral
            type_reward = (
                1.0 if type_text and type_text.lower() == expected_type.lower() else 0.0
            )
    else:
        # Basic evaluation
        acc_reward = (
            1.0
            if answer_text
            and answer_text.lower().strip() == ground_truth_answer.lower().strip()
            else 0.0
        )
        tool_usage_reward = crop_tool_score
        localization_reward = 0.5
        type_reward = (
            1.0 if type_text and type_text.lower() == expected_type.lower() else 0.0
        )

    # Vision tool usage reward
    vision_reward = 1.0 if count_vision_1 > 0 else 0.0

    # Format penalty
    format_reward = -1.0 if is_format_error else 0.0

    # Bbox format reward
    bbox_format_reward = 0.5 if bbox_format_ok else 0.0

    # Final score calculation with emphasis on crop tool effectiveness
    final_score = (
        0.4 * acc_reward  # Answer accuracy
        + 8 * tool_usage_reward  # Crop tool usage effectiveness
        + 0.2 * localization_reward  # Localization accuracy
        + 0.2 * type_reward  # Type classification
        + 5 * vision_reward  # Vision tool usage
        + 0.1 * format_reward  # Format penalty
        + 0.5 * bbox_format_reward  # Bbox format bonus
    )

    log.info(
        f"Crop inspection score breakdown: acc={acc_reward:.2f}, tool_usage={tool_usage_reward:.2f}, "
        f"loc={localization_reward:.2f}, type={type_reward:.2f}, vision={vision_reward:.2f}, "
        f"format={format_reward:.2f}, bbox_fmt={bbox_format_reward:.2f}, final={final_score:.2f}, "
        f"crops={len(crop_history)}, quality={crop_quality}"
    )
    print(
        f"Crop inspection score breakdown: acc={0.4 * acc_reward:.2f}, tool_usage={8 * tool_usage_reward:.2f}, "
        f"loc={0.2 * localization_reward:.2f}, type={0.2 * type_reward:.2f}, vision={5 * vision_reward:.2f}, "
        f"format={0.1 * format_reward:.2f}, bbox_fmt={0.5 * bbox_format_reward:.2f}, final={final_score:.2f}, "
        f"crops={len(crop_history)}, quality={crop_quality}"
    )

    return max(0.0, final_score)


if __name__ == "__main__":
    # Example usage
    predict_str = """<think>I need to inspect this image for defects. Let me first crop a suspicious area.</think>
    <tool_call>
    {"name": "crop_from_location", "arguments": {"location_data": "[{\"bbox2d\": [100, 100, 200, 200]}]", "crop_index": 0}}
    </tool_call>
    Now I can see the cropped region more clearly. There appears to be a scratch.
    <answer>yes</answer>
    <location>[{"bbox2d": [120, 120, 180, 180]}]</location>
    <type>scratch</type>"""

    ground_truth = "yes"
    extra_info = {
        "question": "Is there a defect in this image?",
        "answer": "Yes, there is a scratch defect.",
        "type": "scratch",
        "bboxes": [{"bbox2d": [110, 110, 190, 190]}],
    }

    crop_history = [
        {
            "level": 0,
            "original_bbox": [100, 100, 200, 200],
            "resized_bbox": [100, 100, 200, 200],
            "crop_size": (100, 100),
            "parent_size": (500, 500),
        }
    ]

    score = compute_crop_inspection_score(
        predict_str, ground_truth, extra_info, crop_history
    )
    print(f"Crop inspection score: {score:.3f}")
