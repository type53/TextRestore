# -*- coding: utf-8 -*-
"""临时测试: 细滚动条/无箭头 + 历史列表滚动条按需显示 + 主题回归。"""
import os
import tempfile
import tkinter as tk
from tkinter import ttk
import text_restore as t

TMP = tempfile.mkdtemp()
t._config_path = lambda: os.path.join(TMP, 'config.json')


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


root = tk.Tk()
app = t.App(root)
app.lang = 'zh'
app.apply_language()
root.update()
style = ttk.Style()

for dark in (False, True):
    app.apply_theme(dark)
    root.update()
    # 无上下箭头
    vlay = style.layout('Vertical.TScrollbar')
    flat = str(vlay)
    assert 'uparrow' not in flat and 'downarrow' not in flat, flat
    # 宽度收窄
    assert int(style.lookup('TScrollbar', 'width')) == 9, \
        style.lookup('TScrollbar', 'width')
    print(('dark' if dark else 'light'), 'scrollbar layout OK:', flat[:70], '...')
app.apply_theme(False)
root.update()

# ---- 历史列表滚动条按需显示 ----
assert app._hist_sb_shown is False, '空列表不应显示滚动条'
# 少量条目 -> 仍不显示
for i in range(3):
    app._add_history(f'条目{i}')
root.update()
assert app._hist_sb_shown is False, '条目少时不应显示滚动条'
# 大量条目 -> 显示
for i in range(40):
    app._add_history(f'大量条目{i}')
root.update()
assert app._hist_sb_shown is True, '条目超出时应显示滚动条'
print('scrollbar auto-show OK (many items)')
# 清空 -> 恢复隐藏
app._ask_confirm = lambda msg: 'ok'
app.clear_history()
root.update()
assert app._hist_sb_shown is False, '清空后应隐藏滚动条'
print('scrollbar auto-hide OK (cleared)')

# ---- 主窗口滚动条仍在且更细 ----
sbs = [w for w in walk(root) if w.winfo_class() == 'TScrollbar']
assert len(sbs) >= 3, len(sbs)
packed = [w for w in sbs if w.winfo_manager()]
widths = sorted({w.winfo_width() for w in packed})
print('packed scrollbars:', len(packed), 'widths:', widths)
assert widths == [9], widths   # 细滚动条

# ---- 浅色主题使用 clam 且配色可读 ----
app.apply_theme(False)
root.update()
assert style.theme_use() == 'clam'
assert str(style.lookup('TButton', 'background')) == '#e9e9e9'
assert str(style.lookup('TEntry', 'fieldbackground')) == '#ffffff'
assert str(style.lookup('TEntry', 'foreground')) == '#000000'
print('light clam styling OK')

# ---- 回归: 转换 + 对话框 + 侧栏按钮 ----
app.input_text.insert('1.0', 'Ｈｅｌｌｏ 2024年1月5日')
app.do_convert()
root.update()
assert app.output_text.get('1.0', 'end-1c') == 'Hello 2024-01-05'
app.open_settings()
root.update()
assert app._settings_win.winfo_exists()
assert len([w for w in walk(app._settings_win) if isinstance(w, t.Switch)]) == 11
app._settings_win.destroy()
root.update()
btns = [w for w in walk(app.sidebar) if w.winfo_class() == 'TButton']
assert len(btns) == 4 and all(b.winfo_width() > 30 for b in btns)
print('regression OK')
root.destroy()
print('ALL TESTS PASSED')
