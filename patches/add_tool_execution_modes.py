#!/usr/bin/env python3
"""
添加工具执行模式切换功能的补丁

将此代码插入到 parallel_env.py 的 execute_tool_call 函数开始部分（约行988附近）
在 parsed_output = agent_input_dict.get('parsed_output', {}) 之后添加
"""

# =================================================================================
# 在 execute_tool_call 函数中添加以下代码
# 位置：在 parsed_output = agent_input_dict.get('parsed_output', {}) 之后
# =================================================================================

def execute_tool_call_with_modes(agent_input_dict, tokenizer, processor=None, pbar=None, size_anomaly_records=None):
    """
    Enhanced execute_tool_call function with mode switching support.
    
    Supports two modes:
    1. "chain" mode (V7): Execute all tools in sequence from original image
    2. "iterative" mode (new): Execute first tool only, pass result to next turn
    """
    idx = agent_input_dict.get('idx', 0)
    valid_idx = agent_input_dict.get('valid_idx', 0)
    action_string = agent_input_dict.get('action', '')
    tools = agent_input_dict.get('tools', [])
    parsed_output = agent_input_dict.get('parsed_output', {})
    turn_info = agent_input_dict.get('turn_info', f'T?-样本{valid_idx}')
    origin_multi_modal_data = agent_input_dict.get('origin_multi_modal_data')
    raw_prompt = agent_input_dict.get('raw_prompt')
    
    # 🆕 获取当前图像数据（用于迭代模式）
    current_multi_modal_data = agent_input_dict.get('current_multi_modal_data')
    
    # 🆕 获取执行模式配置（默认为chain）
    tool_execution_mode = agent_input_dict.get('tool_execution_mode', 'chain')
    
    if size_anomaly_records is None:
        size_anomaly_records = []

    # non-agent data or no tools to execute
    if action_string == '':
        return {}, 0.0, True, {}
    elif not tools:
        error_msg = "Failed to parse valid tool calls from the action string. Please check the format of your <tool_call> blocks."
        error_text = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        obs_token_ids = tokenizer.encode(error_text, add_special_tokens=False)
        error_obs = {
            "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
            "prompt_token_ids_model": torch.tensor(obs_token_ids),
        }
        return error_obs, 0.0, False, {"error": error_msg, "status": "failed"}

    # Handle <answer> case - episode is done
    if parsed_output.get('is_done', False):
        return {}, 0.0, True, {"status": "success", "type": "answer"}

    # ==========================================================
    # 🆕 模式选择逻辑
    # ==========================================================
    print(f'[DEBUG {turn_info}] 🔧 工具执行模式: {tool_execution_mode.upper()}')
    
    if tool_execution_mode == 'chain':
        # ========== 模式A：链式执行（V7默认模式） ==========
        # 一次执行所有工具，从原图开始，链式传递
        print(f'[DEBUG {turn_info}] 🔗 [链式模式] 执行{len(tools)}个工具的完整序列')
        return _execute_chain_mode(
            tools, parsed_output, origin_multi_modal_data, raw_prompt,
            tokenizer, processor, turn_info, pbar, size_anomaly_records
        )
    
    elif tool_execution_mode == 'iterative':
        # ========== 模式B：迭代执行（新增单工具模式） ==========
        # 每次只执行第一个工具，结果传递给下一轮
        print(f'[DEBUG {turn_info}] 🔄 [迭代模式] 只执行第1个工具，共{len(tools)}个')
        return _execute_iterative_mode(
            tools, parsed_output, current_multi_modal_data, origin_multi_modal_data,
            raw_prompt, tokenizer, processor, turn_info, pbar, size_anomaly_records
        )
    
    else:
        raise ValueError(f"Unknown tool_execution_mode: {tool_execution_mode}. Must be 'chain' or 'iterative'")


def _execute_chain_mode(tools, parsed_output, origin_multi_modal_data, raw_prompt, 
                        tokenizer, processor, turn_info, pbar, size_anomaly_records):
    """
    链式执行模式（V7）：一次执行所有工具，从原图开始
    
    流程：
    1. 从原图开始
    2. 依次执行工具1 → 工具2 → 工具3 → ...
    3. 每个工具的输出作为下一个工具的输入
    4. 返回最终结果
    """
    from copy import deepcopy
    import json
    import torch
    
    print(f'[DEBUG {turn_info}] 🔧 [链式] 开始执行工具链，共{len(tools)}个工具')
    
    if origin_multi_modal_data is None:
        error_msg = "Cannot find origin image data for tool execution."
        error_text = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        obs_token_ids = tokenizer.encode(error_text, add_special_tokens=False)
        error_obs = {
            "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
            "prompt_token_ids_model": torch.tensor(obs_token_ids),
        }
        return error_obs, 0.0, False, {"error": error_msg, "status": "failed", "executed_tools": []}
    
    # 工具链执行：从原图开始，链式传递
    current_image_data = deepcopy(origin_multi_modal_data)
    executed_tools = []
    total_reward = 0.0
    final_done = False
    final_info = {}
    
    for i, tool in enumerate(tools):
        if tool is None:
            print(f'[DEBUG {turn_info}] [链式] ⚠️  工具{i+1}为None，跳过')
            continue
        
        try:
            tool_call = parsed_output['tool_calls'][i] if i < len(parsed_output['tool_calls']) else {}
            
            # 重置工具，使用当前图像数据
            print(f'[DEBUG {turn_info}] [链式] 🔄 工具{i+1}/{len(tools)}: {tool.name} (输入: {"原图" if i==0 else f"工具{i}结果"})')
            
            tool.reset(
                raw_prompt=raw_prompt,
                multi_modal_data=deepcopy(current_image_data) if current_image_data else None,
                origin_multi_modal_data=deepcopy(origin_multi_modal_data) if origin_multi_modal_data else None,
            )
            
            # 执行工具
            if isinstance(tool_call, dict):
                compatible_action_string = f"<tool_call>{json.dumps(tool_call)}</tool_call>"
            else:
                compatible_action_string = f"<tool_call>{json.dumps({'name': str(tool_call), 'arguments': {}})}</tool_call>"
            
            print(f'[DEBUG {turn_info}] [链式] 🚀 开始执行工具{i+1}: {tool.name}')
            tool_result, reward, done, info = tool.execute(compatible_action_string)
            print(f'[DEBUG {turn_info}] [链式] ✅ 工具{i+1}执行完成: reward={reward:.3f}')
            
            # 更新当前图像为这个工具的输出
            if isinstance(tool_result, dict) and 'multi_modal_data' in tool_result:
                current_image_data = tool_result['multi_modal_data']
            
            executed_tools.append(tool.name)
            total_reward += reward
            final_done = final_done or done
            final_info.update(info)
            
        except Exception as e:
            print(f'[ERROR {turn_info}] [链式] ❌ 工具{i+1}({tool.name})执行失败: {str(e)}')
            import traceback
            traceback.print_exc()
            total_reward -= 0.1
            continue
    
    if not executed_tools:
        error_msg = "All tool executions failed."
        error_text = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        obs_token_ids = tokenizer.encode(error_text, add_special_tokens=False)
        error_obs = {
            "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
            "prompt_token_ids_model": torch.tensor(obs_token_ids),
        }
        return error_obs, total_reward, False, {"error": error_msg, "status": "failed", "executed_tools": []}
    
    print(f'[DEBUG {turn_info}] [链式] 🎉 工具链执行完成: {" -> ".join(executed_tools)}')
    
    # 构建返回的observation
    tools_summary = " → ".join(executed_tools)
    result_prompt = (
        f"\n<|im_start|>user\n"
        f"<tool_response><image>"
        f"Result after applying: [{tools_summary}]"
        f"</tool_response>"
        f"<|im_end|>\n<|im_start|>assistant\n"
    )
    
    final_tool_result = {
        "prompt": result_prompt,
        "multi_modal_data": current_image_data
    }
    
    final_info.update({
        "status": "success",
        "executed_tools": executed_tools,
        "tool_chain": tools_summary,
        "mode": "chain"
    })
    
    # 后处理（调用原有的后处理逻辑）
    return _post_process_tool_result(final_tool_result, final_info, total_reward, final_done, 
                                     tokenizer, processor, turn_info, pbar)


def _execute_iterative_mode(tools, parsed_output, current_multi_modal_data, origin_multi_modal_data,
                            raw_prompt, tokenizer, processor, turn_info, pbar, size_anomaly_records):
    """
    迭代执行模式（新）：每次只执行第一个工具，结果传给下一轮
    
    流程：
    1. 只执行第一个工具
    2. 使用当前图像（上一轮的结果）作为输入
    3. 返回结果，等待下一轮调用
    """
    from copy import deepcopy
    import json
    import torch
    
    print(f'[DEBUG {turn_info}] 🔄 [迭代] 只执行第1个工具')
    
    # 使用当前图像数据（如果没有则使用原图）
    if current_multi_modal_data is None:
        print(f'[DEBUG {turn_info}] [迭代] 使用原图作为输入')
        input_image_data = deepcopy(origin_multi_modal_data)
    else:
        print(f'[DEBUG {turn_info}] [迭代] 使用上一轮结果作为输入')
        input_image_data = deepcopy(current_multi_modal_data)
    
    if not tools or tools[0] is None:
        error_msg = "No valid tool to execute in iterative mode."
        error_text = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        obs_token_ids = tokenizer.encode(error_text, add_special_tokens=False)
        error_obs = {
            "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
            "prompt_token_ids_model": torch.tensor(obs_token_ids),
        }
        return error_obs, 0.0, False, {"error": error_msg, "status": "failed"}
    
    # 只执行第一个工具
    tool = tools[0]
    tool_call = parsed_output['tool_calls'][0] if parsed_output['tool_calls'] else {}
    
    try:
        # 重置工具
        tool.reset(
            raw_prompt=raw_prompt,
            multi_modal_data=input_image_data,
            origin_multi_modal_data=deepcopy(origin_multi_modal_data) if origin_multi_modal_data else None,
        )
        
        # 执行工具
        if isinstance(tool_call, dict):
            compatible_action_string = f"<tool_call>{json.dumps(tool_call)}</tool_call>"
        else:
            compatible_action_string = f"<tool_call>{json.dumps({'name': str(tool_call), 'arguments': {}})}</tool_call>"
        
        print(f'[DEBUG {turn_info}] [迭代] 🚀 执行工具: {tool.name}')
        tool_result, reward, done, info = tool.execute(compatible_action_string)
        print(f'[DEBUG {turn_info}] [迭代] ✅ 工具执行完成: reward={reward:.3f}')
        
        # 构建observation
        result_prompt = (
            f"\n<|im_start|>user\n"
            f"<tool_response><image>"
            f"Applied tool: {tool.name}. "
            f"You can continue with another tool or provide final answer."
            f"</tool_response>"
            f"<|im_end|>\n<|im_start|>assistant\n"
        )
        
        if isinstance(tool_result, dict) and 'multi_modal_data' in tool_result:
            output_image_data = tool_result['multi_modal_data']
        else:
            output_image_data = input_image_data
        
        final_tool_result = {
            "prompt": result_prompt,
            "multi_modal_data": output_image_data
        }
        
        info.update({
            "status": "success",
            "executed_tools": [tool.name],
            "tool_chain": tool.name,
            "mode": "iterative",
            "remaining_tools": len(tools) - 1
        })
        
        # 后处理
        return _post_process_tool_result(final_tool_result, info, reward, done, 
                                         tokenizer, processor, turn_info, pbar)
        
    except Exception as e:
        print(f'[ERROR {turn_info}] [迭代] ❌ 工具执行失败: {str(e)}')
        import traceback
        traceback.print_exc()
        
        error_msg = f"Tool execution failed: {str(e)}"
        error_text = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        obs_token_ids = tokenizer.encode(error_text, add_special_tokens=False)
        error_obs = {
            "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
            "prompt_token_ids_model": torch.tensor(obs_token_ids),
        }
        return error_obs, -0.1, False, {"error": error_msg, "status": "failed"}


def _post_process_tool_result(final_tool_result, final_info, total_reward, final_done, 
                               tokenizer, processor, turn_info, pbar):
    """
    工具结果的统一后处理逻辑
    """
    from copy import deepcopy
    import torch
    
    try:
        if not final_tool_result:
            tool_result_info = {}

        elif isinstance(final_tool_result, str):
            obs_token_ids = tokenizer.encode(final_tool_result, add_special_tokens=False)
            tool_result_info = {
                "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
                "prompt_token_ids_model": torch.tensor(obs_token_ids),
            }

        elif isinstance(final_tool_result, dict):
            prompt_str = final_tool_result.pop("prompt", "")
            chat_list = final_tool_result.pop("chat", [])

            if len(prompt_str) == 0 and len(chat_list) > 0:
                prompt_str = tokenizer.apply_chat_template(chat_list, add_generation_prompt=True, tokenize=False)
                prompt_str = _strip_system_block(prompt_str)

            # 保存原始PIL图像
            original_multi_modal_data_for_reward = deepcopy(final_tool_result.get("multi_modal_data", {}))
            
            # 预处理multi_modal输入
            prompt_str_vllm, obs_token_ids_model, mm_inputs = _preprocess_multi_modal_inputs(prompt_str, processor, **final_tool_result)
            obs_token_ids_vllm = tokenizer.encode(prompt_str_vllm, add_special_tokens=False, return_tensors='pt')[0]
            tool_result_info = {
                "prompt_token_ids_vllm": obs_token_ids_vllm,
                "prompt_token_ids_model": obs_token_ids_model,
                **final_tool_result
            }
            if mm_inputs:
                tool_result_info["multi_modal_inputs"] = mm_inputs
            
            # 添加原始图像用于reward计算
            tool_result_info["multi_modal_data_for_reward"] = original_multi_modal_data_for_reward

        else:
            raise ValueError(f"Invalid tool_result type: {type(final_tool_result)}")
        
        if pbar is not None:
            pbar.update(1)
        
        return tool_result_info, total_reward, final_done, final_info
        
    except Exception as post_process_error:
        print(f'[ERROR {turn_info}] ❌ 工具结果后处理失败: {str(post_process_error)}')
        import traceback
        traceback.print_exc()
        
        error_msg = f"Tool result post-processing failed: {str(post_process_error)}"
        error_text = f"\n<|im_start|>user\nError: {error_msg}<|im_end|>\n<|im_start|>assistant\n"
        obs_token_ids = tokenizer.encode(error_text, add_special_tokens=False)
        error_obs = {
            "prompt_token_ids_vllm": torch.tensor(obs_token_ids),
            "prompt_token_ids_model": torch.tensor(obs_token_ids),
        }
        return error_obs, total_reward, False, {"error": error_msg, "status": "failed"}


# =================================================================================
# 使用说明：
# 1. 将上述函数添加到 parallel_env.py 中
# 2. 将原有的 execute_tool_call 函数重命名或替换为 execute_tool_call_with_modes
# 3. 在 ParallelEnv.step() 中传递 tool_execution_mode 参数
# =================================================================================

# 在 ParallelEnv.step() 中修改 agent_inputs.append() 部分：
"""
agent_inputs.append(dict(
    idx=i,
    valid_idx=idx,
    action=action,
    tools=tools,
    parsed_output=parsed_output,
    turn_info=turn_info,
    origin_multi_modal_data=self.origin_multi_modal_data_list[idx],
    raw_prompt=self.raw_prompts[idx],
    current_multi_modal_data=self.get_current_image(idx),  # 🆕 添加当前图像
    tool_execution_mode=self.config.tool_execution_mode,   # 🆕 添加模式配置
))
"""

