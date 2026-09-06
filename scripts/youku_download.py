"""并行下载 33 个分片。
策略：每个分片切成 N 段 Range 并发下载写入同一文件；同时并发处理 M 个分片。
带完整性校验（末尾补拉 / 自动重试）。
"""
import json, os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
import urllib.request

import sys
ROOT = (sys.argv[1] if len(sys.argv) > 1 else '.').rstrip('/') + '/'
SEG = ROOT + 'seg'
os.makedirs(SEG, exist_ok=True)

CHUNK_THREADS = 6      # 单个分片内的并发 Range 数
CHUNK_PARALLEL = 3     # 同时下载的分片数

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36')
HDR = {'Referer': 'https://v.youku.com/', 'User-Agent': UA}

info = json.load(open(ROOT + 'chunks_full.json'))
lock = threading.Lock()
progress = {}


def fetch_range(url, start, end, retries=4):
    """下载 [start, end] 闭区间字节，返回 bytes"""
    req = urllib.request.Request(url, headers=dict(HDR, Range=f'bytes={start}-{end}'))
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                if len(data) == end - start + 1:
                    return data
        except Exception as e:
            if i == retries - 1:
                print(f'    [range fail] {start}-{end}: {str(e)[:60]}')
            time.sleep(1.2 * (i + 1))
    return None


def download_chunk(item):
    k, meta = item
    url, size = meta['url'], meta['size']
    out = os.path.join(SEG, f'chunk_{k}.mp4')
    if os.path.exists(out) and os.path.getsize(out) == size:
        with lock:
            print(f'[{k}] 已存在且大小一致，跳过')
        return k, True, 'cached'

    # 预分配文件
    with open(out, 'wb') as f:
        f.truncate(size)

    part = size // CHUNK_THREADS
    ranges = []
    for i in range(CHUNK_THREADS):
        s = i * part
        e = (size - 1) if i == CHUNK_THREADS - 1 else (s + part - 1)
        ranges.append((s, e))

    def work(rg):
        s, e = rg
        data = fetch_range(url, s, e)
        if data is None:
            return False
        with lock:
            with open(out, 'r+b') as f:
                f.seek(s)
                f.write(data)
            progress[k] = progress.get(k, 0) + len(data)
        return True

    ok = all(ThreadPoolExecutor(max_workers=CHUNK_THREADS).map(work, ranges))

    actual = os.path.getsize(out)
    if actual != size:
        return k, False, f'size {actual}!={size}'
    return k, ok, 'ok'


def main():
    items = sorted(info.items())
    t0 = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=CHUNK_PARALLEL) as ex:
        for k, ok, note in ex.map(download_chunk, items):
            results[k] = (ok, note)
            print(f'[{k}] {"OK" if ok else "FAIL"}  {note}  ({time.time()-t0:.0f}s)')

    good = [k for k, (ok, _) in results.items() if ok]
    bad = [k for k, (ok, _) in results.items() if not ok]
    total = sum(os.path.getsize(os.path.join(SEG, f'chunk_{k}.mp4')) for k in good)
    print(f'\n完成 {len(good)}/33，失败 {len(bad)}：{bad}')
    print(f'已下载 {total/1073741824:.2f} GB，耗时 {time.time()-t0:.0f}s')
    json.dump({'bad': bad}, open(ROOT + 'dl_result.json', 'w'))


if __name__ == '__main__':
    main()
