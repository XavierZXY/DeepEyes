# Crop Inspection System

A comprehensive tool and reward system for multi-round image inspection using progressive cropping for detailed defect detection.

## Overview

The Crop Inspection System consists of two main components:

1. **CropInspectionTool**: A tool that can extract locations from `<location>` tags and crop images for detailed inspection
2. **Crop Inspection Reward System**: A reward system that evaluates multi-round tool usage and crop effectiveness

## Features

### CropInspectionTool Features
- **Multi-round cropping**: Supports up to 3 levels of progressive cropping
- **Location-based cropping**: Extracts bounding boxes from `<location>` tags in JSON format
- **Automatic validation**: Validates and resizes bounding boxes to ensure reasonable crop regions
- **Crop history tracking**: Maintains detailed history of all crop operations
- **Error handling**: Robust error handling with informative error messages

### Reward System Features
- **Multi-dimensional evaluation**: Evaluates detection accuracy, tool usage, localization, and type classification
- **Crop effectiveness scoring**: Rewards appropriate crop strategies and penalizes excessive cropping
- **LLM-based evaluation**: Optional enhanced evaluation using language models
- **Progressive inspection bonus**: Rewards logical progression from coarse to fine inspection
- **Format validation**: Comprehensive format checking for all required tags

## Usage

### Basic Tool Usage

```python
from verl.workers.agent.envs.mm_process_engine.crop_inspection_tool import CropInspectionTool

# Initialize the tool
tool = CropInspectionTool()

# Setup with image data
multi_modal_data = {"image": [your_pil_image]}
tool.reset("Inspect for defects", multi_modal_data, multi_modal_data)

# First crop operation
action_1 = '''
<tool_call>
{"name": "crop_from_location", "arguments": {"location_data": "[{\"bbox2d\": [100, 100, 200, 200]}]", "crop_index": 0}}
</tool_call>
'''

obs, reward, done, info = tool.execute(action_1)

# Continue with more crops or provide final answer
final_action = '''
<answer>yes</answer>
<location>[{"bbox2d": [120, 120, 180, 180]}]</location>
<type>scratch</type>
'''

final_obs, final_reward, final_done, final_info = tool.execute(final_action)
```

### Reward System Usage

```python
from verl.utils.reward_score.crop_inspection_reward import compute_crop_inspection_score

# Compute score with crop history
score = compute_crop_inspection_score(
    predict_str=model_prediction,
    ground_truth=ground_truth_answer,
    extra_info={
        "question": "Is there a defect?",
        "answer": "Yes, there is a scratch",
        "type": "scratch",
        "bboxes": [{"bbox2d": [115, 115, 185, 185]}]
    },
    crop_history=crop_history,
    use_enhanced_evaluation=True
)
```

## Tool Call Format

### Crop Tool Call
```json
{
    "name": "crop_from_location",
    "arguments": {
        "location_data": "[{\"bbox2d\": [x1, y1, x2, y2]}, {\"bbox2d\": [x3, y3, x4, y4]}]",
        "crop_index": 0
    }
}
```

### Final Answer Format
```xml
<answer>yes/no</answer>
<location>[{"bbox2d": [x1, y1, x2, y2]}]</location>
<type>defect_type</type>
```

## Reward Components

The reward system evaluates multiple aspects:

### 1. Detection Accuracy (40% weight)
- Correctness of yes/no defect detection decision
- Evaluated against ground truth answer

### 2. Tool Usage Effectiveness (30% weight)
- **EXCELLENT**: Optimal 1-2 crop strategy with logical progression
- **GOOD**: Reasonable crop usage with some effectiveness
- **FAIR**: Suboptimal but functional crop strategy
- **POOR**: No crops or excessive/ineffective cropping

### 3. Localization Accuracy (20% weight)
- Precision of bounding box predictions
- IoU-based evaluation against ground truth boxes
- Bonus for improved localization through cropping

### 4. Type Classification (20% weight)
- Accuracy of defect type classification
- "good" type for no-defect cases
- Semantic matching for defect types

### Additional Components
- **Vision Tool Usage** (30% bonus): Using vision tokens correctly
- **Format Validation** (10% penalty if errors): Proper XML tag formatting
- **Bbox Format** (10% bonus): Valid JSON bbox format

## Crop Strategy Evaluation

### Optimal Strategies (High Rewards)
1. **Single Focused Crop**: One well-placed crop on suspicious area
2. **Two-Stage Inspection**: Coarse crop followed by fine crop
3. **Progressive Zooming**: Logical sequence from general to specific

### Suboptimal Strategies (Lower Rewards)
1. **No Cropping**: Missing opportunity for detailed inspection
2. **Excessive Cropping**: More than 3 levels, diminishing returns
3. **Poor Crop Selection**: Crops that don't focus on relevant areas
4. **Inconsistent Progression**: Random or illogical crop sequence

## Configuration Options

### Tool Configuration
- `max_crop_levels`: Maximum allowed crop levels (default: 3)
- `min_crop_size`: Minimum crop dimensions (default: 20px)
- `aspect_ratio_limit`: Maximum aspect ratio (default: 100:1)

### Reward Configuration
- `use_enhanced_evaluation`: Enable LLM-based evaluation
- `bbox_reward_weight`: Weight for localization component
- `crop_effectiveness_weight`: Weight for tool usage evaluation

## Integration with Existing Systems

### With VL Agent
```python
# Import both systems
from verl.utils.reward_score.vl_agent import compute_score
from verl.utils.reward_score.crop_inspection_reward import compute_crop_inspection_score

# Use crop inspection score when crop history is available
if crop_history:
    score = compute_crop_inspection_score(predict_str, ground_truth, extra_info, crop_history)
else:
    score = compute_score(predict_str, ground_truth, extra_info)
```

### With Visual Toolbox
The crop inspection tool can work alongside existing visual tools:

```python
# Combine with rotation and other tools
if tool_name == "crop_from_location":
    # Handle crop tool
    result = crop_tool.execute(action)
elif tool_name == "image_rotate_tool":
    # Handle rotation tool
    result = visual_toolbox.execute(action)
```

## Error Handling

The system includes comprehensive error handling:

- **Invalid JSON**: Clear error messages for malformed tool calls
- **Invalid Bounding Boxes**: Automatic validation and resizing
- **Excessive Cropping**: Prevents infinite crop loops
- **Format Errors**: Detailed format validation with specific error types
- **Image Processing Errors**: Graceful handling of PIL/image errors

## Performance Considerations

- **Crop Limits**: Maximum 3 crop levels to prevent excessive processing
- **Image Size Limits**: Automatic resizing for very small crops
- **Memory Management**: Efficient image handling with minimal memory overhead
- **Evaluation Speed**: Optional fast evaluation mode without LLM calls

## Examples and Testing

Run the comprehensive example:

```bash
cd verl/examples
python crop_inspection_example.py
```

This will demonstrate:
- Multi-round inspection simulation
- Different crop strategies
- Reward system evaluation
- Strategy comparison

## Best Practices

### For Tool Usage
1. Start with broader crops and progressively focus
2. Limit crops to 2-3 levels for optimal efficiency
3. Ensure crops focus on suspicious/relevant areas
4. Provide clear final answers with proper formatting

### For Reward Design
1. Balance detection accuracy with tool effectiveness
2. Encourage logical inspection progression
3. Penalize excessive or random cropping
4. Reward appropriate tool usage over no tool usage

### For Integration
1. Check for crop history before choosing reward function
2. Combine with existing visual tools seamlessly
3. Handle edge cases gracefully
4. Maintain consistent evaluation criteria

## Troubleshooting

### Common Issues

1. **"Invalid bounding box coordinates"**
   - Ensure bbox coordinates are within image bounds
   - Check that x1 < x2 and y1 < y2
   - Verify minimum size requirements

2. **"Maximum crop levels exceeded"**
   - Reduce number of progressive crops
   - Consider if all crops are necessary

3. **"No valid bounding boxes found"**
   - Check JSON format in location_data
   - Ensure bbox2d or bbox_2d keys are present
   - Verify array has exactly 4 elements

4. **Low reward scores**
   - Check final answer format
   - Ensure appropriate crop strategy
   - Verify ground truth alignment

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger("rich").setLevel(logging.DEBUG)
```

This will provide detailed information about:
- Crop operations and validation
- Reward component breakdown
- Error details and stack traces
- Performance metrics
