# 把「千千静听 经典皮肤(~Classic.skn, nanling)」里的 BMP 转成带透明通道的 PNG（#FF00FF 是皮肤定义的透明色）。
# 用法：python tools/make_tt_assets.py /path/to/~Classic.skn(解压后的目录) web/xp/tt     （开发用，需要 Pillow）
# 皮肤来源：https://github.com/szc126/ttplayer-skins-my-archive 里的 ~Classic.skn（官方自带的“经典皮肤”）
import sys, os
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
for n in "player_skin number play pause stop prev next mute open lyric equalizer playlist minimize exit progress_thumb volume_thumb volume_fill playlist_toolbar playlist_title".split():
    im = Image.open(os.path.join(src, n + ".bmp")).convert("RGBA")
    px = im.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            if px[x, y][:3] == (255, 0, 255):
                px[x, y] = (0, 0, 0, 0)
    im.save(os.path.join(dst, n + ".png"))
    print(n, im.size)

# 播放列表窗口：皮肤是 268×90（resize_rect 14,54,254,76 纵向平铺），这里拉成 268×146 的 playlist_win.png
im = Image.open(os.path.join(src, "playlist_skin.bmp")).convert("RGBA")
px = im.load()
for y in range(im.size[1]):
    for x in range(im.size[0]):
        if px[x, y][:3] == (255, 0, 255):
            px[x, y] = (0, 0, 0, 0)
EXTRA = 56
out = Image.new("RGBA", (268, 90 + EXTRA), (0, 0, 0, 0))
out.paste(im.crop((0, 0, 268, 54)), (0, 0))
tile = im.crop((0, 54, 268, 76))
y = 54
while y < 76 + EXTRA:
    out.paste(tile.crop((0, 0, 268, min(22, 76 + EXTRA - y))), (0, y)); y += 22
out.paste(im.crop((0, 76, 268, 90)), (0, 76 + EXTRA))
out.save(os.path.join(dst, "playlist_win.png"))
print("playlist_win", out.size)
