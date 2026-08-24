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
"""

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

    返回 (结果字符串, {分类: 替换数量}, 输入中被替换的区间, 输出中还原结果的区间)。
    区间为 [(起始下标, 结束下标), ...] 形式, 已合并相邻区间, 用于 diff 高亮。
    末尾的换行符(\n / \r)会被删除, 并在输入区间中标注出来。
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
    for in_pos in range(cut):
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
    return ''.join(out), counts, _merge_ranges(red), _merge_ranges(green)


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry('820x680')
        root.minsize(640, 320)
        try:
            ttk.Style().configure('.', font=UI_FONT)
        except tk.TclError:
            pass
        self.enabled = {k: tk.BooleanVar(value=True) for k in OPTION_ORDER}
        self._status_after = None
        self._syncing = False   # 防止同步滚动互相触发
        self._build_ui()
        self.input_text.focus_set()
        self.do_convert()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky='nsew')
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)

        # ---- 顶部提示 + 图例 ----
        ttk.Label(main, text=APP_HINT, foreground='#667',
                  wraplength=760).grid(row=0, column=0, sticky='w')
        legend = ttk.Frame(main)
        legend.grid(row=1, column=0, sticky='w', pady=(2, 0))
        ttk.Label(legend, text='■ 输入中被替换的字符',
                  foreground='#c0392b').pack(side='left')
        ttk.Label(legend, text='   ', foreground='#667').pack(side='left')
        ttk.Label(legend, text='■ 输出中还原后的字符',
                  foreground='#1e8449').pack(side='left')

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

        # ---- 还原选项 (两行 x 4列, 窄窗口下也不裁剪) ----
        opt_frame = ttk.LabelFrame(main, text='还原选项', padding=8)
        opt_frame.grid(row=4, column=0, sticky='ew', pady=(10, 8))
        for i, key in enumerate(OPTION_ORDER):
            ttk.Checkbutton(opt_frame, text=CHECK_LABELS[key],
                            variable=self.enabled[key],
                            command=self.do_convert).grid(row=i // 4, column=i % 4,
                                                          padx=9, pady=2, sticky='w')
        for col in range(4):
            opt_frame.columnconfigure(col, weight=1)

        # ---- 输出区 ----
        ttk.Label(main, text='输出(转换结果):').grid(row=5, column=0,
                                                    sticky='w', pady=(0, 2))
        out_frame = ttk.Frame(main)
        out_frame.grid(row=6, column=0, sticky='nsew')
        self.output_text = tk.Text(out_frame, height=8, font=TEXT_FONT,
                                   wrap='word')
        self.out_scroll = ttk.Scrollbar(out_frame, command=self._scroll_both)
        self.output_text.configure(yscrollcommand=self.out_scroll.set)
        self.output_text.pack(side='left', fill='both', expand=True)
        self.out_scroll.pack(side='right', fill='y')

        # 两个文本框等高、均匀分配空间, 缩放行为一致
        main.rowconfigure(3, weight=1, uniform='texts')
        main.rowconfigure(6, weight=1, uniform='texts')

        # diff 高亮配色: 输入框替换字符飘红, 输出框还原字符飘绿
        self.input_text.tag_configure('red', foreground='#c0392b',
                                      background='#fdecea')
        self.output_text.tag_configure('green', foreground='#1e8449',
                                       background='#eafaf1')

        # 输出框: 只读, 但允许鼠标选中, Ctrl+C 复制选中, Ctrl+A 全选
        self.output_text.bind('<Key>', self._readonly_block)

        # ---- 底部: 复制按钮 + 状态栏 ----
        bottom = ttk.Frame(main)
        bottom.grid(row=7, column=0, sticky='ew', pady=(10, 0))
        ttk.Button(bottom, text='复制结果', command=self.copy_result).pack(side='left')
        ttk.Button(bottom, text='清空输入', command=self.clear_input).pack(side='left', padx=8)
        self.status_var = tk.StringVar(value='就绪。')
        ttk.Label(bottom, textvariable=self.status_var,
                  foreground='#1a6fb0').pack(side='right')

        # 输入内容变化时自动转换
        self.input_text.bind('<KeyRelease>', self._on_change)
        self.input_text.bind('<<Paste>>', self._on_change)

        # 同步滚动: 滚轮作用于两个文本框
        for w in (self.input_text, self.output_text):
            w.bind('<MouseWheel>', self._wheel_both)   # Windows / macOS
            w.bind('<Button-4>', self._wheel_both)     # Linux 上滚
            w.bind('<Button-5>', self._wheel_both)     # Linux 下滚

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

    # ---------- 事件处理 ----------
    def _on_change(self, event=None):
        self.do_convert()

    def do_convert(self):
        raw = self.input_text.get('1.0', 'end-1c')
        enabled = {k: v.get() for k, v in self.enabled.items()}
        result, counts, red, green = convert_text(raw, enabled)
        self.output_text.delete('1.0', 'end')
        self.output_text.insert('1.0', result)
        # diff 高亮: 输入框飘红, 输出框飘绿
        self.input_text.tag_remove('red', '1.0', 'end')
        self.output_text.tag_remove('green', '1.0', 'end')
        for s, e in red:
            self.input_text.tag_add('red', f'1.0+{s}c', f'1.0+{e}c')
        for s, e in green:
            self.output_text.tag_add('green', f'1.0+{s}c', f'1.0+{e}c')
        total = sum(counts.values())
        if total:
            parts = ' · '.join(f'{STATUS_NAMES[k]} {v}'
                               for k, v in counts.items() if v)
            self.status_var.set(f'已还原 {total} 个字符 — {parts}')
        else:
            self.status_var.set('未发现需要还原的字符。')
        # 输出内容刷新后, 滚动位置对齐到输入框 (键盘翻页等场景)
        self.root.after_idle(self._sync_output_view)

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


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
