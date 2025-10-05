# Copyright 2024 Bytedance Ltd. and/or its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import base64
import numpy as np
from typing import Union, Tuple
from PIL import Image
import torch

try:
    from skimage.metrics import structural_similarity as ssim
    from skimage.metrics import peak_signal_noise_ratio as psnr
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False
    print("[WARNING] scikit-image not found. SSIM and PSNR will not be available.")

try:
    import lpips
    HAS_LPIPS = True
except ImportError:
    HAS_LPIPS = False
    print("[WARNING] lpips not found. LPIPS will not be available.")


class ImageQualityMetrics:
    """
    计算图像质量指标：SSIM、LPIPS、PSNR
    """
    
    def __init__(self, lpips_net: str = 'alex'):
        """
        初始化图像质量评估器
        
        Args:
            lpips_net: LPIPS网络类型，可选 'alex', 'vgg', 'squeeze'
        """
        self.lpips_net = lpips_net
        self._lpips_model = None
        
        if HAS_LPIPS:
            try:
                self._lpips_model = lpips.LPIPS(net=lpips_net)
                # 只在需要时移到GPU，而不是初始化时就移到GPU
                # if torch.cuda.is_available():
                #     self._lpips_model = self._lpips_model.cuda()
            except Exception as e:
                print(f"[WARNING] Failed to initialize LPIPS model: {e}")
                self._lpips_model = None
    
    def _prepare_image(self, image_data: Union[str, bytes, np.ndarray, Image.Image]) -> np.ndarray:
        """
        将不同格式的图像数据转换为numpy数组
        
        Args:
            image_data: 图像数据，可以是base64字符串、bytes、numpy数组或PIL图像
            
        Returns:
            numpy数组格式的图像 (H, W, C)，值范围[0, 255]
        """
        if isinstance(image_data, str):
            # 假设是base64编码的图像
            try:
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))
            except Exception:
                raise ValueError("Invalid base64 image data")
        elif isinstance(image_data, bytes):
            # 原始字节数据
            image = Image.open(io.BytesIO(image_data))
        elif isinstance(image_data, Image.Image):
            # PIL图像
            image = image_data
        elif isinstance(image_data, np.ndarray):
            # 已经是numpy数组
            if image_data.dtype == np.float32 or image_data.dtype == np.float64:
                if image_data.max() <= 1.0:
                    # 假设是[0,1]范围，转换到[0,255]
                    image_data = (image_data * 255).astype(np.uint8)
            return image_data
        else:
            raise ValueError(f"Unsupported image data type: {type(image_data)}")
        
        # 转换PIL图像到numpy数组
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        return np.array(image)
    
    def _handle_size_mismatch(self, image1: np.ndarray, image2: np.ndarray, metric_name: str = "") -> tuple:
        """
        处理图像尺寸不匹配的情况，特别针对超分辨率场景
        
        Args:
            image1: 第一张图像
            image2: 第二张图像
            metric_name: 指标名称（用于调试）
            
        Returns:
            (处理后的image1, 处理后的image2)
        """
        if image1.shape == image2.shape:
            return image1, image2
            
        h1, w1 = image1.shape[:2]
        h2, w2 = image2.shape[:2]
        print(f"[DEBUG {metric_name}] 图像尺寸不匹配: image1={h1}x{w1}, image2={h2}x{w2}")
        
        # 策略1：如果一个图像是另一个的整数倍（常见于超分场景）
        scale_h1_to_h2 = h2 / h1 if h1 > 0 else 0
        scale_w1_to_w2 = w2 / w1 if w1 > 0 else 0
        scale_h2_to_h1 = h1 / h2 if h2 > 0 else 0
        scale_w2_to_w1 = w1 / w2 if w2 > 0 else 0
        
        # 检查是否是整数倍关系（允许小的误差）
        def is_integer_scale(scale):
            return abs(scale - round(scale)) < 0.01 and scale >= 1.0
        
        if (is_integer_scale(scale_h1_to_h2) and is_integer_scale(scale_w1_to_w2)):
            # image2是image1的整数倍，下采样image2
            image2 = self._resize_image(image2, (h1, w1))
            print(f"[DEBUG {metric_name}] 下采样较大图像到{h1}x{w1} (缩放比例: {scale_h1_to_h2:.1f}x)")
        elif (is_integer_scale(scale_h2_to_h1) and is_integer_scale(scale_w2_to_w1)):
            # image1是image2的整数倍，下采样image1
            image1 = self._resize_image(image1, (h2, w2))
            print(f"[DEBUG {metric_name}] 下采样较大图像到{h2}x{w2} (缩放比例: {scale_h2_to_h1:.1f}x)")
        else:
            # 策略2：非整数倍关系，调整到相同尺寸（使用较小的尺寸以避免信息丢失）
            min_h = min(h1, h2)
            min_w = min(w1, w2)
            image1 = image1[:min_h, :min_w]
            image2 = image2[:min_h, :min_w]
            print(f"[DEBUG {metric_name}] 裁剪到相同尺寸: {min_h}x{min_w}")
            
        return image1, image2
    
    def _resize_image(self, image: np.ndarray, target_size: tuple) -> np.ndarray:
        """
        调整图像尺寸
        
        Args:
            image: numpy数组图像 (H, W, C)
            target_size: 目标尺寸 (H, W)
            
        Returns:
            调整后的图像
        """
        try:
            from PIL import Image as PILImage
            
            # 转换为PIL图像进行resize
            if len(image.shape) == 3:
                pil_image = PILImage.fromarray(image)
            else:
                pil_image = PILImage.fromarray(image, mode='L')
            
            # 使用高质量的重采样方法
            resized_pil = pil_image.resize((target_size[1], target_size[0]), PILImage.Resampling.LANCZOS)
            
            # 转换回numpy数组
            return np.array(resized_pil)
            
        except Exception as e:
            print(f"[WARNING] Image resize failed: {e}, using simple crop instead")
            # 降级到简单裁剪
            target_h, target_w = target_size
            return image[:target_h, :target_w]
    
    def _normalize_image_for_lpips(self, image: np.ndarray) -> torch.Tensor:
        """
        为LPIPS计算准备图像张量
        
        Args:
            image: numpy数组图像 (H, W, C)，值范围[0, 255]
            
        Returns:
            torch张量 (1, C, H, W)，值范围[-1, 1]
        """
        # 转换到[0, 1]
        image = image.astype(np.float32) / 255.0
        
        # 转换到[-1, 1] (LPIPS期望的范围)
        image = image * 2.0 - 1.0
        
        # 转换维度从 (H, W, C) 到 (C, H, W) 并添加batch维度
        image_tensor = torch.from_numpy(image.transpose(2, 0, 1)).unsqueeze(0)
        
        # 保持tensor在CPU上，只在计算时临时移到GPU
        # if torch.cuda.is_available() and self._lpips_model is not None:
        #     # 获取LPIPS模型所在的设备
        #     model_device = next(self._lpips_model.parameters()).device
        #     image_tensor = image_tensor.to(model_device)
            
        return image_tensor
    
    def calculate_ssim(self, img1: Union[str, bytes, np.ndarray, Image.Image], 
                      img2: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """
        计算SSIM (Structural Similarity Index)
        
        Args:
            img1: 第一张图像
            img2: 第二张图像
            
        Returns:
            SSIM值，范围[-1, 1]，值越大表示相似度越高
        """
        if not HAS_SKIMAGE:
            raise RuntimeError("scikit-image is required for SSIM calculation")
        
        try:
            image1 = self._prepare_image(img1)
            image2 = self._prepare_image(img2)
            
            # 处理图像尺寸不匹配的情况
            image1, image2 = self._handle_size_mismatch(image1, image2, "SSIM")
            
            # 计算SSIM
            if len(image1.shape) == 3:  # RGB图像
                ssim_value = ssim(image1, image2, channel_axis=2, data_range=255)
            else:  # 灰度图像
                ssim_value = ssim(image1, image2, data_range=255)
                
            return float(ssim_value)
        except Exception as e:
            print(f"[WARNING] SSIM calculation failed: {e}")
            return 0.0
    
    def calculate_psnr(self, img1: Union[str, bytes, np.ndarray, Image.Image], 
                      img2: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """
        计算PSNR (Peak Signal-to-Noise Ratio)
        
        Args:
            img1: 第一张图像
            img2: 第二张图像
            
        Returns:
            PSNR值，单位dB，值越大表示质量越好
        """
        if not HAS_SKIMAGE:
            raise RuntimeError("scikit-image is required for PSNR calculation")
        
        try:
            image1 = self._prepare_image(img1)
            image2 = self._prepare_image(img2)
            
            # 处理图像尺寸不匹配的情况
            image1, image2 = self._handle_size_mismatch(image1, image2, "PSNR")
            
            # 计算PSNR
            psnr_value = psnr(image1, image2, data_range=255)
            return float(psnr_value)
        except Exception as e:
            print(f"[WARNING] PSNR calculation failed: {e}")
            return 0.0
    
    def calculate_lpips(self, img1: Union[str, bytes, np.ndarray, Image.Image], 
                       img2: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """
        计算LPIPS (Learned Perceptual Image Patch Similarity)
        
        Args:
            img1: 第一张图像
            img2: 第二张图像
            
        Returns:
            LPIPS值，范围[0, 1]，值越小表示感知相似度越高
        """
        if not HAS_LPIPS or self._lpips_model is None:
            print("[WARNING] LPIPS model not available, returning 0.0")
            return 0.0
        
        try:
            image1 = self._prepare_image(img1)
            image2 = self._prepare_image(img2)
            
            # 处理图像尺寸不匹配的情况
            image1, image2 = self._handle_size_mismatch(image1, image2, "LPIPS")
            
            # 转换为LPIPS所需的张量格式（保持在CPU）
            tensor1 = self._normalize_image_for_lpips(image1)
            tensor2 = self._normalize_image_for_lpips(image2)
            
            # 临时移到GPU计算，然后立即清理
            with torch.no_grad():
                # 检查是否需要移到GPU
                if torch.cuda.is_available() and self._lpips_model is not None:
                    # 临时移动模型和数据到GPU
                    model_device = 'cuda' if torch.cuda.is_available() else 'cpu'
                    model_on_gpu = self._lpips_model.to(model_device)
                    tensor1_gpu = tensor1.to(model_device)
                    tensor2_gpu = tensor2.to(model_device)
                    
                    # 计算LPIPS
                    lpips_value = model_on_gpu(tensor1_gpu, tensor2_gpu)
                    result = float(lpips_value.item())
                    
                    # 立即清理GPU内存
                    del tensor1_gpu, tensor2_gpu, lpips_value
                    # 将模型移回CPU以释放GPU内存
                    self._lpips_model = self._lpips_model.cpu()
                    torch.cuda.empty_cache()
                else:
                    # CPU计算
                    lpips_value = self._lpips_model(tensor1, tensor2)
                    result = float(lpips_value.item())
                
                # 清理CPU tensor
                del tensor1, tensor2
                
            return result
        except Exception as e:
            print(f"[WARNING] LPIPS calculation failed: {e}")
            return 0.0
    
    def calculate_all_metrics(self, img1: Union[str, bytes, np.ndarray, Image.Image], 
                             img2: Union[str, bytes, np.ndarray, Image.Image]) -> dict:
        """
        计算所有图像质量指标
        
        Args:
            img1: 第一张图像
            img2: 第二张图像
            
        Returns:
            包含所有指标的字典
        """
        metrics = {}
        
        try:
            metrics['ssim'] = self.calculate_ssim(img1, img2)
        except Exception as e:
            print(f"[WARNING] SSIM calculation failed: {e}")
            metrics['ssim'] = 0.0
            
        try:
            metrics['psnr'] = self.calculate_psnr(img1, img2)
        except Exception as e:
            print(f"[WARNING] PSNR calculation failed: {e}")
            metrics['psnr'] = 0.0
            
        try:
            metrics['lpips'] = self.calculate_lpips(img1, img2)
        except Exception as e:
            print(f"[WARNING] LPIPS calculation failed: {e}")
            metrics['lpips'] = 0.0
            
        return metrics


def normalize_metrics(ssim: float, lpips: float, psnr: float, 
                     ssim_range: Tuple[float, float] = (-1.0, 1.0),
                     lpips_range: Tuple[float, float] = (0.0, 1.0),
                     psnr_range: Tuple[float, float] = (0.0, 50.0)) -> Tuple[float, float, float]:
    """
    归一化图像质量指标到[0, 1]范围
    
    Args:
        ssim: SSIM值
        lpips: LPIPS值
        psnr: PSNR值
        ssim_range: SSIM的预期范围
        lpips_range: LPIPS的预期范围
        psnr_range: PSNR的预期范围
        
    Returns:
        归一化后的 (ssim, lpips, psnr) 元组
    """
    def normalize(value, min_val, max_val):
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
    
    norm_ssim = normalize(ssim, ssim_range[0], ssim_range[1])
    norm_lpips = normalize(lpips, lpips_range[0], lpips_range[1])
    norm_psnr = normalize(psnr, psnr_range[0], psnr_range[1])
    
    return norm_ssim, norm_lpips, norm_psnr


def cleanup_gpu_memory():
    """清理GPU内存"""
    try:
        if torch.cuda.is_available():
            # 获取清理前的内存使用
            before_cleanup = torch.cuda.memory_allocated() / 1024**2  # MB
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            # 获取清理后的内存使用
            after_cleanup = torch.cuda.memory_allocated() / 1024**2  # MB
            if before_cleanup > after_cleanup:
                print(f"[DEBUG] GPU内存清理: {before_cleanup:.1f}MB -> {after_cleanup:.1f}MB (释放{before_cleanup-after_cleanup:.1f}MB)")
    except Exception as e:
        print(f"[WARNING] GPU cleanup failed: {e}")


def compute_image_restoration_reward(img1: Union[str, bytes, np.ndarray, Image.Image], 
                                   img2: Union[str, bytes, np.ndarray, Image.Image],
                                   alpha: float = 0.4, 
                                   beta: float = 0.4, 
                                   gamma: float = 0.2,
                                   metrics_calculator: ImageQualityMetrics = None) -> float:
    """
    计算图像复原奖励函数
    
    r_final(x̂, x) = α * SSIM_norm(x̂, x) + β * (1 - LPIPS_norm(x̂, x)) + γ * PSNR_norm(x̂, x)
    
    Args:
        img1: 复原后的图像
        img2: 原始图像
        alpha: SSIM权重
        beta: LPIPS权重
        gamma: PSNR权重
        metrics_calculator: 图像质量计算器实例
        
    Returns:
        奖励分数，范围[0, 1]
    """
    if metrics_calculator is None:
        metrics_calculator = ImageQualityMetrics()
    
    # 计算原始指标
    metrics = metrics_calculator.calculate_all_metrics(img1, img2)
    ssim_val = metrics['ssim']
    lpips_val = metrics['lpips']
    psnr_val = metrics['psnr']
    
    # 归一化指标
    norm_ssim, norm_lpips, norm_psnr = normalize_metrics(ssim_val, lpips_val, psnr_val)
    
    # 计算最终奖励
    reward = alpha * norm_ssim + beta * (1.0 - norm_lpips) + gamma * norm_psnr
    
    # 确保奖励在[0, 1]范围内
    reward = max(0.0, min(1.0, reward))
    
    print(f' [DEBUG image_quality] ssim={ssim_val:.4f}(norm={norm_ssim:.4f}), '
          f'lpips={lpips_val:.4f}(norm={norm_lpips:.4f}), '
          f'psnr={psnr_val:.4f}(norm={norm_psnr:.4f})')
    print(f' [DEBUG image_quality] weights: α={alpha}, β={beta}, γ={gamma}')
    print(f' [DEBUG image_quality] reward={reward:.4f}')
    
    # 清理GPU内存
    cleanup_gpu_memory()
    
    return reward


# 测试函数
def test_image_quality_metrics():
    """测试图像质量指标计算"""
    print("Testing Image Quality Metrics...")
    
    # 创建测试图像
    test_img1 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    test_img2 = test_img1 + np.random.randint(-10, 10, (100, 100, 3), dtype=np.int16)
    test_img2 = np.clip(test_img2, 0, 255).astype(np.uint8)
    
    calculator = ImageQualityMetrics()
    
    # 测试各个指标
    print("\nTesting individual metrics:")
    ssim_val = calculator.calculate_ssim(test_img1, test_img2)
    print(f"SSIM: {ssim_val:.4f}")
    
    psnr_val = calculator.calculate_psnr(test_img1, test_img2)
    print(f"PSNR: {psnr_val:.4f}")
    
    lpips_val = calculator.calculate_lpips(test_img1, test_img2)
    print(f"LPIPS: {lpips_val:.4f}")
    
    # 测试综合奖励
    print("\nTesting combined reward:")
    reward = compute_image_restoration_reward(test_img1, test_img2, metrics_calculator=calculator)
    print(f"Final reward: {reward:.4f}")


if __name__ == "__main__":
    test_image_quality_metrics()
