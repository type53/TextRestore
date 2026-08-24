# -*- coding: utf-8 -*-
"""生成应用图标 icon.ico (仅打包时需要, 需要 Pillow)。"""
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 256


def main():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 圆角矩形 + 竖向渐变背景
    top = (74, 108, 247)
    bottom = (47, 84, 210)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        d.line([(0, y), (SIZE, y)], fill=color)

    mask = Image.new('L', (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=52, fill=255)
    img.putalpha(mask)
    d = ImageDraw.Draw(img)

    # 白色字母 A
    font = None
    for path in (r'C:\Windows\Fonts\arialbd.ttf', r'C:\Windows\Fonts\seguisb.ttf'):
        if os.path.exists(path):
            font = ImageFont.truetype(path, 150)
            break
    if font is None:
        font = ImageFont.load_default(size=160)
    bbox = d.textbbox((0, 0), 'A', font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((SIZE - w) / 2 - bbox[0], (SIZE - h) / 2 - bbox[1]),
           'A', font=font, fill=(255, 255, 255, 255))

    # 右下角绿色对勾
    d.ellipse([172, 172, 236, 236], fill=(46, 204, 113, 255))
    d.line([(186, 204), (197, 215), (222, 189)], fill=(255, 255, 255, 255),
           width=12, joint='curve')

    img.save('icon.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                (64, 64), (128, 128), (256, 256)])
    print('icon.ico generated')


if __name__ == '__main__':
    main()
