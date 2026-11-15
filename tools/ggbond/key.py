import glob, numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi

def key(path):
    c = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
    h, w, _ = c.shape
    b = np.concatenate([c[:10].reshape(-1,3), c[-10:].reshape(-1,3), c[:, :10].reshape(-1,3), c[:, -10:].reshape(-1,3)])
    bg = np.median(b, 0)
    r, g, bl = c[...,0], c[...,1], c[...,2]
    d = g - np.maximum(r, bl)
    dbg = bg[1] - max(bg[0], bg[2])
    hi, lo = 0.93*dbg, 0.10*dbg
    a = np.clip((hi - d) / (hi - lo), 0, 1)
    # 去掉背景里零星噪点、保留细小前景：只做极轻的形态学清理
    a[a < 0.02] = 0
    # 轻微收边，去掉最外圈残留的绿边（对半透明像素更狠）
    a2 = a.copy()
    k = np.ones((3,3), np.float32)
    mn = cv2.erode(a, k)
    a2 = np.where(a < 0.999, np.minimum(a, 0.5*a + 0.5*mn) if False else a, a)
    # 反混合：c = a*f + (1-a)*bg
    af = np.maximum(a, 0.06)[...,None]
    f = (c - (1 - a)[...,None]*bg) / af
    f = np.clip(f, 0, 255)
    # 去溢色：绿通道不允许高于红/蓝的最大值
    f[...,1] = np.minimum(f[...,1], np.maximum(f[...,0], f[...,2]) + 2)
    # 小孤岛（<40px 的低 alpha 噪点）
    lab, n = ndi.label(a > 0.05)
    if n:
        sizes = ndi.sum(a > 0.05, lab, range(1, n+1))
        small = np.isin(lab, [i+1 for i, s in enumerate(sizes) if s < 60])
        a[small] = 0
    out = np.dstack([f, a*255]).astype(np.uint8)
    return out, bg

if __name__ == '__main__':
    fs = sorted(glob.glob('x/ig_*.png'))
    for i, f in enumerate(fs):
        o, bg = key(f)
        Image.fromarray(o, 'RGBA').save(f'work/k{i:02d}.png')
    print('done')
