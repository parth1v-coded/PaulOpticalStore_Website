import sys
from PIL import Image
import numpy as np
src, dst = sys.argv[1], sys.argv[2]
im0 = Image.open(src).convert("RGBA"); im = Image.new("RGB", im0.size, (255,255,255)); im.paste(im0, mask=im0.getchannel("A"))
a = np.asarray(im).astype(float)
navy = np.array([19, 41, 77.0])
# alpha = how far each pixel is from white, relative to navy-from-white; recolour everything navy
alpha = np.clip((255 - a.mean(axis=2)) / (255 - navy.mean()), 0, 1)
out = np.zeros(a.shape[:2] + (4,), np.uint8)
out[..., :3] = navy.astype(np.uint8)
out[..., 3] = (alpha * 255).astype(np.uint8)
img = Image.fromarray(out, "RGBA")
img = img.crop(img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
pad = 12
canvas = Image.new("RGBA", (img.width + 2*pad, img.height + 2*pad), (0, 0, 0, 0))
canvas.paste(img, (pad, pad))
canvas.save(dst, optimize=True)
print(canvas.size, "navy sample:", a[300, 480])

