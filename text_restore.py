# -*- coding: utf-8 -*-
"""
text_restore.py — 隐蔽字符还原工具
===================================

背景
----
ChatGPT / Claude Code / Gemini 等模型有时会在输出中偷偷插入或替换一些
肉眼几乎无法分辨的字符(全角字符、零宽字符、花体字母、西里尔相似字母等),
用来识别中文用户。

本工具提供一个简单的图形界面(tkinter, 仅标准库, 无需安装任何第三方依赖):
    * 上方输入框粘贴模型输出;
    * 程序自动检查输入内容, 把所有"隐蔽字符"还原为对应的普通英文字符;
    * 结果实时显示在下方输出框;
    * 点击"复制结果"一键复制。

运行方式
--------
    python text_restore.py
或直接双击本文件(Windows)。

还原内容(均可通过界面上的复选框开关):
    1. 全角转半角      : ＡＢＣ１２３ -> ABC123
    2. 中文标点转英文  : ，。？！《》“” -> ,.?!<>""
    3. 花体/数学字体   : 𝐀𝐁𝐂𝟏𝟐𝟑 -> ABC123
    4. 上下标          : x²y₃ -> x2y3
    5. 相似字母        : С(西里尔) ᴀ(小型大写) Ⱥ -> C A A
    6. 删除不可见字符  : 零宽空格/连接符/BOM/双向控制符等
    7. 特殊空格归一    : 不间断空格/窄空格 -> 普通空格
    8. 删除末尾换行    : 输入末尾多余的 \n / \r 不会出现在输出中

其他特性:
    * diff 高亮: 输入框中被替换的字符飘红, 输出框中还原后的字符飘绿
    * 输入/输出框滚动位置同步, 方便对照观察
    * 窗口缩放时两个文本框等高自适应, 按钮始终可见
    * 选中联动(IDE diff 效果): 鼠标框选任一边的内容, 另一边的对应区域
      同步高亮(浅蓝色), 且拖拽选中时的自动滚动也会同步
    * 深色主题: 右下角按钮一键切换
    * 设置面板: 还原选项收纳在"设置"窗口中, 主界面更简洁
    * 前后缀: 设置中可配置多行前缀/后缀, 主界面勾选是否附加到输出结果
    * 所有设置(主题/选项/前后缀)持久化到 %APPDATA%/TextRestore/config.json
"""

import os
import json
import bisect
import tkinter as tk
from tkinter import ttk
import unicodedata

APP_TITLE = "隐蔽字符还原工具"
APP_HINT = ("把模型输出粘贴到上方输入框, 下方输出框会自动给出还原后的文本。"
            "全角、中文标点、花体字母、上下标、相似字母、不可见字符等都会被还原为普通英文字符。")

UI_FONT = ('Microsoft YaHei UI', 10)
TEXT_FONT = ('Microsoft YaHei UI', 11)

# ---------------- 字符映射表 ----------------

# 1) 全角 -> 半角 (U+FF01..U+FF5E 及全角空格 U+3000)
FW_MAP = {chr(c): chr(c - 0xFEE0) for c in range(0xFF01, 0xFF5F)}
FW_MAP['\u3000'] = ' '
# 半角片假名中的类标点字符
FW_MAP.update({
    '\uFF61': '.',   # ｡ 半角句号
    '\uFF62': '[',   # ｢
    '\uFF63': ']',   # ｣
    '\uFF64': ',',   # ､
    '\uFF65': '.',   # ･
    '\uFF70': '-',   # ｰ
})

# 2) 中文/全角标点 -> 英文标点 (仅在全角区 FF01..FF5E 之外的字符)
PUNCT_MAP = {
    '。': '.', '、': ',',
    '《': '<', '》': '>', '〈': '<', '〉': '>',
    '「': '[', '」': ']', '『': '[', '』': ']',
    '〖': '[', '〗': ']', '〔': '(', '〕': ')',
    '｟': '(', '｠': ')',
    '—': '-', '–': '-', '―': '-',
    '…': '...', '⋯': '...',
    '“': '"', '”': '"', '‘': "'", '’': "'",
    '〝': '"', '〞': '"',
    '・': '·',
}

# 3) 数学字母数字符号(粗体/斜体/花体/双线体/等宽体等) -> 普通字母数字
def _build_math_map():
    m = {}
    # 字母: 13 种字体风格, 每种 52 个槽位(A-Z 占 0..25, a-z 占 26..51), 未分配处为空洞
    for style in range(13):
        base = 0x1D400 + style * 52
        for slot in range(52):
            cp = base + slot
            ch = chr(cp)
            if unicodedata.category(ch) == 'Cn':  # 未分配代码点, 跳过
                continue
            m[ch] = chr(0x41 + slot) if slot < 26 else chr(0x61 + slot - 26)
    # 数字: 粗体/双线体/无衬线/粗无衬线/等宽, 共 5 种风格各 10 个
    for cp in range(0x1D7CE, 0x1D800):
        m[chr(cp)] = chr(0x30 + (cp - 0x1D7CE) % 10)
    m['\U0001D6A4'] = 'i'  # 𝚤 无点 i
    m['\U0001D6A5'] = 'j'  # 𝚥 无点 j
    return m

MATH_MAP = _build_math_map()

# 4) 不可见字符(零宽字符、双向控制符、软连字符等) -> 删除
INVISIBLE_MAP = {
    '\u200B': '', '\u200C': '', '\u200D': '',      # 零宽空格/非连接符/连接符
    '\uFEFF': '',                                   # BOM/零宽无断空格
    '\u2060': '', '\u2061': '', '\u2062': '',       # 词连接符/函数应用/隐形乘号
    '\u2063': '', '\u2064': '',                     # 隐形分隔符/隐形加号
    '\u034F': '',                                   # 组合字素连接符
    '\u200E': '', '\u200F': '',                     # 左/右标记
    '\u202A': '', '\u202B': '', '\u202C': '',       # 双向控制符
    '\u202D': '', '\u202E': '',
    '\u180E': '', '\u3164': '', '\u115F': '', '\u1160': '',  # 各种填充符
    '\u00AD': '',                                   # 软连字符
}

# 5) 特殊空格 -> 普通空格
SPACE_MAP = {chr(c): ' ' for c in range(0x2000, 0x200B)}
SPACE_MAP.update({
    '\u00A0': ' ', '\u1680': ' ', '\u202F': ' ', '\u205F': ' ',
})

# 6) 相似字母(西里尔/希腊/小型大写/拉丁变体) -> 拉丁字母
HOMOGLYPH_MAP = {
    # 西里尔
    '\u0410': 'A', '\u0412': 'B', '\u0415': 'E', '\u041A': 'K',
    '\u041C': 'M', '\u041D': 'H', '\u041E': 'O', '\u0420': 'P',
    '\u0421': 'C', '\u0422': 'T', '\u0423': 'Y', '\u0425': 'X',
    '\u0405': 'S', '\u0406': 'I', '\u0408': 'J',
    '\u0430': 'a', '\u0435': 'e', '\u043E': 'o', '\u0440': 'p',
    '\u0441': 'c', '\u0443': 'y', '\u0445': 'x',
    '\u0455': 's', '\u0456': 'i', '\u0458': 'j', '\u04CF': 'l',
    # 希腊
    '\u0391': 'A', '\u0392': 'B', '\u0395': 'E', '\u0396': 'Z',
    '\u0397': 'H', '\u0399': 'I', '\u039A': 'K', '\u039C': 'M',
    '\u039D': 'N', '\u039F': 'O', '\u03A1': 'P', '\u03A4': 'T',
    '\u03A5': 'Y', '\u03A7': 'X', '\u03F2': 'c', '\u03F9': 'C',
    # 拉丁变体 / 小型大写
    '\u0131': 'i', '\u017F': 's', '\u0237': 'j',
    '\u0261': 'g', '\u0269': 'i',
    '\u0262': 'G', '\u029C': 'H', '\u026A': 'I', '\u029F': 'L',
    '\u0274': 'N', '\u0280': 'R', '\u028F': 'Y',
    '\u1D00': 'A', '\u1D03': 'B', '\u1D04': 'C', '\u1D05': 'D',
    '\u1D07': 'E', '\u1D0A': 'J', '\u1D0B': 'K', '\u1D0D': 'M',
    '\u1D0F': 'O', '\u1D18': 'P', '\u1D1B': 'T', '\u1D1C': 'U',
    '\u1D20': 'V', '\u1D21': 'W', '\u1D22': 'Z',
    '\uA730': 'F', '\uA731': 'S',
}

# 7) 上标/下标 -> 普通字符
SUPERSUB_MAP = {
    # 上标数字
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
    '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    # 上标字母
    'ᵃ': 'a', 'ᵇ': 'b', 'ᶜ': 'c', 'ᵈ': 'd', 'ᵉ': 'e',
    'ᶠ': 'f', 'ᵍ': 'g', 'ʰ': 'h', 'ⁱ': 'i', 'ʲ': 'j',
    'ᵏ': 'k', 'ˡ': 'l', 'ᵐ': 'm', 'ⁿ': 'n', 'ᵒ': 'o',
    'ᵖ': 'p', 'ʳ': 'r', 'ˢ': 's', 'ᵗ': 't', 'ᵘ': 'u',
    'ᵛ': 'v', 'ʷ': 'w', 'ˣ': 'x', 'ʸ': 'y', 'ᶻ': 'z',
    # 上标符号
    '⁺': '+', '⁻': '-', '⁼': '=', '⁽': '(', '⁾': ')',
    # 下标数字
    '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
    '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
    # 下标符号
    '₊': '+', '₋': '-', '₌': '=', '₍': '(', '₎': ')',
    # 下标字母
    'ₐ': 'a', 'ₑ': 'e', 'ₒ': 'o', 'ₓ': 'x',
    'ᵢ': 'i', 'ⱼ': 'j', 'ᵣ': 'r', 'ᵤ': 'u', 'ᵥ': 'v',
}

# 处理顺序(后面的会再处理前面产生的结果, 当前无交叉冲突)
MAPPINGS = {
    'fullwidth': FW_MAP,
    'punct': PUNCT_MAP,
    'math': MATH_MAP,
    'super': SUPERSUB_MAP,
    'homoglyph': HOMOGLYPH_MAP,
    'invisible': INVISIBLE_MAP,
    'space': SPACE_MAP,
}

CHECK_LABELS = {
    'fullwidth': '全角转半角',
    'punct': '中文标点',
    'math': '花体字体',
    'super': '上下标',
    'homoglyph': '相似字母',
    'invisible': '不可见字符',
    'space': '特殊空格',
    'trailing': '删除末尾换行',
}

STATUS_NAMES = {
    'fullwidth': '全角',
    'punct': '标点',
    'math': '花体',
    'super': '上下标',
    'homoglyph': '相似',
    'invisible': '不可见',
    'space': '空格',
    'trailing': '末尾换行',
}

# 界面上的选项顺序 (trailing 在 convert_text 中单独处理, 不在 MAPPINGS 里)
OPTION_ORDER = list(MAPPINGS) + ['trailing']


def _merge_ranges(ranges):
    """把区间排序并合并相邻区间, 减少 Tk 标注次数。"""
    if not ranges:
        return []
    ranges = sorted(ranges)
    merged = [list(ranges[0])]
    for s, e in ranges[1:]:
        if s <= merged[-1][1]:
            if e > merged[-1][1]:
                merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(a, b) for a, b in merged]


def convert_text(text, enabled):
    """按启用选项转换文本。

    返回 (结果字符串, {分类: 替换数量}, 输入中被替换的区间, 输出中还原结果的区间,
          映射信息)。
    区间为 [(起始下标, 结束下标), ...] 形式, 已合并相邻区间, 用于 diff 高亮。
    末尾的换行符(\n / \r)会被删除, 并在输入区间中标注出来。
    映射信息用于选中区域联动:
        'in_to_out_start': 每个输入字符对应的输出起点(含末尾哨兵)
        'out_to_in'       : 每个输出字符对应的输入下标
        'cut'             : 参与转换的输入长度(末尾换行被排除)
    """
    order = [k for k in MAPPINGS if enabled.get(k, True)]
    counts = {k: 0 for k in order}
    red = []     # 输入中发生替换的区间
    green = []   # 输出中替换结果的区间

    # 末尾换行处理: 删除末尾所有 \n / \r, 在输入中标注
    cut = len(text)
    if enabled.get('trailing', True):
        while cut > 0 and text[cut - 1] in '\r\n':
            cut -= 1
        if cut < len(text):
            counts['trailing'] = len(text) - cut
            red.append((cut, len(text)))

    out = []
    out_pos = 0
    in_to_out_start = []   # 每个输入字符对应的输出起点
    out_to_in = []         # 每个输出字符对应的输入下标
    for in_pos in range(cut):
        in_to_out_start.append(out_pos)
        ch = text[in_pos]
        new = ch
        changed = False
        for k in order:
            n = MAPPINGS[k].get(new, new)
            if n != new:
                counts[k] += 1
                new = n
                changed = True
        if changed:
            red.append((in_pos, in_pos + 1))
            if new:
                green.append((out_pos, out_pos + len(new)))
        out.append(new)
        out_pos += len(new)
        for _ in new:
            out_to_in.append(in_pos)
    in_to_out_start.append(out_pos)   # 哨兵: 输入末尾之后
    return ''.join(out), counts, _merge_ranges(red), _merge_ranges(green), {
        'in_to_out_start': in_to_out_start,
        'out_to_in': out_to_in,
        'cut': cut,
    }


def _line_starts(s):
    """返回每行在字符串中的起始偏移(第 1 行从 0 开始)。"""
    starts = [0]
    for i, ch in enumerate(s):
        if ch == '\n':
            starts.append(i + 1)
    return starts


def _idx_to_offset(index, line_starts):
    """Tk 文本索引 'line.col' -> 字符偏移。"""
    line, col = (int(x) for x in index.split('.'))
    return line_starts[line - 1] + col


def _offset_to_index(offset, line_starts, total_len):
    """字符偏移 -> Tk 文本索引 'line.col'。"""
    offset = max(0, min(offset, total_len))
    li = bisect.bisect_right(line_starts, offset) - 1
    return f'{li + 1}.{offset - line_starts[li]}'


# ---------------- 主题配色 ----------------

THEMES = {
    'light': {
        'ttk_theme': 'vista',
        'root_bg': '#f0f0f0',
        'text_bg': '#ffffff',
        'text_fg': '#000000',
        'sel_bg': '#c9e2ff',      # 浅蓝选中色
        'sel_fg': None,
        'mirror_bg': '#dcebff',   # 另一边联动高亮 (更浅的蓝)
        'mirror_fg': None,
        'red_fg': '#c0392b', 'red_bg': '#fdecea',
        'green_fg': '#1e8449', 'green_bg': '#eafaf1',
        'status_fg': '#1a6fb0',
        'hint_fg': '#667777',
    },
    'dark': {
        'ttk_theme': 'clam',
        'root_bg': '#1e1e1e',
        'text_bg': '#1e1e1e',
        'text_fg': '#d4d4d4',
        'sel_bg': '#c9e2ff',
        'sel_fg': '#000000',
        'mirror_bg': '#a9c8ec',
        'mirror_fg': '#000000',
        'red_fg': '#ff8a80', 'red_bg': '#4a2323',
        'green_fg': '#7ee787', 'green_bg': '#1f3d2b',
        'status_fg': '#79b8ff',
        'hint_fg': '#9d9d9d',
    },
}


# ---------------- iOS 风格开关 ----------------

SWITCH_THUMB = '#ffffff'
SWITCH_ON = '#34c759'        # 浅色主题开启色 (iOS 绿)
SWITCH_ON_DARK = '#30d158'   # 深色主题开启色
SWITCH_OFF = '#e9e9eb'       # 浅色主题关闭色
SWITCH_OFF_DARK = '#3a3a3c'  # 深色主题关闭色


class Switch(tk.Canvas):
    """iOS 风格开关控件, 绑定 tk.BooleanVar, 点击切换并带动画。

    开启: 绿色轨道 + 白色圆点滑到右侧; 关闭: 灰色轨道 + 圆点滑到左侧。
    边缘使用超采样抗锯齿渲染 (4x), 圆角平滑无锯齿。
    """

    _SS = 4   # 超采样倍数

    def __init__(self, master, variable=None, command=None, dark=False,
                 width=46, height=26, pad=2, bg='#f0f0f0', **kw):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0, bd=0, bg=bg, **kw)
        self._var = variable
        self._command = command
        self._dark = dark
        self._width = width
        self._height = height
        self._pad = pad
        self._anim = None
        self._thumb_x = pad
        self._photo = None
        self._image_item = None
        self._bg = self._parse_color(bg)
        self._track_cov = None    # 轨道覆盖掩码缓存 (几何不变)
        if variable is not None:
            variable.trace_add('write', lambda *a: self._draw())
        self.bind('<Button-1>', self._on_click)
        self._draw()

    # ---------- 对外接口 ----------
    def set_dark(self, dark, bg=None):
        self._dark = dark
        if bg:
            self.configure(bg=bg)
            self._bg = self._parse_color(bg)
        self._draw()

    # ---------- 内部 ----------
    def _on_click(self, event=None):
        if self._var is not None:
            self._var.set(not self._var.get())
        if self._command:
            self._command()
        return 'break'

    def _is_on(self):
        return bool(self._var.get()) if self._var is not None else False

    def _track_color(self):
        if self._is_on():
            return SWITCH_ON_DARK if self._dark else SWITCH_ON
        return SWITCH_OFF_DARK if self._dark else SWITCH_OFF

    @staticmethod
    def _parse_color(c):
        c = c.lstrip('#')
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def _blend(bg, fg, cov):
        return tuple(round(b + (f - b) * cov) for b, f in zip(bg, fg))

    @staticmethod
    def _in_pill(x, y, w, r, cy):
        """点是否在胶囊轨道内 (中部矩形 + 两端半圆)。"""
        if r <= x <= w - r:
            return 0 <= y <= 2 * cy
        cx = r if x < r else w - r
        dx = x - cx
        dy = y - cy
        return dx * dx + dy * dy <= r * r

    def _draw(self):
        if self._photo is None:
            self._photo = tk.PhotoImage(width=self._width, height=self._height)
            self._image_item = self.create_image(0, 0, image=self._photo,
                                                 anchor='nw')
        target = self._width - self._height + self._pad if self._is_on() else self._pad
        if self._anim is not None:
            try:
                self.after_cancel(self._anim)
            except Exception:
                pass
            self._anim = None
        if target != self._thumb_x:
            self._animate(target)
        else:
            self._render(self._thumb_x)

    def _render(self, thumb_x):
        """超采样抗锯齿渲染当前帧到 PhotoImage。

        注意: 当前 Tk 版本的 PhotoImage.put 按"列优先"放置像素,
        每列最多放置 height 个, 因此按列逐次 put。
        """
        w, h = self._width, self._height
        pad = self._pad
        s = self._SS
        inv = 1.0 / (s * s)
        bg = self._bg
        track_rgb = self._parse_color(self._track_color())
        thumb_rgb = self._parse_color(SWITCH_THUMB)
        cy = h / 2.0
        r_thumb = (h - 2 * pad) / 2.0
        cx = thumb_x + r_thumb

        # 轨道覆盖掩码 (几何固定, 首次计算后缓存)
        if self._track_cov is None:
            r_track = h / 2.0
            cov = []
            for j in range(h):
                row = []
                for i in range(w):
                    cnt = 0
                    for sy in range(s):
                        y = j + (sy + 0.5) / s
                        for sx in range(s):
                            x = i + (sx + 0.5) / s
                            if self._in_pill(x, y, w, r_track, cy):
                                cnt += 1
                    row.append(cnt * inv)
                cov.append(row)
            self._track_cov = cov

        # 拇指包围盒 (只在此范围内计算覆盖)
        bx0 = max(0, int(cx - r_thumb - 1))
        bx1 = min(w - 1, int(cx + r_thumb + 1))
        by0 = max(0, int(cy - r_thumb - 1))
        by1 = min(h - 1, int(cy + r_thumb + 1))
        r2 = r_thumb * r_thumb

        # 按列生成像素字符串, 每列一次 put
        for i in range(w):
            parts = []
            for j in range(h):
                t_cov = self._track_cov[j][i]
                if bx0 <= i <= bx1 and by0 <= j <= by1:
                    cnt = 0
                    for sy in range(s):
                        y = j + (sy + 0.5) / s
                        for sx in range(s):
                            x = i + (sx + 0.5) / s
                            dx = x - cx
                            dy = y - cy
                            if dx * dx + dy * dy <= r2:
                                cnt += 1
                    u_cov = cnt * inv
                else:
                    u_cov = 0.0
                if u_cov >= 1.0:
                    c = thumb_rgb
                elif t_cov <= 0.0:
                    c = bg
                else:
                    c = self._blend(bg, track_rgb, t_cov)
                    if u_cov > 0.0:
                        c = self._blend(c, thumb_rgb, u_cov)
                parts.append('#%02x%02x%02x' % c)
            self._photo.put(' '.join(parts), to=(i, 0))

    def _animate(self, target):
        step = (target - self._thumb_x) / 8.0

        def tick():
            self._thumb_x += step
            if step == 0 or (step > 0 and self._thumb_x >= target) \
                    or (step < 0 and self._thumb_x <= target):
                self._thumb_x = target
                self._render(self._thumb_x)
                self._anim = None
            else:
                self._render(self._thumb_x)
                self._anim = self.after(12, tick)

        tick()


def _config_path():
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    d = os.path.join(base, 'TextRestore')
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return os.path.join(d, 'config.json')


def _load_config():
    try:
        with open(_config_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_config(cfg):
    try:
        with open(_config_path(), 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False)
    except OSError:
        pass


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry('820x680')
        root.minsize(640, 320)
        self._status_after = None
        self._syncing = False
        self._map = None          # 最近一次转换的映射信息
        self._last_result = ''
        self._in_line_starts = [0]
        self._out_line_starts = [0]
        self._switches = []       # 所有 Switch 控件, 主题切换时统一更新
        self._settings_win = None
        cfg = _load_config()
        self.dark = bool(cfg.get('dark', False))
        self.prefix_var = tk.StringVar(value=cfg.get('prefix', ''))
        self.suffix_var = tk.StringVar(value=cfg.get('suffix', ''))
        self.include_prefix = tk.BooleanVar(value=bool(cfg.get('include_prefix', False)))
        self.include_suffix = tk.BooleanVar(value=bool(cfg.get('include_suffix', False)))
        opts = cfg.get('options', {})
        self.enabled = {k: tk.BooleanVar(value=bool(opts.get(k, True)))
                        for k in OPTION_ORDER}
        self._build_ui()
        self.apply_theme(self.dark)
        self.input_text.focus_set()
        self.do_convert()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky='nsew')
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)

        # ---- 顶部提示 + 图例 ----
        self.hint_label = ttk.Label(main, text=APP_HINT, foreground='#667',
                                    wraplength=760)
        self.hint_label.grid(row=0, column=0, sticky='w')
        legend = ttk.Frame(main)
        legend.grid(row=1, column=0, sticky='w', pady=(2, 0))
        self.legend_red = ttk.Label(legend, text='■ 输入中被替换的字符',
                                    foreground='#c0392b')
        self.legend_red.pack(side='left')
        ttk.Label(legend, text='   ', foreground='#667').pack(side='left')
        self.legend_green = ttk.Label(legend, text='■ 输出中还原后的字符',
                                      foreground='#1e8449')
        self.legend_green.pack(side='left')

        # ---- 输入区 ----
        ttk.Label(main, text='输入(自动转换):').grid(row=2, column=0,
                                                    sticky='w', pady=(8, 2))
        in_frame = ttk.Frame(main)
        in_frame.grid(row=3, column=0, sticky='nsew')
        self.input_text = tk.Text(in_frame, height=8, font=TEXT_FONT,
                                  wrap='word', undo=True)
        self.in_scroll = ttk.Scrollbar(in_frame, command=self._scroll_both)
        self.input_text.configure(yscrollcommand=self.in_scroll.set)
        self.input_text.pack(side='left', fill='both', expand=True)
        self.in_scroll.pack(side='right', fill='y')

        # ---- 输出区 ----
        ttk.Label(main, text='输出(转换结果):').grid(row=4, column=0,
                                                    sticky='w', pady=(0, 2))
        out_frame = ttk.Frame(main)
        out_frame.grid(row=5, column=0, sticky='nsew')
        self.output_text = tk.Text(out_frame, height=8, font=TEXT_FONT,
                                   wrap='word')
        self.out_scroll = ttk.Scrollbar(out_frame, command=self._scroll_both)
        self.output_text.configure(yscrollcommand=self.out_scroll.set)
        self.output_text.pack(side='left', fill='both', expand=True)
        self.out_scroll.pack(side='right', fill='y')

        # 两个文本框等高、均匀分配空间, 缩放行为一致
        main.rowconfigure(3, weight=1, uniform='texts')
        main.rowconfigure(5, weight=1, uniform='texts')

        # diff 高亮配色: 输入框替换字符飘红, 输出框还原字符飘绿
        self.input_text.tag_configure('red', foreground='#c0392b',
                                      background='#fdecea')
        self.output_text.tag_configure('green', foreground='#1e8449',
                                       background='#eafaf1')

        # 输出框: 只读, 但允许鼠标选中, Ctrl+C 复制选中, Ctrl+A 全选
        self.output_text.bind('<Key>', self._readonly_block)

        # ---- 状态信息 (独占一行) ----
        self.status_var = tk.StringVar(value='就绪。')
        self.status_label = ttk.Label(main, textvariable=self.status_var,
                                      foreground='#1a6fb0')
        self.status_label.grid(row=6, column=0, sticky='w', pady=(10, 0))

        # ---- 底部: 复制/清空/设置 + 前后缀开关 + 主题 ----
        bottom = ttk.Frame(main)
        bottom.grid(row=7, column=0, sticky='ew', pady=(6, 0))
        ttk.Button(bottom, text='复制结果', command=self.copy_result).pack(side='left')
        ttk.Button(bottom, text='清空输入', command=self.clear_input).pack(side='left', padx=8)
        ttk.Button(bottom, text='设置', command=self.open_settings).pack(side='left')
        ttk.Label(bottom, text='包含前缀').pack(side='left', padx=(16, 4))
        sw1 = Switch(bottom, variable=self.include_prefix,
                     command=self._on_setting_changed, dark=self.dark,
                     bg=THEMES['dark' if self.dark else 'light']['root_bg'])
        sw1.pack(side='left')
        ttk.Label(bottom, text='包含后缀').pack(side='left', padx=(16, 4))
        sw2 = Switch(bottom, variable=self.include_suffix,
                     command=self._on_setting_changed, dark=self.dark,
                     bg=THEMES['dark' if self.dark else 'light']['root_bg'])
        sw2.pack(side='left')
        self._switches.extend([sw1, sw2])
        self.theme_btn = ttk.Button(bottom, text='深色主题', command=self.toggle_theme)
        self.theme_btn.pack(side='right', padx=(0, 8))

        # 输入内容变化时自动转换
        self.input_text.bind('<KeyRelease>', self._on_change)
        self.input_text.bind('<<Paste>>', self._on_change)

        # 同步滚动: 滚轮作用于两个文本框
        for w in (self.input_text, self.output_text):
            w.bind('<MouseWheel>', self._wheel_both)   # Windows / macOS
            w.bind('<Button-4>', self._wheel_both)     # Linux 上滚
            w.bind('<Button-5>', self._wheel_both)     # Linux 下滚

        # 选中联动 (IDE diff 效果) + 拖拽自动滚动同步
        for w in (self.input_text, self.output_text):
            w.bind('<<Selection>>', self._on_selection)
            w.bind('<B1-Motion>', self._on_drag)
            w.bind('<ButtonRelease-1>', self._on_selection)
        self.input_text.bind('<Control-a>', self._select_all_in)

    # ---------- 同步滚动 ----------
    def _scroll_both(self, *args):
        """滚动条拖动时, 两个文本框一起滚动。"""
        if self._syncing:
            return
        self._syncing = True
        try:
            self.input_text.yview(*args)
            self.output_text.yview(*args)
        finally:
            self._syncing = False

    def _wheel_both(self, event):
        """滚轮事件: 两个文本框一起滚动。"""
        delta = getattr(event, 'delta', 0)
        if delta:
            steps = -1 if delta > 0 else 1
            if abs(delta) >= 120:
                steps = -delta // 120
        else:
            steps = 1 if event.num == 4 else -1
        if not self._syncing:
            self._syncing = True
            try:
                self.input_text.yview_scroll(steps, 'units')
                self.output_text.yview_scroll(steps, 'units')
            finally:
                self._syncing = False
        return 'break'

    def _sync_output_view(self):
        """把输出框滚动位置对齐到输入框。"""
        if self._syncing:
            return
        self._syncing = True
        try:
            frac, _ = self.input_text.yview()
            self.output_text.yview_moveto(frac)
        finally:
            self._syncing = False

    # ---------- 主题 ----------
    def toggle_theme(self):
        self.dark = not self.dark
        self.apply_theme(self.dark)
        self._save_settings()

    def apply_theme(self, dark):
        theme = THEMES['dark' if dark else 'light']
        style = ttk.Style()
        try:
            style.theme_use(theme['ttk_theme'])
        except tk.TclError:
            pass
        style.configure('.', font=UI_FONT)
        if dark:
            style.configure('.', background=theme['root_bg'],
                            foreground=theme['text_fg'],
                            fieldbackground=theme['text_bg'],
                            bordercolor='#3c3c3c',
                            lightcolor='#3c3c3c', darkcolor='#3c3c3c')
            style.configure('TFrame', background=theme['root_bg'])
            style.configure('TLabel', background=theme['root_bg'],
                            foreground=theme['text_fg'])
            style.configure('TLabelframe', background=theme['root_bg'],
                            foreground=theme['text_fg'],
                            bordercolor='#3c3c3c',
                            lightcolor='#3c3c3c', darkcolor='#3c3c3c')
            style.configure('TLabelframe.Label', background=theme['root_bg'],
                            foreground=theme['text_fg'])
            style.configure('TButton', background='#333333',
                            foreground=theme['text_fg'],
                            bordercolor='#3c3c3c', relief='flat')
            style.map('TButton',
                      background=[('active', '#454545'), ('pressed', '#2a2a2a')])
            style.configure('TCheckbutton', background=theme['root_bg'],
                            foreground=theme['text_fg'])
            style.map('TCheckbutton', background=[('active', theme['root_bg'])])
            style.configure('TScrollbar', background='#3c3c3c',
                            troughcolor=theme['root_bg'],
                            arrowcolor=theme['text_fg'],
                            bordercolor=theme['root_bg'])
            style.map('TScrollbar', background=[('active', '#4a4a4a')])
        self.root.configure(bg=theme['root_bg'])
        for w in (self.input_text, self.output_text):
            w.configure(bg=theme['text_bg'], fg=theme['text_fg'],
                        insertbackground=theme['text_fg'],
                        highlightbackground=theme['root_bg'],
                        highlightthickness=1)
            if theme['sel_fg']:
                w.tag_configure('sel', background=theme['sel_bg'],
                                foreground=theme['sel_fg'])
            else:
                w.tag_configure('sel', background=theme['sel_bg'])
            if theme['mirror_fg']:
                w.tag_configure('mirror', background=theme['mirror_bg'],
                                foreground=theme['mirror_fg'])
            else:
                w.tag_configure('mirror', background=theme['mirror_bg'])
            w.tag_raise('mirror')   # 保证联动高亮盖过 diff 标记
        self.input_text.tag_configure('red', foreground=theme['red_fg'],
                                      background=theme['red_bg'])
        self.output_text.tag_configure('green', foreground=theme['green_fg'],
                                       background=theme['green_bg'])
        self.legend_red.configure(foreground=theme['red_fg'])
        self.legend_green.configure(foreground=theme['green_fg'])
        self.status_label.configure(foreground=theme['status_fg'])
        self.hint_label.configure(foreground=theme['hint_fg'])
        self.theme_btn.configure(text='浅色主题' if dark else '深色主题')
        # 所有开关控件跟随主题
        for sw in self._switches:
            if sw.winfo_exists():
                sw.set_dark(dark, theme['root_bg'])
        # 设置窗口中的文本框也跟随主题
        for w in (getattr(self, 'prefix_edit', None),
                  getattr(self, 'suffix_edit', None)):
            if w is not None and w.winfo_exists():
                self._apply_text_widget_theme(w)

    # ---------- 设置 ----------
    def open_settings(self):
        if self._settings_win is not None and self._settings_win.winfo_exists():
            self._settings_win.lift()
            self._settings_win.focus_set()
            return
        win = tk.Toplevel(self.root)
        win.title('设置')
        win.geometry('580x480')
        win.resizable(False, False)
        win.transient(self.root)
        main = ttk.Frame(win, padding=10)
        main.pack(fill='both', expand=True)
        theme = THEMES['dark' if self.dark else 'light']

        opt_frame = ttk.LabelFrame(main, text='还原选项', padding=8)
        opt_frame.pack(fill='x')
        for i, key in enumerate(OPTION_ORDER):
            cell = ttk.Frame(opt_frame)
            cell.grid(row=i // 4, column=i % 4, padx=6, pady=4, sticky='w')
            sw = Switch(cell, variable=self.enabled[key],
                        command=self._on_setting_changed, dark=self.dark,
                        width=40, height=22, bg=theme['root_bg'])
            sw.pack(side='left')
            ttk.Label(cell, text=CHECK_LABELS[key]).pack(side='left', padx=(6, 0))
            self._switches.append(sw)
        for col in range(4):
            opt_frame.columnconfigure(col, weight=1)

        pf_frame = ttk.LabelFrame(main, text='前后缀 (附加到输出结果)', padding=8)
        pf_frame.pack(fill='both', expand=True, pady=(10, 0))
        ttk.Label(pf_frame, text='前缀 (支持多行):').pack(anchor='w')
        self.prefix_edit = tk.Text(pf_frame, height=3, font=TEXT_FONT, wrap='word')
        self._apply_text_widget_theme(self.prefix_edit)
        self.prefix_edit.pack(fill='both', expand=True)
        self.prefix_edit.insert('1.0', self.prefix_var.get())
        ttk.Label(pf_frame, text='后缀 (支持多行):').pack(anchor='w', pady=(6, 0))
        self.suffix_edit = tk.Text(pf_frame, height=3, font=TEXT_FONT, wrap='word')
        self._apply_text_widget_theme(self.suffix_edit)
        self.suffix_edit.pack(fill='both', expand=True)
        self.suffix_edit.insert('1.0', self.suffix_var.get())

        self.prefix_edit.bind('<KeyRelease>', self._on_prefix_edit)
        self.suffix_edit.bind('<KeyRelease>', self._on_suffix_edit)

        ttk.Button(main, text='完成', command=win.destroy).pack(anchor='e', pady=(10, 0))
        self._settings_win = win

    def _on_prefix_edit(self, event=None):
        try:
            self.prefix_var.set(self.prefix_edit.get('1.0', 'end-1c'))
        except tk.TclError:
            return
        self._save_settings()
        self.do_convert()

    def _on_suffix_edit(self, event=None):
        try:
            self.suffix_var.set(self.suffix_edit.get('1.0', 'end-1c'))
        except tk.TclError:
            return
        self._save_settings()
        self.do_convert()

    def _on_setting_changed(self):
        self._save_settings()
        self.do_convert()

    def _save_settings(self):
        _save_config({
            'dark': self.dark,
            'prefix': self.prefix_var.get(),
            'suffix': self.suffix_var.get(),
            'include_prefix': self.include_prefix.get(),
            'include_suffix': self.include_suffix.get(),
            'options': {k: self.enabled[k].get() for k in OPTION_ORDER},
        })

    def _apply_text_widget_theme(self, w):
        theme = THEMES['dark' if self.dark else 'light']
        w.configure(bg=theme['text_bg'], fg=theme['text_fg'],
                    insertbackground=theme['text_fg'],
                    highlightbackground=theme['root_bg'],
                    highlightthickness=1)

    # ---------- 选中联动 (IDE diff 效果) ----------
    def _on_selection(self, event=None):
        src = getattr(event, 'widget', event) if event is not None else self.input_text
        self._mirror_selection(src)
        self.root.after_idle(self._follow_view, src)

    def _on_drag(self, event):
        # 鼠标拖拽选中的自动滚动: 让另一个文本框跟随
        src = getattr(event, 'widget', event)
        self.root.after_idle(self._follow_view, src)

    def _follow_view(self, src):
        if self._syncing or src is None:
            return
        self._syncing = True
        try:
            other = self.output_text if src is self.input_text else self.input_text
            other.yview_moveto(src.yview()[0])
        finally:
            self._syncing = False

    def _mirror_selection(self, src):
        other = self.output_text if src is self.input_text else self.input_text
        other.tag_remove('mirror', '1.0', 'end')
        if self._map is None:
            return
        try:
            s = src.index('sel.first')
            e = src.index('sel.last')
        except tk.TclError:
            return
        # 仅在源框确实有选区时, 才清除另一边旧的选区;
        # 程序化 tag_remove('sel') 会触发排队的 <<Selection>> 事件,
        # 若此时源框无选区则直接返回, 避免递归清除新选区
        other.tag_remove('sel', '1.0', 'end')
        if src is self.input_text:
            rng = self._map_input_range(s, e)
        else:
            rng = self._map_output_range(s, e)
        if rng:
            other.tag_add('mirror', rng[0], rng[1])

    def _map_input_range(self, s_idx, e_idx):
        """输入框选区 -> 输出框对应区间 (返回 Tk 索引或 None)。"""
        m = self._map
        s = _idx_to_offset(s_idx, self._in_line_starts)
        e = _idx_to_offset(e_idx, self._in_line_starts)
        if s >= m['cut']:
            return None
        e = min(e, m['cut'])
        os_ = m['in_to_out_start'][s] + self._prefix_len
        oe = m['in_to_out_start'][e] + self._prefix_len
        if os_ == oe:
            return None
        return (_offset_to_index(os_, self._out_line_starts, len(self._last_display)),
                _offset_to_index(oe, self._out_line_starts, len(self._last_display)))

    def _map_output_range(self, s_idx, e_idx):
        """输出框选区 -> 输入框对应区间 (返回 Tk 索引或 None)。"""
        m = self._map
        if not m['out_to_in']:
            return None
        s = _idx_to_offset(s_idx, self._out_line_starts) - self._prefix_len
        e = _idx_to_offset(e_idx, self._out_line_starts) - self._prefix_len
        total = len(m['out_to_in'])
        if e <= 0 or s >= total:
            return None
        s = max(0, min(s, total - 1))
        e = min(e, total)
        if s >= e:
            return None
        ins = m['out_to_in'][s]
        ine = m['out_to_in'][e - 1] + 1
        return (_offset_to_index(ins, self._in_line_starts, m['cut']),
                _offset_to_index(ine, self._in_line_starts, m['cut']))

    def _refresh_mirror(self):
        """转换后若仍有选区, 重新生成联动高亮。"""
        for src in (self.input_text, self.output_text):
            try:
                src.index('sel.first')
            except tk.TclError:
                continue
            self._mirror_selection(src)
            break

    def _select_all_in(self, event=None):
        self.input_text.tag_add('sel', '1.0', 'end-1c')
        self._mirror_selection(self.input_text)
        return 'break'

    # ---------- 事件处理 ----------
    def _on_change(self, event=None):
        self.do_convert()

    def do_convert(self):
        raw = self.input_text.get('1.0', 'end-1c')
        enabled = {k: v.get() for k, v in self.enabled.items()}
        result, counts, red, green, mapping = convert_text(raw, enabled)
        # 前后缀: 仅在勾选时附加
        prefix = self.prefix_var.get() if self.include_prefix.get() else ''
        suffix = self.suffix_var.get() if self.include_suffix.get() else ''
        display = prefix + result + suffix
        self._map = mapping
        self._last_result = result
        self._last_display = display
        self._prefix_len = len(prefix)
        self._in_line_starts = _line_starts(raw)
        self._out_line_starts = _line_starts(display)
        self.output_text.delete('1.0', 'end')
        self.output_text.insert('1.0', display)
        # diff 高亮: 输入框飘红, 输出框飘绿 (绿色区间整体后移前缀长度)
        self.input_text.tag_remove('red', '1.0', 'end')
        self.output_text.tag_remove('green', '1.0', 'end')
        plen = self._prefix_len
        for s, e in red:
            self.input_text.tag_add('red', f'1.0+{s}c', f'1.0+{e}c')
        for s, e in green:
            self.output_text.tag_add('green', f'1.0+{s + plen}c', f'1.0+{e + plen}c')
        total = sum(counts.values())
        if total:
            parts = ' · '.join(f'{STATUS_NAMES[k]} {v}'
                               for k, v in counts.items() if v)
            self.status_var.set(f'已还原 {total} 个字符 — {parts}')
        else:
            self.status_var.set('未发现需要还原的字符。')
        # 输出内容刷新后, 滚动位置对齐到输入框 (键盘翻页等场景)
        self.root.after_idle(self._sync_output_view)
        # 若存在选区, 重新生成联动高亮
        self.output_text.tag_remove('mirror', '1.0', 'end')
        self.input_text.tag_remove('mirror', '1.0', 'end')
        self.root.after_idle(self._refresh_mirror)

    def copy_result(self):
        content = self.output_text.get('1.0', 'end-1c')
        if not content:
            self._flash('输出为空, 没有可复制的内容。')
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self._flash('已复制到剪贴板 ✓')

    def clear_input(self):
        self.input_text.delete('1.0', 'end')
        self.do_convert()

    def _flash(self, msg):
        self.status_var.set(msg)
        if self._status_after is not None:
            try:
                self.root.after_cancel(self._status_after)
            except Exception:
                pass
        self._status_after = self.root.after(2500, self.do_convert)

    # ---------- 输出框只读控制 ----------
    def _readonly_block(self, event):
        # Ctrl+C: 复制选中内容; Ctrl+A: 全选; 其余按键一律拦截
        if event.state & 0x4:
            if event.keysym.lower() == 'c':
                self._copy_selection()
            elif event.keysym.lower() == 'a':
                self._select_all()
        return 'break'

    def _copy_selection(self):
        try:
            text = self.output_text.get('sel.first', 'sel.last')
        except tk.TclError:
            text = ''
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

    def _select_all(self):
        self.output_text.tag_add('sel', '1.0', 'end-1c')
        self._mirror_selection(self.output_text)
        self._follow_view(self.output_text)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
