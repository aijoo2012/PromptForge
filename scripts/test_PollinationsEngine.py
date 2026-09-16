import os
from dotenv import load_dotenv
load_dotenv()

from api_engines.pollinations import PollinationsEngine

engine = PollinationsEngine(
    api_key=os.getenv("POLLINATIONS_API_KEY"),
    model="black-forest-labs/flux.1-schnell",
    audio_model="community/NamanSoni78/aura-2-amalthea-en",
)

# 1. 文生图
img = engine.text_to_image("a beautiful sunset over the ocean", width=1024, height=1024)
img.save("test_sunset.png")
print("✅ 文生图 OK，尺寸:", img.size)   # 免费层会强制 768x768

# 2. TTS
engine.generate_audio("Hello from Pollinations", voice="nova", output_path="test.mp3")
print("✅ TTS OK")

# 3. 图生图（预期会失败，因为免费模型不支持）
try:
    out = engine.image_to_image("make it watercolor", image=img)
    print("✅ 图生图 OK")
except Exception as e:
    print("❌ 图生图失败（预期）:", str(e)[:120])