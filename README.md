# 像素风解说视频 · 起步工程

用 Python 一帧一帧画像素风解说视频：文案 → 分镜 → 角色表情 → 像素材质场景 → 配音时间轴 → 音效 / BGM → 动画 → 成片 → 自检。
做法来自我做得最好的一期像素片：拟物化的精细场景、按剧情做的表情、卡在台词上的动效和音效、有快有慢的节奏。
自带一个十几秒的示例（奶茶店小满「两分钟挣六毛七」）和一张场景样张。

**每一步发给 AI 的提示词都在 `GUIDE.md`（复刻手册）里。** 把这个仓库给你的 AI 编程助手，让它先读 `GUIDE.md`，从第 0 步开始做。

## 下载
- 有 git：`git clone https://github.com/m1dsa/pixel-video-starter.git`
- 没有 git：下载压缩包 https://github.com/m1dsa/pixel-video-starter/releases/latest/download/pixel-video-starter.zip

## 安装
1. Python 3.10+（推荐 3.12），以及 ffmpeg（命令行能直接运行 `ffmpeg -version`）。
2. `pip install -r requirements.txt`
3. 复制 `.env.example` 为 `.env`，填入豆包语音合成 2.0 的 API Key（没有 Key 也能先用 `--dry` 跑通画面）。

## 跑示例
```
python voice.py --dry          # 或 python voice.py（真配音）
python film.py --chars         # 定妆照 out/定妆.png
python film.py --sheet S01 S02 # 联系表 out/sheet_S01-S02.png
python sfx.py                  # 混音 out/mix.wav
python film.py --full          # 成片 out/成片.mp4
python qa.py                   # 自检 out/qa.md
python px_demo.py              # 场景样张 out/像素材质样张.png
python sfx.py --preview        # 音效试听 out/音效试听/
```
Windows 上如果中文输出乱码，用 `python -X utf8 ...`。
渲染时报 `Unable to allocate`（内存不够）：设环境变量 `PXV_PROCS=1`（或 2）再跑 `film.py --full`。

完整流程（从写文案到出成片，每一步跟 AI 说什么）见 `GUIDE.md`（复刻手册）。

## 文件
| 文件 | 作用 |
| --- | --- |
| `pxv.py` | 渲染内核：浮点像素格、光照、像素字（风格的根，别改） |
| `sprites.py` | 主角和路人的像素行、表情零件、换装 |
| `kit.py` | 时间轴上下文、缓动、字幕、进度条、标签、大字、小道具 |
| `pix.py` | 像素材质画法：逐格上色（色阶、体积、材质、选择性描边、投影），别改 |
| `px_parts.py` | 场景零件库：房间、地板、墙纸、窗、窗帘、书架、盆栽、挂钟、门、桌子、想象云、对话气泡…… |
| `px_demo.py` | 场景样张：夜里的房间一角 + 书桌（照着写新场景） |
| `docs/pixel-material.md` | 像素材质画法的规则、例子、踩过的坑、自查清单 |
| `sets.py` | 示例用的简单场景：奶茶店、店门口、卧室、舞台、夜街 |
| `scenes_demo.py` | 示例镜头（照着写你自己的 `scenes_xxx.py`） |
| `voice.py` | 字幕核对 + 豆包配音 + 时间轴 |
| `sfx.py` | 代码合成音效 + 混音（-14 LUFS，BGM 可选：放 `music/bgm.wav`） |
| `film.py` | 渲染、检查图、定妆照、封面 |
| `qa.py` | 成片自检 |
| `GUIDE.md` | 复刻手册：每一步你做什么、发给 AI 的提示词、怎么验收 |
| `AGENTS.md` / `CLAUDE.md` | 给 AI 编程助手的项目规矩（内容相同） |

## 字体
`fonts/` 里两款字体都是 SIL Open Font License 1.1（许可证文本在同目录）：
- Fusion Pixel（像素字幕）：https://github.com/TakWolf/fusion-pixel-font
- Noto Sans SC 思源黑体（进度条等界面字）：https://github.com/notofonts/noto-cjk
