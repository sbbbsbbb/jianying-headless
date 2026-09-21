"""用 pyJianYingDraft 生成明文剪映草稿（视频 + 一条字幕），不经过 codec。

剪映 11.5.0 直接认明文草稿，要点只有三个：主文件叫 draft_info.json、
元信息里写真实时长、草稿目录里放一张封面。
"""
import json
import shlex
import shutil
import subprocess
from pathlib import Path

import pyJianYingDraft as draft
from pyJianYingDraft import SEC, trange

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / 'work' / 'lite' / 'drafts'
JIANYING_ROOT = Path.home() / 'Movies/JianyingPro/User Data/Projects/com.lveditor.draft'
FPS = 30


def frames_to_us(frames: int) -> int:
    """帧数转微秒，向下取整（剪映自己也是这样记的）。

    引擎按总时长向上取整出帧：四舍五入多出的不到 1 微秒就会让成片多一帧（实测 1652 帧的时间线导出 1653 帧）。
    """
    return frames * SEC // FPS


def probe(video: Path):
    info = json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height:format=duration',
         '-of', 'json', str(video)]))
    stream = info['streams'][0]
    return stream['width'], stream['height'], float(info['format']['duration'])


def build(name: str, video: Path, out_root: Path, subtitle: str) -> Path:
    """在 out_root/name 生成草稿，返回草稿目录。素材复制进草稿目录，草稿可整体搬走。"""
    out_root.mkdir(parents=True, exist_ok=True)
    width, height, seconds = probe(video)
    script = draft.DraftFolder(str(out_root)).create_draft(name, width, height, fps=FPS, allow_replace=True)
    target = out_root / name
    media = target / 'materials' / video.name
    media.parent.mkdir(exist_ok=True)
    shutil.copy2(video, media)

    duration = frames_to_us(int(seconds * FPS))
    video_track = script.append_track(draft.TrackSpec(draft.TrackType.video))
    script.add_segment(draft.VideoSegment(str(media), trange(0, duration)), video_track)
    if subtitle:
        text_track = script.append_track(draft.TrackSpec(draft.TrackType.text))
        script.add_segment(draft.TextSegment(subtitle, trange(0, duration),
                                             clip_settings=draft.ClipSettings(transform_y=-0.7)), text_track)
    script.save()

    content = target / 'draft_content.json'
    # 剪映 6.0+ 的主文件名是 draft_info.json；沿用旧名会报“草稿内容已损坏”（pyJianYingDraft#198）
    shutil.copy2(content, target / 'draft_info.json')
    # pyJianYingDraft 不写时长和封面，首页会显示 00:00 和黑图
    meta_path = target / 'draft_meta_info.json'
    meta = json.loads(meta_path.read_text())
    meta['tm_duration'] = json.loads(content.read_text())['duration']
    meta_path.write_text(json.dumps(meta, ensure_ascii=False))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(media), '-frames:v', '1',
                    str(target / 'draft_cover.jpg')], check=True)
    return target


def main():
    raw = input('把一个视频拖到终端后回车（直接回车用 4 秒测试图）: ').strip()
    if raw:
        video = Path(shlex.split(raw)[0]).expanduser().resolve(strict=True)
    else:
        video = ROOT / 'work' / 'lite' / 'sample.mp4'
        video.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1280x720:rate=30:duration=4',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-shortest', str(video)], check=True)
    name = input('草稿名（默认 lite-demo）: ').strip() or 'lite-demo'
    subtitle = input('字幕文字（留空则不加）: ').strip()
    print('1. 生成到 work/lite/drafts（给 export.py 无界面导出）')
    print('2. 生成到剪映草稿目录（回到剪映首页就能看到）')
    root = JIANYING_ROOT if input('选 1 或 2（默认 1）: ').strip() == '2' else DRAFTS
    print('已生成:', build(name, video, root, subtitle))


if __name__ == '__main__':
    main()
