# TextRestore — 隐蔽字符还原工具

ChatGPT / Claude Code / Gemini 等模型有时会在输出中偷偷插入或替换一些**肉眼几乎无法分辨的字符**（全角字符、零宽字符、花体字母、西里尔相似字母等），用来识别中文用户。本工具把这类"隐蔽字符"自动还原为对应的普通英文字符。

## 功能特性

- 简洁图形界面（tkinter，仅标准库）
- 输入即自动转换，上输入 / 下输出双文本框
- **diff 高亮**：输入框中被替换的字符飘红，输出框中还原后的字符飘绿，一眼看出模型替换了哪些位置
- 7 类还原，均可独立开关：
  1. 全角转半角：`ＡＢＣ１２３` → `ABC123`
  2. 中文标点转英文：`，。？！《》“”` → `,.?!<>""`
  3. 花体/数学字体：`𝐀𝐁𝐂𝟏𝟐𝟑` → `ABC123`
  4. 上下标：`x²y₃` → `x2y3`
  5. 相似字母（西里尔/希腊/小型大写）：`СА ᴀᴋ` → `CA AK`
  6. 删除不可见字符：零宽空格/连接符/BOM/双向控制符等
  7. 特殊空格归一：不间断空格/窄空格 → 普通空格
- 一键复制结果，状态栏统计各类还原数量

## 使用

### 运行源码

```bash
python text_restore.py
```

### 使用发布版

从 [Releases](../../releases) 下载 `TextRestore.exe`（Windows 单文件，无需安装 Python，双击即用，无控制台窗口）。

## 从源码打包

```bash
pip install pyinstaller pillow
python build_icon.py    # 生成 icon.ico
pyinstaller --noconfirm --clean --onefile --windowed --name TextRestore --icon icon.ico text_restore.py
```

产物位于 `dist/TextRestore.exe`。

## License

[MIT](LICENSE)
