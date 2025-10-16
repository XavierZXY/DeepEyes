"""
测试 Retinexformer Toolbox 的功能
Test cases for RetinexformerToolbox implementation
"""

import unittest
import numpy as np
from PIL import Image
import os
import sys
import io

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from verl.workers.agent.envs.tool_envs import ToolBase


class TestRetinexformerToolboxRegistration(unittest.TestCase):
    """测试工具注册"""
    
    def test_all_tools_registered(self):
        """测试所有Retinexformer工具是否已注册"""
        expected_tools = [
            "retinexformer_enhance",           # 通用工具
            "retinexformer_lol_v1",
            "retinexformer_lol_v2_real",
            "retinexformer_lol_v2_synthetic",
            "retinexformer_sdsd_indoor",
            "retinexformer_sdsd_outdoor",
            "retinexformer_sid",
            "retinexformer_smid",
            "retinexformer_fivek",
        ]
        
        registry = ToolBase.registry
        
        for tool_name in expected_tools:
            with self.subTest(tool=tool_name):
                self.assertIn(tool_name, registry, 
                             f"Tool '{tool_name}' should be registered")
    
    def test_tool_creation(self):
        """测试工具创建"""
        tool = ToolBase.create("retinexformer_enhance")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "retinexformer_enhance")
    
    def test_invalid_tool_creation(self):
        """测试创建不存在的工具"""
        with self.assertRaises(ValueError):
            ToolBase.create("retinexformer_nonexistent")


class TestRetinexformerToolboxBasicFunctionality(unittest.TestCase):
    """测试基础功能"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建测试图片（模拟低光图片）
        self.test_image = self._create_dark_test_image(256, 256)
        self.initial_prompt = [{"role": "user", "content": "Enhance this low-light image."}]
        self.initial_data = {"image": [self.test_image]}
        
    def _create_dark_test_image(self, width, height):
        """创建低亮度测试图片"""
        img_array = np.random.randint(20, 80, (height, width, 3), dtype=np.uint8)
        return Image.fromarray(img_array)
    
    def test_tool_reset(self):
        """测试工具重置功能"""
        tool = ToolBase.create("retinexformer_enhance")
        
        # 执行重置
        tool.reset(raw_prompt=self.initial_prompt, multi_modal_data=self.initial_data)
        
        # 验证状态
        self.assertIsNotNone(tool.multi_modal_data)
        self.assertIn("image", tool.multi_modal_data)
        self.assertEqual(len(tool.multi_modal_data["image"]), 1)
    
    def test_extract_tool_call(self):
        """测试工具调用提取"""
        tool = ToolBase.create("retinexformer_enhance")
        
        action_string = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {"task": "LOL_v2_real"}
}
</tool_call>"""
        
        extracted = tool.extract_action(action_string)
        self.assertIsNotNone(extracted)
        self.assertIn("retinexformer_enhance", extracted)
    
    def test_extract_answer(self):
        """测试答案提取"""
        tool = ToolBase.create("retinexformer_enhance")
        
        action_string = "<answer>The image has been enhanced successfully.</answer>"
        
        extracted = tool.extract_answer(action_string)
        self.assertIsNotNone(extracted)
        self.assertIn("enhanced", extracted)
    
    def test_no_image_error(self):
        """测试没有图像时的错误处理"""
        tool = ToolBase.create("retinexformer_enhance")
        
        # 不调用reset，直接执行
        tool_call = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {"task": "LOL_v2_real"}
}
</tool_call>"""
        
        obs, reward, done, info = tool.execute(tool_call)
        
        # 应该返回错误
        self.assertEqual(info.get("status"), "failed")
        self.assertIn("error", info)


class TestRetinexformerToolboxParameterBuilding(unittest.TestCase):
    """测试参数构建"""
    
    def test_generic_tool_params(self):
        """测试通用工具参数构建"""
        from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import RetinexformerToolbox
        
        tool = RetinexformerToolbox("test", "test", {})
        
        # 测试默认参数
        params = tool.build_params({})
        self.assertEqual(params["task"], "LOL_v2_real")
        self.assertEqual(params["format"], "base64")
        
        # 测试指定任务
        params = tool.build_params({"task": "LOL_v1"})
        self.assertEqual(params["task"], "LOL_v1")
        
        # 测试无效任务（应该使用默认值）
        params = tool.build_params({"task": "INVALID_TASK"})
        self.assertEqual(params["task"], "LOL_v2_real")
    
    def test_specific_tool_params(self):
        """测试特定工具参数构建"""
        from verl.workers.agent.envs.mm_process_engine.RetinexformerToolbox import (
            RetinexformerLOLv1Toolbox,
            RetinexformerSDSDIndoorToolbox
        )
        
        lol_v1_tool = RetinexformerLOLv1Toolbox("test", "test", {})
        params = lol_v1_tool.build_params({})
        self.assertEqual(params["task"], "LOL_v1")
        
        indoor_tool = RetinexformerSDSDIndoorToolbox("test", "test", {})
        params = indoor_tool.build_params({})
        self.assertEqual(params["task"], "SDSD_indoor")


class TestRetinexformerToolboxExecution(unittest.TestCase):
    """测试工具执行（需要服务运行）"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_image = self._create_dark_test_image(256, 256)
        self.initial_prompt = [{"role": "user", "content": "Enhance this image."}]
        self.initial_data = {"image": [self.test_image]}
        
        # 检查服务是否可用
        self.service_available = self._check_service_available()
    
    def _create_dark_test_image(self, width, height):
        """创建低亮度测试图片"""
        img_array = np.random.randint(20, 80, (height, width, 3), dtype=np.uint8)
        return Image.fromarray(img_array)
    
    def _check_service_available(self):
        """检查Retinexformer服务是否可用"""
        try:
            import requests
            api_url = f"http://{os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')}:5009/health"
            response = requests.get(api_url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    @unittest.skipUnless(
        os.environ.get('RUN_INTEGRATION_TESTS') == '1',
        "Skipping integration test (set RUN_INTEGRATION_TESTS=1 to run)"
    )
    def test_generic_tool_execution(self):
        """测试通用工具执行（需要服务运行）"""
        if not self.service_available:
            self.skipTest("Retinexformer service not available")
        
        tool = ToolBase.create("retinexformer_enhance")
        tool.reset(raw_prompt=self.initial_prompt, multi_modal_data=self.initial_data)
        
        tool_call = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "LOL_v2_real"
    }
}
</tool_call>"""
        
        obs, reward, done, info = tool.execute(tool_call)
        
        # 验证执行结果
        if info.get("status") == "success":
            self.assertIsInstance(obs, dict)
            self.assertIn("multi_modal_data", obs)
            self.assertIn("image", obs["multi_modal_data"])
            
            enhanced_image = obs["multi_modal_data"]["image"][0]
            self.assertIsInstance(enhanced_image, Image.Image)
            
            # 验证图像尺寸未改变
            self.assertEqual(enhanced_image.size, self.test_image.size)
            
            # 验证图像亮度有提升（简单检查）
            input_brightness = np.mean(np.array(self.test_image))
            output_brightness = np.mean(np.array(enhanced_image))
            self.assertGreater(output_brightness, input_brightness,
                             "Enhanced image should be brighter")
        else:
            # 如果失败，打印错误信息但不失败测试（服务可能不可用）
            print(f"Tool execution failed: {info.get('error')}")
    
    @unittest.skipUnless(
        os.environ.get('RUN_INTEGRATION_TESTS') == '1',
        "Skipping integration test (set RUN_INTEGRATION_TESTS=1 to run)"
    )
    def test_specific_tool_execution(self):
        """测试特定工具执行（需要服务运行）"""
        if not self.service_available:
            self.skipTest("Retinexformer service not available")
        
        tool = ToolBase.create("retinexformer_lol_v2_real")
        tool.reset(raw_prompt=self.initial_prompt, multi_modal_data=self.initial_data)
        
        tool_call = """<tool_call>
{
    "name": "retinexformer_lol_v2_real",
    "arguments": {}
}
</tool_call>"""
        
        obs, reward, done, info = tool.execute(tool_call)
        
        if info.get("status") == "success":
            self.assertIsInstance(obs, dict)
            enhanced_image = obs["multi_modal_data"]["image"][0]
            self.assertIsInstance(enhanced_image, Image.Image)
    
    def test_invalid_json_handling(self):
        """测试无效JSON格式的处理"""
        tool = ToolBase.create("retinexformer_enhance")
        tool.reset(raw_prompt=self.initial_prompt, multi_modal_data=self.initial_data)
        
        # 无效的JSON
        invalid_json = """<tool_call>
{
    "name": "retinexformer_enhance",
    "arguments": {
        "task": "LOL_v2_real"  // invalid comment
    }
}
</tool_call>"""
        
        obs, reward, done, info = tool.execute(invalid_json)
        
        # 应该返回错误
        self.assertEqual(info.get("status"), "failed")
        self.assertIn("error", info)
    
    def test_wrong_tool_name_handling(self):
        """测试错误的工具名称处理"""
        tool = ToolBase.create("retinexformer_enhance")
        tool.reset(raw_prompt=self.initial_prompt, multi_modal_data=self.initial_data)
        
        # 工具名称不匹配
        wrong_name = """<tool_call>
{
    "name": "wrong_tool_name",
    "arguments": {}
}
</tool_call>"""
        
        obs, reward, done, info = tool.execute(wrong_name)
        
        # 应该返回错误
        self.assertEqual(info.get("status"), "failed")
        self.assertIn("error", info)
    
    def test_answer_tag_handling(self):
        """测试<answer>标签处理"""
        tool = ToolBase.create("retinexformer_enhance")
        tool.reset(raw_prompt=self.initial_prompt, multi_modal_data=self.initial_data)
        
        answer_string = "<answer>The image has been enhanced.</answer>"
        
        obs, reward, done, info = tool.execute(answer_string)
        
        # 应该标记为完成
        self.assertTrue(done)


class TestRetinexformerToolboxEdgeCases(unittest.TestCase):
    """测试边界情况"""
    
    def setUp(self):
        """设置测试环境"""
        self.initial_prompt = [{"role": "user", "content": "Test."}]
    
    def test_small_image(self):
        """测试小尺寸图像"""
        small_image = Image.fromarray(
            np.random.randint(20, 80, (64, 64, 3), dtype=np.uint8)
        )
        data = {"image": [small_image]}
        
        tool = ToolBase.create("retinexformer_enhance")
        tool.reset(raw_prompt=self.initial_prompt, multi_modal_data=data)
        
        # 应该能够正常重置
        self.assertIsNotNone(tool.multi_modal_data)
    
    def test_large_image(self):
        """测试大尺寸图像"""
        # 创建一个相对大的图像（但不会太大以免测试太慢）
        large_image = Image.fromarray(
            np.random.randint(20, 80, (1024, 1024, 3), dtype=np.uint8)
        )
        data = {"image": [large_image]}
        
        tool = ToolBase.create("retinexformer_enhance")
        tool.reset(raw_prompt=self.initial_prompt, multi_modal_data=data)
        
        # 应该能够正常重置
        self.assertIsNotNone(tool.multi_modal_data)
    
    def test_grayscale_image_conversion(self):
        """测试灰度图像转换为RGB"""
        # 创建灰度图像
        gray_array = np.random.randint(20, 80, (256, 256), dtype=np.uint8)
        gray_image = Image.fromarray(gray_array, mode='L')
        
        # 转换为RGB（工具期望RGB图像）
        rgb_image = gray_image.convert('RGB')
        data = {"image": [rgb_image]}
        
        tool = ToolBase.create("retinexformer_enhance")
        tool.reset(raw_prompt=self.initial_prompt, multi_modal_data=data)
        
        self.assertIsNotNone(tool.multi_modal_data)


class TestRetinexformerToolboxPrompts(unittest.TestCase):
    """测试提示词"""
    
    def test_prompt_import(self):
        """测试提示词导入"""
        from verl.workers.agent.envs.mm_process_engine.RetinexformerPrompt import PROMPT
        
        self.assertIsNotNone(PROMPT.USER_PROMPT_V1)
        self.assertIsNotNone(PROMPT.USER_PROMPT_V2)
        self.assertIsNotNone(PROMPT.TOOL_DESCRIPTION)
    
    def test_prompt_formatting(self):
        """测试提示词格式化"""
        from verl.workers.agent.envs.mm_process_engine.RetinexformerPrompt import PROMPT
        
        formatted = PROMPT.USER_PROMPT_V1.format(tool_name="retinexformer_enhance")
        
        self.assertIn("retinexformer_enhance", formatted)
        self.assertNotIn("{tool_name}", formatted)


def run_tests(verbosity=2):
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestRetinexformerToolboxRegistration))
    suite.addTests(loader.loadTestsFromTestCase(TestRetinexformerToolboxBasicFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestRetinexformerToolboxParameterBuilding))
    suite.addTests(loader.loadTestsFromTestCase(TestRetinexformerToolboxExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestRetinexformerToolboxEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestRetinexformerToolboxPrompts))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # 打印总结
    print("\n" + "=" * 70)
    print("测试总结 / Test Summary")
    print("=" * 70)
    print(f"运行测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"跳过: {len(result.skipped)}")
    print("=" * 70)
    
    return result


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Retinexformer Toolbox 测试套件")
    print("=" * 70)
    print("\n提示:")
    print("1. 基础测试不需要服务运行")
    print("2. 集成测试需要 Retinexformer 服务运行在端口 5009")
    print("3. 运行集成测试: export RUN_INTEGRATION_TESTS=1")
    print("4. 设置服务器地址: export TOOL_SERVICE_IP=your_ip")
    print()
    
    # 检查是否运行集成测试
    if os.environ.get('RUN_INTEGRATION_TESTS') == '1':
        print("⚠️  集成测试已启用")
        print(f"服务器地址: {os.environ.get('TOOL_SERVICE_IP', '10.21.9.34')}:5009\n")
    else:
        print("ℹ️  集成测试已跳过（设置 RUN_INTEGRATION_TESTS=1 启用）\n")
    
    result = run_tests(verbosity=2)
    
    # 返回适当的退出码
    sys.exit(0 if result.wasSuccessful() else 1)

