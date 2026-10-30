"""
Puzzle World - Modul Puzzle Generator (Versi Tanpa Library)
Tugas Besar Pengolahan Citra Digital

Seluruh pengolahan citra ditulis manual dengan Python murni (tanpa NumPy).
PIL hanya dipakai untuk membaca (decode) dan menyimpan (encode) file gambar.

Representasi citra: dict {"w", "h", "gray", "px"}
  px = list baris, setiap piksel berupa tuple kanal:
       (v,) untuk grayscale atau (r, g, b) untuk RGB.
"""

import io
import json
import random
import zipfile

from PIL import Image  # hanya untuk baca/simpan file gambar

MAX_SIDE = 600  # sisi terpanjang setelah diperkecil (loop Python murni relatif lambat)


def clip(v):
    """Batasi intensitas ke rentang 0..255."""
    return 0 if v < 0 else 255 if v > 255 else int(v + 0.5)


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
    data = pil.getdata()

    scale = min(1.0, max_side / max(w, h))
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))

    def samples(i, n_new, n_old):
        """3 titik sampel di dalam blok ke-i (hasil perkecilan) pada satu sumbu."""
        lo, hi = i * n_old // n_new, max(i * n_old // n_new + 1, (i + 1) * n_old // n_new)
        k = min(3, hi - lo)
        return [lo + (2 * j + 1) * (hi - lo) // (2 * k) for j in range(k)]

    sx = [samples(c, nw, w) for c in range(nw)]
    px = []
    for r in range(nh):
        rows = [y * w for y in samples(r, nh, h)]
        row = []
        for xs in sx:
            vals = [data[base + x] for base in rows for x in xs]
            if gray:
                row.append((sum(vals) / len(vals),))
            else:
                row.append(tuple(sum(v[ch] for v in vals) / len(vals) for ch in range(3)))
        px.append(row)

    # Normalisasi min-max: citra 16-bit / float dipetakan ke 0..255
    lo, hi, k = 0, 255, 1
    if high_depth:
        lo = min(p[0] for row in px for p in row)
        hi = max(p[0] for row in px for p in row)
        k = 255 / (hi - lo) if hi > lo else 0
    px = [[tuple(clip((v - lo) * k) for v in p) for p in row] for row in px]
    return {"w": nw, "h": nh, "gray": gray, "px": px}, w, h


def to_png_bytes(px, w, h, mode):
    """Simpan list piksel 2D (tuple kanal) ke PNG. mode: L, LA, RGB atau RGBA."""
    flat = [p for row in px for p in row]
    if mode == "L":
        flat = [p[0] for p in flat]  # PIL meminta int untuk citra 1 kanal
    pil = Image.new(mode, (w, h))
    pil.putdata(flat)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# OPERASI CITRA MANUAL
# ──────────────────────────────────────────────────────────────────────────────

def compute_bounds(length, M):
    """Batas potongan di satu sumbu; sisa piksel dibagi rata agar seluruh citra tercakup."""
    return [round(i * length / M) for i in range(M + 1)]


def crop_with_edge_pad(img, y0, y1, x0, x1, pad):
    """Potong area [y0-pad, y1+pad) x [x0-pad, x1+pad); piksel di luar citra = piksel tepi terdekat."""
    src, H, W = img["px"], img["h"], img["w"]
    xs = [min(max(x, 0), W - 1) for x in range(x0 - pad, x1 + pad)]
    return [[src[min(max(y, 0), H - 1)][x] for x in xs] for y in range(y0 - pad, y1 + pad)]


def create_jigsaw_mask(ph, pw, row, col, M, tab_h, tab_v, radius):
    """
    Mask jigsaw (True = bagian potongan): persegi inti ditambah/dikurangi lingkaran
    di tengah tiap sisi, memakai rumus jarak (x-cx)^2 + (y-cy)^2 <= r^2.
      tab_h[i][j] = +1 : sisi bawah potongan (i, j) menonjol (tab), -1 : cekung (blank)
      tab_v[i][j] = +1 : sisi kanan potongan (i, j) menonjol (tab), -1 : cekung (blank)
    """
    pad = radius + 2
    H, W = ph + 2 * pad, pw + 2 * pad
    mask = [[pad <= y < pad + ph and pad <= x < pad + pw for x in range(W)] for y in range(H)]

    def circle(cy, cx, value):
        for y in range(max(0, cy - radius), min(H, cy + radius + 1)):
            for x in range(max(0, cx - radius), min(W, cx + radius + 1)):
                if (y - cy) ** 2 + (x - cx) ** 2 <= radius * radius:
                    mask[y][x] = value

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
    weights = (1,) if len(patch[0][0]) == 1 else (0.299, 0.587, 0.114)
    lum = [sum(w * v for w, v in zip(weights, p)) for row in patch for p in row]
    mean = sum(lum) / len(lum) * b
    return [[tuple(clip(mean + c * (v * b - mean)) for v in p) for p in row] for row in patch]


def rotate(px, angle):
    """
    Rotasi berlawanan arah jarum jam dengan pemetaan indeks (H x W -> W x H):
       90 : new[r][c] = old[c][W-1-r]
      180 : new[r][c] = old[H-1-r][W-1-c]
      270 : new[r][c] = old[H-1-c][r]
    """
    H, W = len(px), len(px[0])
    if angle == 90:
        return [[px[c][W - 1 - r] for c in range(H)] for r in range(W)]
    if angle == 180:
        return [row[::-1] for row in px[::-1]]
    if angle == 270:
        return [[px[H - 1 - c][r] for c in range(H)] for r in range(W)]
    return px


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
    H, W = len(px), len(px[0])
    s = max(2, min(H, W) // 25)  # ukuran satu titik font
    n_color = len(px[0][0]) - 1  # jumlah kanal warna (tanpa alpha)
    for value, shift in ((0, max(1, s // 2)), (255, 0)):
        color = (value,) * n_color + (255,)
        x0 = y0 = offset + 4 + shift
        for ch in str(number):
            for gy, line in enumerate(DIGITS[ch]):
                for gx, bit in enumerate(line):
                    if bit == "1":
                        for y in range(max(0, y0 + gy * s), min(H, y0 + (gy + 1) * s)):
                            for x in range(max(0, x0 + gx * s), min(W, x0 + (gx + 1) * s)):
                                px[y][x] = color
            x0 += 4 * s
    return px


# ──────────────────────────────────────────────────────────────────────────────
# FUNGSI UTAMA
# ──────────────────────────────────────────────────────────────────────────────

def make_frame(image, ys, xs, thickness):
    """Bingkai kosong seukuran citra: latar gelap + garis grid terang."""
    H, W = image["h"], image["w"]
    n = 1 if image["gray"] else 3
    bg, line = (18,) * n, (200,) * n
    t = thickness
    line_rows = {y for b in ys for y in range(min(max(b, t), H - t) - t, min(max(b, t), H - t) + t)}
    line_cols = {x for b in xs for x in range(min(max(b, t), W - t) - t, min(max(b, t), W - t) + t)}
    return [[line if (y in line_rows or x in line_cols) else bg for x in range(W)] for y in range(H)]


def generate_puzzle(image, M, do_jigsaw, do_rotation, do_augmentation, do_numbering,
                    jigsaw_radius_ratio):
    """
    Pecah citra menjadi M x M potongan.
    Returns dict {frame (PNG), pieces [dict], tab_map_h, tab_map_v, zip (bytes)}.
    """
    gray, H, W = image["gray"], image["h"], image["w"]
    mode = "L" if gray else "RGB"
    ys, xs = compute_bounds(H, M), compute_bounds(W, M)
    min_step = min(H // M, W // M)

    # 1. Bingkai (ukuran sama dengan citra masukan)
    frame = make_frame(image, ys, xs, max(1, min_step // 60))
    frame_bytes = to_png_bytes(frame, W, H, mode)

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
                mask = [[True] * pw for _ in range(ph)]
            # tambahkan kanal alpha: 255 = bagian potongan, 0 = transparan
            piece = [[p + (255 if m else 0,) for p, m in zip(prow, mrow)]
                     for prow, mrow in zip(patch, mask)]
            if do_numbering:
                piece = draw_number(piece, row * M + col + 1, pad)
            angle = random.choice([0, 90, 180, 270]) if do_rotation else 0
            piece = rotate(piece, angle)
            pieces.append({"data": to_png_bytes(piece, len(piece[0]), len(piece), mode + "A"),
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
