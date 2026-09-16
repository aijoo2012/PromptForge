from .base import BaseHandler

class AudioHandler(BaseHandler):
    def handle(self, intent):
        text = intent.get("original_text", "")
        if not text:
            self._reply("❌ 请提供要转换的文本")
            return

        from handlers.text_to_image import TextToImageHandler
        engine = TextToImageHandler(self.app)._get_api_engine()
        if not hasattr(engine, "generate_audio"):
            self._reply("❌ 当前 API 不支持音频生成")
            return

        self._update_status("🔊 生成语音中...")
        try:
            audio_bytes = engine.generate_audio(text, voice="nova", output_path="output/audio.mp3")
            self._reply(f"✅ 音频已生成：output/audio.mp3")
        except Exception as e:
            self._reply(f"❌ 音频生成失败：{e}")