"""把 work/lite/drafts 下的明文草稿用本机剪映引擎无界面导出成 MP4。

只复用上游的 engine/native_export.cpp：它读的是明文时间线 JSON，不需要 codec；
它只认 libvideoeditor.dylib 哈希匹配的剪映 11.5.0 / 11.4.2，不匹配会直接报错退出。
"""
import copy
import json
import math
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work' / 'lite'
HELPER = WORK / 'native-export-helper'
SOURCE = ROOT / 'engine' / 'native_export.cpp'
FRAMEWORKS = Path('/Applications/VideoFusion-macOS.app/Contents/Frameworks')
BITRATE, TIMEOUT = 8_000_000, 600


def build_helper():
    # 导出助手的编译产物上游只记录不校验，本机任意版本的 clang 都行
    if HELPER.exists() and HELPER.stat().st_mtime >= SOURCE.stat().st_mtime:
        return
    WORK.mkdir(parents=True, exist_ok=True)
    subprocess.run(['/usr/bin/xcrun', 'clang++', '-std=c++17', '-arch', 'arm64', '-O2',
                    '-Wno-deprecated-declarations', str(SOURCE), f'-L{FRAMEWORKS}', '-lvideoeditor',
                    f'-Wl,-rpath,{FRAMEWORKS}', '-o', str(HELPER)], check=True)


def sandbox_profile(job: Path) -> str:
    # sandbox-exec 不解析 json.dumps 的 \uXXXX 转义，路径必须按 UTF-8 原样写入（上游 issue #11）
    for path in (WORK, job):
        if any(ch in str(path) for ch in '"\\\n'):
            raise ValueError(f'路径不能含引号、反斜杠或换行: {path}')
    return ('(version 1)\n(allow default)\n(deny network*)\n(deny file-write*)\n'
            '(deny file-read-data (subpath "/Users"))\n'
            '(deny file-read-data (subpath "/Library/Keychains"))\n'
            f'(allow file-read-data (subpath "{WORK}"))\n'
            f'(allow file-write* (subpath "{job}"))\n'
            '(allow file-write* (literal "/dev/null"))\n')


def pin_static_y(timeline: dict):
    """只有 X 位置关键帧、没有 Y 关键帧的片段，补一条恒定 Y 关键帧。

    无界面导出时这种片段的 Y 会逐帧在 +y/-y 间跳（上游 issue #9，720p 实测 178↔538px）；
    反过来只有 Y 关键帧时 X 不抖，所以只补这一个方向。只改导出用的副本，不动草稿。
    """
    for track in timeline['tracks']:
        for segment in track['segments']:
            lists = {k['property_type']: k for k in segment.get('common_keyframes', [])}
            if 'KFTypePositionX' not in lists or 'KFTypePositionY' in lists:
                continue
            pinned = copy.deepcopy(lists['KFTypePositionX'])
            pinned.update(id=uuid.uuid4().hex, property_type='KFTypePositionY')
            for keyframe in pinned['keyframe_list']:
                keyframe.update(id=uuid.uuid4().hex, values=[segment['clip']['transform']['y']])
            segment['common_keyframes'].append(pinned)


def export(draft: Path) -> Path:
    timeline = json.loads((draft / 'draft_info.json').read_text())
    pin_static_y(timeline)
    canvas, fps = timeline['canvas_config'], timeline.get('fps', 30)
    # 素材必须在 work/lite 内，否则沙箱里读不到，成片会缺画面
    materials = timeline['materials'].get('videos', []) + timeline['materials'].get('audios', [])
    outside = [m['path'] for m in materials if not Path(m['path']).resolve().is_relative_to(WORK)]
    if outside:
        raise ValueError(f'素材不在 {WORK} 内: {outside}')

    job = WORK / 'exports' / f'{draft.name}-{time.strftime("%Y%m%d-%H%M%S")}'
    job.mkdir(parents=True)
    (job / 'timeline.json').write_text(json.dumps(timeline, ensure_ascii=False))
    (job / 'export.sb').write_text(sandbox_profile(job))
    output = job / 'render.mp4'
    with open(job / 'engine.log', 'wb') as log:
        result = subprocess.run(['/usr/bin/sandbox-exec', '-f', str(job / 'export.sb'), str(HELPER),
                                 str(job / 'timeline.json'), str(output), str(canvas['width']), str(canvas['height']),
                                 str(fps), str(BITRATE), str(TIMEOUT), '0'],
                                cwd=job, stdout=log, stderr=log, timeout=TIMEOUT + 60)
    if result.returncode:
        tail = (job / 'engine.log').read_text(errors='replace').splitlines()[-3:]
        raise RuntimeError(f'导出失败，日志 {job / "engine.log"}\n' + '\n'.join(tail))

    # 帧数和完整解码都过才算成片；上游记录过图片/GIF 偶发少一帧，少帧不算成片
    probe = json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
         '-show_entries', 'stream=nb_read_frames', '-of', 'json', str(output)]))
    frames = int(probe['streams'][0]['nb_read_frames'])
    expected = math.ceil(timeline['duration'] * fps / 1_000_000)  # 引擎按总时长向上取整出帧，三组实测一致
    if frames != expected:
        raise RuntimeError(f'帧数不对: {frames}，应为 {expected}')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(output), '-f', 'null', '-'], check=True)
    print(f'成片 {output}（{frames} 帧，完整解码通过）')
    return output


def main():
    drafts_dir = WORK / 'drafts'
    drafts = sorted(p for p in drafts_dir.iterdir() if (p / 'draft_info.json').exists()) if drafts_dir.is_dir() else []
    if not drafts:
        print('work/lite/drafts 下没有草稿，先运行 lite/make_draft.py 并选 1')
        return
    for index, path in enumerate(drafts, 1):
        print(f'{index}. {path.name}')
    choice = input('导出哪个草稿（序号）: ').strip()
    build_helper()
    export(drafts[int(choice) - 1])


if __name__ == '__main__':
    main()
