# -*- coding: utf-8 -*-
import os
import tempfile
import tkinter as tk
import text_restore as t

TMP = tempfile.mkdtemp()
t._config_path = lambda: os.path.join(TMP, 'config.json')

root = tk.Tk()
app = t.App(root)
root.update()
app.open_settings()
root.update()
inner = app._settings_inner
inner.update_idletasks()
print('inner h:', inner.winfo_height(), 'canvas h:', app._settings_canvas.winfo_height())
for i, sec in enumerate(app._sections):
    print(f'section {i}: y={sec.winfo_y()} h={sec.winfo_height()} (bottom={sec.winfo_y() + sec.winfo_height()})')

print('--- scroll to section 2 ---')
app._scroll_to_section(app._sections[2])
root.update()
print('yview:', app._settings_canvas.yview(), 'nav sel:', app._settings_nav.curselection())
print('--- scroll to section 1 ---')
app._scroll_to_section(app._sections[1])
root.update()
print('yview:', app._settings_canvas.yview(), 'nav sel:', app._settings_nav.curselection())
print('--- scroll to section 0 ---')
app._scroll_to_section(app._sections[0])
root.update()
print('yview:', app._settings_canvas.yview(), 'nav sel:', app._settings_nav.curselection())
root.destroy()
