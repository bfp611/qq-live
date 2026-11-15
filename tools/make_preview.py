# 开发用：录制 猪猪侠 QQ秀的动画预览 GIF：python tools/make_preview.py URL out.gif
# 流程：正常演示 ~14 秒（语音+动作）→ 强制犯困/睡着 → 被吵醒
import sys, time, os, subprocess, tempfile
from playwright.sync_api import sync_playwright
url, out = sys.argv[1], sys.argv[2]
d = tempfile.mkdtemp(); frames = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(viewport={"width": 760, "height": 720})
    pg.goto(url)
    clip = {"x": 0, "y": 55, "width": 760, "height": 640}
    def rec(sec):
        t_end = time.time() + sec
        while time.time() < t_end:
            t = time.time(); f = f"{d}/{len(frames):04d}.png"
            pg.screenshot(path=f, clip=clip); frames.append((f, time.time()))
            time.sleep(max(0, 0.09 - (time.time() - t)))
    pg.wait_for_timeout(2500)
    rec(16)
    pg.evaluate("QQPig.fallAsleep()"); rec(3)
    pg.evaluate("QQPig.setPose(6)"); rec(2.5)
    pg.evaluate("QQPig.setPose(17)"); rec(2)
    pg.evaluate("QQPig.markActivity()"); rec(3)
    b.close()
n = len(frames); fps = (n - 1) / (frames[-1][1] - frames[0][1])
print("frames", n, "fps", round(fps, 1))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{fps:.2f}", "-i", f"{d}/%04d.png",
    "-vf", "scale=500:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4", "-loop", "0", out], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", f"{fps:.2f}", "-i", f"{d}/%04d.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "scale=760:-2", out.replace(".gif", ".mp4")], check=True)
print(os.path.getsize(out) // 1024, "KB")
