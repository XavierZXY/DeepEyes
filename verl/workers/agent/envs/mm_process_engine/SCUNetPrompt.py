class PROMPT():
    """SCUNet denoising tool prompts"""
    
    USER_PROMPT_V1 = "The `{tool_name}` tool was applied successfully. Please analyze the new image for any remaining noise or degradations according to the denoising principle."

    USER_PROMPT_V2 = (
        "Here is the processed image after calling the function {}.\n"
        "If this image is sufficient to answer the user's question, please provide your final answer within <answer></answer>. "
        "Otherwise, you can continue to call tools within <tool_call></tool_call>."
    )

