"""
Prompt definitions for Retinexformer Low-light Enhancement Toolbox
"""

class PROMPT:
    """Retinexformer工具的提示词定义"""
    
    # 基础提示词 - 用于工具返回后的观察
    USER_PROMPT_V1 = (
        "The low-light image has been enhanced using the {tool_name}. "
        "The enhanced image is now available in the current state. "
        "Please analyze the enhanced image and provide your assessment."
    )
    
    # 替代提示词 - 更详细的描述
    USER_PROMPT_V2 = (
        "Image enhancement completed using {tool_name}. "
        "The lighting and visibility have been improved. "
        "You can now analyze the enhanced image to extract information or answer questions."
    )
    
    # 工具描述提示词
    TOOL_DESCRIPTION = (
        "A low-light image enhancement tool powered by Retinexformer. "
        "This tool can enhance images captured in low-light conditions by improving "
        "brightness, contrast, and overall visibility while preserving image details and colors. "
        "Multiple models are available for different scenarios (indoor, outdoor, synthetic, etc.)."
    )

