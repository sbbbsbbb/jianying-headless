# Jianying Headless

面向剪映专业版 macOS 的本地自动化工具。通过结构化剪辑计划生成可编辑草稿，
在独立副本中修改多轨工程，并调用本机剪映引擎导出 MP4。

**主要适配版本：11.5.0 · 兼容版本：11.4.2**

**首次使用请从 [从零生成第一个剪映草稿](docs/GETTING-STARTED.md) 开始。**
教程包含安装前提、环境检查、拖入自己的视频、首页登记、保存重开和常见报错处理。
11.5.0 仍需匹配具体安装身份与工具链，尚不保证任意电脑安装即用。

项目适用于 AI 视频工作流的工程交接、批量草稿生成和 Agent 辅助剪辑。
提供 Python 命令行入口及配套 Agent Skill。它不是剪映官方 SDK，运行时需要安装匹配版本的剪映。

## 本 fork 的补充：lite 拼装方案

> 这一节和 `lite/` 目录是本 fork 新增的，上游的代码和固定哈希一行没动，`tools/check_package.py` 与 `tests/` 照常通过。
> 以下结论都来自一台机器的实测（Apple Silicon，macOS 26.4.1，CLT 26.4.1 / `clang-2100.0.123.102`，剪映 11.5.0 通用版），不代表其他环境。
> 许可沿用上游 [LICENSE](LICENSE)：仅限个人学习和非商业使用。

### 思路

上游卡住多数人的是草稿加解密 codec 的固定哈希（#2、#3），以及 `publish` 登记首页（#5）。实测这两步都可以不要：

1. **草稿用明文。** 用 [pyJianYingDraft](https://github.com/GuanYixuan/pyJianYingDraft) 生成时间线，主文件写成明文的 `draft_info.json`。
   剪映 11.5.0 能直接打开，打开后自己补齐 `Timelines/`、备份等结构，改写后的文件仍是明文 JSON。
2. **首页不用登记。** 把草稿文件夹放进 `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/`，回到剪映首页就出现，不用重启。
3. **导出只用 `engine/native_export.cpp`。** 它读的是明文时间线 JSON，不经过 codec；编译产物上游只记录不校验，本机任意版本的 clang 都能编。
   它仍然只认 `libvideoeditor.dylib` 哈希匹配的剪映，这一条绕不开，见下一小节。

同一份明文草稿，既能在剪映界面里继续编辑，也能无界面导出成 MP4。

### 用法

```bash
pip install pyJianYingDraft==0.3.0
python3 lite/make_draft.py   # 交互式：拖入视频、填字幕、选生成到 work/lite/drafts 还是剪映草稿目录
python3 lite/export.py       # 选 work/lite/drafts 下的草稿，导出到 work/lite/exports/<名字-时间>/render.mp4
```

要导出的草稿，素材必须在 `work/lite/` 内：导出跑在沙箱里，禁网络，禁读用户目录的其他位置。

### 装哪一版剪映（#3、#8 的答案）

同样叫 11.5.0，官方有几种打包，里面的 `libvideoeditor.dylib` 不一样。上游支持的 `2041482a…` 在**通用版**里；
arm64 单架构包里是 #3 报告的那份 `a282bd76…`。

| 版本 | build | 打包 | `libvideoeditor.dylib` SHA-256 | 上游是否支持 |
| --- | --- | --- | --- | --- |
| 11.5.0 | 13199 | 通用（x86_64 + arm64） | `2041482a1aaeffa4d8bd69b836f8cf38807aaad8021bca410d567c59af3bccfa` | 支持（已实测） |
| 11.5.0 | 13201 | arm64 | `a282bd763e1a396963d1c913ce75d3e2fdaf5b7fe9c7455a65bf1bf40deed019` | 不支持（已实测） |
| 11.5.0 | 13191 | 通用 | 未下载 | 未知 |
| 11.5.0 | 13200 | x86_64 | 未下载 | 未知 |
| 11.4.2 | 13174 | arm64 | 未下载 | 未知 |
| 11.5.3 | 13237 | arm64，官方当前正式版（2026-09-21） | 未下载 | 不支持 |

官方 CDN 上旧版安装包都还在，知道 build 号就能下：

```text
https://lf3-package.vlabstatic.com/obj/faceu-packages/Jianying_<主>_<次>_<补>_<build>_jianyingpro_0[_arm64|_x86_64]_creatortool_nosandbox.dmg
```

不带架构的是通用版。上游支持的那一版：

```text
https://lf3-package.vlabstatic.com/obj/faceu-packages/Jianying_11_5_0_13199_jianyingpro_0_creatortool_nosandbox.dmg
```

下载后先核对再安装：

```bash
codesign --verify --deep --strict /Volumes/*/VideoFusion-macOS.app          # TeamIdentifier 应为 X2JNK7LY8J
shasum -a 256 /Volumes/*/VideoFusion-macOS.app/Contents/Frameworks/libvideoeditor.dylib
```

官方引导安装器装的永远是当前正式版（现在是 11.5.3），装完上游就不认了。它查询版本用的接口如下，返回里的
`installer_downloader_config.url` 就是当前正式版安装包地址：

```text
https://lv-api.ulikecam.com/service/settings/v3/?app=1&aid=572943&arch_info=arm64&device_id=1&device_platform=mac&from_aid=572943&from_channel=jianyingpro_0&from_version=0.0.0&local_info=zh_CN&version_code=0.0.0
```

装好后在剪映设置里关掉自动更新，并留一份 dmg，被更新了就重装。

### 上游 issue / PR 在 lite 方案下的情况

| 上游 issue / PR | lite 方案的情况 | 依据 |
| --- | --- | --- |
| #2 codec 哈希复现不了，PR #4 | 不涉及 | 不编译 codec，明文草稿不需要加解密 |
| #3 同版本号但库哈希不符 | 遇到了，已解决 | arm64 包里的库就是 `a282bd76…`，换成通用版 build 13199 后哈希对上 |
| #5 `publish` 的 `com.apple.macl` 问题，PR #14 | 不涉及 | 草稿直接放进剪映草稿目录，首页能认出来，不走 `publish` |
| #8 找不到旧版安装包 | 已解决 | 官方 CDN 上旧版还在，命名规则见上一小节 |
| #9 后半 / PR #10 后半：只有 X 位置关键帧时 Y 抖动 | 复现了，已修 | 见下一小节 |
| #9 前半 / PR #10 前半：保存后回读校验误报 | 不涉及 | lite 没有“剪映保存后再校验”这一步 |
| #11① 中文路径导出失败，PR #13 | 已处理，已实测 | 沙箱策略按 UTF-8 原样写路径；用中文草稿名实际导出成功 |
| #11② MP4 重复 brand 被拒 | 不涉及，本机也没出现 | 本机成片 `major_brand=isom` 是单值，lite 不校验 brand |
| #6 / PR #7 本地字体 | 没移植，没测 | 上游实现在它自己的 Python 引擎里，lite 用的是 pyJianYingDraft |
| PR #12 11.5.3-beta2、PR #1 Windows 后端 | 不涉及 | |

### #9 的 Y 抖动：复现数据和修法

测试片段：720p 画布，画面缩放 0.3，静态 `transform_y = 0.5`，X 位置关键帧 0 秒 −0.5、2 秒 0.5。逐帧量非黑区域的垂直中心：

| 情形 | Y 中心（像素） | 跨度 |
| --- | --- | --- |
| 没有关键帧（对照） | 恒为 178 | 0 |
| 只有 X 关键帧 | 178、538 逐帧交替 | 360 |
| X 关键帧 + 恒定 Y 关键帧 | 恒为 178 | 0 |
| 只有 Y 关键帧、静态 X 非零（反向对照，量 X 中心） | 恒为 958 | 0 |

所以只有“只有 X 关键帧”这一个方向会抖。`lite/export.py` 的 `pin_static_y` 在导出用的时间线副本里，
给这种片段补一条取值等于静态 Y 的恒定 Y 关键帧，草稿本身不动。修复后只有 X 关键帧的片段 Y 跨度为 0，
X 动画照常（中心 318 → 638 → 958 后停住），120 / 120 帧。思路与 PR #10 一致。

### 测过的和没测的

测过（无界面导出，逐项核对成片）：单视频加字幕；位置关键帧；中文路径；
一份 3 秒的多轨草稿——主轨两段且第二段 2 倍速、画中画（缩放加位移、静音）、字幕、独立音频轨配乐。
多轨那份导出 90 / 90 帧，2.5 秒处主画面的源时间码是 3.0 秒（变速正确），画中画按时出现和消失，
成片音频里原声 440Hz 和配乐 880Hz 两个分量都在。

没测：转场、特效、滤镜、蒙版、复合片段、图片和 GIF 素材、本地字体。
特效和转场这类资源剪映界面会联网下载，而 lite 的导出跑在禁网络的沙箱里，能不能出来要实测才知道。
上游记录过图片和 GIF 偶发少一帧，`lite/export.py` 的帧数校验要求完全相等，少帧会直接报错。

## 核心功能

| 功能 | 支持范围 |
| --- | --- |
| 生成可编辑草稿 | 视频分段、多轨组合、变速、音量、画中画、字幕和标题 |
| 导入本地素材 | 视频、PNG、JPEG、GIF、配音、音乐和音效 |
| 本地字体 | 新建文字或在副本中换字体，静态 OTF/TTF 随草稿保存；详见[字体说明](docs/LOCAL-FONTS.md) |
| 基础动画 | 位置、缩放、旋转、透明度和音量的线性关键帧 |
| 原生效果 | 六类静态几何蒙版、叠化转场、轻微抖动；需要匹配的本机资源与使用权限 |
| 编辑已有工程 | 检查源草稿，在独立副本中修改，不覆盖原项目 |
| 原生视频导出 | 通过本机剪映引擎将已验证快照导出为 H.264/AAC MP4 |
| 环境与工程检查 | 核对运行版本、组件身份、素材完整性和草稿保存结果 |

核心流程为：**素材与剪辑计划 → 可编辑剪映草稿 → 原生引擎导出**。
剪映中后续手工修改的内容不会自动同步回原计划或旧导出快照。

## Hypit 协作案例

一个约 **50.23 秒**的 IG 滚动动画教程展示了从 Hypit 到剪映的工程交接。
转换使用原工程的独立画面、配音、图片和文字时间安排，而不是仅导入一条最终成片。

| 工程内容 | 数量 |
| --- | --- |
| 原始素材 | 39 份 |
| 视频与图片 | 8 条轨道、38 个片段 |
| 独立配音 | 1 条轨道、7 个片段 |
| 可编辑文字 | 14 条轨道、109 个片段 |
| 合计 | 23 条轨道、154 个片段 |

该案例已在剪映 11.5.0 完成构建、打开播放、保存、完全退出、冷重开和结构回读，
并通过原生导出的 **1507 / 1507 帧**检查与完整解码检查。

### 画面对照

| Hypit 原成片 | 剪映工程原生导出 |
| --- | --- |
| ![Hypit 原成片六帧](docs/media/hypit-original-frames.png) | ![剪映导出六帧](docs/media/jianying-import-frames.png) |

两组图片均取自真实案例的 1、8、17、28、37、48 秒。展示的是可编辑工程交接，
**不是视觉无损转换**：特殊字体、逐词颜色动画、部分裁切与阴影未原样保留，
第 37 秒的补充画面也存在差异。完整主观视听验收尚未完成。

详见 [Hypit 协作案例](docs/HYPIT-COLLABORATION.md) 和 [媒体说明](docs/media/README.md)。
当前转换是单向、按项目实现；不提供任意 Hypit 工程的一键无损转换或双向同步。

## 运行环境

- Apple Silicon Mac，macOS 26.0+；已验证环境为 macOS 26.5.1。
- 剪映专业版 11.5.0，或兼容配置对应的 11.4.2。
- Python 3.9+、FFmpeg / ffprobe、Xcode Command Line Tools。
- 已验证桥接工具链：Apple clang 21.0.0 / macOS SDK 26.5。

应用版本、build、官方库哈希、签名与开发者身份均有检查。
未知版本或不匹配组件会被拒绝，不通过放宽校验强行运行。干净机器安装验收尚未完成。
官方引擎、账号数据、原始工程素材库和效果资源不随源码分发。

构建工具选择、安装诊断、登记恢复及字体支持的进展和待验限制见
[Issue 修复进展](docs/ISSUE-REMEDIATION.md)。环境检查通过不等于任意电脑兼容。

## 快速开始

```bash
git clone https://github.com/mcncarl/jianying-headless.git
cd jianying-headless
python3 tools/build_native_codec.py
python3 skills/yichen-jianying-edit/scripts/headless_draft.py doctor
```

`doctor` 是**环境检查命令**：检查剪映版本、组件身份和必要工具。
检查通过表示环境符合运行条件，不代表任意草稿都已通过画面、声音或导出验收。

桥接构建只编译项目源码并链接本机已安装程序库，不下载剪映、不修改官方库或账号权益。
编译结果必须匹配固定哈希，否则停止。

按 [计划格式](skills/yichen-jianying-edit/references/headless-macos.md) 准备 JSON，
或参考 [基础计划](examples/basic.plan.json) 和 [Hypit 交接格式示例](examples/hypit-handoff.plan.json)。
示例中的素材路径须替换为有权使用的本地文件。

```bash
python3 skills/yichen-jianying-edit/scripts/headless_draft.py build \
  --plan /absolute/path/to/plan.json --out "$PWD/work/new-build"
python3 skills/yichen-jianying-edit/scripts/headless_draft.py verify-build \
  --build "$PWD/work/new-build"
```

保存当前工作并完全退出剪映后，将新草稿登记到本机首页：

```bash
python3 skills/yichen-jianying-edit/scripts/headless_draft.py publish \
  --build "$PWD/work/new-build" --audit "$PWD/work/new-publish-audit"
```

`publish` 在此仅指本机首页登记，不是互联网发布。生成的草稿仍需实际打开、播放和保存检查。
需要成片时，可独立导出已验证快照：

```bash
python3 skills/yichen-jianying-edit/scripts/headless_draft.py export \
  --build "$PWD/work/new-build" --out "$PWD/work/new-export"
```

输出目录须不存在，成片为该目录下的 `render.mp4`。
导出在隔离进程中运行，默认不联网、不读取账号数据。

## Agent Skill

`skills/yichen-jianying-edit/` 提供 Agent 调用入口、口播计划辅助脚本与操作参考。
Skill 不包含剪映引擎；独立安装后仍需检出核心项目，并指定其路径：

```bash
export JIANYING_HEADLESS_ROOT="/absolute/path/to/jianying-headless"
```

安装说明见 [独立 Skill](skills/yichen-jianying-edit/README.md)。
Skill 另收录于 [yichen-skills](https://github.com/mcncarl/yichen-skills/tree/main/yichen-jianying-edit)。

## 当前限制

- 复合片段仅支持实验性的离线修改与冻结快照导出，尚不能交付为保存可靠的可编辑嵌套草稿。
- 图片/GIF 样本曾出现间歇少一帧；严格帧数检查会拒绝缺帧输出，根因尚未解决。
- 不支持任意剪映版本、任意效果组合、在线模板、资源下载、云端工程或账号权益获取。
- 高清黑白滤镜与橙色描边花字已退出支持范围；含这些效果的计划或旧快照会明确报错。
- 工程结构检查、原生播放、视觉一致性、主观听感与素材许可是不同的验收项目。

详细结果及已知问题见 [验证状态](docs/VERIFICATION.md)。

## 项目结构与验证

| 目录 | 内容 |
| --- | --- |
| `engine/` | 草稿构建、独立副本编辑、资源校验与原生导出 |
| `bridge/` | 文件与管道桥接源码、保留来源声明的接口头文件 |
| `skills/` | Agent Skill 及配套参考 |
| `tools/`、`tests/` | 构建、源码包装检查与可移植测试 |
| `licenses/` | 第三方许可证 |

```bash
python3 tools/check_package.py
python3 -m unittest discover -s tests -v
```

专项原生测试的本机素材与证据不随仓库分发；源码检查不能替代实际工程验收。

## 许可与来源

原创部分采用 [个人学习和非商业使用许可](LICENSE)；商业使用需取得作者书面授权。
第三方内容继续适用原许可证，详见 [第三方声明](THIRD_PARTY_NOTICES.md)。
本项目不是 MIT / Apache-2.0 整包授权，代码许可也不包含剪映集成授权、账号权益或素材许可。
分发边界见 [分发范围](docs/DISTRIBUTION-SCOPE.md)。
