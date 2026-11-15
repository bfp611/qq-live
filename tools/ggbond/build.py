import numpy as np, cv2, json, os
from PIL import Image
from scipy import ndimage as ndi
OUT = '/workspace/qq-live/web/gg'
os.makedirs(OUT, exist_ok=True)
CAN = 1254
BASE = 1135          # 脚底统一基线（原图坐标）
CX = 625
JUMP = {0}           # 跳跃姿势不压到基线
imgs = []; meta = {}
for i in range(18):
    im = np.asarray(Image.open(f'work/k{i:02d}.png'))
    a = im[..., 3]
    ys, xs = np.where(a > 25)
    bottom = ys.max()
    lab, n = ndi.label(a > 128)
    sizes = ndi.sum(a > 128, lab, range(1, n+1)); big = lab == (1 + int(np.argmax(sizes)))
    cx = np.where(big)[1].mean()
    dy = 0 if i in JUMP else int(BASE - bottom)
    dx = int(np.clip(CX - cx, -120, 120))
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    sh = cv2.warpAffine(im, M, (CAN + 300, CAN + 300), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    imgs.append(sh); meta[i] = dict(dx=dx, dy=dy)
# 并集裁剪
x0 = y0 = 10**9; x1 = y1 = 0
for s in imgs:
    ys, xs = np.where(s[..., 3] > 12)
    x0 = min(x0, xs.min()); x1 = max(x1, xs.max()); y0 = min(y0, ys.min()); y1 = max(y1, ys.max())
pad = 8
x0 = max(0, x0 - pad); y0 = max(0, y0 - pad); x1 += pad; y1 += pad
W, H = x1 - x0, y1 - y0
TH = 512
sc = TH / H
print('union', x0, y0, x1, y1, W, H, 'scale', sc)
tot = 0
for i, s in enumerate(imgs):
    c = s[y0:y1, x0:x1].copy()
    # 预乘缩放，避免缩小时边缘发白/发绿光晕
    f = c[..., :3].astype(np.float32) * (c[..., 3:4].astype(np.float32) / 255)
    a = c[..., 3].astype(np.float32)
    nw, nh = round(W * sc), TH
    f2 = cv2.resize(f, (nw, nh), interpolation=cv2.INTER_AREA)
    a2 = cv2.resize(a, (nw, nh), interpolation=cv2.INTER_AREA)
    rgb = np.where(a2[..., None] > 0.5, f2 / np.maximum(a2[..., None] / 255, 1e-3), 0)
    out = np.dstack([np.clip(rgb, 0, 255), a2]).astype(np.uint8)
    Image.fromarray(out, 'RGBA').save(f'{OUT}/p{i:02d}.webp', quality=88, method=6, alpha_quality=95)
    tot += os.path.getsize(f'{OUT}/p{i:02d}.webp')
print('pose total KB', tot // 1024, 'size', nw, nh)
json.dump({'w': nw, 'h': nh, 'baseline': round((BASE - y0) * sc)}, open('work/meta.json', 'w'))
# 头像：从 pose 8 / 16 取脸部裁切
for pid, name in ((8, 'head8'), (16, 'head16')):
    s = imgs[pid]
    ys, xs = np.where(s[..., 3] > 25)
    top = ys.min(); left = xs.min(); right = xs.max()
    cxm = (left + right) // 2
    size = int((right - left) * 0.95)
    crop = s[max(0, top - 10): max(0, top - 10) + size, cxm - size // 2: cxm + size // 2]
    im = Image.fromarray(crop, 'RGBA')
    bg = Image.new('RGBA', im.size, (255, 230, 150, 255)); bg.alpha_composite(im)
    bg.convert('RGB').resize((48, 48), Image.LANCZOS).save(f'{OUT}/{name}.png')
# 背景
b = Image.open('x/背景.png').convert('RGB').resize((900, 900), Image.LANCZOS)
b.save(f'{OUT}/bg.webp', quality=82, method=6)
print('bg KB', os.path.getsize(f'{OUT}/bg.webp') // 1024)
