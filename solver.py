"""
Puzzle World - Modul Puzzle Solver (Versi NumPy)
Tugas Besar Pengolahan Citra Digital

Input  : 1 citra Bingkai + N citra Potongan (hasil Puzzle Generator).
Output : citra utuh yang telah tersusun.

Pengolahan citra diimplementasikan dengan operasi array NumPy;
PIL hanya dipakai untuk membaca (decode) dan menyimpan (encode) file gambar.

Tahapan:
  1. Deteksi grid M x M dari garis pada citra Bingkai (profil proyeksi).
  2. Ekstraksi inti tiap potongan: tebal margin pasak (pad) dideteksi dari kanal alpha.
  3. Untuk setiap kemungkinan rotasi (0/90/180/270): ambil piksel tepi dan tentukan
     jenis tiap sisi jigsaw (datar / tab / blank).
  4. Hitung ketidakcocokan (dissimilarity) antar sisi potongan dengan selisih piksel
     tepi + prediksi gradien.
  5. Normalisasi ketidakcocokan menjadi rasio terhadap pesaing terdekat, lalu
     penyusunan greedy yang tumbuh dari potongan paling meyakinkan ke slot mana pun
     (dibatasi M x M dan aturan sisi datar jigsaw). Beberapa potongan awal dicoba dan
     dipilih susunan dengan total ketidakcocokan terkecil.
  6. Rekonstruksi: tempel tiap potongan (beserta pasaknya) ke kanvas berukuran bingkai.
"""

import io
import json
import zipfile

import numpy as np
import streamlit as st
from PIL import Image  # hanya untuk baca/simpan file gambar

from generator import compute_bounds, rotate, to_png_bytes

INF = float("inf")
ROTATIONS = (0, 90, 180, 270)


# ──────────────────────────────────────────────────────────────────────────────
# BACA INPUT
# ──────────────────────────────────────────────────────────────────────────────

def decode_png(data):
    """Decode file gambar menjadi array H x W x C (kanal terakhir = alpha)."""
    pil = Image.open(io.BytesIO(data))
    gray = pil.mode in ("L", "LA", "1", "I", "I;16", "F")
    return np.array(pil.convert("LA" if gray else "RGBA"))


def base_name(path):
    return path.rsplit("/", 1)[-1]


def read_solver_input(files):
    """
    files: list of (nama_file, bytes). Bisa berisi file ZIP hasil generator
    atau file-file PNG terpisah (1 bingkai + N potongan), opsional answer.json.
    Returns dict {frame: (name, bytes), pieces: [(name, bytes)], answer: dict|None}.
    """
    entries = []
    for name, data in files:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for info in zf.infolist():
                    if not info.is_dir():
                        entries.append((info.filename, zf.read(info)))
        else:
            entries.append((name, data))

    answer, frame, pieces = None, None, []
    for name, data in entries:
        low = name.lower()
        if low.endswith(".json"):
            try:
                answer = json.loads(data.decode("utf-8"))
            except Exception:
                pass
        elif low.endswith((".png", ".bmp", ".tif", ".tiff", ".jpg", ".jpeg")):
            if frame is None and base_name(low).startswith(("bingkai", "frame")):
                frame = (name, data)
            else:
                pieces.append((name, data))

    if frame is None and pieces:
        # Tanpa nama "Bingkai": pilih citra terbesar yang tidak punya piksel transparan
        def score(item):
            px = decode_png(item[1])
            return ((px[:, :, -1] == 255).all(), px.shape[0] * px.shape[1])
        frame = max(pieces, key=score)
        pieces.remove(frame)

    pieces.sort(key=lambda it: it[0])
    return {"frame": frame, "pieces": pieces, "answer": answer}


# ──────────────────────────────────────────────────────────────────────────────
# 1. DETEKSI GRID DARI BINGKAI
# ──────────────────────────────────────────────────────────────────────────────

def count_runs(flags):
    """Hitung jumlah kelompok True yang berurutan."""
    return int(flags[0]) + int((np.diff(flags.astype(int)) == 1).sum())


def detect_grid(frame_px):
    """
    Cari M dari citra bingkai dengan profil proyeksi: kolom/baris yang hampir
    seluruhnya terang dianggap garis grid. Jumlah garis = M + 1.
    """
    bright = frame_px[:, :, :-1].mean(axis=2) > 100
    col_line = bright.mean(axis=0) >= 0.9
    row_line = bright.mean(axis=1) >= 0.9
    m_w, m_h = count_runs(col_line) - 1, count_runs(row_line) - 1
    return m_w if m_w == m_h and m_w >= 1 else None


# ──────────────────────────────────────────────────────────────────────────────
# 2-3. EKSTRAKSI POTONGAN & FITUR TEPI
# ──────────────────────────────────────────────────────────────────────────────

def detect_pad(px):
    """
    Tebal margin pasak = jarak dari sudut ke piksel ber-alpha pertama di diagonal.
    Sudut inti potongan selalu terisi, sedangkan sudut margin selalu transparan.
    """
    alpha = px[:, :, -1]
    limit = min(alpha.shape) // 2
    pads = []
    for corner in (alpha, alpha[::-1], alpha[:, ::-1], alpha[::-1, ::-1]):
        filled = np.flatnonzero(np.diagonal(corner)[:limit])
        pads.append(int(filled[0]) if len(filled) else limit)
    return min(pads)


def side_type(px, pad, side):
    """Jenis sisi jigsaw: 'flat' (datar), 'tab' (menonjol) atau 'blank' (cekung)."""
    if pad == 0:
        return "flat"
    H, W = len(px), len(px[0])
    mr, mc = H // 2, W // 2
    outside, inside = {
        "top": ((pad // 2, mc), (pad + 1, mc)),
        "bottom": ((H - 1 - pad // 2, mc), (H - 2 - pad, mc)),
        "left": ((mr, pad // 2), (mr, pad + 1)),
        "right": ((mr, W - 1 - pad // 2), (mr, W - 2 - pad)),
    }[side]
    if px[outside[0]][outside[1]][-1]:
        return "tab"
    if not px[inside[0]][inside[1]][-1]:
        return "blank"
    return "flat"


def edge_lines(px, pad, side):
    """Dua garis piksel terluar inti pada satu sisi (garis tepi & garis di sebelahnya)."""
    core = px[pad:len(px) - pad, pad:px.shape[1] - pad]
    if side == "top":
        return core[0], core[1]
    if side == "bottom":
        return core[-1], core[-2]
    if side == "left":
        return core[:, 0], core[:, 1]
    return core[:, -1], core[:, -2]


def sample_edge(line1, line2, S):
    """
    Ambil S sampel merata sepanjang tepi (nilai intensitas asli 0..255).
    Returns (tepi, dalam, valid): tepi & dalam berukuran S x C, valid = sampel tidak transparan.
    """
    n = len(line1)
    idx = np.minimum(n - 1, ((np.arange(S) + 0.5) * n / S).astype(int))
    a, b = line1[idx].astype(float), line2[idx].astype(float)
    return a[:, :-1], b[:, :-1], (a[:, -1] > 0) & (b[:, -1] > 0)


def prepare_pieces(pieces_px, ph, pw, allow_rotation, S):
    """
    Buat semua orientasi yang mungkin untuk tiap potongan.
    Orientasi valid jika ukuran intinya cocok dengan ukuran sel grid (toleransi 1 piksel).
    """
    oriented = []
    for pid, px in enumerate(pieces_px):
        pad = detect_pad(px)
        candidates = []
        for rot in (ROTATIONS if allow_rotation else (0,)):
            rpx = rotate(px, rot)
            ch, cw = len(rpx) - 2 * pad, len(rpx[0]) - 2 * pad
            candidates.append((rot, rpx, abs(ch - ph) <= 1.01 and abs(cw - pw) <= 1.01))
        if not any(ok for _, _, ok in candidates):
            candidates = [(r, p, True) for r, p, _ in candidates]
        for rot, rpx, ok in candidates:
            if not ok:
                continue
            oriented.append({
                "pid": pid, "rot": rot, "px": rpx, "pad": pad,
                "type": {s: side_type(rpx, pad, s) for s in ("top", "right", "bottom", "left")},
                "edge": {s: sample_edge(*edge_lines(rpx, pad, s), S)
                         for s in ("top", "right", "bottom", "left")},
            })
    return oriented


# ──────────────────────────────────────────────────────────────────────────────
# 4. KETIDAKCOCOKAN ANTAR SISI
# ──────────────────────────────────────────────────────────────────────────────

def edge_cost(ea, eb):
    """
    Ketidakcocokan sisi A dan sisi B yang bersentuhan (sampel sejajar), dirancang
    tahan terhadap augmentasi brightness (pergeseran intensitas per potongan):
      d_i       = A_tepi_i - B_tepi_i,  offset = rata-rata d_i per kanal
      residu    = sum |d_i - offset|            (pola tepi harus sama)
      gradien   = sum |(A_tepi - A_dalam) - (B_dalam - B_tepi)|   (kontinuitas gradien)
      biaya     = (residu + 0.5 * gradien) / n + 0.05 * sum |offset|
    """
    a_edge, a_in, a_ok = ea
    b_edge, b_in, b_ok = eb
    ok = a_ok & b_ok
    cnt = ok.sum()
    if cnt < max(2, len(ok) // 4):
        return INF
    d = a_edge[ok] - b_edge[ok]
    offset = d.mean(axis=0)
    resid = np.abs(d - offset).sum()
    grad = np.abs((a_edge[ok] - a_in[ok]) - (b_in[ok] - b_edge[ok])).sum()
    return (resid + 0.5 * grad) / cnt + 0.05 * np.abs(offset).sum()


def compatible(type_a, type_b):
    """Sisi jigsaw yang bersentuhan harus tab-blank atau blank-tab."""
    return (type_a, type_b) in (("tab", "blank"), ("blank", "tab"))


def build_cost_tables(oriented, use_types):
    K = len(oriented)
    LR = np.full((K, K), INF)  # LR[a][b]: a di kiri b
    TB = np.full((K, K), INF)  # TB[a][b]: a di atas b
    for i, a in enumerate(oriented):
        for j, b in enumerate(oriented):
            if a["pid"] == b["pid"]:
                continue
            if not use_types or compatible(a["type"]["right"], b["type"]["left"]):
                LR[i][j] = edge_cost(a["edge"]["right"], b["edge"]["left"])
            if not use_types or compatible(a["type"]["bottom"], b["type"]["top"]):
                TB[i][j] = edge_cost(a["edge"]["bottom"], b["edge"]["top"])
    return LR, TB


def normalize_costs(T):
    """
    Ubah ketidakcocokan menjadi rasio terhadap pesaing terdekat (second-best),
    seperti pada Gallagher (2012). Nilai < 1 berarti pasangan itu jauh lebih cocok
    dibanding alternatif lainnya, sehingga lebih bisa dipercaya.
    """
    def second(values):
        v = np.sort(values[values < INF])
        return v[1] if len(v) > 1 else (v[0] if len(v) else 1.0)

    row2 = np.array([second(row) for row in T])
    col2 = np.array([second(col) for col in T.T])
    return T / (np.minimum(row2[:, None], col2[None, :]) + 1e-6)


# ──────────────────────────────────────────────────────────────────────────────
# 5. PENYUSUNAN (GREEDY TUMBUH)
# ──────────────────────────────────────────────────────────────────────────────

SIDES = (("top", -1, 0), ("bottom", 1, 0), ("left", 0, -1), ("right", 0, 1))


def flat_ok(o, r, c, pos, bounds):
    """
    Aturan jigsaw: sisi datar hanya boleh berada di tepi luar puzzle.
    Sisi datar di atas => tidak boleh ada potongan di baris atasnya, dan baris r
    menjadi batas atas; sisi tidak datar tidak boleh berada di batas yang sudah tetap.
    """
    for side, dr, dc in SIDES:
        flat = o["type"][side] == "flat"
        line = r if dr else c
        fixed = bounds[side]
        if flat:
            if fixed is not None and fixed != line:
                return False
            beyond = [(pr, pc) for (pr, pc) in pos
                      if (dr and (pr - r) * dr > 0) or (dc and (pc - c) * dc > 0)]
            if beyond:
                return False
        elif fixed is not None and fixed == line:
            return False
    return True


def grow_place(seed, oriented, LR, TB, M, use_types):
    """
    Penyusunan greedy yang tumbuh dari satu potongan awal: pada tiap langkah dipilih
    pasangan (slot kosong, potongan) dengan ketidakcocokan rata-rata terkecil terhadap
    tetangga yang sudah terpasang, selama ukuran susunan tidak melebihi M x M.
    """
    pos = {(0, 0): seed}
    used = {oriented[seed]["pid"]}
    bounds = {"top": None, "bottom": None, "left": None, "right": None}

    def fix_bounds(o, r, c):
        for side, dr, dc in SIDES:
            if o["type"][side] == "flat" and use_types:
                bounds[side] = r if dr else c

    fix_bounds(oriented[seed], 0, 0)
    while len(pos) < M * M:
        rows = [r for r, _ in pos]
        cols = [c for _, c in pos]
        rmin, rmax, cmin, cmax = min(rows), max(rows), min(cols), max(cols)
        slots = set()
        for (r, c) in pos:
            for _, dr, dc in SIDES:
                s = (r + dr, c + dc)
                if s in pos:
                    continue
                if max(rmax, s[0]) - min(rmin, s[0]) >= M or max(cmax, s[1]) - min(cmin, s[1]) >= M:
                    continue
                slots.add(s)

        best = None
        for relax in (False, True):
            for (r, c) in slots:
                nbrs = []
                if (r, c - 1) in pos:
                    nbrs.append((LR, pos[(r, c - 1)], True))
                if (r, c + 1) in pos:
                    nbrs.append((LR, pos[(r, c + 1)], False))
                if (r - 1, c) in pos:
                    nbrs.append((TB, pos[(r - 1, c)], True))
                if (r + 1, c) in pos:
                    nbrs.append((TB, pos[(r + 1, c)], False))
                bonus = 0.85 ** (len(nbrs) - 1)  # slot dengan lebih banyak tetangga lebih dipercaya
                for k, o in enumerate(oriented):
                    if o["pid"] in used:
                        continue
                    if use_types and not relax and not flat_ok(o, r, c, pos, bounds):
                        continue
                    s = 0.0
                    for T, n, n_first in nbrs:
                        v = T[n][k] if n_first else T[k][n]
                        s += min(v, 50.0) if relax else v
                    score = s / len(nbrs) * bonus
                    if best is None or score < best[0]:
                        best = (score, (r, c), k)
            if best is not None and best[0] < INF:
                break
        _, (r, c), k = best
        pos[(r, c)] = k
        used.add(oriented[k]["pid"])
        fix_bounds(oriented[k], r, c)

    rmin = min(r for r, _ in pos)
    cmin = min(c for _, c in pos)
    grid = [[None] * M for _ in range(M)]
    for (r, c), k in pos.items():
        grid[r - rmin][c - cmin] = k
    return grid


def grid_cost(grid, LR, TB, M):
    """Total ketidakcocokan seluruh pasangan bertetangga pada susunan akhir."""
    total = 0.0
    for r in range(M):
        for c in range(M):
            if c + 1 < M:
                total += min(LR[grid[r][c]][grid[r][c + 1]], 50.0)
            if r + 1 < M:
                total += min(TB[grid[r][c]][grid[r + 1][c]], 50.0)
    return total


def choose_seeds(oriented, LR, TB, n_seeds):
    """Potongan awal: yang memiliki pasangan paling meyakinkan (rasio terkecil)."""
    best = np.minimum.reduce([LR.min(axis=1), TB.min(axis=1), LR.min(axis=0), TB.min(axis=0)])
    seeds, seen = [], set()
    for k in np.argsort(best, kind="stable").tolist():
        pid = oriented[k]["pid"]
        if pid not in seen:
            seen.add(pid)
            seeds.append(k)
        if len(seeds) >= n_seeds:
            break
    return seeds


# ──────────────────────────────────────────────────────────────────────────────
# 6. REKONSTRUKSI & EVALUASI
# ──────────────────────────────────────────────────────────────────────────────

def paste(canvas, px, oy, ox):
    """Tempel piksel tidak transparan dari px ke kanvas mulai posisi (oy, ox)."""
    H, W = canvas.shape[:2]
    y0, y1 = max(oy, 0), min(oy + px.shape[0], H)
    x0, x1 = max(ox, 0), min(ox + px.shape[1], W)
    part = px[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    visible = part[:, :, -1] > 0
    canvas[y0:y1, x0:x1][visible] = part[visible][:, :-1]


def render(grid, oriented, H, W, M):
    """Tempel tiap potongan (beserta pasaknya) ke kanvas; pasak mengisi cekungan tetangganya."""
    ys, xs = compute_bounds(H, M), compute_bounds(W, M)
    canvas = np.zeros((H, W, oriented[0]["px"].shape[2] - 1), dtype=np.uint8)
    for r in range(M):
        for c in range(M):
            o = oriented[grid[r][c]]
            px, pad = o["px"], o["pad"]
            paste(canvas, px, ys[r] - pad, xs[c] - pad)
    return canvas


def rotate_result(png_bytes, angle):
    """Putar citra hasil (berlawanan arah jarum jam)."""
    return to_png_bytes(rotate(decode_png(png_bytes)[:, :, :-1], angle))


def neighbor_accuracy(layout, expected, M):
    """
    Persentase pasangan bertetangga (kanan & bawah) yang benar, termasuk rotasinya.
    Tidak menghukum susunan yang benar tetapi bergeser posisinya.
    """
    true_right, true_down = {}, {}
    for r in range(M):
        for c in range(M):
            if c + 1 < M:
                true_right[expected[r][c]] = expected[r][c + 1]
            if r + 1 < M:
                true_down[expected[r][c]] = expected[r + 1][c]
    ok = 0
    for r in range(M):
        for c in range(M):
            if c + 1 < M and true_right.get(layout[r][c]) == layout[r][c + 1]:
                ok += 1
            if r + 1 < M and true_down.get(layout[r][c]) == layout[r + 1][c]:
                ok += 1
    return ok / (2 * M * (M - 1))


def evaluate(layout, answer, M):
    """
    Bandingkan susunan dengan kunci jawaban (answer.json dari generator).
    Puzzle persegi tanpa acuan arah dapat tersusun benar namun terputar secara global,
    sehingga dicek untuk 4 rotasi global dan diambil yang terbaik.
    Returns dict {position, rotation, neighbor, global_rotation}.
    """
    truth = answer.get("pieces", {})
    best = None
    for g in ROTATIONS:
        # posisi & rotasi koreksi yang benar jika seluruh hasil terputar g derajat
        expected = np.empty((M, M), dtype=object)
        for name, t in truth.items():
            expected[t["row"], t["col"]] = (name, (360 - t["angle"] + g) % 360)
        expected = rotate(expected, g)
        pos_ok = rot_ok = 0
        for r in range(M):
            for c in range(M):
                name, rot = layout[r][c]
                if expected[r][c][0] == name:
                    pos_ok += 1
                    rot_ok += expected[r][c][1] == rot
        cand = {"position": pos_ok / (M * M), "rotation": rot_ok / (M * M), "global_rotation": g,
                "neighbor": neighbor_accuracy(layout, expected, M)}
        key = (cand["neighbor"], cand["position"], cand["rotation"])
        if best is None or key > (best["neighbor"], best["position"], best["rotation"]):
            best = cand
    return best


# ──────────────────────────────────────────────────────────────────────────────
# FUNGSI UTAMA
# ──────────────────────────────────────────────────────────────────────────────

def solve_puzzle(frame_bytes, pieces, allow_rotation=True, progress=None):
    """
    frame_bytes : PNG citra bingkai.
    pieces      : list of (nama_file, bytes) potongan.
    Returns dict {image (PNG bytes), M, layout [[(nama, rotasi)]], cost, jigsaw}.
    """
    def step(frac, text):
        if progress:
            progress(frac, text)

    step(0.05, "Mendeteksi grid dari bingkai...")
    frame_px = decode_png(frame_bytes)
    H, W = frame_px.shape[:2]
    N = len(pieces)
    M = detect_grid(frame_px)
    if M is None or M * M != N:
        root = round(N ** 0.5)
        if root * root != N:
            raise ValueError(f"Jumlah potongan ({N}) bukan bilangan kuadrat dan grid bingkai tidak terdeteksi.")
        M = root
    ph, pw = H / M, W / M

    step(0.15, "Membaca potongan & mengekstrak fitur tepi...")
    S = max(2, min(32, int(min(ph, pw)) - 1))  # jumlah sampel per sisi
    oriented = prepare_pieces([decode_png(data) for _, data in pieces], ph, pw, allow_rotation, S)
    use_types = any(o["pad"] > 0 for o in oriented)

    step(0.35, f"Menghitung ketidakcocokan antar sisi ({len(oriented)} orientasi)...")
    LR, TB = build_cost_tables(oriented, use_types)
    LR, TB = normalize_costs(LR), normalize_costs(TB)

    step(0.7, "Menyusun potongan...")
    best_grid, best_cost = None, INF
    seeds = choose_seeds(oriented, LR, TB, 8 if len(oriented) <= 150 else 4)
    for i, seed in enumerate(seeds):
        grid = grow_place(seed, oriented, LR, TB, M, use_types)
        cost = grid_cost(grid, LR, TB, M)
        if cost < best_cost:
            best_grid, best_cost = grid, cost
        step(0.7 + 0.2 * (i + 1) / len(seeds), f"Menyusun potongan (percobaan {i + 1}/{len(seeds)})...")

    step(0.9, "Merekonstruksi citra utuh...")
    canvas = render(best_grid, oriented, H, W, M)
    layout = [[(base_name(pieces[oriented[k]["pid"]][0]), oriented[k]["rot"]) for k in row]
              for row in best_grid]
    step(1.0, "Selesai")
    return {
        "image": to_png_bytes(canvas),
        "M": M,
        "layout": layout,
        "cost": best_cost,
        "jigsaw": use_types,
        "size": (W, H),
    }


# ──────────────────────────────────────────────────────────────────────────────
# SUSUN MANUAL: LOGIKA PERMAINAN
# ──────────────────────────────────────────────────────────────────────────────

def new_game(data):
    """
    Buat permainan dari hasil read_solver_input. Pemain menyusun sendiri: pilih potongan,
    putar bila perlu, lalu klik slot tujuan pada grid.
    Keadaan game: pieces (list dict {name, px, pad, rot}), grid (M x M berisi indeks
    potongan atau None), selected (indeks potongan terpilih atau None).
    """
    frame = decode_png(data["frame"][1])
    N = len(data["pieces"])
    M = detect_grid(frame)
    if M is None or M * M != N:
        M = round(N ** 0.5)
        if M * M != N:
            raise ValueError(f"Jumlah potongan ({N}) bukan bilangan kuadrat.")
    pieces = []
    for name, png in data["pieces"]:
        px = decode_png(png)
        pieces.append({"name": base_name(name), "px": px, "pad": detect_pad(px), "rot": 0})
    return {"M": M, "frame": frame[:, :, :-1], "pieces": pieces, "answer": data["answer"],
            "grid": [[None] * M for _ in range(M)], "selected": None}


def click_slot(game, r, c):
    """Pasang potongan terpilih ke slot; slot terisi ditukar kembali ke daftar potongan."""
    occupant = game["grid"][r][c]
    game["grid"][r][c] = game["selected"]
    game["selected"] = occupant


def tray(game):
    """Indeks potongan yang belum terpasang di grid."""
    placed = {k for row in game["grid"] for k in row}
    return [k for k in range(len(game["pieces"])) if k not in placed]


def render_board(game):
    """Tempel potongan yang sudah terpasang ke atas citra bingkai."""
    canvas = game["frame"].copy()
    H, W = canvas.shape[:2]
    ys, xs = compute_bounds(H, game["M"]), compute_bounds(W, game["M"])
    for r, row in enumerate(game["grid"]):
        for c, k in enumerate(row):
            if k is None:
                continue
            p = game["pieces"][k]
            paste(canvas, rotate(p["px"], p["rot"]), ys[r] - p["pad"], xs[c] - p["pad"])
    return canvas


def check_game(game):
    """Nilai susunan yang sudah lengkap dengan kunci jawaban."""
    layout = [[(game["pieces"][k]["name"], game["pieces"][k]["rot"]) for k in row]
              for row in game["grid"]]
    return evaluate(layout, game["answer"], game["M"])


# ──────────────────────────────────────────────────────────────────────────────
# SUSUN MANUAL: HALAMAN
# ──────────────────────────────────────────────────────────────────────────────

def manual_page(header, section, empty_state, sidebar_footer):
    """Komponen tampilan diterima dari app.py agar gayanya sama dengan halaman lain."""
    with st.sidebar:
        st.markdown("## Pengaturan Permainan")
        st.markdown("---")
        uploads = st.file_uploader("Upload ZIP hasil generator, atau Bingkai + Potongan",
                                   type=["zip", "png", "json"], accept_multiple_files=True,
                                   key="manual_uploads")
        sidebar_footer()

    header("Susun Manual")
    if not uploads:
        empty_state("Upload Bingkai &amp; Potongan",
                    "Upload file ZIP hasil Puzzle Generator untuk mulai menyusun sendiri.")
        return

    files = [(f.name, f.getvalue()) for f in uploads]
    files_key = tuple((n, len(b)) for n, b in files)
    if st.session_state.get("manual_key") != files_key:
        data = read_solver_input(files)
        if data["frame"] is None or not data["pieces"]:
            st.error("Input belum lengkap: dibutuhkan 1 citra bingkai dan minimal 1 potongan.")
            return
        try:
            st.session_state["manual_game"] = new_game(data)
        except ValueError as e:
            st.error(str(e))
            return
        st.session_state["manual_key"] = files_key
    game = st.session_state["manual_game"]
    M, pieces = game["M"], game["pieces"]

    col_board, col_ctrl = st.columns([3, 2])
    with col_board:
        section("Papan")
        st.image(to_png_bytes(render_board(game)), use_container_width=True)
    with col_ctrl:
        section("Slot Grid")
        st.caption("Klik slot untuk memasang potongan terpilih, atau klik slot terisi untuk mengambilnya.")
        for r in range(M):
            for c, col in enumerate(st.columns(M)):
                filled = game["grid"][r][c] is not None
                if col.button("■" if filled else "□", key=f"slot_{r}_{c}", use_container_width=True):
                    click_slot(game, r, c)
                    st.rerun()

        selected = game["selected"]
        if selected is not None:
            p = pieces[selected]
            st.image(to_png_bytes(rotate(p["px"], p["rot"])), width=120,
                     caption=f"Terpilih: {p['name']}")
            if st.button("Putar 90 deg", use_container_width=True):
                p["rot"] = (p["rot"] + 90) % 360
                st.rerun()

        if st.button("Periksa", use_container_width=True):
            if tray(game):
                st.warning("Pasang semua potongan terlebih dahulu.")
            elif not game["answer"]:
                st.info("Kunci jawaban (answer.json) tidak tersedia.")
            else:
                ev = check_game(game)
                if ev["position"] == 1 and ev["rotation"] == 1:
                    st.success("Selamat, puzzle tersusun dengan benar!")
                else:
                    st.warning(f"Posisi benar {ev['position'] * 100:.1f}%, "
                               f"rotasi benar {ev['rotation'] * 100:.1f}%.")

    waiting = [k for k in tray(game) if k != game["selected"]]
    section(f"Potongan Tersedia ({len(waiting)})")
    cols = st.columns(8)
    for i, k in enumerate(waiting):
        p = pieces[k]
        with cols[i % 8]:
            st.image(to_png_bytes(rotate(p["px"], p["rot"])), use_container_width=True)
            if st.button("Pilih", key=f"pick_{k}", use_container_width=True):
                game["selected"] = k
                st.rerun()
