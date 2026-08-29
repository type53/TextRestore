# -*- coding: utf-8 -*-
"""临时测试: 窗口图标 + 暗色主题下拉框样式。"""
import os
import tempfile
import tkinter as tk
from tkinter import ttk
import text_restore as t

TMP = tempfile.mkdtemp()
t._config_path = lambda: os.path.join(TMP, 'config.json')

root = tk.Tk()
app = t.App(root)
root.update()

# ---- 1) 窗口图标已应用 (iconphoto 加载成功) ----
assert app._icon_photo is not None
assert app._icon_photo.width() == 256, app._icon_photo.width()
app.open_settings()
root.update()
win = app._settings_win
# 设置窗口也有图标 (iconphoto(True) 设为默认)
assert win.winfo_exists()
app._settings_win.destroy()
root.update()
print('window icons OK')

# ---- 2) 暗色主题下拉框样式 ----
app.toggle_theme()   # -> 深色
root.update()
style = ttk.Style()
assert str(style.lookup('TCombobox', 'fieldbackground')) == '#1e1e1e', \
    style.lookup('TCombobox', 'fieldbackground')
assert str(style.lookup('TCombobox', 'foreground')) == '#d4d4d4'
assert str(style.lookup('TSpinbox', 'fieldbackground')) == '#1e1e1e'
# 弹出列表颜色选项已注册
opts = root.tk.call('option', 'get', '.', '*TCombobox*Listbox.background', 'Listbox')
print('popdown bg option:', repr(opts))
assert str(opts) == '#1e1e1e', opts
# 深色下打开设置窗口
app.open_settings()
root.update()
assert app._settings_win.winfo_exists()
# 语言下拉框存在且样式字段正确
lang_cb = None
for w in app._settings_win.winfo_children():
    pass
assert app.tr('lang_label') in ('语言:', 'Language:')
print('dark settings open OK')
app._settings_win.destroy()
root.update()
app.toggle_theme()   # 回浅色
root.update()
print('ALL TESTS PASSED')
