# -*- coding: utf-8 -*-
"""临时回归: 全部转换类别 + UI。"""
import os
import tempfile
import tkinter as tk
import text_restore as t

TMP = tempfile.mkdtemp()
t._config_path = lambda: os.path.join(TMP, 'c.json')
ON = {k: True for k in t.OPTION_ORDER}


def run(raw):
    r, c, red, green, m = t.convert_text(raw, ON)
    return r, c


# 原有 9 类仍正常
assert run('Ｈｅｌｌｏ，ｗｏｒｌｄ！１２３ 你好。')[0] == 'Hello,world!123 你好.'
assert run('𝐀𝐁𝐂 x₂ СА ᴀᴋ')[0] == 'ABC x2 CA AK'
assert run('2024年1月5日下午3点')[0] == '2024-01-05 15:00'
assert run('hi\n\n')[0] == 'hi'
# 混合: 全角 + 日期时间 + 不可见
r, c = run('今天２０２４年１月５日下午３点\ufeff开会')
assert r == '今天2024-01-05 15:00开会', repr(r)
# 全角数字日期可被 datetime 识别 (\d 匹配全角)
assert run('２０２４年１月５日')[0] == '2024-01-05', repr(run('２０２４年１月５日')[0])

root = tk.Tk()
app = t.App(root)
app.lang = 'zh'
app.apply_language()
root.update()
app.input_text.insert('1.0', 'a\ufe0fb 2024年1月5日\n')
app.do_convert()
root.update()
disp = app.output_text.get('1.0', 'end-1c')
assert disp == 'ab 2024-01-05', repr(disp)
assert '不可见 1' in app.status_var.get(), app.status_var.get()
assert '日期时间 1' in app.status_var.get(), app.status_var.get()
# 设置窗口 9 开关 + 语言切换
app.open_settings()
root.update()
assert app._settings_win.winfo_exists()
app._on_lang_change('English')
root.update()
assert app._settings_nav.get(0) == 'Options'
app._settings_win.destroy()
root.update()
print('FULL REGRESSION PASSED')
root.destroy()
