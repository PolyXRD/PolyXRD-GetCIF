# PolyXRD GetCIF v1.1.0

**CIF 检索与获取小工具** —— PolyXRD 家族成员。单文件 exe，双击即用，无需安装。

![logo](resources/logo-horizontal.png)

## 📦 两个版本（按需下载其一即可）

| 版本 | 资产 | 体积 | 适用 |
|---|---|---|---|
| **标准版** | `PolyXRD-GetCIF.exe` | ~106 MB | 只需检索 / 预览 / 下载 CIF；轻量（无 3D，Qt 已精简） |
| **Plus 版** | `PolyXRD-GetCIF-Plus.exe` | ~269 MB | 需要**应用内 3D 结构展示**（对称操作展开渲染）；保留完整 Qt 便于后续功能扩展 |

两个版本检索能力完全一致；标准版预览窗会提示升级 Plus。

## ✨ v1.1.0 更新：注册机制

复用 PolyXRD 家族统一注册机制（与 PolyXRD-Reg 注册机算法一致，离线 HMAC 校验）：

| 场景 | 行为 |
|---|---|
| 未注册，每次打开软件 | 弹窗：「本软件未注册，版权所有，禁止用于商业用途。如需注册请联系 sshztx@outlook.com」 |
| 点「确定」 | 关闭弹窗，软件正常使用；下次打开依旧提示 |
| 点「输入注册码」 | 打开注册对话框，粘贴注册码 → 校验通过即注册成功，以后不再提示 |
| 帮助菜单 | 新增「输入注册码 (&R)…」 |
| 注册成功后 | 状态栏**最下面一排最右侧（右对齐）**显示「已注册：\<单位部门名称\>」；未注册显示「未注册」 |

- 注册码由**开发方**根据用户提供的「单位部门名称」生成（PolyXRD-Reg 注册机），用户在软件内「帮助 → 输入注册码」粘贴后即完成注册；
- 注册码格式 `PXRD1-XXXX-XXXX-...`：Base32 编码的「单位部门名称 + HMAC 签名」，软件端离线校验真伪并还原单位名，**无需联网、无需机器码**，同一注册码可在同一单位的多台电脑使用；
- 注册状态保存于 `%APPDATA%\PolyXRD\GetCIF\registration.json`，每次启动重新校验，手改文件伪造「已注册」无效；
- 三语界面同步：注册相关文案随界面语言切换（中文 / English / 日本語）；
- 冒烟 / 离屏自动化测试自动跳过弹窗（`POLYXRD_REG_NO_PROMPT` / `QT_QPA_PLATFORM=offscreen`），不影响发布前自检。

## 📥 安装

1. 下载下方 Assets 中任一版本的 exe（单文件免安装）；
2. 双击运行。首次启动解压需数秒，属正常现象；
3. 配置保存在 `%APPDATA%\PolyXRD\GetCIF\settings.toml`，注册状态 `%APPDATA%\PolyXRD\GetCIF\registration.json`，下载的 CIF 默认存于 `%APPDATA%\PolyXRD\GetCIF\downloads`。

## ✅ 发布前验证

- 离线自检 36 项全过：CIF 解析（对称操作数值验证 / esd 剥离 / 分号多行块）、MP structure→CIF、本地库六类条件过滤、3D 渲染、**注册机制 11 项**（初始态 / 出码 / 校验还原 / 容错 / 拒绝伪造 / 防手改）、GUI 离屏冒烟
- **注册交互全链路**（离屏自动点击）：启动未注册提示 → 输入注册码 → 注册成功 → 状态栏右侧显示单位名（右对齐、贴状态栏右端）→ 已注册再启动静默无提示，全部通过
- 双版本产物离屏冒烟均 EXIT=0

运行 `tests/run_checks.py`（`--online` 附加联网检查）可复现以上验证；
`tests/_interactive_reg_check.py` 可复现注册弹窗交互链路。

## 📄 许可

双许可（学术 / 商业），详见 LICENSE 与 LICENSE-CN。

## 🙏 数据源致谢

COD · AMCSD/RRUFF · Materials Project · Atomly 的公开数据服务。
