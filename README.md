# Jianying Headless

面向剪映专业版 macOS 的本地自动化工具。通过结构化剪辑计划生成可编辑草稿，
在独立副本中修改多轨工程，并调用本机剪映引擎导出 MP4。

**主要适配版本：11.5.0 · 兼容版本：11.4.2**

**首次使用请从 [从零生成第一个剪映草稿](docs/GETTING-STARTED.md) 开始。**
教程包含安装前提、环境检查、拖入自己的视频、首页登记、保存重开和常见报错处理。
11.5.0 仍需匹配具体安装身份与工具链，尚不保证任意电脑安装即用。

项目适用于 AI 视频工作流的工程交接、批量草稿生成和 Agent 辅助剪辑。
提供 Python 命令行入口及配套 Agent Skill。它不是剪映官方 SDK，运行时需要安装匹配版本的剪映。

## 本 fork 的补充：让上游原版流程在自己的机器上跑起来

> 这一节是本 fork 新增的，上游的代码和固定哈希一行没动，`tools/check_package.py` 与 `tests/` 照常通过。
> 以下结论都来自一台机器的实测（Apple Silicon，macOS 26.4.1，剪映 11.5.0 通用版），不代表其他环境。
> 许可沿用上游 [LICENSE](LICENSE)：仅限个人学习和非商业使用。
> 本 fork 早先试过一条不经过 codec 的精简链路（`lite/`），现已移除，改用上游原版流程；历史提交里还能看到。

按下面两小节装对剪映、编出 codec 之后，实测 `doctor` 返回 `runtime_hashes_verified: true`，
`tools/start_here.py build` 返回 `build-verified`，上游 `export` 导出 60 / 60 帧；一份 55 秒、10 段视频加 24 条字幕的口播粗剪草稿
（`edit_plan.py compile` → `from-compiled` → `build` → `verify-build`）导出 1648 / 1648 帧，`publish` 成功登记到剪映首页。

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

### 不装 Xcode 编译 codec（#2 的答案）

上游的 `build`、`verify`、`edit`、`publish`、`export` 都先过 `doctor`，缺 codec 就停，所以这一步绕不开。

上游要求的工具链是 `clang-2100.1.1.101`、SDK 26.5、linker 1267。不用装 Xcode，也不用 Apple ID：
苹果公开的软件更新目录里有 “Command Line Tools for Xcode 26.6”（产品号 `140-17812`），实测这三项完全一致。

```bash
# 1. 在更新目录里找到产品 140-17812 的两个包：CLTools_Executables_Universal.pkg（约 740MB）和 CLTools_macOSNMOS_SDK.pkg（约 59MB）
curl -s 'https://swscan.apple.com/content/catalogs/others/index-26-15-14-13-12-10.16-10.15-10.14-10.13-10.12-10.11-10.10-10.9-mountainlion-lion-snowleopard-leopard.merged-1.sucatalog.gz' | gunzip | grep -oE 'https://[^<]*140-17812[^<]*(Executables_Universal|macOSNMOS_SDK)\.pkg' | sort -u
# 2. 下载后先验签，应显示 signed Apple Software
pkgutil --check-signature CLTools_Executables_Universal.pkg
# 3. 只解压、不安装，不动系统里现有的命令行工具
pkgutil --expand-full CLTools_Executables_Universal.pkg x_exec
pkgutil --expand-full CLTools_macOSNMOS_SDK.pkg x_sdk
ditto x_exec/Payload/Library/Developer/CommandLineTools work/clt-26.6
ditto x_sdk/Payload/Library/Developer/CommandLineTools/SDKs work/clt-26.6/SDKs
```

`xcrun` 不认放在非标准位置的命令行工具（报 `unable to find Xcode installation`），所以上游的
`tools/build_native_codec.py --developer-dir` 用不了这份解压出来的工具链。直接调用其中的编译器，
参数与上游 `tools/build_toolchain.py` 的 `compile_command` 完全相同，输出文件名也必须相同（文件名会进签名）：

```bash
F=/Applications/VideoFusion-macOS.app/Contents/Frameworks
mkdir -p work/codec-build-manual
env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C work/clt-26.6/usr/bin/clang++ -std=c++17 -arch arm64 -O2 \
  -isysroot "$PWD/work/clt-26.6/SDKs/MacOSX26.5.sdk" -mmacosx-version-min=26.0 bridge/jy14_codec.cpp \
  -L"$F" -lvideoeditor -Wl,-rpath,"$F" -o work/codec-build-manual/jy14_codec_hardened_11_4
shasum -a 256 work/codec-build-manual/jy14_codec_hardened_11_4    # 应为 b6533eb5…f971d
install -m 0700 work/codec-build-manual/jy14_codec_hardened_11_4 bridge/
```

实测（macOS 26.4.1 主机）：产物哈希 `b6533eb5eb1eea58dfa74fb1d16d3bb580970fe881f587605d358af1745f971d`，与上游固定值逐字节一致，
没有改任何固定哈希。之后 `doctor` 返回 `runtime_hashes_verified: true`，`tools/start_here.py build` 返回 `build-verified`，
上游的 `export` 导出 60 / 60 帧，`publish` 也成功（见下表 #5）。

### 上游 issue / PR 的实测情况

| 上游 issue / PR | 情况 | 依据 |
| --- | --- | --- |
| #2 codec 哈希复现不了，PR #4 | 已能复现 | 用苹果公开更新目录里的命令行工具 26.6，见上一小节 |
| #3 同版本号但库哈希不符 | 已解决 | arm64 包里的库就是 `a282bd76…`，换成通用版 build 13199 后哈希对上 |
| #8 找不到旧版安装包 | 已解决 | 官方 CDN 上旧版还在，命名规则见“装哪一版剪映” |
| #5 `publish` 的 `com.apple.macl` 问题，PR #14 | 本机没出现 | macOS 26.4.1 上 `publish` 成功，审计里 `os_managed_attribute_changes` 为空、`security_attributes_preserved: true`；上游两位复现者是 26.6.2 和 26.7 |
| #9 后半 / PR #10 后半：只有 X 位置关键帧时 Y 抖动 | 复现了 | 见下一小节 |
| #11① 中文路径导出失败，PR #13 | 上游未修 | 工作目录用纯 ASCII 路径即可避开 |
| #11② MP4 重复 brand 被拒 | 本机没出现 | 本机成片 `major_brand=isom` 是单值 |

### #9 的 Y 抖动：复现数据

测试片段：720p 画布，画面缩放 0.3，静态 `transform_y = 0.5`，X 位置关键帧 0 秒 −0.5、2 秒 0.5。逐帧量非黑区域的垂直中心：

| 情形 | Y 中心（像素） | 跨度 |
| --- | --- | --- |
| 没有关键帧（对照） | 恒为 178 | 0 |
| 只有 X 关键帧 | 178、538 逐帧交替 | 360 |
| X 关键帧 + 恒定 Y 关键帧 | 恒为 178 | 0 |
| 只有 Y 关键帧、静态 X 非零（反向对照，量 X 中心） | 恒为 958 | 0 |

所以只有“只有 X 关键帧”这一个方向会抖，这是引擎无界面导出的行为，和草稿由谁生成无关。
规避办法是给这种片段同时写一条取值等于静态 Y 的恒定 Y 关键帧；上游的修复在 PR #10，还没合并。

### 其他实测发现

- 剪映 11.5.0 能直接打开明文的 `draft_info.json` 草稿：把草稿文件夹放进
  `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/`，回到首页就出现，不用重启；
  打开后剪映自己补齐 `Timelines/` 等结构，改写后的文件仍是明文。
- 引擎按时间线总时长**向上取整**出帧：总时长 53.949996 秒导出 1619 帧；1652 帧的时间线若把微秒四舍五入成 55066667，
  只多出不到 1 微秒，导出就成了 1653 帧。帧数换算成微秒要向下取整。
- 用 Whisper 的词级时间戳定切点时，词起点常偏晚 0.1 秒以上；句首只留 0.08 秒会切掉辅音，留 0.2 秒后逐词核对一致。

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
