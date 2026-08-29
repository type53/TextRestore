# -*- coding: utf-8 -*-
"""生成应用图标 icon.ico (仅打包时需要, 需要 Pillow)。

设计: 靛蓝->紫渐变圆角方块, 中央大字母 A 左半红(被替换)右半绿(已还原),
寓意"隐蔽字符 -> 正常字符"的还原过程。
"""
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 256


def main():
    # ---- 背景: 对角渐变 ----
    c1 = (74, 108, 247)    # #4A6CF7 靛蓝
    c2 = (124, 77, 255)    # #7C4DFF 紫
    g = Image.new('RGBA', (2, 2))
    g.putpixel((0, 0), c1)
    g.putpixel((1, 0), c1)
    g.putpixel((0, 1), c2)
    g.putpixel((1, 1), c2)
    grad = g.resize((SIZE, SIZE), Image.BILINEAR)

    # 圆角矩形遮罩
    mask = Image.new('L', (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [10, 10, SIZE - 10, SIZE - 10], radius=58, fill=255)
    img = grad.copy()
    img.putalpha(mask)

    # ---- 中央字母 A: 左红右绿 ----
    font = None
    for path in (r'C:\Windows\Fonts\arialbd.ttf',
                 r'C:\Windows\Fonts\seguisb.ttf'):
        if os.path.exists(path):
            font = ImageFont.truetype(path, 165)
            break
    if font is None:
        font = ImageFont.load_default(size=170)

    amask = Image.new('L', (SIZE, SIZE), 0)
    ImageDraw.Draw(amask).text((SIZE / 2, SIZE / 2), 'A', font=font,
                               fill=255, anchor='mm')

    half = SIZE // 2
    left = amask.crop((0, 0, half, SIZE))
    right = amask.crop((half, 0, SIZE, SIZE))
    img.paste((255, 95, 86, 255), (0, 0), left)       # 红: 被替换
    img.paste((46, 213, 115, 255), (half, 0), right)  # 绿: 已还原

    # ---- 中央分隔细线 (半透明白) ----
    d = ImageDraw.Draw(img)
    for y in range(38, SIZE - 38):
        d.point((half, y), fill=(255, 255, 255, 150))

    img.save('icon.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                (64, 64), (128, 128), (256, 256)])
    # 同时输出 256px PNG 预览 (运行时作为窗口图标, 打包时捆绑)
    img.save('icon_preview.png')
    print('icon.ico + icon_preview.png generated')


if __name__ == '__main__':
    main()
