# 文档隐私清理器

一个完全在本机运行的 Windows 图形工具，用于检查并清理常见文档、PDF 和图片中的作者身份、审阅历史及文档属性。程序始终生成 `_clean` 副本，不主动覆盖原文件。

当前版本：`1.0.2`。

## v1.0.2 更新

本版修复了公开发布前安全审计发现的问题：

- 清理 Word `people.xml`、移动范围修订及更多审阅者标识。
- PDF 个人信息模式改用 XMP 安全白名单，移除历史、软件代理及 IPTC 联系信息。
- 检测并跳过空用户密码但仍带加密字典的 PDF，以及含加密成员的 OpenDocument。
- 清理 ODF 模板绝对路径，同时保证正文中的 `text:date` 不被误删。
- “全部属性”模式移除图片 ICC 配置。
- 所有格式先写入程序自有临时文件，再排他发布；竞态出现的同名外部文件不会被覆盖或删除。
- 清除 PDF trailer ID；含嵌入附件的 PDF 会明确标记“需复核”。

`1.0.0` 生成的 Office 副本可能含无效空日期节点；`1.0.1` 又存在上述漏检边界。请从原文件使用 `1.0.2` 重新生成副本。

## 使用方法

1. 启动程序，添加文件、文件夹或直接拖放。
2. 选择“仅个人信息”或“全部文档属性”。
3. 保持“清理后复检残留元数据”开启，点击“开始清理”。
4. 只有显示“已清理”的副本才通过了所选范围的复检；“已输出，需复核”的文件不要直接发送。

默认输出位于原文件旁。例如 `报告.docx` 会生成 `报告_clean.docx`；若名称已存在，则依次使用 `_clean_2`、`_clean_3`。

## 支持范围

- Office OOXML：`.docx/.docm/.dotx/.dotm`、`.xlsx/.xlsm/.xltx/.xltm`、`.pptx/.pptm/.potx/.potm/.ppsx/.ppsm`
- PDF：`.pdf`
- OpenDocument：`.odt/.ods/.odp/.odg`
- 静态图片：`.jpg/.jpeg/.png/.tif/.tiff/.webp`

“仅个人信息”默认清理作者、最后修改者、创建/修改时间、公司、管理者、自定义属性、缩略图及所选审阅者信息。PDF XMP 仅保留少量描述字段和 PDF 合规声明；标题、主题和关键词会尽量保留。

“全部文档属性”还会移除标题、主题、关键词、应用程序属性及可识别的技术元数据。图片 ICC 颜色配置在“仅个人信息”模式中会显示并保留，在“全部属性”模式中移除；移除颜色配置可能改变色彩管理效果。

## 安全与边界

- 所有处理均在本机完成；没有上传、联网、遥测或自动更新代码。
- 加密文件及检测到数字签名的文件会跳过。
- Office 宏原样保留；检测到 VBA 项目签名时会要求复核。
- PDF 嵌入附件、Office 内嵌 OLE 文档和内嵌媒体自身的元数据不会递归清理。含 PDF 附件的输出会保留附件并标记“需复核”。
- 图片会重新编码：JPEG 使用高质量有损编码，WebP 使用无损编码。
- 该工具不会清除 Windows ACL/文件所有者、资源管理器或 Office 最近记录、云盘版本历史、邮件历史和备份。
- 元数据格式可由第三方任意扩展。本工具能降低常见泄露风险，但不等于完整匿名化；高敏感文件仍应在目标软件中人工复核。
- PDF/A、电子签章、正式归档或宏文档应在原应用中再次打开，确认正文、格式、宏和合规状态。

## 从源码运行

要求 Windows 10/11 x64、Python 3.10 或更高版本。

```powershell
python -m pip install -r requirements-runtime.txt
python main.py
```

运行自动化测试：

```powershell
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python main.py --engine-smoke-test
$env:QT_QPA_PLATFORM = "offscreen"
python main.py --smoke-test
```

## 本地构建

推荐使用隔离环境：

```powershell
.\build.ps1
```

如果当前 Python 已安装构建依赖：

```powershell
.\build.ps1 -UseCurrentPython
```

生成文件位于 `dist\文档隐私清理器.exe`。GitHub `v1.0.2` Release 仅提供 GitHub 自动生成的 Source code（ZIP/TAR.GZ），不上传任何 EXE、安装包或旧版二进制。自行分发构建产物前，请履行所有第三方组件的许可义务。

## 本机设置留痕

界面偏好和最近输出目录由 Qt `QSettings` 保存在：

```text
HKEY_CURRENT_USER\Software\CodexTools\DocumentPrivacyCleaner
```

保留旧组织名 `CodexTools` 是为了兼容已有设置。卸载源码或删除 EXE 不会自动删除该注册表项；可在“注册表编辑器”中手动删除。

## 许可证

项目自有代码以 [GNU AGPL v3.0 only](LICENSE) 发布。选择该许可证是因为运行时依赖 PyMuPDF 的开源许可路径为 AGPL。第三方组件、版本和许可文本见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [LICENSES](LICENSES/)。

Copyright (C) 2026 Carota-Bunny. 本软件不提供任何担保。

## 安全问题

请通过 GitHub Issues 报告可复现的软件问题，但不要上传真实敏感文档、清理输出、日志或个人路径。优先提供最小化的虚构样本和复现步骤。
