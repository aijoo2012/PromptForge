#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PromptForge 每日任务 - CLI 薄包装

真正的逻辑在 skills/daily_pipeline/skill.py。
这里只负责命令行参数解析，方便脚本/计划任务调用。

用法：见 skills/daily_pipeline/README.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from skills.daily_pipeline import DailyPipeline
    from skills.daily_pipeline.skill import VALID_PRESET_CATEGORIES

    parser = argparse.ArgumentParser(
        description="PromptForge 每日自动化任务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--topic", "-t", default=None, help="主题（默认随机）")
    parser.add_argument("--preset", "-p", default=None, help="预设（默认随机）")
    parser.add_argument("--preset-category", default=None, choices=VALID_PRESET_CATEGORIES)
    parser.add_argument("--vary-preset", action="store_true",
                        help="每张图从同分类换一个预设")
    parser.add_argument("--count", "-c", type=int, default=6, help="张数（默认 6）")
    parser.add_argument("--theme", default="newspaper", help="排版主题")
    parser.add_argument("--output-root", default="output/daily", help="生图输出根目录")
    parser.add_argument("--qr", default="assets/qr/公众号结束处.png", help="文末二维码")
    parser.add_argument("--no-publish", action="store_true",
                        help="不推草稿箱（默认推送）")
    parser.add_argument("--open", action="store_true", help="完成后打开浏览器")
    parser.add_argument("--skip-curate", action="store_true", help="只生图")
    parser.add_argument("--skip-generate", action="store_true",
                        help="跳过生图（需 --image-dir）")
    parser.add_argument("--image-dir", default=None, help="已有图片目录")
    parser.add_argument("--list-presets", action="store_true")
    parser.add_argument("--list-topics", action="store_true")
    args = parser.parse_args()

    # 加载 .env
    try:
        from dotenv import load_dotenv
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass

    pipe = DailyPipeline()

    if args.list_presets:
        cats = pipe.list_presets()
        if not cats:
            print("⚠️ 未加载到预设库")
            return 1
        total = 0
        for cat, names in cats.items():
            print(f"\n【{cat}】({len(names)} 个)")
            total += len(names)
            for i, n in enumerate(names, 1):
                print(f"  {i:3d}. {n}")
        print(f"\n共 {total} 个预设")
        return 0

    if args.list_topics:
        topics = pipe.list_topics()
        total = 0
        for style, tlist in topics.items():
            print(f"\n【{style}】({len(tlist)} 个)")
            total += len(tlist)
            for i, t in enumerate(tlist, 1):
                print(f"  {i:3d}. {t}")
        print(f"\n共 {total} 个主题")
        return 0

    result = pipe.execute(
        topic=args.topic,
        preset=args.preset,
        preset_category=args.preset_category,
        vary_preset=args.vary_preset,
        count=args.count,
        theme=args.theme,
        output_root=args.output_root,
        qr=args.qr,
        publish=not args.no_publish,
        open_browser=args.open,
        skip_curate=args.skip_curate,
        skip_generate=args.skip_generate,
        image_dir=args.image_dir,
    )

    if result["status"] != "success":
        print(f"\n❌ 失败: {result.get('error')}")
        return 1

    r = result["result"]
    print("\n" + "=" * 62)
    print("  🎉 全部完成！")
    print("=" * 62)
    print(f"📁 图片目录  : {r['image_dir']}")
    print(f"📄 文章      : {r['md_path']}")
    print(f"🎨 排版输出  : {r['article_dir']}")
    print(f"🌐 浏览器预览: {r['preview_path']}")
    print(f"📋 富文本    : {r['clipboard_path']}")
    print(f"📤 已推送    : {'是' if r['published'] else '否'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())