# -*- coding: utf-8 -*-
"""临时测试: 日期时间还原的 UI 集成。"""
import os
import tempfile
import tkinter as tk
import text_restore as t

TMP = tempfile.mkdtemp()
t._config_path = lambda: os.path.join(TMP, 'config.json')

root = tk.Tk()
app = t.App(root)
app.lang = 'zh'
app.apply_language()
root.update()

# ---- 1) 主界面转换 + diff 高亮 ----
app.input_text.insert('1.0', '开始时间：2024年1月5日下午3点。')
app.do_convert()
root.update()
disp = app.output_text.get('1.0', 'end-1c')
assert disp == '开始时间:2024-01-05 15:00.', repr(disp)
# 状态栏显示 datetime 计数
assert '日期时间 1' in app.status_var.get(), app.status_var.get()
# diff 标签存在
assert len(app.input_text.tag_ranges('red')) == 2
assert len(app.output_text.tag_ranges('green')) == 2
print('main convert + highlight OK:', app.status_var.get())

# ---- 2) 镜像映射 (选中日期 -> 输出对应区间) ----
app.input_text.tag_remove('sel', '1.0', 'end')
app.input_text.tag_add('sel', '1.6', '1.17')   # 选中 2024年1月5日 区域
app._on_selection(app.input_text)
root.update()
ranges = app.output_text.tag_ranges('mirror')
assert len(ranges) == 2, ranges
print('mirror over datetime OK:', (str(ranges[0]), str(ranges[1])))

# ---- 3) 关闭日期时间选项 -> 不转换 ----
app.enabled['datetime'].set(False)
app.do_convert()
root.update()
disp2 = app.output_text.get('1.0', 'end-1c')
assert '2024年1月5日' in disp2 and '下午3点' in disp2, disp2
app.enabled['datetime'].set(True)
app.do_convert()
root.update()
print('toggle datetime option OK')

# ---- 4) 设置页 9 个开关 ----
app.open_settings()
root.update()
sws = [w for w in app._settings_win.winfo_children()] and True
def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)
switches = [w for w in walk(app._settings_win) if isinstance(w, t.Switch)]
assert len(switches) == 9, len(switches)
print('settings 9 switches OK')
app._settings_win.destroy()
root.update()

# ---- 5) 英文状态 ----
app._on_lang_change('English')
root.update()
app.input_text.delete('1.0', 'end')
app.input_text.insert('1.0', '明天下午2点开会\n')
app.do_convert()
root.update()
assert '明天14:00开会' in app.output_text.get('1.0', 'end-1c'), \
    repr(app.output_text.get('1.0', 'end-1c'))
assert 'datetime 1' in app.status_var.get(), app.status_var.get()
print('en datetime OK:', app.status_var.get())

root.destroy()
print('ALL TESTS PASSED')
