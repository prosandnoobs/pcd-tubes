"""
Puzzle World - Modul Puzzle Solver (Versi Tanpa Library)
Tugas Besar Pengolahan Citra Digital

Input  : 1 citra Bingkai + N citra Potongan (hasil Puzzle Generator).
Output : citra utuh yang telah tersusun.

Pengolahan citra diimplementasikan manual dengan Python murni (tanpa NumPy);
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

from PIL import Image  # hanya untuk baca/simpan file gambar

from generator import compute_bounds, rotate, to_png_bytes

INF = float("inf")
ROTATIONS = (0, 90, 180, 270)


# ──────────────────────────────────────────────────────────────────────────────
# BACA INPUT
# ──────────────────────────────────────────────────────────────────────────────

def decode_png(data):
    """Decode file gambar menjadi list baris piksel (v, a) atau (r, g, b, a)."""
    pil = Image.open(io.BytesIO(data))
    gray = pil.mode in ("L", "LA", "1", "I", "I;16", "F")
    pil = pil.convert("LA" if gray else "RGBA")
    w, h = pil.size
    flat = list(pil.getdata())
    return [flat[r * w:(r + 1) * w] for r in range(h)]


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
            opaque = all(p[-1] == 255 for row in px for p in row)
            return (opaque, len(px) * len(px[0]))
        frame = max(pieces, key=score)
        pieces.remove(frame)

    pieces.sort(key=lambda it: it[0])
    return {"frame": frame, "pieces": pieces, "answer": answer}


# ──────────────────────────────────────────────────────────────────────────────
# 1. DETEKSI GRID DARI BINGKAI
# ──────────────────────────────────────────────────────────────────────────────

def count_runs(flags):
    """Hitung jumlah kelompok True yang berurutan."""
    runs, prev = 0, False
    for f in flags:
        if f and not prev:
            runs += 1
        prev = f
    return runs


def detect_grid(frame_px):
    """
    Cari M dari citra bingkai dengan profil proyeksi: kolom/baris yang hampir
    seluruhnya terang dianggap garis grid. Jumlah garis = M + 1.
    """
    H, W = len(frame_px), len(frame_px[0])

    def lum(p):
        return p[0] if len(p) == 2 else (p[0] + p[1] + p[2]) / 3

    rows = range(0, H, max(1, H // 200))
    cols = range(0, W, max(1, W // 200))
    col_line = [sum(lum(frame_px[y][x]) > 100 for y in rows) >= 0.9 * len(rows) for x in range(W)]
    row_line = [sum(lum(frame_px[y][x]) > 100 for x in cols) >= 0.9 * len(cols) for y in range(H)]
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
    H, W = len(px), len(px[0])
    pads = []
    for (y0, x0, dy, dx) in ((0, 0, 1, 1), (0, W - 1, 1, -1), (H - 1, 0, -1, 1), (H - 1, W - 1, -1, -1)):
        k = 0
        while k < min(H, W) // 2 and px[y0 + dy * k][x0 + dx * k][-1] == 0:
            k += 1
        pads.append(k)
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
    core = [row[pad:len(row) - pad] for row in px[pad:len(px) - pad]]
    if side == "top":
        return core[0], core[1]
    if side == "bottom":
        return core[-1], core[-2]
    if side == "left":
        return [r[0] for r in core], [r[1] for r in core]
    return [r[-1] for r in core], [r[-2] for r in core]


def sample_edge(line1, line2, S):
    """
    Ambil S sampel merata sepanjang tepi (nilai intensitas asli 0..255).
    Returns list S elemen: tuple (nilai_tepi..., nilai_dalam...) atau None jika transparan.
    """
    n = len(line1)
    C = len(line1[0]) - 1
    out = []
    for i in range(S):
        j = min(n - 1, int((i + 0.5) * n / S))
        a, b = line1[j], line2[j]
        if a[-1] and b[-1]:
            out.append(tuple(a[:C]) + tuple(b[:C]))
        else:
            out.append(None)
    return out


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
    diffs, grad, cnt, C = [], 0.0, 0, 1
    for a, b in zip(ea, eb):
        if a is None or b is None:
            continue
        C = len(a) // 2
        diffs.append([a[c] - b[c] for c in range(C)])
        for c in range(C):
            grad += abs((a[c] - a[C + c]) - (b[C + c] - b[c]))
        cnt += 1
    if cnt < max(2, len(ea) // 4):
        return INF
    offset = [sum(d[c] for d in diffs) / cnt for c in range(C)]
    resid = sum(abs(d[c] - offset[c]) for d in diffs for c in range(C))
    return (resid + 0.5 * grad) / cnt + 0.05 * sum(abs(o) for o in offset)


def compatible(type_a, type_b):
    """Sisi jigsaw yang bersentuhan harus tab-blank atau blank-tab."""
    return (type_a, type_b) in (("tab", "blank"), ("blank", "tab"))


def build_cost_tables(oriented, use_types):
    K = len(oriented)
    LR = [[INF] * K for _ in range(K)]  # LR[a][b]: a di kiri b
    TB = [[INF] * K for _ in range(K)]  # TB[a][b]: a di atas b
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
    K = len(T)

    def second(values):
        v = sorted(x for x in values if x < INF)
        return v[1] if len(v) > 1 else (v[0] if v else 1.0)

    row2 = [second(T[i]) for i in range(K)]
    col2 = [second(T[i][j] for i in range(K)) for j in range(K)]
    return [[T[i][j] / (min(row2[i], col2[j]) + 1e-6) if T[i][j] < INF else INF
             for j in range(K)] for i in range(K)]


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
    K = len(oriented)
    conf = []
    for k in range(K):
        best = min(min(LR[k]), min(TB[k]),
                   min(LR[j][k] for j in range(K)), min(TB[j][k] for j in range(K)))
        conf.append((best, k))
    conf.sort()
    seeds, seen = [], set()
    for _, k in conf:
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

def render(grid, oriented, H, W, M):
    """Tempel tiap potongan (beserta pasaknya) ke kanvas; pasak mengisi cekungan tetangganya."""
    ys, xs = compute_bounds(H, M), compute_bounds(W, M)
    bg = (0,) * (len(oriented[0]["px"][0][0]) - 1)
    canvas = [[bg] * W for _ in range(H)]
    for r in range(M):
        for c in range(M):
            o = oriented[grid[r][c]]
            px, pad = o["px"], o["pad"]
            oy, ox = ys[r] - pad, xs[c] - pad
            for dy, row in enumerate(px):
                y = oy + dy
                if 0 <= y < H:
                    out = canvas[y]
                    for dx, p in enumerate(row):
                        x = ox + dx
                        if p[-1] and 0 <= x < W:
                            out[x] = p[:-1]
    return canvas


def png_mode(px):
    return "L" if len(px[0][0]) == 1 else "RGB"


def rotate_result(png_bytes, angle):
    """Putar citra hasil (berlawanan arah jarum jam) dengan rotasi manual."""
    px = rotate([[p[:-1] for p in row] for row in decode_png(png_bytes)], angle)
    return to_png_bytes(px, len(px[0]), len(px), png_mode(px))


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
        expected = [[None] * M for _ in range(M)]
        for name, t in truth.items():
            expected[t["row"]][t["col"]] = (name, (360 - t["angle"] + g) % 360)
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
    H, W = len(frame_px), len(frame_px[0])
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
        "image": to_png_bytes(canvas, W, H, png_mode(canvas)),
        "M": M,
        "layout": layout,
        "cost": best_cost,
        "jigsaw": use_types,
        "size": (W, H),
    }
