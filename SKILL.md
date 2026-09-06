---
name: video-downloader-by-browser
description: "手动介入式分片视频下载：用有头浏览器（用户可见、不自动关闭）打开视频页，拦截真实流地址，多路并行高速下载分片（TS 流 / m3u8 / 大分片 MP4），无损合并为完整 MP4，验收通过后再清理分片。面向需要分片下载的流媒体视频，尤其是需要登录、短信验证码、滑动验证、观看密码或切换清晰度的受限站点（优酷、腾讯视频、爱奇艺、B 站等）。关键词：下载视频、视频下载、优酷下载、需要登录的视频、需要密码的视频、m3u8、ts 分片合并"
version: "1.1.2"
author: "CodeBuddy AI"
created: "2026-09-06"
updated: "2026-09-06"
allowed-tools: Read,Write,Edit,Bash
---

# Video Downloader By Browser —— 手动介入式视频下载

## 核心理念

**能自动的自动，不能自动的立刻停下交给用户。**

这类站点的反爬手段（登录、短信验证码、滑动验证、观看密码、会员画质）本质就是拦自动化。
与其对抗，不如：用**有头浏览器**把界面完整呈现给用户，用户手动完成人机验证，
我们只负责在旁边**监听网络请求把流地址抓下来**，然后甩开浏览器用**并行 HTTP** 高速下载。

**两条铁律：**
1. 用户必须能看到浏览器窗口，脚本**绝不能自动关闭窗口/浏览器**
2. 合并完成**必须经用户验收通过后**才能删除中间分片，绝不提前删

---

## 适用判断

| 场景 | 是否用本 Skill |
|---|---|
| TS 流 / m3u8 / 大分片 MP4 等分片视频，需要拦截真实流地址下载 | ✅ 正是本 Skill 的目标 |
| 分片视频需要登录 / 验证码 / 滑动验证才能播放 | ✅ 手动介入协议处理 |
| 需要会员才能看高画质 / 需要观看密码 | ✅ |
| yt-dlp、you-get 等现成工具已直接支持的站点 | ❌ 用现成工具更省事 |

---

## ⛔ 手动介入协议（最重要，违反必失败）

遇到以下任何情况，**立即停止自动化尝试，明确告诉用户需要做什么，然后等用户回复**：

1. **登录**（账号密码 / 扫码 / 短信验证码）
2. **滑动拼图 / 点选验证码**
3. **观看密码弹窗** — 优酷密码框**可全自动**（见下「观看密码自动化」），失败再交给用户
4. **会员画质切换**
5. **任何自动化连续失败 2 次以上的交互**

### 观看密码自动化（优酷已验证 2026-09-06）

优酷视频密码弹窗**能全自动过**，一条命令搞定：

```bash
echo "pwauto <密码>" > <工作目录>/cmd.txt
# 等待 15~20 秒后看 status.txt，出现 {"t":..,"dur":..,"w":1920} 且 t 增长即成功
```

`pwauto` 内部做三件事：真实点击聚焦密码框 → `keyboard.type` 逐字符输入 → 真实鼠标点「确定」。

**为什么能成功（踩坑后的正确解法）**：
- ❌ 原生 setter 设 `inp.value=x` + 派发 input 事件（即 `pwfill`）：DOM 回读 `value` 正确，
  但优酷 Vue 组件的 v-model 响应式数据**没同步** → 点确定提交的是**空密码** → 「密码错误，请重新输入」。
- ✅ `page.keyboard.type()` 逐字符派发完整 `keydown→keypress→input→keyup`，Vue 必然响应。
- ❌ Enter 键对该弹窗**无效**（没绑回车提交事件），必须鼠标点「确定」。
- ✅ `page.mouse` 按 `getBoundingClientRect()` 中心坐标 down/up（即 `realclick`）可靠触发；
  JS `dispatchEvent(MouseEvent)` 可能被前端拦截。
- 若 `pwauto` 失败，用 `pwinfo` 命令导出弹窗 HTML 确认输入框/按钮选择器，再降级请用户手动点。

### 介入时的标准做法

- 用**有头模式**，窗口保持在用户屏幕上
- 短信验证码、滑动拼图这类**无法可靠自动化**的：停下交给用户
- 观看密码优先用 `pwauto` 自动；只有它失败时才降级为「填好值、让用户点确定」
- 用 `dom` 命令导出页面文本，确认到底弹了什么窗，**别靠猜**；关键弹窗用截图看
- ⚠️ **命令通道竞态**：`cmd.txt` 是单文件，连发两条命令会互相覆盖（后写的把先写的冲掉，
  先写的永远不执行）。**每条命令之间等它被消费**（日志出现 `[CMD] xxx`），再发下一条。
- 一句话说清：用户要做什么 → 做完回复什么 → 你接下来自动做什么

### 介入话术模板

> 浏览器已打开《XXX》，窗口在你屏幕上，不会自动关闭。
> 请：① 点登录，手机号获取验证码（你给的 0980 我已填好）② 手动滑一下验证 ③ 登录成功后把清晰度切到 1080P ④ 播放 5~10 秒。
> 完成后回我一句「好了」，我就开始抓流并下载。

---

## 标准流程（6 阶段）

### 阶段 0：环境准备（新电脑/迁移后先跑一次）

**一键就绪（推荐）**：

```bash
bash <skill>/scripts/setup.sh
```

`setup.sh` 幂等，会自动：定位 node/python3 → 装 `playwright-core` 并建可移植 `node_modules` 软链
→ 检测本机 Chrome → 检测/安装 ffmpeg → 全部脚本语法自检。跑完看末尾提示即可。

依赖清单（手动装也可）：
- **Node.js 18+**（跑 browser_ctl.mjs）
- **playwright-core**（`npm i playwright-core`；ESM 不读 `NODE_PATH`，`setup.sh` 会把它链到 `scripts/node_modules/`）
- **本机 Google Chrome**（有头模式固定用它；`channel:'chrome'`）
- **Python 3.8+**（下载/合并脚本全部只用标准库，零 pip 依赖）
- **ffmpeg**（合并用；系统有 `ffmpeg` 即可，没有则 `pip install imageio-ffmpeg`，merge_verify.py 会自动找）
- **curl**（youku_probe.py 探测分片大小用；macOS/Linux 自带）

有头模式**固定用本机 Chrome**（`channel:'chrome'`）；Chrome 启动失败才回退内置 Chromium。
**不要在 Chrome / Chromium 之间随意切换**——两套环境 profile 不互通，会导致用户反复登录。

> 下文所有 `node` / `python` 命令都按 PATH 中的可用版本执行即可，不要写死某台机器的绝对路径。

### 阶段 1：拉起常驻浏览器

```bash
mkdir -p <工作目录>/shots
node <skill>/scripts/browser_ctl.mjs <工作目录> "<视频页URL>" <正片最小时长>
```

- `正片最小时长`：区分正片和广告/预览（长视频填 600，短视频填 60）
- 脚本长驻，通过文件通道通信（见脚本头部注释）

**🔑 浏览器与 profile 全局唯一（防止反复登录的核心）：**
- **浏览器固定本机 Chrome**，失败才回退 Chromium（启动日志会打印实际用了哪个）。
- **profile 用全局共享目录** `~/.workbuddy/browser-profiles/video-downloader`，**与工作目录无关**。
  用户在任意一次任务里登录后，登录态写进这个共享 profile，以后**所有**视频下载任务
  （优酷/腾讯/爱奇艺/B站、任何工作目录）都免登录、免重新切画质。
- 可用环境变量 `CHROME_PROFILE=<路径>` 覆盖 profile（一般不需要）。
- **不要**用 agent-browser / playwright 默认 profile / 用户日常 Chrome 来做视频下载——
  profile 不互通会造成"两边横跳、反复登录"。视频下载一律走本 skill 的 browser_ctl.mjs。
- **启动前先确认没有残留的本 skill Chrome 实例**（`pkill -f "Google Chrome.app"` 或 stop.flag），
  同一 profile 不能被两个 Chrome 同时占用。

**启动方式必须用 `start_new_session=True`**，否则 Bash 工具结束时会把整个进程组回收：

```python
subprocess.Popen([...], stdout=open('browser.log','ab'),
                 stderr=subprocess.STDOUT, start_new_session=True)
```

**停止**：`touch <工作目录>/stop.flag`（脚本吞掉了 SIGINT/SIGTERM，Ctrl+C 无效，这是故意的——防止误杀窗口）

### 阶段 2：判断页面状态（三分支）

启动后约 1~2 秒看 `browser.log`，控制器会**自动**输出两行关键结论（不用干等 150 秒）：

1. **登录态**（强制前置，决定能否拿高画质）：
   - `【登录态】已登录 ✓` → 可采集最高画质
   - `【登录态】未登录 ✗` → **必须先停下提醒用户手动登录 + 切到最高清晰度（1080P）**，否则只能拿到低画质。
     登录/短信验证码/滑动验证都交给用户做（见介入协议）。用户登录后可再发 `echo "logininfo" > cmd.txt` 复核。
   - 优酷登录态以 cookie `unb`（用户ID）/`tracknick`（昵称）为准；也可用 `logininfo` 命令手动复查。
2. **视频拦截状态**（三分支）：

| 日志结论 | 含义 | 下一步 |
|---|---|---|
| `主视频就绪（无密码拦截）` | **无验证码视频**，视频直接播放 | 确认画质后直接进阶段 3 采集，**不要**发 pwauto |
| `检测到观看密码弹窗` | 有观看密码 | 发 `echo "pwauto <密码>" > cmd.txt`；失败再请用户手动 |
| `超时：既无主视频也无密码弹窗` | 需要登录 / 滑动验证 / 短信验证码 | 走**手动介入协议**，停下等用户 |

辅助判断：
```bash
cat <工作目录>/status.txt       # 有 {"t":..,"w":1920} 且 t 增长 = 视频在播放
echo "dom" > <工作目录>/cmd.txt  # 导出页面文本，确认到底弹了什么（别靠猜）
echo "logininfo" > cmd.txt       # 手动复查登录态（写 logininfo.txt）
```

**画质确认**：不管哪条分支，采集 URL 前都要让用户在播放器里把清晰度切到最高
（1080P 需登录、部分需会员）。采集到的分片画质 = 播放器当前选定画质。
用户处理完、视频正常播放后，确认 `status.txt` 的 `w` 已是目标分辨率（1080→1920，720→1280）。

- **无验证码的公开/已登录视频**：视频自动播放，`status.txt` 直接有值，跳过密码步骤。
- **观看密码**：`pwauto` 自动过（见下）。**pwauto 只对有密码弹窗的视频使用**，无密码视频发它返回 no-input（无害但无意义）。
- **登录 / 滑动 / 短信验证码**：无法可靠自动化，必须交给用户。

> 密码弹窗的确定按钮坐标由 `getBoundingClientRect()` 实时读取，是**浏览器视口相对坐标**，
> Playwright 内部自动换算屏幕位置——窗口在屏幕上移动、调整大小都不影响点击（已实测移动窗口后仍命中）。

### 阶段 3：采集分片 URL

按平台调用采集脚本（优酷：`scripts/youku_collect.py <工作目录> [总时长]`）。

通用原理：**seek 到各分片起点 → 浏览器发请求 → 监听器记录 URL**。
分片起点时间按平台规律推算，见 `references/`。

采集完立即进入阶段 4，令牌可能过期。

### 阶段 4：探测 + 并行下载

```bash
python <skill>/scripts/youku_probe.py <工作目录>      # 优酷：窗口URL → 整分片URL + 大小
python <skill>/scripts/youku_download.py <工作目录>   # 并行下载
```

**⚠️ 别跳过 probe**：`youku_collect.py` 产出的是带 10 秒窗口参数的 URL，
`youku_download.py` 需要的是去掉窗口参数的整分片 URL（`chunks_full.json`）。
两者之间**必须**经过 `youku_probe.py` 转换，否则下载到的只是 10 秒片段。

核心提速手段（**必用**）：
- 单个文件切成 N 段 **Range 请求并发**（CDN 单连接限速，并发可线性提速）
- 多个分片同时下载
- 推荐组合：单分片 6 路 × 3 分片并发 → 实测 2.45 GB / 175 秒
- 每片下载完**比对字节数**是否等于 CDN `Content-Range` 声明的总长

### 阶段 5：合并 + 校验

```bash
python <skill>/scripts/merge_verify.py <工作目录> <输出.mp4> [分片目录]
```

自动完成：concat 无损合并（`-c copy`，不重编码）→ 解析时长/分辨率 → **逐个拼接点解码体检**。

### 阶段 6：⛔ 用户验收 → 清理分片（不可跳过）

合并完成**不等于**任务完成。必须走完验收：

**6.1 报告结果**，明确给出：文件名、大小、分辨率、时长、拼接点校验结论。

**6.2 请求用户验收**，话术：

> 合并完成，成品在 `<路径>`，1080P / 01:16:39 / 2.4 GB，32 个拼接点解码零错误。
> **麻烦你打开播放确认一下**（重点看几个拼接处、开头结尾、音画是否同步）。
> 确认没问题回我一句「OK」，我就把 2.5 GB 的中间分片清掉；有问题我重新下对应分片。

**6.3 等用户明确确认后**才清理：

```bash
python <skill>/scripts/cleanup.py <工作目录> seg                     # 默认进废纸篓，可恢复
python <skill>/scripts/cleanup.py <工作目录> seg --merged <成品.mp4> # 成品在工作目录外时必用
python <skill>/scripts/cleanup.py <工作目录> seg --purge             # 永久删除，需输入 DELETE
```

`cleanup.py` 内置**安全闸**：
- 找不到成品文件 → 拒绝执行（成品若已移到工作目录外，必须用 `--merged <成品路径>` 显式指定）
- 成品 < 1 MB（占位空文件）→ 拒绝
- 成品体积 < 分片总量 × 0.9 → 拒绝
- 默认不物理删除：macOS 优先移废纸篓（osascript 失败则 `mv ~/.Trash`），其他系统重命名 `_pending_delete`

**6.4 收尾**：把成品移到工作区根目录，命名「标题_分辨率.mp4」；
`touch <工作目录>/stop.flag` 停掉浏览器脚本；告诉用户 Chrome 窗口可自行关闭。

> **非分片类下载**（单个完整文件 / 单个 m3u8 直接下）：跳过阶段 6 的清理环节，
> 但仍需让用户确认视频可正常播放。

---

## 平台适配表

| 平台 | 参考文档 | 分片规律 | 状态 |
|---|---|---|---|
| 优酷 youku.com | `references/youku.md` | N = ceil(时长/140)，分片号**十六进制** | ✅ 已验证（1080P / 76分钟 / 2.45GB） |
| 腾讯视频 | — | 待补充 | ⬜ |
| 爱奇艺 | — | 待补充 | ⬜ |
| B站 | — | 待补充 | ⬜ |

### 新增平台的标准动作

1. 用 `browser_ctl.mjs` 打开视频页，播放，观察 `netlog2.jsonl` 里的媒体 URL 形态
2. 判断分片规律：改 URL 参数看能取回多大（用 `curl -r 0-0 -D -` 读 `Content-Range` 总长）
3. 找出分片号在 URL 里的位置和进制（**务必确认是十进制还是十六进制**）
4. 写 `scripts/<platform>_collect.py`，复用 `browser_ctl.mjs` 的 seek 通道
5. 若存在「窗口 URL → 整片 URL」的转换，单独写 `<platform>_probe.py`
6. 在 `references/<platform>.md` 记录规律 + 踩过的坑
7. 更新本文件的平台适配表

---

## 通用踩坑清单

| 坑 | 现象 | 解法 |
|---|---|---|
| 响应监听没挂上 | 首屏请求全漏 | 监听器注册必须在 `page.goto()` **之前** |
| 重复 seek 抓不到 URL | 同一位置第二次没请求 | CDP `Network.setCacheDisabled` 禁缓存 |
| 分片号进制错 | 死活差几个分片 | 优酷是**十六进制**，务必 `int(x, 16)` 验证 |
| 漏了 probe 环节 | 下下来只有 10 秒 | collect → **probe** → download，三步不能少 |
| `page.waitForTimeout` 不存在 | 脚本崩溃 | 统一用 `new Promise(r=>setTimeout(r,ms))` |
| 后台进程被回收 | Bash 工具结束进程就没了 | `Popen(..., start_new_session=True)` |
| 反复要求登录 | 每个任务开不同浏览器/profile，登录态不互通 | **固定本机 Chrome + 全局共享 profile** `~/.workbuddy/browser-profiles/video-downloader`；视频下载只用 browser_ctl.mjs，别用其他浏览器/默认 profile |
| 拿到的是低画质 | 未登录就采集 | 启动后先看【登录态】，未登录必须提醒用户手动登录 + 切最高画质再采集（优酷以 cookie `unb` 判登录） |
| 自己的 `inspect.py` 遮蔽标准库 | `import inspect` 报 IndexError | **工作目录别放 stdlib 同名文件**；或换 cwd 执行 |
| playwright-core 找不到 | `Cannot find module` | 设 `NODE_PATH` 或建 `node_modules` 软链 |
| 填密码后提交空值 | 框里显示 0980 但「密码错误」 | 原生 setter 不同步 Vue v-model；用 `page.keyboard.type()` 逐字符输入（`pwauto`） |
| Enter 提交不了密码 | 按回车弹窗没反应 | 优酷密码框不绑回车，必须真实鼠标点「确定」(`page.mouse` + getBoundingClientRect 坐标) |
| cmd.txt 命令不执行 | 日志没有 `[CMD] xxx` | **单文件通道竞态**：连发命令互相覆盖；每条等日志出现再发下一条 |
| 填不进普通输入框 | `page.fill()` 无效 | 先 `handle.click()` 聚焦，再 `keyboard.type`；跨 iframe 用 fr.fill |
| 下载慢 | 单连接 1 MB/s | 并发 Range，6 路可达 55 MB/s |
| 400 错误 | 时间窗参数超界 | 说明该文件只含一个分片，换分片 URL |
| 分片文件名没补零 | 合并顺序错乱 | `merge_verify.py` 用自然排序，已处理 |
| 提前删了分片 | 用户发现视频有问题，无法重下 | **必须等用户验收通过** |
| `import imageio_ffmpeg` 崩 | 工作目录有 `inspect.py` 等同名文件 | 换到 `/tmp` 等干净目录执行 |

---

## 文件清单

```
scripts/
  setup.sh             【新电脑先跑】一键环境就绪：装 playwright-core、建 node_modules 软链、检测 Chrome/ffmpeg、语法自检（幂等）
  browser_ctl.mjs      有头浏览器常驻控制器（通用，多平台复用；固定本机 Chrome + 全局共享 profile）
  youku_collect.py     优酷：seek 各分片起点，采集窗口 URL → chunks.json
  youku_probe.py       优酷：窗口 URL → 整分片 URL + 大小 → chunks_full.json
  youku_download.py    优酷：整分片并行 Range 下载（含字节数校验）
  merge_verify.py      通用：concat 无损合并 + 时长/分辨率校验 + 接缝解码体检
  cleanup.py           通用：验收通过后安全清理分片（废纸篓 + 安全闸，--merged/--purge）
  mp4info.py           纯 Python 解析 MP4 moov（编码/分辨率/采样率/时长）
references/
  youku.md             优酷流结构完整逆向笔记
```

> **平台**：主要支持 macOS / Linux（有头 Chrome、bash、curl、ffmpeg）。Windows 需在 Git-Bash/WSL 下运行；
> 清理分片的"移废纸篓"在 macOS 用 osascript，其他系统自动降级为重命名 `_pending_delete`（可恢复）。
>
> **迁移到别的电脑**：拷贝整个 skill 目录后，先 `bash scripts/setup.sh`，再首次运行时在弹出的 Chrome 里登录一次即可。
> 注意：`scripts/node_modules` 是指向本机 playwright-core 的软链，**不要直接拷贝**，到新机由 setup.sh 重建。

### 优酷流水线命令速查

```bash
S=~/.workbuddy/skills/video-downloader-by-browser/scripts
W=/path/to/workdir

node $S/browser_ctl.mjs $W "<url>" 600 &          # 阶段1-2：起浏览器，用户介入
python $S/youku_collect.py $W 4599                 # 阶段3：采集 33 个分片 URL
python $S/youku_probe.py $W                        # 阶段4a：转整分片 URL
python $S/youku_download.py $W                     # 阶段4b：并行下载
python $S/merge_verify.py $W "$W/out.mp4" seg      # 阶段5：合并+校验
python $S/cleanup.py $W seg                        # 阶段6：用户验收通过后清理
```
