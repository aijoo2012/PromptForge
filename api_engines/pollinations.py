# core/api_engines/pollinations.py
"""
Pollinations AI 多模态生成引擎
支持：文生图、图生图、音频生成（TTS/音乐）、视频生成

API 文档：https://gen.pollinations.ai/docs
获取 API Key：https://enter.pollinations.ai/keys

新 API 统一网关：https://gen.pollinations.ai
"""

import os
import re
import io
import json
import time
import random
import base64
import urllib.parse
from typing import Optional, Dict, Any, List, Union
from enum import Enum

import requests
from PIL import Image


class PollinationsMode(Enum):
    """Pollinations 支持的模式"""
    TEXT_TO_IMAGE = "text-to-image"
    IMAGE_TO_IMAGE = "image-to-image"
    AUDIO = "audio"          # TTS / 音乐
    VIDEO = "video"          # 文生视频 / 图生视频
    CHAT = "chat"            # 文本对话 / 视觉理解


class PollinationsEngine:
    """Pollinations AI 多模态引擎 - 统一网关版"""

    # ✅ 统一网关（新 API）
    BASE_URL = "https://gen.pollinations.ai"

    # ✅ 默认模型配置
    DEFAULT_MODELS = {
        "text-to-image": "black-forest-labs/flux.1-schnell",   # ⭐ 改成免费模型
        "image-to-image": "black-forest-labs/flux.1-kontext-pro",  # ⚠️ 见下方说明
        "chat": "community/NamanSoni78/gemini-3.8-flash",       # ⭐ 免费
        "vision": "community/NamanSoni78/gemini-3.8-flash",      # ⭐ 免费
        "video": "",                                             # ⭐ 留空
        "video-i2v": "",                                         # ⭐ 留空
        "audio": "community/NamanSoni78/aura-2-amalthea-en",     # ⭐ 免费
        "music": "",
    }

    # ✅ 支持的图像尺寸（长宽均为 8 的倍数）
    SUPPORTED_IMAGE_SIZES = [
        "512x512", "768x768", "1024x1024",
        "1024x768", "768x1024", "1280x720", "720x1280",
    ]

    # ✅ 音频可用语音
    AVAILABLE_VOICES = [
        "alloy", "echo", "fable", "onyx", "nova", "shimmer",
        "coral", "verse", "ballad", "ash", "sage",
    ]

    # ✅ 音频输出格式
    AUDIO_FORMATS = ["mp3", "opus", "aac", "flac", "wav", "pcm"]

    # ✅ 音频可用语音（OpenAI 兼容）
    AVAILABLE_VOICES = [
        "alloy", "echo", "fable", "onyx", "nova", "shimmer",
        "coral", "verse", "ballad", "ash", "sage",
    ]

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        image_model: str = None,
        video_model: str = None,
        audio_model: str = None,
    ):
        """
        初始化 Pollinations AI 引擎

        Args:
            api_key: Pollinations API Key（从 enter.pollinations.ai 获取）
                     支持 sk_（服务端，无速率限制）或 pk_（客户端，有速率限制）
            model: 默认图像模型（兼容旧接口）
            image_model: 图像生成模型
            video_model: 视频生成模型
            audio_model: 音频生成模型
        """
        self.api_key = api_key or os.environ.get("POLLINATIONS_API_KEY")
        self.base_url = self.BASE_URL

        # 模型配置
        self.image_model = image_model or model or self.DEFAULT_MODELS["text-to-image"]
        self.video_model = video_model or self.DEFAULT_MODELS["video"]
        self.audio_model = audio_model or self.DEFAULT_MODELS["audio"]

        # 可用模型缓存
        self._available_models: Optional[Dict[str, List[str]]] = None

        # 限速控制
        self.last_request_time = 0.0
        self.min_interval = 0.5

        # 重试配置
        self.max_retries = 3
        self.retry_delay = 2

        # 质量词（用于文生图清理）
        self.quality_words = [
            "masterpiece", "best quality", "photorealistic", "8k",
            "highly detailed", "intricate details", "professional photography",
            "beautiful", "stunning", "amazing", "perfect", "gorgeous",
            "elegant", "high quality", "ultra detailed", "hdr",
            "highest quality", "sharp focus", "cinematic", "award winning",
        ]

        if not self.api_key:
            print("⚠️ 未设置 POLLINATIONS_API_KEY，请从 https://enter.pollinations.ai/keys 获取")

        print(f"🔍 Pollinations AI 引擎初始化")
        print(f"🔍 API 地址: {self.base_url}")
        print(f"🔍 图像模型: {self.image_model}")
        print(f"🔍 视频模型: {self.video_model}")
        print(f"🔍 音频模型: {self.audio_model}")

    # ==================== 通用工具方法 ====================

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头（带认证）"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _rate_limit(self):
        """限速控制"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None,
        timeout: int = 120,
        stream: bool = False,
    ) -> requests.Response:
        """发送请求到 Pollinations 统一网关（带重试）"""
        if not self.api_key:
            raise ValueError(
                "请设置 POLLINATIONS_API_KEY\n"
                "获取地址：https://enter.pollinations.ai/keys"
            )

        self._rate_limit()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=timeout,
                    stream=stream,
                )

                # 401 - 认证失败，不重试
                if response.status_code == 401:
                    raise Exception(
                        f"API Key 无效或已过期 (401)\n"
                        f"请从 https://enter.pollinations.ai/keys 重新获取"
                    )

                # 429 - 限流，等待后重试
                if response.status_code == 429:
                    wait = self.retry_delay * (2 ** attempt)
                    print(f"⚠️ 请求限流 (429)，{wait}s 后重试 ({attempt+1}/{self.max_retries})...")
                    time.sleep(wait)
                    continue

                # 5xx - 服务端错误，重试
                if response.status_code >= 500:
                    if attempt < self.max_retries - 1:
                        print(f"⚠️ 服务端错误 ({response.status_code})，重试...")
                        time.sleep(self.retry_delay)
                        continue
                    raise Exception(f"服务端错误 ({response.status_code}): {response.text[:200]}")

                # 其他非 200
                if response.status_code != 200:
                    error_msg = response.text[:300]
                    try:
                        err_json = response.json()
                        error_msg = err_json.get("error", {}).get("message", error_msg)
                    except Exception:
                        pass
                    raise Exception(f"API 调用失败 ({response.status_code}): {error_msg}")

                return response

            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    print(f"⚠️ 请求超时，重试 ({attempt+1}/{self.max_retries})...")
                    time.sleep(self.retry_delay)
                    continue
                raise Exception("请求超时")

            except requests.exceptions.ConnectionError as e:
                if attempt < self.max_retries - 1:
                    print(f"⚠️ 连接失败，重试 ({attempt+1}/{self.max_retries})...")
                    time.sleep(self.retry_delay)
                    continue
                raise Exception(f"连接失败: {e}")

        raise Exception("所有重试已用尽")

    def _download_image(self, image_url: str) -> Image.Image:
        """从 URL 或 data URI 加载图片"""
        if image_url.startswith("data:image"):
            base64_data = re.sub(r"^data:image/.+;base64,", "", image_url)
            image_bytes = base64.b64decode(base64_data)
            return Image.open(io.BytesIO(image_bytes))

        resp = requests.get(image_url, timeout=60, headers=self._get_headers())
        if resp.status_code != 200:
            raise Exception(f"下载图片失败: {resp.status_code}")
        return Image.open(io.BytesIO(resp.content))

    def _image_to_base64(self, image: Image.Image) -> str:
        """将 PIL Image 转为 base64"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def _image_to_data_uri(self, image: Image.Image) -> str:
        """将 PIL Image 转为 Data URI"""
        return f"data:image/png;base64,{self._image_to_base64(image)}"

    def _resize_for_api(self, image: Image.Image, max_size: int = 1024) -> Image.Image:
        """缩放图片到 API 支持的最大尺寸"""
        w, h = image.size
        if max(w, h) > max_size:
            scale = max_size / max(w, h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            new_w = ((new_w + 7) // 8) * 8
            new_h = ((new_h + 7) // 8) * 8
            image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            print(f"🔍 图片已缩放: {w}x{h} → {new_w}x{new_h}")
        return image

    def _to_size_tier(self, width: int, height: int) -> str:
        """将宽高转换为尺寸档位（1K/2K/3K/4K）"""
        max_edge = max(width, height)
        if max_edge <= 1024:
            return "1K"
        elif max_edge <= 2048:
            return "2K"
        elif max_edge <= 3072:
            return "3K"
        else:
            return "4K"

    # ==================== 模型发现 ====================

    def get_available_models(self, category: str = None) -> Dict[str, List[str]]:
        """
        获取可用模型列表

        Args:
            category: 可选过滤类别（image / text / video / audio）

        Returns:
            {"image": [...], "text": [...], "video": [...], "audio": [...]}
        """
        if self._available_models is not None:
            return self._available_models

        models = {"image": [], "text": [], "video": [], "audio": []}

        try:
            # 图像/视频模型
            resp = requests.get(f"{self.base_url}/image/models", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    models["image"] = data
                elif isinstance(data, dict):
                    models["image"] = data.get("models", data.get("data", []))
        except Exception as e:
            print(f"⚠️ 获取图像模型列表失败: {e}")

        try:
            # 文本模型
            resp = requests.get(f"{self.base_url}/v1/models", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    models["text"] = [m.get("id", m) if isinstance(m, dict) else m for m in data]
                elif isinstance(data, dict):
                    models["text"] = data.get("data", [])
        except Exception as e:
            print(f"⚠️ 获取文本模型列表失败: {e}")

        # 视频模型通常包含在图像模型列表中（带 video_capabilities）
        models["video"] = [
            m for m in models["image"]
            if isinstance(m, dict) and m.get("video_capabilities")
        ]

        self._available_models = models

        if category and category in models:
            return {category: models[category]}
        return models

    # ==================== 中文 Prompt 翻译 ====================

    def _to_english_prompt(self, prompt: str) -> str:
        """将中文 Prompt 转换为英文"""
        if all(ord(c) < 128 for c in prompt):
            return prompt

        translations = {
            "日落": "sunset", "日出": "sunrise",
            "风景": "landscape", "山水": "mountain and water",
            "水墨画": "ink wash painting", "国画": "traditional Chinese painting",
            "风格": "style", "自然": "nature", "景观": "scenery",
            "美女": "beautiful woman", "女孩": "girl", "男孩": "boy",
            "男人": "man", "女人": "woman",
            "动漫": "anime", "赛博朋克": "cyberpunk",
            "城市": "city", "森林": "forest", "海洋": "ocean",
            "沙滩": "beach", "星空": "starry sky",
            "唯美": "aesthetic", "写实": "photorealistic",
            "肖像": "portrait", "全身": "full body", "半身": "half body",
            "侧面": "side view", "正面": "front view",
            "温暖": "warm", "冷色": "cold color",
            "金色": "golden", "蓝色": "blue", "红色": "red",
            "粉色": "pink", "浪漫": "romantic",
            "梦幻": "dreamy", "复古": "vintage", "未来": "futuristic",
            "高清": "high definition", "细节": "detailed",
            "光影": "light and shadow", "氛围": "atmosphere",
        }

        result = prompt
        for cn, en in translations.items():
            result = result.replace(cn, en)
        return result

    def _clean_prompt(self, prompt: str) -> str:
        """清理质量词并限制长度"""
        clean = prompt
        for word in self.quality_words:
            clean = clean.replace(word, "")
            clean = clean.replace(word.title(), "")

        clean = ", ".join([p.strip() for p in clean.split(",") if p.strip()])
        if not clean:
            clean = prompt

        english = self._to_english_prompt(clean)

        max_length = 300
        if len(english) > max_length:
            parts = english.split(",")
            truncated = ""
            for part in parts:
                if len(truncated) + len(part) < max_length:
                    truncated += part + ", "
                else:
                    break
            english = truncated.rstrip(", ")
        if len(english) > max_length:
            english = english[:max_length]

        return english

    # ==================== 文生图 ====================

    def generate_single(
        self,
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 7.5,
        seed: int = None,
    ) -> Image.Image:
        """生成单张图片（文生图）- 兼容旧接口"""
        return self.text_to_image(prompt, negative, width, height, steps, cfg, seed)

    def text_to_image(
        self,
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 7.5,
        seed: int = None,
        model: str = None,
        enhance: bool = False,
        nologo: bool = True,
        private: bool = False,
        safe: bool = False,
        transparent: bool = False,
    ) -> Image.Image:
        """
        文生图

        Args:
            prompt: 提示词（支持中英文）
            negative: 负面提示词（部分模型支持）
            width: 宽度
            height: 高度
            steps: 采样步数（部分模型支持）
            cfg: 引导系数（部分模型支持）
            seed: 随机种子（-1 表示随机）
            model: 模型名称（默认使用 self.image_model）
            enhance: 是否启用 Prompt 增强
            nologo: 是否移除 Logo
            private: 是否私有（不进入公开 feed）
            safe: 安全过滤
            transparent: 透明背景（部分模型支持）

        Returns:
            PIL Image 对象
        """
        model = model or self.image_model

        # 处理 seed
        if seed is None:
            seed = -1
        elif seed > 2147483647:
            seed = seed % 2147483648

        # 清理 Prompt
        clean_prompt = self._clean_prompt(prompt)
        print(f"🔍 Pollinations 文生图")
        print(f"🔍 模型: {model}, 尺寸: {width}x{height}, seed: {seed}")
        print(f"🔍 Prompt: {clean_prompt[:120]}...")

        # 限制尺寸
        if width > 2048:
            scale = 2048 / width
            width = 2048
            height = int(height * scale)
        if height > 2048:
            scale = 2048 / height
            height = 2048
            width = int(width * scale)

        width = int(width)
        height = int(height)

        # 构建请求
        encoded_prompt = urllib.parse.quote(clean_prompt)
        endpoint = f"/image/{encoded_prompt}"

        params = {
            "model": model,
            "width": width,
            "height": height,
            "seed": seed,
        }

        # 可选参数
        if negative and len(negative) < 100:
            params["negative"] = negative
        if enhance:
            params["enhance"] = "true"
        if nologo:
            params["nologo"] = "true"
        if private:
            params["private"] = "true"
        if safe:
            params["safe"] = "true"
        if transparent:
            params["transparent"] = "true"

        # 部分模型支持 steps/cfg
        if steps and steps > 0:
            params["steps"] = steps
        if cfg and cfg > 0:
            params["cfg"] = cfg

        response = self._request("GET", endpoint, params=params, timeout=180)
        image = Image.open(io.BytesIO(response.content))

        if image.size[0] < 10 or image.size[1] < 10:
            raise Exception("生成的图片尺寸异常")

        return image

    # ==================== 图生图 ====================

    def image_to_image(
        self,
        prompt: str,
        image,
        strength: float = 0.7,
        width: int = None,
        height: int = None,
        seed: int = None,
        model: str = None,
        nologo: bool = True,
        safe: bool = False,
        **kwargs,
    ) -> Image.Image:
        """
        图生图 / 图像编辑

        改用 POST /v1/images/edits（OpenAI 兼容），把 base64 图片放在 body 里，
        避免 GET 查询参数过长触发 414。
        """
        model = model or self.DEFAULT_MODELS["image-to-image"]

        # ── 统一处理图片输入，转成 Data URI 列表 ──
        image_urls: List[str] = []

        if isinstance(image, str):
            image_urls = [image]
        elif isinstance(image, list):
            for img in image:
                if isinstance(img, str):
                    image_urls.append(img)
                elif isinstance(img, Image.Image):
                    resized = self._resize_for_api(img, max_size=1024)
                    image_urls.append(self._image_to_data_uri(resized))
        elif isinstance(image, Image.Image):
            resized = self._resize_for_api(image, max_size=1024)
            image_urls = [self._image_to_data_uri(resized)]
        else:
            raise ValueError("image 参数必须是 PIL Image、图片列表或 URL 字符串")

        if not image_urls:
            raise ValueError("至少需要提供一张参考图片")

        # ── 输出尺寸 ──
        if width is None or height is None:
            if isinstance(image, Image.Image):
                width, height = image.size
            elif isinstance(image, list) and isinstance(image[0], Image.Image):
                width, height = image[0].size
            else:
                width, height = 1024, 1024

        max_size = 1024
        if width > max_size or height > max_size:
            scale = max_size / max(width, height)
            width = int(width * scale)
            height = int(height * scale)
        width = ((width + 7) // 8) * 8
        height = ((height + 7) // 8) * 8

        if seed is None:
            seed = -1

        clean_prompt = self._clean_prompt(prompt)

        print(f"🔍 Pollinations 图生图 (POST)")
        print(f"🔍 模型: {model}, 尺寸: {width}x{height}")
        print(f"🔍 参考图数量: {len(image_urls)}")
        print(f"🔍 Prompt: {clean_prompt[:120]}...")

        # ── 构建 POST 请求体（base64 图片走 body，不走 URL）──
        data = {
            "model": model,
            "prompt": clean_prompt,
            "image": image_urls,             # ⭐ 数组，走 body
            "n": 1,
            "size": f"{width}x{height}",
            "response_format": "b64_json",
            "seed": seed,
        }

        if nologo:
            data["nologo"] = True
        if safe:
            data["safe"] = True
        if strength and 0 < strength < 1:
            data["strength"] = strength

        # 走 OpenAI 兼容的图像编辑端点
        response = self._request(
            "POST", "/v1/images/edits",
            data=data,
            timeout=300,
        )

        result = response.json()

        # ── 解析返回 ──
        image_b64 = None
        if "data" in result and result["data"]:
            item = result["data"][0]
            image_b64 = item.get("b64_json")
            if not image_b64 and item.get("url"):
                return self._download_image(item["url"])

        if not image_b64 and "image" in result:
            image_b64 = result["image"]

        if not image_b64:
            raise Exception(f"无法解析图片数据: {json.dumps(result)[:300]}")

        # 去掉可能的 data URI 前缀
        if image_b64.startswith("data:image"):
            image_b64 = image_b64.split(",", 1)[1]

        image_bytes = base64.b64decode(image_b64)
        result_image = Image.open(io.BytesIO(image_bytes))

        if result_image.size[0] < 10 or result_image.size[1] < 10:
            raise Exception("生成的图片尺寸异常")

        return result_image
    # ==================== 音频生成 ====================

    def generate_audio(
        self,
        text: str,
        voice: str = "alloy",
        model: str = None,
        output_format: str = "mp3",
        duration: float = None,
        output_path: str = None,
    ) -> bytes:
        """
        音频生成（TTS / 音乐）
        使用 OpenAI 兼容的 POST /v1/audio/speech 端点，支持社区免费 TTS 模型。
        """
        model = model or self.audio_model

        # 验证格式
        if output_format not in self.AUDIO_FORMATS:
            print(f"⚠️ 不支持的格式 '{output_format}'，使用 'mp3'")
            output_format = "mp3"

        print(f"🔍 Pollinations 音频生成")
        print(f"🔍 模型: {model}, 语音: {voice}, 格式: {output_format}")
        print(f"🔍 文本长度: {len(text)} 字符")

        # 构建 POST 请求体（OpenAI 兼容格式）
        data = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": output_format,
        }

        if duration is not None:
            data["duration"] = duration

        # 发送 POST 请求到 /v1/audio/speech
        response = self._request(
            "POST", "/v1/audio/speech",
            data=data,
            timeout=180,
        )

        audio_bytes = response.content

        if output_path:
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            print(f"✅ 音频已保存: {output_path}")

        return audio_bytes
    
    def text_to_speech(
        self,
        text: str,
        voice: str = "nova",
        output_path: str = "speech.mp3",
    ) -> bytes:
        """文本转语音（便捷方法）"""
        return self.generate_audio(text, voice=voice, output_path=output_path)

    def generate_music(
        self,
        prompt: str,
        duration: float = 30,
        output_path: str = "music.mp3",
    ) -> bytes:
        """音乐生成（便捷方法）"""
        return self.generate_audio(
            prompt,
            model="elevenmusic",
            duration=duration,
            output_path=output_path,
        )

    # ==================== 视频生成 ====================

    def generate_video(
        self,
        prompt: str,
        image: Union[Image.Image, str, List[Union[Image.Image, str]]] = None,
        model: str = None,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        width: int = None,
        height: int = None,
        enable_audio: bool = False,
        seed: int = None,
        output_path: str = None,
    ) -> bytes:
        """
        视频生成（文生视频 / 图生视频）

        Args:
            prompt: 视频描述
            image: 参考图像（图生视频时传入）：
                   - 单张图（起始帧）
                   - 图片列表（[起始帧, 结束帧]）
                   - URL 字符串
            model: 视频模型（veo / seedance / seedance-pro 等）
            duration: 视频时长（秒）
            aspect_ratio: 宽高比（16:9 / 9:16 / 1:1）
            width: 宽度（用于确定宽高比，优先级低于 aspect_ratio）
            height: 高度
            enable_audio: 是否启用音频（仅 veo 支持）
            seed: 随机种子
            output_path: 如果指定，将视频保存到该路径

        Returns:
            视频二进制数据（bytes）
        """
        # 根据是否有图片选择模型
        if image is not None:
            model = model or self.DEFAULT_MODELS["video-i2v"]
        else:
            model = model or self.video_model

        # 处理时长（Clamp 到合理范围）
        original_duration = duration
        if duration < 2:
            duration = 2
        elif duration > 120:
            duration = 120
        if original_duration != duration:
            print(f"⚠️ 视频时长已调整: {original_duration}s → {duration}s")

        # 处理宽高比
        if width and height:
            if width == height:
                aspect_ratio = "1:1"
            elif width > height:
                aspect_ratio = "16:9"
            else:
                aspect_ratio = "9:16"

        # 处理 seed
        if seed is None:
            seed = -1

        # 清理 Prompt
        clean_prompt = self._clean_prompt(prompt)

        print(f"🔍 Pollinations 视频生成")
        print(f"🔍 模型: {model}, 时长: {duration}s, 宽高比: {aspect_ratio}")
        print(f"🔍 Prompt: {clean_prompt[:120]}...")

        # 构建请求
        encoded_prompt = urllib.parse.quote(clean_prompt)
        endpoint = f"/video/{encoded_prompt}"

        params = {
            "model": model,
            "duration": duration,
            "aspectRatio": aspect_ratio,
            "seed": seed,
        }

        if enable_audio and "veo" in model.lower():
            params["audio"] = "true"

        # ⭐ 图生视频：处理参考图像
        if image is not None:
            image_urls: List[str] = []

            if isinstance(image, str):
                image_urls = [image]
            elif isinstance(image, list):
                for item in image:
                    if isinstance(item, str):
                        image_urls.append(item)
                    elif isinstance(item, Image.Image):
                        resized = self._resize_for_api(item, max_size=1024)
                        image_urls.append(self._image_to_data_uri(resized))
            elif isinstance(image, Image.Image):
                resized = self._resize_for_api(image, max_size=1024)
                image_urls = [self._image_to_data_uri(resized)]
            else:
                raise ValueError("image 参数必须是 PIL Image、图片列表或 URL")

            # 用 | 分隔多张图片（image[0] 为起始帧，image[1] 为结束帧）
            params["image"] = "|".join(image_urls)
            print(f"🔍 参考图数量: {len(image_urls)}")

        # 视频生成耗时较长
        timeout = max(300, duration * 30)
        print(f"🔍 超时设置: {timeout}s")

        response = self._request("GET", endpoint, params=params, timeout=timeout)
        video_bytes = response.content

        if len(video_bytes) < 1000:
            raise Exception(f"生成的视频数据异常（仅 {len(video_bytes)} 字节）")

        if output_path:
            with open(output_path, "wb") as f:
                f.write(video_bytes)
            print(f"✅ 视频已保存: {output_path}")

        return video_bytes

    def text_to_video(
        self,
        prompt: str,
        model: str = None,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        enable_audio: bool = False,
        output_path: str = "output.mp4",
    ) -> bytes:
        """文生视频（便捷方法）"""
        return self.generate_video(
            prompt=prompt,
            model=model or self.video_model,
            duration=duration,
            aspect_ratio=aspect_ratio,
            enable_audio=enable_audio,
            output_path=output_path,
        )

    def image_to_video(
        self,
        prompt: str,
        image: Union[Image.Image, str],
        model: str = None,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        output_path: str = "output.mp4",
    ) -> bytes:
        """图生视频（便捷方法）"""
        return self.generate_video(
            prompt=prompt,
            image=image,
            model=model or self.DEFAULT_MODELS["video-i2v"],
            duration=duration,
            aspect_ratio=aspect_ratio,
            output_path=output_path,
        )


    # ==================== 旧接口兼容 ====================

    def video_generation(
        self,
        prompt: str,
        image=None,
        duration: int = 5,
        width: int = 768,
        height: int = 768,
        model: str = None,
        callback_url: str = None,
        **kwargs,
    ) -> dict:
        """
        兼容 Agnes 风格的 video_generation 接口。
        
        项目里的 VideoHandler 原来是为 Agnes 写的，调用的是 engine.video_generation(...)，
        它期望返回一个带 video_id 的 dict，然后轮询等待。但 Pollinations 是同步返回
        视频二进制的，所以这里做一层适配：直接生成完整视频，保存到本地，返回一个
        伪 video_id，并让 wait_for_video 立刻返回本地路径。
        """
        import os
        from datetime import datetime

        output_path = kwargs.pop("output_path", None)
        if output_path is None:
            # 默认保存到 output/ 目录
            out_dir = getattr(self, "_output_dir", "./output")
            os.makedirs(out_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = "".join(c for c in prompt[:20] if c.isalnum() or c in " _-") or "video"
            output_path = os.path.join(out_dir, f"{timestamp}_pollinations_{safe}.mp4")

        # 根据 width/height 推断宽高比
        if width == height:
            aspect_ratio = "1:1"
        elif width > height:
            aspect_ratio = "16:9"
        else:
            aspect_ratio = "9:16"

        # 调用核心视频生成
        self.generate_video(
            prompt=prompt,
            image=image,
            model=model or self.video_model,
            duration=duration,
            aspect_ratio=aspect_ratio,
            output_path=output_path,
        )

        # 返回一个"伪 video_id"（就是本地路径），同时带上直接结果
        return {
            "video_id": output_path,
            "video_url": output_path,
            "status": "completed",
            "progress": 100,
            "_sync": True,  # 标记这是同步结果，不需要轮询
        }

    def video_status(self, video_id: str) -> dict:
        """兼容 VideoHandler 的状态查询：Pollinations 是同步的，直接返回完成"""
        import os
        if os.path.exists(video_id):
            return {
                "status": "completed",
                "progress": 100,
                "video_url": video_id,
                "url": video_id,
            }
        return {
            "status": "failed",
            "error": f"文件不存在: {video_id}",
        }

    def wait_for_video(self, video_id: str, max_wait: int = 900, poll_interval: int = 10) -> str:
        """兼容 VideoHandler 的等待接口：Pollinations 同步返回，直接返回路径"""
        import os
        if os.path.exists(video_id):
            return video_id
        raise Exception(f"视频文件不存在: {video_id}")
        
    # ==================== 文本对话 / 视觉理解 ====================

    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str = "openai",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str:
        """
        文本对话 / 视觉理解（OpenAI 兼容）

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度
            max_tokens: 最大 token 数
            stream: 是否流式

        Returns:
            模型响应文本
        """
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        print(f"🔍 Pollinations 对话")
        print(f"🔍 模型: {model}")

        if stream:
            resp = self._request(
                "POST", "/v1/chat/completions",
                data=data, timeout=120, stream=True,
            )
            result_text = ""
            for line in resp.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                        if line == "[DONE]":
                            break
                        try:
                            chunk = json.loads(line)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                print(content, end="", flush=True)
                                result_text += content
                        except Exception:
                            pass
            print()
            return result_text

        resp = self._request("POST", "/v1/chat/completions", data=data, timeout=120)
        result = resp.json()

        if "choices" in result and result["choices"]:
            return result["choices"][0].get("message", {}).get("content", "")

        raise Exception(f"无法解析对话结果: {json.dumps(result)[:300]}")

    def image_to_text(
        self,
        image: Union[Image.Image, str],
        prompt: str = "请描述这张图片的内容",
        model: str = "openai",
    ) -> str:
        """
        图片反推 / 视觉理解

        Args:
            image: 图片（PIL Image 或 URL）
            prompt: 提示词
            model: 视觉模型

        Returns:
            图片描述文本
        """
        # 构建 image_url
        if isinstance(image, str):
            image_url = image
        elif isinstance(image, Image.Image):
            resized = self._resize_for_api(image, max_size=1024)
            image_url = self._image_to_data_uri(resized)
        else:
            raise ValueError("image 必须是 PIL Image 或 URL 字符串")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        return self.chat(messages, model=model)

    # ==================== 工具方法 ====================

    def get_usage(self) -> Dict[str, Any]:
        """获取使用量信息"""
        return {
            "info": "请访问 https://enter.pollinations.ai 查看账户余额和使用量",
            "balance_endpoint": f"{self.base_url}/account/balance",
        }

    def get_model(self) -> str:
        return self.image_model

    def get_name(self) -> str:
        return f"Pollinations AI (图像: {self.image_model}, 视频: {self.video_model})"

    def check_balance(self) -> Dict[str, Any]:
        """查询 Pollen 余额"""
        try:
            resp = self._request("GET", "/account/balance", timeout=30)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}