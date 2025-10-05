# Image Restoration Reward Function Modification Summary

## Overview
Modified the reward system to support image restoration tasks with format checking and restoration order accuracy evaluation.

## Files Modified

### 1. `/verl/utils/reward_score/image_restoration.py` (NEW)
- **Purpose**: Core reward computation logic for image restoration tasks
- **Key Functions**:
  - `extract_restoration_log_from_response()`: Extracts restoration log from model responses
  - `check_response_format()`: Validates response format (30% of total score)
  - `check_restoration_order()`: Validates restoration order accuracy (70% of total score)
  - `compute_score()`: Main scoring function

### 2. `/verl/utils/reward_score/__init__.py` (MODIFIED)
- **Changes**: Added support for "image_restoration" data source
- **Lines Added**: 79-81

### 3. `/verl/workers/reward_manager/naive.py` (MODIFIED)  
- **Changes**: Enhanced ground truth handling to support your parquet format
- **Lines Modified**: 74-82

## Parquet Data Format Support

The reward function now supports your parquet format with these columns:

- **`data_source`**: Set to `"image_restoration"` to use the new reward function
- **`prompt`**: List of dicts with system and user prompts (used for tokenization)
- **`images`**: Image bytes data (not directly used in reward computation)
- **`env_name`**: String format degradations in **reverse order of addition** (e.g., "jpeg compression artifact, motion blur, haze")
- **`reward_model`**: List format degradations in **addition order** (e.g., `[{'degradation_type': 'haze', 'degradation_level': 'low'}, {'degradation_type': 'motion blur', 'degradation_level': 'medium'}]`)
- **`extra_info`**: Additional metadata (e.g., `{'index': 0}`)

## Reward Scoring Components

### 1. Format Checking (30% weight)
Validates that model responses follow the required format:
- `<think>` block with `reasoning`, `diagnosis`, and `pass` fields
- Appropriate action based on `pass` value with mutual exclusivity:
  - `pass=false`: Should have `<tool_call>` block and NOT have `<answer>`
  - `pass=true`: Should have `<answer>` block and NOT have `<tool_call>`
- Penalties for format violations:
  - Having both `<tool_call>` and `<answer>` simultaneously: Heavy penalty
  - Wrong action type for `pass` value: Medium penalty

### 2. Order Accuracy (70% weight)
Validates that restoration follows LIFO (Last In, First Out) principle:
- Model's restoration_log should match reward_model's reverse order
- Or equivalently, match env_name's forward order (since env_name is already in correct restoration order)
- Full credit for exact match
- Partial credit for partially correct sequences
- Minimum 50% credit if all degradations are present (even if wrong order)

**Example**:
- reward_model: `[{"degradation_type": "haze"}, {"degradation_type": "motion blur"}, {"degradation_type": "jpeg compression artifact"}]` (addition order)
- env_name: `"jpeg compression artifact, motion blur, haze"` (reverse of addition order)
- Correct restoration_log: `["jpeg compression artifact", "motion blur", "haze"]` (LIFO order, same as env_name order)

## Usage Instructions

1. Set `data_source` column to `"image_restoration"` in your parquet data
2. The reward function automatically:
   - Extracts expected degradation order from `reward_model` or `env_name`
   - Parses model response for restoration log
   - Computes format score and order accuracy score
   - Returns detailed scoring breakdown

## Example Scores

- **Perfect response**: 0.97 (0.9 format + 1.0 order)
- **Wrong order**: 0.62 (0.9 format + 0.5 order)
- **Bad format**: Lower format score affects total

## Ray Training Compatibility

The reward function follows the same pattern as other reward functions in the codebase (like `vl_agent.py`):
- Returns a single float value (no complex data structures)
- Uses print statements for debug output instead of returning dictionaries
- Fully compatible with Ray distributed training

## Return Value

The reward function returns a single float score between 0 and 1, calculated as:
```
total_score = 0.3 * format_score + 0.7 * order_score
```

Debug information is printed to console in the format:
```
[DEBUG image_restoration] predicted_log="...", expected_order="...", correct_restoration="...", format_score=X.XXX, order_score=X.XXX, total_score=X.XXX
```

## Testing

The implementation has been tested with:
- Correct format validation
- Order accuracy checking
- Complete scoring scenarios
- Error handling for malformed responses
- Numpy compatibility for Ray training

Run `python image_restoration_reward_example.py` to see the reward function in action.
