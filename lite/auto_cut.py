"""口播粗剪：语音识别 → 选句子 → 生成带字幕的明文剪映草稿（可在剪映里继续改，也可无界面导出）。

视频放在 work/lite/src/。识别用本机 mlx-whisper（pip install mlx-whisper），结果缓存成同名 .asr.json。
选哪些句子由人或大模型决定，本脚本只负责把决定变成时间线。
"""
import json
import shutil
import subprocess
from pathlib import Path

import pyJianYingDraft as draft
from pyJianYingDraft import SEC, trange

from make_draft import FPS, JIANYING_ROOT, frames_to_us, probe

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work' / 'lite'
MODEL = 'mlx-community/whisper-large-v3-turbo'
PAD_BEFORE, PAD_AFTER = 0.2, 0.2     # Whisper 的词起点常偏晚 0.1 秒以上，0.08 秒实测会切掉句首辅音
LINE_CHARS = 42                      # 一行字幕的最大字符数


def transcribe(video: Path) -> list:
    cache = video.with_suffix('.asr.json')
    if not cache.exists():
        import mlx_whisper
        wav = video.with_suffix('.wav')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video), '-ac', '1', '-ar', '16000', str(wav)], check=True)
        result = mlx_whisper.transcribe(str(wav), path_or_hf_repo=MODEL, word_timestamps=True)
        cache.write_text(json.dumps(result, ensure_ascii=False))
    return json.loads(cache.read_text())['segments']


def caption_lines(words: list) -> list:
    """把一句话的词按长度切成若干行字幕，每行带自己的起止时间。"""
    lines, current = [], []
    for word in words:
        text = ''.join(w['word'] for w in current + [word]).strip()
        if current and len(text) > LINE_CHARS:
            lines.append(current)
            current = []
        current.append(word)
    lines.append(current)
    return [(''.join(w['word'] for w in line).strip(), line[0]['start'], line[-1]['end']) for line in lines]


def build(name: str, video: Path, segments: list, keep: list, title: str, fixes: dict, out_root: Path) -> Path:
    width, height, total = probe(video)
    out_root.mkdir(parents=True, exist_ok=True)
    script = draft.DraftFolder(str(out_root)).create_draft(name, width, height, fps=FPS, allow_replace=True)
    target = out_root / name
    media = target / 'materials' / video.name
    media.parent.mkdir(exist_ok=True)
    shutil.copy2(video, media)

    video_track = script.append_track(draft.TrackSpec(draft.TrackType.video))
    caption_track = script.append_track(draft.TrackSpec(draft.TrackType.text, name='字幕'))
    title_track = script.append_track(draft.TrackSpec(draft.TrackType.text, name='标题'))
    caption_style = draft.TextStyle(size=7.0, color=(1.0, 1.0, 1.0), align=1, auto_wrapping=True)
    border = draft.TextBorder(color=(0.0, 0.0, 0.0), width=40.0)

    # 每句前后留余量；源里紧挨着的两句余量会重叠，就在两句中间切，避免重复画面或切掉句首
    ranges = [[max(segments[i]['words'][0]['start'] - PAD_BEFORE, 0.0),
               min(segments[i]['words'][-1]['end'] + PAD_AFTER, total)] for i in keep]
    for left, right, a, b in zip(ranges, ranges[1:], keep, keep[1:]):
        if b == a + 1 and left[1] > right[0]:
            left[1] = right[0] = (segments[a]['words'][-1]['end'] + segments[b]['words'][0]['start']) / 2

    # 所有切点按帧计数再换算成微秒：累计帧数保证总时长正好是整数帧
    cursor_frames = 0
    for index, (start, end) in zip(keep, ranges):
        words = segments[index]['words']
        start_frame, end_frame = round(start * FPS), round(end * FPS)
        cursor, duration = frames_to_us(cursor_frames), frames_to_us(cursor_frames + end_frame - start_frame) - frames_to_us(cursor_frames)
        script.add_segment(draft.VideoSegment(str(media), trange(cursor, duration),
                                              source_timerange=trange(frames_to_us(start_frame), duration)), video_track)
        for text, line_start, line_end in caption_lines(words):
            for wrong, right in fixes.items():
                text = text.replace(wrong, right)
            first = cursor_frames + max(round(line_start * FPS) - start_frame, 0)
            last = min(cursor_frames + round(line_end * FPS) - start_frame, cursor_frames + end_frame - start_frame)
            if last <= first:
                continue
            script.add_segment(draft.TextSegment(text, trange(frames_to_us(first), frames_to_us(last) - frames_to_us(first)),
                                                 style=caption_style, border=border,
                                                 clip_settings=draft.ClipSettings(transform_y=-0.75)), caption_track)
        cursor_frames += end_frame - start_frame
    cursor = frames_to_us(cursor_frames)
    if title:
        script.add_segment(draft.TextSegment(title, trange(0, min(3 * SEC, cursor)),
                                             style=draft.TextStyle(size=12.0, bold=True, color=(1.0, 0.85, 0.2), align=1),
                                             border=border, clip_settings=draft.ClipSettings(transform_y=0.72)), title_track)
    script.save()

    shutil.copy2(target / 'draft_content.json', target / 'draft_info.json')
    meta_path = target / 'draft_meta_info.json'
    meta = json.loads(meta_path.read_text())
    meta['tm_duration'] = cursor
    meta_path.write_text(json.dumps(meta, ensure_ascii=False))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(segments[keep[0]]['start'] + 1), '-i', str(media),
                    '-frames:v', '1', str(target / 'draft_cover.jpg')], check=True)
    return target


def main():
    videos = sorted((WORK / 'src').glob('*.mp4'))
    if not videos:
        print('先把视频放进 work/lite/src/')
        return
    for index, path in enumerate(videos, 1):
        print(f'{index}. {path.name}')
    video = videos[int(input('剪哪个视频（序号）: ').strip()) - 1]
    segments = transcribe(video)
    for index, segment in enumerate(segments):
        print(f'{index:3d} {segment["start"]:7.2f}-{segment["end"]:7.2f} {segment["text"].strip()}')
    keep = [int(part) for part in input('保留哪些句子（序号，空格分隔，按成片顺序）: ').split()]
    name = input('草稿名: ').strip() or video.stem + '-cut'
    title = input('开头标题（留空则不加）: ').strip()
    fixes = dict(pair.split('=', 1) for pair in input('字幕替换词（如 CIFR=CIPHER，空格分隔，可留空）: ').split())
    print('已生成（供无界面导出）:', build(name, video, segments, keep, title, fixes, WORK / 'drafts'))
    if input('同时放一份到剪映草稿目录？(y/N): ').strip().lower() == 'y':
        print('已生成（剪映首页可见）:', build(name, video, segments, keep, title, fixes, JIANYING_ROOT))


if __name__ == '__main__':
    main()
