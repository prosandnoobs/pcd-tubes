"""
Puzzle World - Modul Puzzle Generator (Versi NumPy)
Tugas Besar Pengolahan Citra Digital

Seluruh pengolahan citra ditulis dengan operasi array NumPy.
PIL hanya dipakai untuk membaca (decode) dan menyimpan (encode) file gambar.

Representasi citra: dict {"w", "h", "gray", "px"}
  px = array uint8 berukuran H x W x C (C = 1 untuk grayscale, 3 untuk RGB).
"""

import io
import json
import random
import zipfile

import numpy as np
from PIL import Image  # hanya untuk baca/simpan file gambar

MAX_SIDE = 600  # sisi terpanjang setelah diperkecil


def to_uint8(a):
    """Batasi intensitas ke rentang 0..255 lalu bulatkan."""
    return np.clip(a + 0.5, 0, 255).astype(np.uint8)


# ──────────────────────────────────────────────────────────────────────────────
# BACA & SIMPAN CITRA
# ──────────────────────────────────────────────────────────────────────────────

def load_image(file_bytes, max_side=MAX_SIDE):
    """
    Baca gambar lalu perkecil (rasio tetap) dengan rata-rata 3x3 titik sampel per blok.
    Returns (image, lebar_asli, tinggi_asli).
    """
    pil = Image.open(io.BytesIO(file_bytes))
    high_depth = pil.mode in ("I", "I;16", "I;16B", "I;16L", "F")  # citra 16-bit / float
    gray = high_depth or pil.mode in ("L", "1", "LA")
    if not high_depth:
        pil = pil.convert("L" if gray else "RGB")
    w, h = pil.size
    data = np.asarray(pil, dtype=float)
    if gray:
        data = data[:, :, np.newaxis]

    scale = min(1.0, max_side / max(w, h))
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))

    def samples(n_new, n_old):
        """Indeks 3 titik sampel di dalam tiap blok: array n_new x 3."""
        return ((np.arange(n_new)[:, None] + [1 / 6, 1 / 2, 5 / 6]) * n_old / n_new).astype(int)

    # hasil pengindeksan: nh x nw x 3 x 3 x C, dirata-ratakan pada 3 x 3 titik sampel
    px = data[samples(nh, h)[:, None, :, None], samples(nw, w)[None, :, None, :]].mean(axis=(2, 3))

    # Normalisasi min-max: citra 16-bit / float dipetakan ke 0..255
    if high_depth:
        lo, hi = px.min(), px.max()
        px = (px - lo) * (255 / (hi - lo)) if hi > lo else np.zeros_like(px)
    return {"w": nw, "h": nh, "gray": gray, "px": to_uint8(px)}, w, h


def to_png_bytes(px):
    """Simpan array H x W x C ke PNG (C = 1: L, 2: LA, 3: RGB, 4: RGBA)."""
    pil = Image.fromarray(px[:, :, 0] if px.shape[2] == 1 else px)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# OPERASI CITRA
# ──────────────────────────────────────────────────────────────────────────────

def compute_bounds(length, M):
    """Batas potongan di satu sumbu; sisa piksel dibagi rata agar seluruh citra tercakup."""
    return [round(i * length / M) for i in range(M + 1)]


def crop_with_edge_pad(img, y0, y1, x0, x1, pad):
    """Potong area [y0-pad, y1+pad) x [x0-pad, x1+pad); piksel di luar citra = piksel tepi terdekat."""
    ys = np.clip(np.arange(y0 - pad, y1 + pad), 0, img["h"] - 1)
    xs = np.clip(np.arange(x0 - pad, x1 + pad), 0, img["w"] - 1)
    return img["px"][np.ix_(ys, xs)]


def create_jigsaw_mask(ph, pw, row, col, M, tab_h, tab_v, radius):
    """
    Mask jigsaw (True = bagian potongan): persegi inti ditambah/dikurangi lingkaran
    di tengah tiap sisi, memakai rumus jarak (x-cx)^2 + (y-cy)^2 <= r^2.
      tab_h[i][j] = +1 : sisi bawah potongan (i, j) menonjol (tab), -1 : cekung (blank)
      tab_v[i][j] = +1 : sisi kanan potongan (i, j) menonjol (tab), -1 : cekung (blank)
    """
    pad = radius + 2
    H, W = ph + 2 * pad, pw + 2 * pad
    mask = np.zeros((H, W), dtype=bool)
    mask[pad:pad + ph, pad:pad + pw] = True
    yy, xx = np.ogrid[:H, :W]

    def circle(cy, cx, value):
        mask[(yy - cy) ** 2 + (xx - cx) ** 2 <= radius * radius] = value

    # Sisi atas/kiri berpasangan dengan sisi bawah/kanan tetangganya (tandanya berlawanan)
    if row > 0:
        circle(pad, pad + pw // 2, tab_h[row - 1][col] == -1)
    if row < M - 1:
        circle(pad + ph, pad + pw // 2, tab_h[row][col] == 1)
    if col > 0:
        circle(pad + ph // 2, pad, tab_v[row][col - 1] == -1)
    if col < M - 1:
        circle(pad + ph // 2, pad + pw, tab_v[row][col] == 1)
    return mask


def augment_piece(patch):
    """
    Augmentasi brightness (b) dan contrast (c) acak:  p' = mean + c * (p * b - mean)
    mean = rata-rata luminans potongan setelah brightness.
    """
    b, c = random.uniform(0.8, 1.2), random.uniform(0.8, 1.2)
    weights = [1] if patch.shape[2] == 1 else [0.299, 0.587, 0.114]
    mean = (patch @ np.array(weights)).mean() * b
    return to_uint8(mean + c * (patch * b - mean))


def rotate(px, angle):
    """Rotasi berlawanan arah jarum jam sebesar 0/90/180/270 derajat."""
    return np.rot90(px, angle // 90)


# Font bitmap 3x5 untuk angka 0-9 (1 = piksel menyala)
DIGITS = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
}


def draw_number(px, number, offset):
    """Tulis nomor potongan dengan font bitmap: bayangan hitam lalu teks putih."""
    s = max(2, min(px.shape[:2]) // 25)  # ukuran satu titik font
    for value, shift in ((0, max(1, s // 2)), (255, 0)):
        x0 = y0 = offset + 4 + shift
        for ch in str(number):
            for gy, line in enumerate(DIGITS[ch]):
                for gx, bit in enumerate(line):
                    if bit == "1":
                        cell = px[y0 + gy * s:y0 + (gy + 1) * s, x0 + gx * s:x0 + (gx + 1) * s]
                        cell[:, :, :-1] = value  # kanal warna
                        cell[:, :, -1] = 255     # kanal alpha
            x0 += 4 * s
    return px


# ──────────────────────────────────────────────────────────────────────────────
# FUNGSI UTAMA
# ──────────────────────────────────────────────────────────────────────────────

def make_frame(image, ys, xs, thickness):
    """Bingkai kosong seukuran citra: latar gelap + garis grid terang."""
    H, W = image["h"], image["w"]
    t = thickness
    frame = np.full(image["px"].shape, 18, dtype=np.uint8)
    for b in ys:
        y = min(max(b, t), H - t)
        frame[y - t:y + t] = 200
    for b in xs:
        x = min(max(b, t), W - t)
        frame[:, x - t:x + t] = 200
    return frame


def generate_puzzle(image, M, do_jigsaw, do_rotation, do_augmentation, do_numbering,
                    jigsaw_radius_ratio):
    """
    Pecah citra menjadi M x M potongan.
    Returns dict {frame (PNG), pieces [dict], tab_map_h, tab_map_v, zip (bytes)}.
    """
    H, W = image["h"], image["w"]
    ys, xs = compute_bounds(H, M), compute_bounds(W, M)
    min_step = min(H // M, W // M)

    # 1. Bingkai (ukuran sama dengan citra masukan)
    frame_bytes = to_png_bytes(make_frame(image, ys, xs, max(1, min_step // 60)))

    # 2. Peta tab/blank jigsaw untuk setiap batas antar potongan
    tab_h = [[random.choice([-1, 1]) for _ in range(M)] for _ in range(M - 1)]
    tab_v = [[random.choice([-1, 1]) for _ in range(M - 1)] for _ in range(M)]
    radius = max(2, int(min_step * jigsaw_radius_ratio))
    pad = radius + 2 if do_jigsaw else 0  # margin tempat pasak menonjol

    # 3. Potong citra
    pieces = []
    for row in range(M):
        for col in range(M):
            ph, pw = ys[row + 1] - ys[row], xs[col + 1] - xs[col]
            patch = crop_with_edge_pad(image, ys[row], ys[row + 1], xs[col], xs[col + 1], pad)
            if do_augmentation:
                patch = augment_piece(patch)
            if do_jigsaw:
                mask = create_jigsaw_mask(ph, pw, row, col, M, tab_h, tab_v, radius)
            else:
                mask = np.ones((ph, pw), dtype=bool)
            # tambahkan kanal alpha: 255 = bagian potongan, 0 = transparan
            piece = np.dstack([patch, mask * np.uint8(255)])
            if do_numbering:
                piece = draw_number(piece, row * M + col + 1, pad)
            angle = random.choice([0, 90, 180, 270]) if do_rotation else 0
            pieces.append({"data": to_png_bytes(rotate(piece, angle)),
                           "angle": angle, "row": row, "col": col})

    # 4. Acak urutan; nama file tidak membocorkan posisi/rotasi (kunci ada di answer.json)
    random.shuffle(pieces)
    answer = {}
    for i, p in enumerate(pieces, start=1):
        p["name"] = f"Piece_{i:03d}.png"
        answer[p["name"]] = {"row": p["row"], "col": p["col"], "angle": p["angle"]}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Bingkai.png", frame_bytes)
        for p in pieces:
            zf.writestr(f"Pieces/{p['name']}", p["data"])
        zf.writestr("answer.json", json.dumps({"M": M, "pieces": answer}, indent=2))

    return {"frame": frame_bytes, "pieces": pieces, "tab_map_h": tab_h, "tab_map_v": tab_v,
            "zip": buf.getvalue()}
