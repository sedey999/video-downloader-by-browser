"""采集全部 33 个分片的 URL。
优酷分片规律：
  文件名 03000C21{HEX}649EAA...  其中 {HEX} = 分片号(00~20 十六进制)
  每个分片约 140 秒，seek 到 i*140+5 即可引出第 i 个分片的 URL
  请求带 ts_start/ts_end/ts_seg_no(10秒窗口)，去掉后可取回整个分片
"""
import json, os, math, time, urllib.parse as up

import sys
ROOT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
NET2 = ROOT + 'netlog2.jsonl'
CMD = ROOT + 'cmd.txt'
WIN = 140.0
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 4599.0  # 正片总时长
# N = ceil(总时长/140)，自动适配不同长度视频（优酷每分片约140秒）
CHUNKS = max(1, math.ceil(DUR / WIN))
print(f'[collect] 按时长 {DUR:.0f}s 推算分片数 N={CHUNKS}')


def chunk_index(url):
    """从 URL 文件名提取分片号(十六进制2位)"""
    fn = up.urlparse(url).path.split('/')[-1]
    # 03000C21 XX 649EAA...
    if len(fn) >= 10 and fn.startswith('03000C21'):
        hx = fn[8:10].lower()
        try:
            return int(hx, 16)
        except ValueError:
            return None
    return None


def discovered(since_ts=0):
    """返回 {分片号: (时间戳, url)}"""
    got = {}
    if not os.path.exists(NET2):
        return got
    for line in open(NET2):
        try:
            r = json.loads(line)
        except Exception:
            continue
        u = r.get('url', '')
        if 'cibntv' not in u:
            continue
        if r.get('ts', 0) < since_ts:
            continue
        idx = chunk_index(u)
        if idx is None or not (0 <= idx < CHUNKS):
            continue
        got.setdefault(idx, (r['ts'], u))
    return got


def main():
    # 只用本次运行之后抓到的记录，避免混入过期令牌
    t0 = int(time.time() * 1000)
    print(f'基准时间戳 {t0}，开始遍历 {CHUNKS} 个分片...')

    for rnd in range(3):
        got = discovered(t0)
        missing = [k for k in range(CHUNKS) if k not in got]
        print(f'\n== 第{rnd+1}轮: 已发现 {len(got)}/{CHUNKS}, 缺 {[f"{k:02x}" for k in missing]}')
        if not missing:
            break
        for k in missing:
            # 在分片内取多个探测点，任一点命中即可
            for offset in (5, 60, 120, 30, 95):
                got = discovered(t0)
                if k in got:
                    break
                t = min(WIN * k + offset, DUR - 9)
                with open(CMD, 'w') as f:
                    f.write(f'seek {t:.1f}\n')
                time.sleep(3.2)
            got = discovered(t0)
            print(f'  chunk {k:02x} (t={WIN*k+5:.0f}s) -> {"OK" if k in got else "MISS"}   共 {len(got)}/33')
        time.sleep(1)

    got = discovered(t0)
    print(f'\n最终发现 {len(got)}/{CHUNKS} 个分片')
    out = {}
    for k in sorted(got):
        out[f'{k:02x}'] = got[k][1]
        fn = up.urlparse(got[k][1]).path.split('/')[-1][:12]
        print(f'  {k:02x}  {fn}')
    with open(ROOT + 'chunks.json', 'w') as f:
        json.dump(out, f, indent=1)
    print(f'\n已写入 chunks.json ({len(out)} 条)')
    return len(out)


if __name__ == '__main__':
    main()
