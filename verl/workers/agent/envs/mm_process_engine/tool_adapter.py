import re
import json
from typing import Dict, Any, Tuple, Union, List


def extract_think_and_tool_calls(action_string: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    从action_string中提取<think>内容和<tool_call>中的工具调用列表
    
    Args:
        action_string: 包含<think>和<tool_call>的完整字符串
        
    Returns:
        Tuple[think_content, tool_calls_list]
        - think_content: <think>标签内的内容，如果没有则为空字符串
        - tool_calls_list: 解析后的工具调用列表，每个元素包含name和arguments
    """
    # 提取<think>内容
    think_pattern = r'<think>(.*?)</think>'
    think_match = re.search(think_pattern, action_string, re.DOTALL)
    think_content = think_match.group(1).strip() if think_match else ""
    
    # 提取<tool_call>内容
    tool_call_pattern = r'<tool_call>(.*?)</tool_call>'
    tool_call_matches = re.findall(tool_call_pattern, action_string, re.DOTALL)
    
    tool_calls_list = []
    for tool_call_content in tool_call_matches:
        tool_call_content = tool_call_content.strip()
        try:
            # 解析JSON内容
            if tool_call_content.startswith('[') and tool_call_content.endswith(']'):
                # 处理列表格式: [{"name":"...","arguments":{...}}]
                parsed_calls = json.loads(tool_call_content)
                if isinstance(parsed_calls, list):
                    tool_calls_list.extend(parsed_calls)
                else:
                    tool_calls_list.append(parsed_calls)
            else:
                # 处理单个对象格式: {"name":"...","arguments":{...}}
                parsed_call = json.loads(tool_call_content)
                tool_calls_list.append(parsed_call)
        except json.JSONDecodeError as e:
            print(f"[WARNING] Failed to parse tool_call JSON: {tool_call_content}, error: {e}")
            continue
    
    return think_content, tool_calls_list


def execute_new_format_tool_call(tool, action_string: str) -> Tuple[Any, float, bool, Dict[str, Any]]:
    """
    处理新格式的工具调用，支持<think>和<tool_call>格式
    
    Args:
        tool: 工具实例
        action_string: 包含<think>和<tool_call>的完整字符串
        
    Returns:
        Tuple[observation, reward, done, info]
    """
    # 首先检查是否有<answer>标签（最终答案）
    answer_pattern = r'<answer>(.*?)</answer>'
    answer_match = re.search(answer_pattern, action_string, re.DOTALL)
    if answer_match:
        answer_content = answer_match.group(1).strip()
        return "", 0.0, True, {"status": "finished", "answer": answer_content}
    
    # 提取think内容和工具调用
    think_content, tool_calls_list = extract_think_and_tool_calls(action_string)
    
    if not tool_calls_list:
        error_msg = "No valid tool calls found in action string"
        obs = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        return obs, -0.1, False, {"error": error_msg, "status": "failed"}
    
    # 目前只处理第一个工具调用
    tool_call = tool_calls_list[0]
    tool_name = tool_call.get("name", "")
    arguments = tool_call.get("arguments", {})
    
    # 检查工具名称是否匹配
    if hasattr(tool, 'name') and tool_name != tool.name:
        error_msg = f"Tool name mismatch: expected '{tool.name}', got '{tool_name}'"
        obs = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        return obs, -0.1, False, {"error": error_msg, "status": "failed"}
    
    try:
        # 检查工具是否支持新的execute接口（接受arguments参数）
        import inspect
        execute_signature = inspect.signature(tool.execute)
        execute_params = list(execute_signature.parameters.keys())
        
        if len(execute_params) >= 1 and execute_params[0] in ['arguments', 'args']:
            # 新接口：execute(arguments: Dict[str, Any])
            print(f"[DEBUG] Using new interface for tool {tool_name}")
            return tool.execute(arguments)
        else:
            # 旧接口：execute(action_string: str)
            # 将新格式转换为旧格式
            print(f"[DEBUG] Using legacy interface for tool {tool_name}")
            legacy_action_string = f'<tool_call>{{"name": "{tool_name}", "arguments": {json.dumps(arguments)}}}</tool_call>'
            return tool.execute(legacy_action_string)
            
    except Exception as e:
        error_msg = f"Tool execution failed: {str(e)}"
        obs = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        return obs, -0.1, False, {"error": str(e), "status": "failed"}


# 测试函数
if __name__ == "__main__":
    # 测试提取函数
    test_action = """
    <think>{"diagnosis":{"labels":["jpeg compression artifact"],"levels":{}},"confidence":0.89,"pass":false}</think>
    <tool_call>[
    {"name":"swinir_jpeg_artifact_removal","arguments":{"strength":0.5}}
    ]</tool_call>
    """
    
    think, tools = extract_think_and_tool_calls(test_action)
    print(f"Think content: {think}")
    print(f"Tool calls: {tools}")
    
    # 测试另一种格式
    test_action2 = """
    Some text here
    <tool_call>{"name":"gamma_correction","arguments":{"gamma":1.2}}</tool_call>
    """
    
    think2, tools2 = extract_think_and_tool_calls(test_action2)
    print(f"Think content 2: {think2}")
    print(f"Tool calls 2: {tools2}")
