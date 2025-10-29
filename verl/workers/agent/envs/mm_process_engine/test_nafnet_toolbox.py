#!/usr/bin/env python3
"""
测试 NAFNet 工具箱
验证工具注册、创建、参数构建和基本功能
"""

import sys
import os
import unittest
from io import BytesIO
import numpy as np
from PIL import Image

# 设置项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from verl.workers.agent.tool_envs import ToolBase

class TestNAFNetToolboxRegistration(unittest.TestCase):
    """测试 NAFNet 工具注册"""
    
    @classmethod
    def setUpClass(cls):
        """确保工具已注册"""
        # 导入agent模块以触发工具注册
        from verl.workers import agent
    
    def test_tool_registered(self):
        """测试工具是否已注册"""
        self.assertIn("nafnet_deblur", ToolBase.registry, 
                     "NAFNet deblur tool should be registered")
    
    def test_tool_class_name(self):
        """测试工具类名是否正确"""
        tool_class = ToolBase.registry.get("nafnet_deblur")
        self.assertIsNotNone(tool_class, "Tool class should not be None")
        self.assertEqual(tool_class.__name__, "NAFNetDeblurToolbox",
                        "Tool class name should be NAFNetDeblurToolbox")
    
    def test_create_tool_instance(self):
        """测试创建工具实例"""
        try:
            tool = ToolBase.create("nafnet_deblur")
            self.assertIsNotNone(tool, "Tool instance should not be None")
            self.assertEqual(tool.name, "nafnet_deblur", 
                           "Tool name should be nafnet_deblur")
            self.assertEqual(tool.task_name, "deblur",
                           "Task name should be deblur")
        except Exception as e:
            self.fail(f"Failed to create tool instance: {e}")
    
    def test_invalid_tool_name(self):
        """测试创建不存在的工具"""
        with self.assertRaises(ValueError):
            ToolBase.create("nafnet_nonexistent")

class TestNAFNetToolboxBasicFunctionality(unittest.TestCase):
    """测试 NAFNet 工具基本功能"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        from verl.workers import agent
        cls.tool = ToolBase.create("nafnet_deblur")
        
        # 创建测试图像
        test_img_array = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
        cls.test_image = Image.fromarray(test_img_array)
        
        # 初始化工具
        initial_prompt = [{"role": "user", "content": "Please deblur this image."}]
        initial_data = {"image": [cls.test_image]}
        cls.tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
    
    def test_tool_attributes(self):
        """测试工具属性"""
        self.assertEqual(self.tool.name, "nafnet_deblur")
        self.assertEqual(self.tool.task_name, "deblur")
        self.assertIn("5012", self.tool.api_url, 
                     "API URL should contain port 5012")
    
    def test_build_params_default(self):
        """测试默认参数构建"""
        params = self.tool.build_params({})
        self.assertEqual(params["task"], "deblur", 
                        "Task should be deblur")
        self.assertEqual(params["format"], "base64",
                        "Default format should be base64")
    
    def test_build_params_custom_format(self):
        """测试自定义格式参数"""
        params = self.tool.build_params({"format": "file"})
        self.assertEqual(params["task"], "deblur")
        self.assertEqual(params["format"], "file")
    
    def test_extract_answer(self):
        """测试提取答案标签"""
        action_string = "Some text <answer>This is the final answer</answer> more text"
        answer = self.tool.extract_answer(action_string)
        self.assertEqual(answer, "This is the final answer")
    
    def test_extract_answer_no_tag(self):
        """测试没有答案标签的情况"""
        action_string = "Some text without answer tag"
        answer = self.tool.extract_answer(action_string)
        self.assertIsNone(answer)
    
    def test_extract_action(self):
        """测试提取工具调用"""
        action_string = 'Text <tool_call>{"name": "nafnet_deblur"}</tool_call> more'
        action = self.tool.extract_action(action_string)
        self.assertIsNotNone(action)
        self.assertIn("nafnet_deblur", action)
    
    def test_reset_with_image(self):
        """测试重置工具状态"""
        new_img_array = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
        new_image = Image.fromarray(new_img_array)
        new_prompt = [{"role": "user", "content": "New prompt"}]
        new_data = {"image": [new_image]}
        
        self.tool.reset(raw_prompt=new_prompt, multi_modal_data=new_data)
        
        self.assertEqual(self.tool.chatml_history, new_prompt)
        self.assertEqual(self.tool.multi_modal_data, new_data)
        self.assertEqual(self.tool.multi_modal_data["image"][0].size, 
                        new_image.size)

class TestNAFNetToolboxExecutionFormat(unittest.TestCase):
    """测试 NAFNet 工具执行格式"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        from verl.workers import agent
        cls.tool = ToolBase.create("nafnet_deblur")
        
        # 创建测试图像
        test_img_array = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
        cls.test_image = Image.fromarray(test_img_array)
        
        # 初始化工具
        initial_prompt = [{"role": "user", "content": "Please deblur this image."}]
        initial_data = {"image": [cls.test_image]}
        cls.tool.reset(raw_prompt=initial_prompt, multi_modal_data=initial_data)
    
    def test_execute_with_answer(self):
        """测试执行带答案的操作"""
        action_string = '<answer>The image has been processed successfully.</answer>'
        obs, reward, done, info = self.tool.execute(action_string)
        
        self.assertEqual(obs, "")
        self.assertEqual(reward, 0.0)
        self.assertTrue(done)
        self.assertEqual(info, {})
    
    def test_execute_no_tags(self):
        """测试执行没有有效标签的操作"""
        action_string = 'Some text without valid tags'
        obs, reward, done, info = self.tool.execute(action_string)
        
        self.assertIn("Error", obs)
        self.assertEqual(reward, 0.0)
        self.assertFalse(done)
        self.assertEqual(info["status"], "failed")
    
    def test_execute_invalid_json(self):
        """测试执行无效JSON的操作"""
        action_string = '<tool_call>invalid json{}</tool_call>'
        obs, reward, done, info = self.tool.execute(action_string)
        
        self.assertIn("Error", obs)
        self.assertEqual(reward, 0.0)
        self.assertFalse(done)
        self.assertEqual(info["status"], "failed")
    
    def test_execute_wrong_tool_name(self):
        """测试执行错误工具名的操作"""
        action_string = '''<tool_call>
{
    "name": "wrong_tool_name",
    "arguments": {}
}
</tool_call>'''
        obs, reward, done, info = self.tool.execute(action_string)
        
        self.assertIn("Error", obs)
        self.assertFalse(done)
        self.assertEqual(info["status"], "failed")
    
    def test_execute_no_image(self):
        """测试执行时没有图像数据"""
        # 创建没有图像的工具实例
        tool_no_img = ToolBase.create("nafnet_deblur")
        tool_no_img.reset(
            raw_prompt=[{"role": "user", "content": "Test"}],
            multi_modal_data={"image": []}
        )
        
        action_string = '''<tool_call>
{
    "name": "nafnet_deblur",
    "arguments": {}
}
</tool_call>'''
        obs, reward, done, info = tool_no_img.execute(action_string)
        
        self.assertIn("Error", obs)
        self.assertIn("No image found", obs)
        self.assertFalse(done)
        self.assertEqual(info["status"], "failed")


def run_all_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestNAFNetToolboxRegistration))
    suite.addTests(loader.loadTestsFromTestCase(TestNAFNetToolboxBasicFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestNAFNetToolboxExecutionFormat))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回测试结果
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 80)
    print("测试 NAFNet 工具箱")
    print("=" * 80)
    
    success = run_all_tests()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ 所有测试通过！")
        sys.exit(0)
    else:
        print("❌ 部分测试失败！")
        sys.exit(1)

