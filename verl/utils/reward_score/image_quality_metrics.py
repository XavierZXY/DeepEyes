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

# 无参考指标依赖
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("[WARNING] OpenCV not found. NIQE and BRISQUE will not be available.")

try:
    from transformers import CLIPProcessor, CLIPModel
    import torch.nn.functional as F
    HAS_CLIP = True
except ImportError:
    HAS_CLIP = False
    print("[WARNING] transformers not found. CLIP-IQA will not be available.")

try:
    import scipy
    from scipy.ndimage import generic_filter, uniform_filter
    from scipy.special import gamma
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("[WARNING] scipy not found. Some no-reference metrics may not be available.")

try:
    import pyiqa
    HAS_PYIQA = True
except ImportError:
    HAS_PYIQA = False
    print("[WARNING] pyiqa not found. Advanced IQA metrics will not be available.")


# 全局单例实例
_global_image_quality_metrics = None

def get_image_quality_metrics():
    """获取图像质量评估器的全局单例实例"""
    global _global_image_quality_metrics
    if _global_image_quality_metrics is None:
        print("[INFO] 初始化图像质量评估器（全局单例）...")
        _global_image_quality_metrics = ImageQualityMetrics()
        print("[INFO] 图像质量评估器初始化完成，后续调用将重用此实例")
    return _global_image_quality_metrics

class ImageQualityMetrics:
    """
    计算图像质量指标：支持有参考和无参考指标
    
    有参考指标：SSIM、LPIPS、PSNR（需要参考图像）
    无参考指标：NIQE、BRISQUE、CPBD、CLIP-IQA、Hyper-IQA（仅需要待评估图像）
    """
    
    def __init__(self, lpips_net: str = 'alex', clip_model_name: str = 'openai/clip-vit-base-patch32'):
        """
        初始化图像质量评估器
        
        Args:
            lpips_net: LPIPS网络类型，可选 'alex', 'vgg', 'squeeze'
            clip_model_name: CLIP模型名称，用于CLIP-IQA计算
        """
        self.lpips_net = lpips_net
        self.clip_model_name = clip_model_name
        self._lpips_model = None
        self._clip_model = None
        self._clip_processor = None
        self._pyiqa_models = {}
        
        # 初始化LPIPS模型（有参考指标）
        if HAS_LPIPS:
            try:
                self._lpips_model = lpips.LPIPS(net=lpips_net)
            except Exception as e:
                print(f"[WARNING] Failed to initialize LPIPS model: {e}")
                self._lpips_model = None
        
        # 初始化CLIP模型（用于CLIP-IQA）
        if HAS_CLIP:
            try:
                self._clip_processor = CLIPProcessor.from_pretrained(clip_model_name)
                self._clip_model = CLIPModel.from_pretrained(clip_model_name)
            except Exception as e:
                print(f"[WARNING] Failed to initialize CLIP model: {e}")
                self._clip_model = None
                self._clip_processor = None
        
        # 初始化PyIQA模型（统一使用pyiqa实现所有无参考指标）
        if HAS_PYIQA:
            try:
                # 初始化NIQE
                try:
                    self._pyiqa_models['niqe'] = pyiqa.create_metric('niqe')
                except Exception as e:
                    print(f"[WARNING] NIQE模型初始化失败: {e}")
                
                # 初始化BRISQUE
                try:
                    self._pyiqa_models['brisque'] = pyiqa.create_metric('brisque')
                except Exception as e:
                    print(f"[WARNING] BRISQUE模型初始化失败: {e}")
                
                # 初始化CLIP-IQA - 使用标准名称
                try:
                    self._pyiqa_models['clipiqa'] = pyiqa.create_metric('clipiqa')
                except Exception as e:
                    print(f"[WARNING] CLIP-IQA模型初始化失败: {e}")
                
                # 初始化Hyper-IQA - 使用标准名称
                try:
                    self._pyiqa_models['hyperiqa'] = pyiqa.create_metric('hyperiqa')
                except Exception as e:
                    print(f"[WARNING] Hyper-IQA模型初始化失败: {e}")
                
                # 初始化CPBD（PyIQA中不存在，使用自定义实现）
                try:
                    self._pyiqa_models['cpbd'] = pyiqa.create_metric('cpbd')
                except:
                    pass  # CPBD使用自定义实现
                
                print(f"[INFO] PyIQA模型初始化完成，成功加载: {list(self._pyiqa_models.keys())}")
                
            except Exception as e:
                print(f"[WARNING] Failed to initialize PyIQA models: {e}")
                self._pyiqa_models = {}
    
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
    
    # ==================== 无参考指标计算方法 ====================
    
    def calculate_niqe(self, img: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """
        计算NIQE (Natural Image Quality Evaluator)
        关注自然场景统计特征的无参考图像质量评估
        
        Args:
            img: 待评估的图像
            
        Returns:
            NIQE值，值越小表示质量越好（通常范围2-15）
        """
        try:
            if HAS_PYIQA and 'niqe' in self._pyiqa_models:
                image = self._prepare_image(img)
                # 转换为PyTorch tensor格式
                if len(image.shape) == 3:
                    image_tensor = torch.from_numpy(image.transpose(2, 0, 1)).unsqueeze(0).float() / 255.0
                else:
                    image_tensor = torch.from_numpy(image).unsqueeze(0).unsqueeze(0).float() / 255.0
                
                with torch.no_grad():
                    niqe_score = self._pyiqa_models['niqe'](image_tensor)
                    return float(niqe_score.item())
            
            # 备用实现：基于OpenCV的简化NIQE计算
            elif HAS_CV2 and HAS_SCIPY:
                return self._calculate_niqe_opencv(img)
            else:
                print("[WARNING] NIQE calculation requires pyiqa or opencv+scipy")
                return 5.0  # 返回中等质量分数
                
        except Exception as e:
            print(f"[WARNING] NIQE calculation failed: {e}")
            return 5.0
    
    def _calculate_niqe_opencv(self, img: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """使用OpenCV实现简化的NIQE计算"""
        try:
            image = self._prepare_image(img)
            
            # 转换为灰度图
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image
            
            gray = gray.astype(np.float64)
            
            # 计算局部均值和方差
            mu = cv2.GaussianBlur(gray, (7, 7), 1.166)
            mu_sq = mu * mu
            sigma = cv2.GaussianBlur(gray * gray, (7, 7), 1.166)
            sigma = (sigma - mu_sq) ** 0.5
            
            # 归一化
            structdis = (gray - mu) / (sigma + 1)
            
            # 计算统计特征
            features = []
            features.append(np.mean(structdis))
            features.append(np.var(structdis))
            features.append(scipy.stats.skew(structdis.flatten()))
            features.append(scipy.stats.kurtosis(structdis.flatten()))
            
            # 简化的NIQE分数计算
            niqe_score = np.sqrt(np.sum(np.square(features)))
            return float(niqe_score)
            
        except Exception as e:
            print(f"[WARNING] OpenCV NIQE calculation failed: {e}")
            return 5.0
    
    def calculate_brisque(self, img: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """
        计算BRISQUE (Blind/Referenceless Image Spatial Quality Evaluator)
        结合亮度和结构信息的无参考图像质量评估
        
        Args:
            img: 待评估的图像
            
        Returns:
            BRISQUE值，值越小表示质量越好（通常范围0-100）
        """
        try:
            if HAS_PYIQA and 'brisque' in self._pyiqa_models:
                image = self._prepare_image(img)
                # 转换为PyTorch tensor格式
                if len(image.shape) == 3:
                    image_tensor = torch.from_numpy(image.transpose(2, 0, 1)).unsqueeze(0).float() / 255.0
                else:
                    image_tensor = torch.from_numpy(image).unsqueeze(0).unsqueeze(0).float() / 255.0
                
                with torch.no_grad():
                    brisque_score = self._pyiqa_models['brisque'](image_tensor)
                    return float(brisque_score.item())
            
            # 备用实现：基于OpenCV的简化BRISQUE计算
            elif HAS_CV2 and HAS_SCIPY:
                return self._calculate_brisque_opencv(img)
            else:
                print("[WARNING] BRISQUE calculation requires pyiqa or opencv+scipy")
                return 30.0  # 返回中等质量分数
                
        except Exception as e:
            print(f"[WARNING] BRISQUE calculation failed: {e}")
            return 30.0
    
    def _calculate_brisque_opencv(self, img: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """使用OpenCV实现简化的BRISQUE计算"""
        try:
            image = self._prepare_image(img)
            
            # 转换为灰度图
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image
            
            gray = gray.astype(np.float64)
            
            # 计算MSCN系数
            mu = cv2.GaussianBlur(gray, (7, 7), 1.166)
            mu_sq = mu * mu
            sigma = cv2.GaussianBlur(gray * gray, (7, 7), 1.166)
            sigma = np.sqrt(np.abs(sigma - mu_sq))
            
            mscn = (gray - mu) / (sigma + 1e-10)
            
            # 计算统计特征
            alpha = np.mean(mscn)
            var = np.var(mscn)
            skew = scipy.stats.skew(mscn.flatten())
            kurt = scipy.stats.kurtosis(mscn.flatten())
            
            # 简化的BRISQUE分数计算
            features = [alpha, var, skew, kurt]
            brisque_score = np.sqrt(np.sum(np.square(features))) * 10
            return float(brisque_score)
            
        except Exception as e:
            print(f"[WARNING] OpenCV BRISQUE calculation failed: {e}")
            return 30.0
    
    def calculate_cpbd(self, img: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """
        计算CPBD (Cumulative Probability of Blur Detection)
        常用于评估模糊和压缩失真的无参考图像质量评估
        
        Args:
            img: 待评估的图像
            
        Returns:
            CPBD值，范围[0, 1]，值越大表示图像越清晰
        """
        try:
            # 优先使用pyiqa实现
            if HAS_PYIQA and 'cpbd' in self._pyiqa_models:
                image = self._prepare_image(img)
                # 转换为PyTorch tensor格式
                if len(image.shape) == 3:
                    image_tensor = torch.from_numpy(image.transpose(2, 0, 1)).unsqueeze(0).float() / 255.0
                else:
                    image_tensor = torch.from_numpy(image).unsqueeze(0).unsqueeze(0).float() / 255.0
                
                with torch.no_grad():
                    cpbd_score = self._pyiqa_models['cpbd'](image_tensor)
                    return float(cpbd_score.item())
            
            # 备用实现：基于OpenCV的自定义CPBD计算
            else:
                return self._calculate_cpbd_custom(img)
                
        except Exception as e:
            print(f"[WARNING] CPBD calculation failed: {e}")
            return 0.5  # 返回中等清晰度分数
    
    def _calculate_cpbd_custom(self, img: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """使用OpenCV实现自定义的CPBD计算"""
        try:
            image = self._prepare_image(img)
            
            # 转换为灰度图
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image
                
            gray = gray.astype(np.float64)
            
            # Sobel边缘检测
            grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            edge_strength = np.sqrt(grad_x**2 + grad_y**2)
            
            # 计算局部对比度
            local_contrast = cv2.Laplacian(gray, cv2.CV_64F)
            local_contrast = np.abs(local_contrast)
            
            # 计算模糊概率
            threshold = np.percentile(edge_strength, 50)  # 自适应阈值
            sharp_edges = edge_strength > threshold
            
            # CPBD分数
            cpbd_score = np.sum(sharp_edges * local_contrast) / (np.sum(local_contrast) + 1e-10)
            cpbd_score = np.clip(cpbd_score, 0.0, 1.0)
            
            return float(cpbd_score)
            
        except Exception as e:
            print(f"[WARNING] Custom CPBD calculation failed: {e}")
            return 0.5
    
    def calculate_clip_iqa(self, img: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """
        计算CLIP-IQA (CLIP-based Image Quality Assessment)
        强调图像的语义信息的无参考图像质量评估
        
        Args:
            img: 待评估的图像
            
        Returns:
            CLIP-IQA值，范围[0, 1]，值越大表示质量越好
        """
        try:
            # 优先使用pyiqa实现
            if HAS_PYIQA and 'clipiqa' in self._pyiqa_models:
                image = self._prepare_image(img)
                # 转换为PyTorch tensor格式
                if len(image.shape) == 3:
                    image_tensor = torch.from_numpy(image.transpose(2, 0, 1)).unsqueeze(0).float() / 255.0
                else:
                    image_tensor = torch.from_numpy(image).unsqueeze(0).unsqueeze(0).float() / 255.0
                
                with torch.no_grad():
                    clipiqa_score = self._pyiqa_models['clipiqa'](image_tensor)
                    return float(clipiqa_score.item())
            else:
                print("[WARNING] CLIP-IQA calculation requires pyiqa")
                return 0.5  # 返回中等质量分数
                
        except Exception as e:
            print(f"[WARNING] CLIP-IQA calculation failed: {e}")
            return 0.5
    
    def calculate_hyper_iqa(self, img: Union[str, bytes, np.ndarray, Image.Image]) -> float:
        """
        计算Hyper-IQA
        能够检测局部失真的无参考图像质量评估
        
        Args:
            img: 待评估的图像
            
        Returns:
            Hyper-IQA值，范围[0, 1]，值越大表示质量越好
        """
        try:
            if HAS_PYIQA and 'hyperiqa' in self._pyiqa_models:
                image = self._prepare_image(img)
                # 转换为PyTorch tensor格式
                if len(image.shape) == 3:
                    image_tensor = torch.from_numpy(image.transpose(2, 0, 1)).unsqueeze(0).float() / 255.0
                else:
                    image_tensor = torch.from_numpy(image).unsqueeze(0).unsqueeze(0).float() / 255.0
                
                with torch.no_grad():
                    hyperiqa_score = self._pyiqa_models['hyperiqa'](image_tensor)
                    # Hyper-IQA通常输出范围[0, 1]，值越大质量越好
                    return float(hyperiqa_score.item())
            else:
                print("[WARNING] Hyper-IQA calculation requires pyiqa")
                return 0.5  # 返回中等质量分数
                
        except Exception as e:
            print(f"[WARNING] Hyper-IQA calculation failed: {e}")
            return 0.5
    
    def calculate_all_no_reference_metrics(self, img: Union[str, bytes, np.ndarray, Image.Image]) -> dict:
        """
        计算所有无参考图像质量指标
        
        Args:
            img: 待评估的图像
            
        Returns:
            包含所有无参考指标的字典
        """
        metrics = {}
        
        try:
            metrics['niqe'] = self.calculate_niqe(img)
        except Exception as e:
            print(f"[WARNING] NIQE calculation failed: {e}")
            metrics['niqe'] = 5.0
            
        try:
            metrics['brisque'] = self.calculate_brisque(img)
        except Exception as e:
            print(f"[WARNING] BRISQUE calculation failed: {e}")
            metrics['brisque'] = 30.0
            
        try:
            metrics['cpbd'] = self.calculate_cpbd(img)
        except Exception as e:
            print(f"[WARNING] CPBD calculation failed: {e}")
            metrics['cpbd'] = 0.5
            
        try:
            metrics['clip_iqa'] = self.calculate_clip_iqa(img)
        except Exception as e:
            print(f"[WARNING] CLIP-IQA calculation failed: {e}")
            metrics['clip_iqa'] = 0.5
            
        try:
            metrics['hyper_iqa'] = self.calculate_hyper_iqa(img)
        except Exception as e:
            print(f"[WARNING] Hyper-IQA calculation failed: {e}")
            metrics['hyper_iqa'] = 0.5
            
        return metrics

    def calculate_all_metrics(self, img1: Union[str, bytes, np.ndarray, Image.Image], 
                             img2: Union[str, bytes, np.ndarray, Image.Image] = None) -> dict:
        """
        计算所有图像质量指标（有参考或无参考）
        
        Args:
            img1: 第一张图像（或待评估图像）
            img2: 第二张图像（参考图像，可选）
            
        Returns:
            包含所有指标的字典
        """
        if img2 is None:
            # 只计算无参考指标
            return self.calculate_all_no_reference_metrics(img1)
        
        # 计算有参考指标
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
                     psnr_range: Tuple[float, float] = (10.0, 40.0)) -> Tuple[float, float, float]:
    """
    归一化图像质量指标到[0, 1]范围
    
    优化说明：
    - SSIM: 范围[-1, 1]，线性归一化。值越接近1表示结构越相似
    - LPIPS: 范围[0, 1]，线性归一化。值越接近0表示感知越相似
    - PSNR: 使用更合理的范围[10, 40]dB，并应用非线性映射增强区分度
      * 10dB: 质量很差
      * 20dB: 可接受的最低质量
      * 30dB: 良好质量
      * 40dB: 优秀质量
    
    Args:
        ssim: SSIM值，范围[-1, 1]
        lpips: LPIPS值，范围[0, 1]
        psnr: PSNR值，单位dB
        ssim_range: SSIM的预期范围
        lpips_range: LPIPS的预期范围
        psnr_range: PSNR的预期范围
        
    Returns:
        归一化后的 (ssim, lpips, psnr) 元组，均在[0, 1]范围内
    """
    def normalize_linear(value, min_val, max_val):
        """线性归一化"""
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
    
    def normalize_psnr_nonlinear(psnr_val, min_db=10.0, max_db=40.0):
        """
        PSNR非线性归一化，增强高质量区域的区分度
        使用sigmoid-like函数使奖励更敏感于质量变化
        """
        # 先线性归一化到[0, 1]
        linear_norm = (psnr_val - min_db) / (max_db - min_db)
        linear_norm = max(0.0, min(1.0, linear_norm))
        
        # 应用平滑的非线性映射 (平方根函数)
        # 这使得低质量到中等质量的提升获得更多奖励
        nonlinear_norm = np.sqrt(linear_norm)
        
        return nonlinear_norm
    
    # SSIM归一化：线性映射，SSIM本身就是很好的相似度指标
    norm_ssim = normalize_linear(ssim, ssim_range[0], ssim_range[1])
    
    # LPIPS归一化：线性映射，值越小越好
    norm_lpips = normalize_linear(lpips, lpips_range[0], lpips_range[1])
    
    # PSNR归一化：使用非线性映射增强区分度
    norm_psnr = normalize_psnr_nonlinear(psnr, psnr_range[0], psnr_range[1])
    
    return norm_ssim, norm_lpips, norm_psnr


def normalize_no_reference_metrics(niqe: float, brisque: float, cpbd: float, 
                                   clip_iqa: float, hyper_iqa: float,
                                   niqe_range: Tuple[float, float] = (2.0, 15.0),
                                   brisque_range: Tuple[float, float] = (0.0, 100.0),
                                   cpbd_range: Tuple[float, float] = (0.0, 1.0),
                                   clip_iqa_range: Tuple[float, float] = (0.0, 1.0),
                                   hyper_iqa_range: Tuple[float, float] = (0.0, 1.0)) -> Tuple[float, float, float, float, float]:
    """
    归一化无参考图像质量指标到[0, 1]范围
    
    指标特点：
    - NIQE: 值越小表示质量越好，范围[2, 15]，使用反向归一化
    - BRISQUE: 值越小表示质量越好，范围[0, 100]，使用反向归一化
    - CPBD: 值越大表示质量越好，范围[0, 1]，直接归一化
    - CLIP-IQA: 值越大表示质量越好，范围[0, 1]，直接归一化
    - Hyper-IQA: 值越大表示质量越好，范围[0, 1]，直接归一化
    
    Args:
        niqe: NIQE值
        brisque: BRISQUE值
        cpbd: CPBD值
        clip_iqa: CLIP-IQA值
        hyper_iqa: Hyper-IQA值
        niqe_range: NIQE的预期范围
        brisque_range: BRISQUE的预期范围
        cpbd_range: CPBD的预期范围
        clip_iqa_range: CLIP-IQA的预期范围
        hyper_iqa_range: Hyper-IQA的预期范围
        
    Returns:
        归一化后的 (niqe, brisque, cpbd, clip_iqa, hyper_iqa) 元组，均在[0, 1]范围内
    """
    def normalize_linear(value, min_val, max_val):
        """线性归一化"""
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
    
    def normalize_inverse(value, min_val, max_val):
        """反向归一化（值越小越好的指标）"""
        linear_norm = normalize_linear(value, min_val, max_val)
        return 1.0 - linear_norm
    
    # NIQE归一化：值越小越好，使用反向归一化
    norm_niqe = normalize_inverse(niqe, niqe_range[0], niqe_range[1])
    
    # BRISQUE归一化：值越小越好，使用反向归一化
    norm_brisque = normalize_inverse(brisque, brisque_range[0], brisque_range[1])
    
    # CPBD归一化：值越大越好，直接归一化
    norm_cpbd = normalize_linear(cpbd, cpbd_range[0], cpbd_range[1])
    
    # CLIP-IQA归一化：值越大越好，直接归一化
    norm_clip_iqa = normalize_linear(clip_iqa, clip_iqa_range[0], clip_iqa_range[1])
    
    # Hyper-IQA归一化：值越大越好，直接归一化
    norm_hyper_iqa = normalize_linear(hyper_iqa, hyper_iqa_range[0], hyper_iqa_range[1])
    
    return norm_niqe, norm_brisque, norm_cpbd, norm_clip_iqa, norm_hyper_iqa


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
                                   alpha: float = 0.35, 
                                   beta: float = 0.50, 
                                   gamma: float = 0.15,
                                   metrics_calculator: ImageQualityMetrics = None) -> float:
    """
    计算图像复原奖励函数（优化版）
    
    r_final(x̂, x) = α * SSIM_norm(x̂, x) + β * (1 - LPIPS_norm(x̂, x)) + γ * PSNR_norm(x̂, x)
    
    权重优化说明：
    - α = 0.35 (SSIM权重): 衡量结构相似性，对纹理和边缘敏感
    - β = 0.50 (LPIPS权重): 衡量感知相似性，最重要的指标，基于深度特征
    - γ = 0.15 (PSNR权重): 衡量像素级误差，辅助指标
    
    为什么LPIPS权重最高？
    1. LPIPS基于深度学习特征，更接近人类视觉感知
    2. 对细节恢复和感知质量最敏感
    3. 能够有效区分不同复原质量
    
    Args:
        img1: 复原后的图像
        img2: 原始图像（ground truth）
        alpha: SSIM权重，控制结构相似性的重要程度
        beta: LPIPS权重，控制感知相似性的重要程度（最重要）
        gamma: PSNR权重，控制像素级精度的重要程度
        metrics_calculator: 图像质量计算器实例
        
    Returns:
        奖励分数，范围[0, 1]，值越接近1表示复原质量越好
    """
    if metrics_calculator is None:
        metrics_calculator = get_image_quality_metrics()
    
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


def compute_no_reference_image_restoration_reward(img: Union[str, bytes, np.ndarray, Image.Image],
                                                  alpha: float = 0.20,  # NIQE权重
                                                  beta: float = 0.20,   # BRISQUE权重  
                                                  gamma: float = 0.20,  # CPBD权重
                                                  delta: float = 0.20,  # CLIP-IQA权重
                                                  epsilon: float = 0.20, # Hyper-IQA权重
                                                  metrics_calculator: ImageQualityMetrics = None) -> float:
    """
    计算无参考图像复原奖励函数
    
    r_final(x̂) = α*NIQE_norm(x̂) + β*BRISQUE_norm(x̂) + γ*CPBD_norm(x̂) + δ*CLIP-IQA_norm(x̂) + ε*Hyper-IQA_norm(x̂)
    
    权重说明：
    - α = 0.20 (NIQE权重): 关注自然场景统计特征
    - β = 0.20 (BRISQUE权重): 结合亮度和结构信息
    - γ = 0.20 (CPBD权重): 评估模糊和压缩失真
    - δ = 0.20 (CLIP-IQA权重): 强调图像的语义信息
    - ε = 0.20 (Hyper-IQA权重): 检测局部失真
    
    为什么采用均等权重？
    1. 各指标关注不同的图像质量维度，均等权重确保全面评估
    2. 避免偏向某一类指标，保持评估的平衡性
    3. 可根据具体应用场景调整权重
    
    Args:
        img: 待评估的复原图像
        alpha: NIQE权重，控制自然统计特征的重要程度
        beta: BRISQUE权重，控制亮度结构信息的重要程度  
        gamma: CPBD权重，控制清晰度的重要程度
        delta: CLIP-IQA权重，控制语义信息的重要程度
        epsilon: Hyper-IQA权重，控制局部失真检测的重要程度
        metrics_calculator: 图像质量计算器实例
        
    Returns:
        奖励分数，范围[0, 1]，值越接近1表示复原质量越好
    """
    if metrics_calculator is None:
        metrics_calculator = get_image_quality_metrics()
    
    # 计算原始无参考指标
    metrics = metrics_calculator.calculate_all_no_reference_metrics(img)
    niqe_val = metrics['niqe']
    brisque_val = metrics['brisque']
    cpbd_val = metrics['cpbd']
    clip_iqa_val = metrics['clip_iqa']
    hyper_iqa_val = metrics['hyper_iqa']
    
    # 归一化指标
    norm_niqe, norm_brisque, norm_cpbd, norm_clip_iqa, norm_hyper_iqa = normalize_no_reference_metrics(
        niqe_val, brisque_val, cpbd_val, clip_iqa_val, hyper_iqa_val
    )
    
    # 计算最终奖励
    reward = alpha * norm_niqe + beta * norm_brisque + gamma * norm_cpbd + delta * norm_clip_iqa + epsilon * norm_hyper_iqa
    
    # 确保奖励在[0, 1]范围内
    reward = max(0.0, min(1.0, reward))
    
    print(f' [DEBUG no_ref_image_quality] niqe={niqe_val:.4f}(norm={norm_niqe:.4f}), '
          f'brisque={brisque_val:.4f}(norm={norm_brisque:.4f}), '
          f'cpbd={cpbd_val:.4f}(norm={norm_cpbd:.4f})')
    print(f' [DEBUG no_ref_image_quality] clip_iqa={clip_iqa_val:.4f}(norm={norm_clip_iqa:.4f}), '
          f'hyper_iqa={hyper_iqa_val:.4f}(norm={norm_hyper_iqa:.4f})')
    print(f' [DEBUG no_ref_image_quality] weights: α={alpha}(NIQE), β={beta}(BRISQUE), γ={gamma}(CPBD), δ={delta}(CLIP-IQA), ε={epsilon}(Hyper-IQA)')
    print(f' [DEBUG no_ref_image_quality] reward={reward:.4f} (越接近1表示复原质量越好)')
    
    # 清理GPU内存
    cleanup_gpu_memory()
    
    return reward


# 测试和可视化函数
def visualize_reward_function():
    """
    可视化优化后的奖励函数特性
    展示不同指标值对最终奖励的影响
    """
    print("\n" + "="*70)
    print("图像质量奖励函数优化说明")
    print("="*70)
    
    print("\n【优化目标】")
    print("使复原图像越接近原图，奖励越高")
    
    print("\n【奖励公式】")
    print("r = 0.35 × SSIM_norm + 0.50 × (1 - LPIPS_norm) + 0.15 × PSNR_norm")
    
    print("\n【权重分配】")
    print("  • LPIPS (感知相似性): 50% - 最重要，基于深度学习特征")
    print("  • SSIM  (结构相似性): 35% - 重要，衡量纹理和边缘")
    print("  • PSNR  (信噪比):     15% - 辅助，衡量像素级误差")
    
    print("\n【归一化策略】")
    print("  • SSIM:  [-1, 1]  → [0, 1]  (线性映射)")
    print("  • LPIPS: [0, 1]   → [0, 1]  (线性映射，取反)")
    print("  • PSNR:  [10, 40]dB → [0, 1] (非线性映射，使用√函数增强低质量区分度)")
    
    print("\n【质量等级参考】")
    quality_levels = [
        ("完美复原", 1.00, 0.00, 40, 0.95),
        ("优秀质量", 0.95, 0.05, 35, 0.87),
        ("良好质量", 0.90, 0.10, 30, 0.75),
        ("中等质量", 0.80, 0.20, 25, 0.58),
        ("可接受质量", 0.70, 0.30, 20, 0.42),
        ("较差质量", 0.60, 0.45, 15, 0.28),
    ]
    
    print(f"{'等级':<12} {'SSIM':<8} {'LPIPS':<8} {'PSNR(dB)':<10} {'奖励分数':<10}")
    print("-" * 60)
    for level, ssim, lpips, psnr, _ in quality_levels:
        norm_ssim, norm_lpips, norm_psnr = normalize_metrics(ssim, lpips, psnr)
        reward = 0.35 * norm_ssim + 0.50 * (1.0 - norm_lpips) + 0.15 * norm_psnr
        reward = max(0.0, min(1.0, reward))
        print(f"{level:<12} {ssim:<8.2f} {lpips:<8.2f} {psnr:<10.1f} {reward:<10.3f}")
    
    print("\n【优化效果】")
    print("  ✓ LPIPS权重提升至50%，更符合人类视觉感知")
    print("  ✓ PSNR非线性归一化，增强低质量到中等质量的区分度")
    print("  ✓ PSNR范围从[0,50]调整为[10,40]，更符合实际复原场景")
    print("  ✓ 整体奖励分布更平滑，有利于RL训练收敛")
    
    print("="*70 + "\n")


def test_image_quality_metrics():
    """测试图像质量指标计算"""
    print("Testing Image Quality Metrics...")
    
    # 先显示优化说明
    visualize_reward_function()
    
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
