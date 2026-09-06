"""
合并分片 + 完整性校验。

用法:
    python merge_verify.py <工作目录> <输出文件.mp4> [分片目录名(默认seg)]

流程:
    1. 按文件名排序生成 concat 列表
    2. ffmpeg -c copy 无损合并（不重编码，画质零损失）+faststart
    3. 解析合并后 MP4 的时长/分辨率/编码
    4. 逐个拼接点做解码体检（ffmpeg -v error 解码接缝处各 10 秒）

依赖: imageio-ffmpeg（pip install imageio-ffmpeg，自带 ffmpeg 二进制）
"""
import os
import sys
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor


def natural_sort(names):
    """自然排序：chunk_2.mp4 排在 chunk_10.mp4 之前（纯字符串排序会错序）"""
    import re
    def key(s):
        return [int(t) if t.isdigit() else t.lower()
                for t in re.split(r'(\d+)', s)]
    return sorted(names, key=key)


def get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ff = os.popen('which ffmpeg').read().strip()
        if ff:
            return ff
        raise SystemExit('未找到 ffmpeg，请先 pip install imageio-ffmpeg')


def main():
    root = sys.argv[1]
    out = sys.argv[2]
    segdir = sys.argv[3] if len(sys.argv) > 3 else 'seg'
    segdir = os.path.join(root, segdir)
    ff = get_ffmpeg()
    print('ffmpeg:', ff)

    files = natural_sort([f for f in os.listdir(segdir) if f.endswith('.mp4')])
    if not files:
        raise SystemExit(f'{segdir} 中没有 mp4 分片')
    print(f'共 {len(files)} 个分片')
    print('顺序:', ' '.join(files[:6]), '...', ' '.join(files[-3:]) if len(files) > 6 else '')

    listf = os.path.join(root, 'concat.txt')
    with open(listf, 'w') as f:
        for name in files:
            p = os.path.join(segdir, name)
            f.write("file '%s'\n" % p.replace("'", "'\\''"))

    print('开始合并（-c copy，无损）...')
    r = subprocess.run(
        [ff, '-f', 'concat', '-safe', '0', '-i', listf,
         '-c', 'copy', '-movflags', '+faststart', '-y', out],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit('合并失败')
    print('合并完成:', out, '%.2f MB' % (os.path.getsize(out) / 1048576))

    # 校验：时长 / 分辨率
    here = os.path.dirname(os.path.abspath(__file__))
    info = subprocess.run([sys.executable, os.path.join(here, 'mp4info.py'), out],
                          capture_output=True, text=True)
    print('\n=== 合并结果 ===')
    print(info.stdout.strip())

    # 接缝体检
    dur = None
    for line in info.stdout.splitlines():
        if line.startswith('时长:'):
            dur = float(line.split()[1])
    if not dur:
        print('无法解析时长，跳过接缝体检')
        return
    n = len(files)
    seg = dur / n
    print(f'\n接缝体检：{n-1} 个拼接点（每段约 {seg:.0f}s）')

    def check(i):
        t = max(0, i * seg - 3)
        rr = subprocess.run([ff, '-v', 'error', '-ss', str(t), '-t', '10',
                             '-i', out, '-f', 'null', '-'],
                            capture_output=True, text=True)
        return i, rr.stderr.strip()

    errs = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, e in ex.map(check, range(1, n)):
            if e:
                errs.append((i, e))

    if errs:
        print(f'发现 {len(errs)} 个接缝有解码错误:')
        for i, e in errs[:10]:
            print(f'  seam {i}: {e[:300]}')
    else:
        print(f'全部 {n-1} 个拼接点解码无错误 ✓')


if __name__ == '__main__':
    main()
