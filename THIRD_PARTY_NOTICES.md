# 第三方组件与许可

文档隐私清理器的自有代码采用 AGPL-3.0-only。以下组件保留各自版权和许可；本文件不是法律意见。

## 运行时依赖

| 组件 | 固定版本 | 许可路径 | 用途 |
|---|---:|---|---|
| PyMuPDF | 1.26.1（捆绑 MuPDF 1.26.2） | GNU AGPL v3 或 Artifex 商业许可 | PDF 读取、检查和重写 |
| PySide6 / Qt for Python | 6.10.2 | LGPL-3.0-only、GPL-2.0-only、GPL-3.0-only 或商业许可，具体以发行包为准 | 桌面界面 |
| PySide6_Essentials / PySide6_Addons / Shiboken6 | 6.10.2（由 PySide6 精确带入） | Qt for Python 发行包所列许可 | Qt 运行库与 Python 绑定 |
| Pillow | 12.0.0 | MIT-CMU | 图片读取和重编码 |

## 构建与测试依赖

| 组件 | 固定版本 | 许可 | 用途 |
|---|---:|---|---|
| PyInstaller | 6.11.0 | GPL-2.0-or-later，附 Bootloader Exception；部分文件为 Apache-2.0 | 本地生成 Windows 可执行文件 |
| python-docx | 1.1.2 | MIT | 仅用于自动化测试夹具 |

## 随附文本

- [项目及 PyMuPDF 开源许可路径：AGPL-3.0](LICENSE)
- [GNU GPL-3.0](LICENSES/GPL-3.0.txt)
- [GNU LGPL-3.0](LICENSES/LGPL-3.0.txt)
- [PySide6 / Qt for Python 许可提示](LICENSES/PySide6-6.10.2.txt)
- [PyMuPDF 许可声明](LICENSES/PyMuPDF-1.26.1.txt)
- [Pillow 许可与随附通知](LICENSES/Pillow-12.0.0.txt)
- [PyInstaller 许可及 Bootloader Exception](LICENSES/PyInstaller-6.11.0.txt)
- [python-docx MIT 许可](LICENSES/python-docx-1.1.2.txt)

依赖的源码和正式条款：

- PyMuPDF 1.26.1: https://pypi.org/project/PyMuPDF/1.26.1/
- Qt for Python 6.10: https://doc.qt.io/qtforpython-6.10/licenses.html
- Pillow 12.0.0: https://github.com/python-pillow/Pillow/blob/12.0.0/LICENSE
- PyInstaller 6.11.0: https://pyinstaller.org/en/v6.11.0/license.html
- python-docx 1.1.2: https://github.com/python-openxml/python-docx/blob/v1.1.2/LICENSE

本仓库固定版本见 `requirements-runtime.txt` 和 `requirements-build.txt`。如果分发自行构建的二进制，还应核对构建环境实际打包的 Python、Qt、MuPDF 及其传递组件，并随成品提供相应许可、通知和源码获取方式。
