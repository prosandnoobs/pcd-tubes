"""
Puzzle World - Puzzle Generator (Streamlit) - Versi Tanpa Library
Tugas Besar Pengolahan Citra Digital
Pengolahan citra diimplementasikan manual (Python murni, tanpa NumPy);
PIL hanya dipakai untuk membaca dan menyimpan file gambar.
Features:
  - Jigsaw-shaped cuts (tab/blank connectors)
  - Random rotation (0/90/180/270 degrees)
  - Per-piece brightness/contrast augmentation
  - Numbered overlay on each piece
  - Frame generation
  - ZIP download
"""

import streamlit as st
from PIL import Image  # hanya untuk baca/simpan file gambar
import io, random, zipfile

# PAGE CONFIG
st.set_page_config(
    page_title="Puzzle World - Generator",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# CUSTOM CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: #111111;
    min-height: 100vh;
}

section[data-testid="stSidebar"] {
    background: #1a1a1a;
    border-right: 1px solid #2e2e2e;
}

/* Force all sidebar text to white */
section[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

/* Slider and toggle labels */
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] .stSlider label,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
    color: #ffffff !important;
}

/* Muted footer text in sidebar */
section[data-testid="stSidebar"] div[style*="color:#666666"] {
    color: #888888 !important;
}

/* Slider value display */
section[data-testid="stSidebar"] .stSlider [data-testid="stTickBarMin"],
section[data-testid="stSidebar"] .stSlider [data-testid="stTickBarMax"] {
    color: #aaaaaa !important;
}

/* File uploader — match slider track dark background */
section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
    background: #2e2e2e !important;
    border: 1px solid #3a3a3a !important;
    border-radius: 6px !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    background: #2e2e2e !important;
    border: 1px solid #3a3a3a !important;
    border-radius: 6px !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {
    color: #aaaaaa !important;
}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
    background: #3a3a3a !important;
    color: #ffffff !important;
    border: 1px solid #4a4a4a !important;
    border-radius: 4px !important;
}

.puzzle-card {
    background: #1e1e1e;
    border: 1px solid #2e2e2e;
    border-radius: 8px;
    padding: 1.2rem;
}

.hero-title {
    font-size: 2.6rem;
    font-weight: 800;
    color: #ffffff;
    text-align: center;
    margin-bottom: 0.2rem;
    line-height: 1.15;
}

.hero-sub {
    text-align: center;
    color: #888888;
    font-size: 0.95rem;
    margin-bottom: 2rem;
}

.badge {
    display: inline-block;
    background: #2e2e2e;
    color: #dddddd;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 4px;
    margin-right: 4px;
    border: 1px solid #3a3a3a;
}

.stat-box {
    background: #1e1e1e;
    border: 1px solid #2e2e2e;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    text-align: center;
}
.stat-num { font-size: clamp(0.95rem, 1.6vw, 1.6rem); font-weight: 700; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stat-label { font-size: 0.75rem; color: #777777; margin-top: 2px; }

div.stButton > button {
    background: #2e2e2e !important;
    color: #ffffff !important;
    border: 1px solid #444444 !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 0.55rem 1.5rem !important;
    width: 100%;
    transition: background 0.15s;
}
div.stButton > button:hover {
    background: #3a3a3a !important;
    border-color: #555555 !important;
}

div.stDownloadButton > button {
    background: #1e3a2e !important;
    color: #ffffff !important;
    border: 1px solid #2e5c45 !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    width: 100%;
}
div.stDownloadButton > button:hover {
    background: #254d3c !important;
}

.piece-label {
    font-size: 0.70rem;
    color: #888888;
    text-align: center;
    margin-top: 4px;
}

.section-header {
    font-size: 1.1rem;
    font-weight: 700;
    color: #ffffff;
    border-left: 3px solid #555555;
    padding-left: 10px;
    margin: 1.5rem 0 1rem;
}

footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# HELPER FUNCTIONS
#
# Versi TANPA LIBRARY pengolahan citra:
#   - PIL hanya dipakai untuk membaca (decode) dan menyimpan (encode) file gambar.
#   - Seluruh pengolahan (resize, bingkai, potong, mask jigsaw, augmentasi,
#     rotasi, penomoran) diimplementasikan manual dengan Python murni.
#
# Representasi citra: dict {"w", "h", "gray", "px"} dengan px = list baris,
# tiap piksel berupa int (grayscale) atau tuple (R, G, B).

MAX_SIDE = 600  # loop Python murni lebih lambat, jadi batas resolusi lebih kecil


def clip(v):
    """Batasi nilai intensitas ke rentang 0..255."""
    return 0 if v < 0 else 255 if v > 255 else int(v + 0.5)


def make_image(w, h, gray, px):
    return {"w": w, "h": h, "gray": gray, "px": px}


SAMPLES = 3  # jumlah sampel per sumbu untuk tiap blok saat memperkecil citra


@st.cache_data(show_spinner="Membaca gambar...")
def load_image(file_bytes: bytes, max_side: int = MAX_SIDE):
    """
    Baca file (PIL hanya decode) lalu ubah ke list piksel 2D, sekaligus memperkecil
    citra besar dengan rasio tetap memakai rata-rata sampel per blok (manual).
    Piksel diambil langsung dari data hasil decode, tanpa menyalin seluruh citra
    ke list, sehingga hemat memori untuk foto beresolusi tinggi.
    Returns (image, lebar_asli, tinggi_asli).
    """
    pil = Image.open(io.BytesIO(file_bytes))
    pil.load()
    high_depth = pil.mode in ("I", "I;16", "I;16B", "I;16L", "F")
    gray = high_depth or pil.mode in ("L", "1", "LA")
    if not high_depth:
        pil = pil.convert("L" if gray else "RGB")
    data = pil.getdata()  # urutan piksel baris demi baris, diakses per indeks
    w, h = pil.size

    scale = min(1.0, max_side / max(w, h))
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    xb = [int(i * w / nw) for i in range(nw + 1)]
    yb = [int(i * h / nh) for i in range(nh + 1)]

    def sample_points(lo, hi):
        n = min(SAMPLES, max(1, hi - lo))
        return [lo + (2 * k + 1) * (hi - lo) // (2 * n) for k in range(n)]

    sx = [sample_points(xb[c], max(xb[c] + 1, xb[c + 1])) for c in range(nw)]
    px = []
    for r in range(nh):
        rows = [y * w for y in sample_points(yb[r], max(yb[r] + 1, yb[r + 1]))]
        new_row = []
        for c in range(nw):
            vals = [data[base + x] for base in rows for x in sx[c]]
            n = len(vals)
            if gray:
                new_row.append(sum(vals) / n)
            else:
                new_row.append((clip(sum(v[0] for v in vals) / n),
                                clip(sum(v[1] for v in vals) / n),
                                clip(sum(v[2] for v in vals) / n)))
        px.append(new_row)

    if gray:
        if high_depth:
            # Normalisasi min-max manual citra 16-bit / float ke 0..255
            lo = min(min(row) for row in px)
            hi = max(max(row) for row in px)
            rng = hi - lo
            px = [[clip((v - lo) * 255 / rng) if rng else 0 for v in row] for row in px]
        else:
            px = [[clip(v) for v in row] for row in px]
    return make_image(nw, nh, gray, px), w, h


def to_png_bytes(px, w, h, mode) -> bytes:
    """Simpan list piksel 2D ke PNG (PIL hanya encode)."""
    pil = Image.new(mode, (w, h))
    pil.putdata([p for row in px for p in row])
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def compute_bounds(length: int, M: int) -> list:
    """Batas potongan sepanjang satu sumbu; sisa piksel dibagi rata sehingga seluruh citra tercakup."""
    return [round(i * length / M) for i in range(M + 1)]


def create_jigsaw_mask(ph, pw, row, col, M, tab_map_h, tab_map_v, radius):
    """
    Mask boolean 2D (ph+2*pad x pw+2*pad) berbentuk jigsaw: persegi + lingkaran
    tab (ditambah) / blank (dibuang) di tengah tiap sisi, dihitung dengan
    rumus jarak Euclidean (x-cx)^2 + (y-cy)^2 <= r^2.
    tab_map_h[i][j] = +1 : sisi bawah potongan (i,j) punya TAB menonjol ke bawah.
    tab_map_v[i][j] = +1 : sisi kanan potongan (i,j) punya TAB menonjol ke kanan.
    """
    pad = radius + 2
    H_pad, W_pad = ph + 2 * pad, pw + 2 * pad
    mask = [[pad <= y < pad + ph and pad <= x < pad + pw for x in range(W_pad)]
            for y in range(H_pad)]

    def set_circle(cy, cx, value):
        r2 = radius * radius
        for y in range(max(0, cy - radius), min(H_pad, cy + radius + 1)):
            dy2 = (y - cy) ** 2
            for x in range(max(0, cx - radius), min(W_pad, cx + radius + 1)):
                if dy2 + (x - cx) ** 2 <= r2:
                    mask[y][x] = value

    if row > 0:
        set_circle(pad, pad + pw // 2, tab_map_h[row-1][col] == -1)
    if row < M - 1:
        set_circle(pad + ph, pad + pw // 2, tab_map_h[row][col] == 1)
    if col > 0:
        set_circle(pad + ph // 2, pad, tab_map_v[row][col-1] == -1)
    if col < M - 1:
        set_circle(pad + ph // 2, pad + pw, tab_map_v[row][col] == 1)
    return mask


def crop_with_edge_pad(img, y0, y1, x0, x1, pad):
    """Ambil area [y0-pad, y1+pad) x [x0-pad, x1+pad); piksel di luar citra diisi piksel tepi terdekat."""
    src, H, W = img["px"], img["h"], img["w"]
    xs = [min(max(x, 0), W - 1) for x in range(x0 - pad, x1 + pad)]
    return [[src[min(max(y, 0), H - 1)][x] for x in xs] for y in range(y0 - pad, y1 + pad)]


def augment_piece(patch, gray):
    """
    Augmentasi brightness & contrast manual:
      brightness : p' = p * b
      contrast   : p' = mean + c * (p - mean), mean = rata-rata luminans
    """
    b = random.uniform(0.8, 1.2)
    c = random.uniform(0.8, 1.2)
    if gray:
        n = sum(len(r) for r in patch)
        mean = sum(sum(r) for r in patch) * b / n
        return [[clip(mean + c * (p * b - mean)) for p in row] for row in patch]
    total = n = 0
    for row in patch:
        for (r, g, bl) in row:
            total += 0.299 * r + 0.587 * g + 0.114 * bl
        n += len(row)
    mean = total * b / n
    return [[(clip(mean + c * (r * b - mean)),
              clip(mean + c * (g * b - mean)),
              clip(mean + c * (bl * b - mean))) for (r, g, bl) in row] for row in patch]


def rotate(px, angle):
    """
    Rotasi berlawanan arah jarum jam (0/90/180/270) dengan pemetaan indeks:
       90 : new[r][c] = old[c][W-1-r]
      180 : new[r][c] = old[H-1-r][W-1-c]
      270 : new[r][c] = old[H-1-c][r]
    """
    H, W = len(px), len(px[0])
    if angle == 90:
        return [[px[c][W-1-r] for c in range(H)] for r in range(W)]
    if angle == 180:
        return [row[::-1] for row in px[::-1]]
    if angle == 270:
        return [[px[H-1-c][r] for c in range(H)] for r in range(W)]
    return px


# Font bitmap 3x5 untuk angka 0-9 (1 = piksel menyala)
DIGITS = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
}


def draw_number(px, number, offset, gray):
    """Gambar nomor potongan dengan font bitmap manual (bayangan hitam + teks putih)."""
    H, W = len(px), len(px[0])
    s = max(2, min(H, W) // 25)  # ukuran satu "piksel" font
    white = (255, 255) if gray else (255, 255, 255, 255)
    black = (0, 255) if gray else (0, 0, 0, 255)
    for color, shift in ((black, max(1, s // 2)), (white, 0)):
        x_cursor = offset + 4 + shift
        top = offset + 4 + shift
        for ch in str(number):
            for gy, line in enumerate(DIGITS[ch]):
                for gx, bit in enumerate(line):
                    if bit != "1":
                        continue
                    for y in range(top + gy * s, top + (gy + 1) * s):
                        for x in range(x_cursor + gx * s, x_cursor + (gx + 1) * s):
                            if 0 <= y < H and 0 <= x < W:
                                px[y][x] = color
            x_cursor += 4 * s
    return px


def generate_puzzle(
    image: dict,
    M: int,
    do_jigsaw: bool,
    do_rotation: bool,
    do_augmentation: bool,
    do_numbering: bool,
    jigsaw_radius_ratio: float,
):
    """
    Main generation function. Seluruh hasil disimpan di memori.
    Returns dict: frame (PNG bytes), pieces (list of dict), tab_map_h, tab_map_v, zip (bytes).
    Citra Grayscale tetap Grayscale; citra RGB tetap RGB.
    """
    gray, H, W = image["gray"], image["h"], image["w"]
    ys = compute_bounds(H, M)
    xs = compute_bounds(W, M)

    # 1. CREATE FRAME (ukuran sama persis dengan citra masukan)
    min_step = min(H // M, W // M)
    t = max(1, min_step // 60)
    bg, line = (18, 200) if gray else ((18, 18, 18), (200, 200, 200))
    line_rows, line_cols = set(), set()
    for b in ys:
        b = min(max(b, t), H - t)
        line_rows.update(range(b - t, b + t))
    for b in xs:
        b = min(max(b, t), W - t)
        line_cols.update(range(b - t, b + t))
    frame = [[line if (y in line_rows or x in line_cols) else bg for x in range(W)]
             for y in range(H)]
    frame_bytes = to_png_bytes(frame, W, H, "L" if gray else "RGB")

    # 2. JIGSAW TAB MAPS
    tab_map_h = [[random.choice([-1, 1]) for _ in range(M)] for _ in range(M - 1)]
    tab_map_v = [[random.choice([-1, 1]) for _ in range(M - 1)] for _ in range(M)]
    radius = max(2, int(min_step * jigsaw_radius_ratio))
    pad = radius + 2 if do_jigsaw else 0

    # 3. CUT PIECES
    pieces = []
    counter = 1
    for row in range(M):
        for col in range(M):
            y0, y1 = ys[row], ys[row+1]
            x0, x1 = xs[col], xs[col+1]
            ph, pw = y1 - y0, x1 - x0

            # area potongan + margin pad (berisi piksel tetangga untuk pasak jigsaw)
            patch = crop_with_edge_pad(image, y0, y1, x0, x1, pad)

            if do_augmentation:
                patch = augment_piece(patch, gray)

            if do_jigsaw:
                mask = create_jigsaw_mask(ph, pw, row, col, M, tab_map_h, tab_map_v, radius)
            else:
                mask = [[True] * pw for _ in range(ph)]

            # gabungkan piksel + kanal alpha (255 = bagian potongan, 0 = transparan)
            if gray:
                piece = [[(p, 255 if m else 0) for p, m in zip(prow, mrow)]
                         for prow, mrow in zip(patch, mask)]
            else:
                piece = [[(p[0], p[1], p[2], 255 if m else 0) for p, m in zip(prow, mrow)]
                         for prow, mrow in zip(patch, mask)]

            if do_numbering:
                piece = draw_number(piece, counter, pad, gray)

            angle = random.choice([0, 90, 180, 270]) if do_rotation else 0
            piece = rotate(piece, angle)

            pieces.append({
                "name": f"Piece_{counter:03d}_r{angle}.png",
                "data": to_png_bytes(piece, len(piece[0]), len(piece), "LA" if gray else "RGBA"),
                "angle": angle, "row": row, "col": col,
            })
            counter += 1

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Bingkai.png", frame_bytes)
        for p in pieces:
            zf.writestr(f"Pieces/{p['name']}", p["data"])

    return {
        "frame": frame_bytes,
        "pieces": pieces,
        "tab_map_h": tab_map_h,
        "tab_map_v": tab_map_v,
        "zip": zip_buf.getvalue(),
    }


# SIDEBAR
with st.sidebar:
    st.markdown("## Pengaturan Puzzle")
    st.markdown("---")

    uploaded_file = st.file_uploader(
        "Upload Gambar",
        type=["jpg", "jpeg", "png", "bmp", "tiff"],
        help="Supported: JPG, PNG, BMP, TIFF"
    )

    M = st.slider("Ukuran Grid (M x M)", min_value=2, max_value=10, value=4,
                  help="Gambar akan dipotong menjadi M x M bagian")

    st.markdown("### Fitur Lanjutan")
    do_jigsaw   = st.toggle("Bentuk Jigsaw", value=True)
    do_rotation = st.toggle("Rotasi Acak", value=True)
    do_augment  = st.toggle("Augmentasi Warna", value=True)
    do_number   = st.toggle("Nomor Potongan", value=True)

    if do_jigsaw:
        jigsaw_ratio = st.slider("Ukuran Pasak Jigsaw", 0.10, 0.30, 0.18, 0.02,
                                 help="Rasio radius pasak terhadap ukuran potongan")
    else:
        jigsaw_ratio = 0.18

    st.markdown("---")
    st.markdown("""
    <div style='color:#666666;font-size:0.78rem;'>
    Tugas Besar PCD<br>
    Puzzle World - Puzzle Generator<br>
    Versi Tanpa Library<br>
    Kelompok 3
    </div>
    """, unsafe_allow_html=True)


# MAIN AREA
st.markdown('<div class="hero-title">Puzzle World</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Pengolahan Citra Digital - Puzzle Generator Module (Tanpa Library)</div>', unsafe_allow_html=True)

# Feature badges
badge_html = ""
if do_jigsaw:   badge_html += '<span class="badge">Jigsaw Cuts</span>'
if do_rotation: badge_html += '<span class="badge">Random Rotation</span>'
if do_augment:  badge_html += '<span class="badge">Color Augmentation</span>'
if do_number:   badge_html += '<span class="badge">Numbered Pieces</span>'
if badge_html:
    st.markdown(f'<div style="text-align:center;margin-bottom:1.5rem;">{badge_html}</div>',
                unsafe_allow_html=True)

if uploaded_file is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="puzzle-card" style="text-align:center;padding:3rem 2rem;">
            <div style="font-size:1.3rem;font-weight:700;color:#ffffff;margin-bottom:0.6rem;">
                Upload Gambar
            </div>
            <div style="color:#777777;font-size:0.9rem;">
                Pilih file gambar dari sidebar kiri untuk memulai.<br>
                Format yang didukung: JPG, PNG, BMP, TIFF
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    image, orig_w, orig_h = load_image(uploaded_file.getvalue())
    is_gray = image["gray"]
    img_h, img_w = image["h"], image["w"]

    # Hasil lama dibuang jika gambar/parameter berubah
    settings_key = (uploaded_file.file_id if hasattr(uploaded_file, "file_id") else uploaded_file.name,
                    M, do_jigsaw, do_rotation, do_augment, do_number, jigsaw_ratio)
    if st.session_state.get("settings_key") != settings_key:
        st.session_state.pop("result", None)
        st.session_state["settings_key"] = settings_key

    if (img_h, img_w) != (orig_h, orig_w):
        st.info(f"Gambar {orig_w}x{orig_h} diperkecil menjadi {img_w}x{img_h} "
                f"(rasio tetap) agar proses lebih cepat.")

    # Stats row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-num">{img_w}x{img_h}</div>
            <div class="stat-label">Resolusi</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-num">{M*M}</div>
            <div class="stat-label">Jumlah Potongan</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        mode = "Grayscale" if is_gray else "RGB"
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-num">{mode}</div>
            <div class="stat-label">Mode Warna</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-num">{M}x{M}</div>
            <div class="stat-label">Grid Size</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Preview & action
    col_img, col_btn = st.columns([3, 1])
    with col_img:
        st.markdown('<div class="section-header">Gambar Original</div>', unsafe_allow_html=True)
        st.image(to_png_bytes(image["px"], img_w, img_h, "L" if is_gray else "RGB"),
                 use_container_width=True)
    with col_btn:
        st.markdown('<div class="section-header">Aksi</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        generate_btn = st.button("Generate Puzzle", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="puzzle-card" style="font-size:0.85rem;color:#aaaaaa;">
            <b style="color:#ffffff;">Ringkasan</b><br><br>
            Grid: <b style="color:#ffffff;">{M}x{M}</b><br>
            Potongan: <b style="color:#ffffff;">{M*M}</b><br>
            Jigsaw: <b style="color:#ffffff;">{"Ya" if do_jigsaw else "Tidak"}</b><br>
            Rotasi: <b style="color:#ffffff;">{"Ya" if do_rotation else "Tidak"}</b><br>
            Augmentasi: <b style="color:#ffffff;">{"Ya" if do_augment else "Tidak"}</b><br>
            Nomor: <b style="color:#ffffff;">{"Ya" if do_number else "Tidak"}</b>
        </div>
        """, unsafe_allow_html=True)

    # GENERATE
    if generate_btn:
        with st.spinner(f"Memotong gambar menjadi {M*M} potongan..."):
            st.session_state["result"] = generate_puzzle(
                image, M,
                do_jigsaw=do_jigsaw,
                do_rotation=do_rotation,
                do_augmentation=do_augment,
                do_numbering=do_number,
                jigsaw_radius_ratio=jigsaw_ratio,
            )

    result = st.session_state.get("result")
    if result:
        pieces = result["pieces"]
        st.success(f"Selesai! {len(pieces)} potongan puzzle berhasil dibuat.")

        # FRAME
        st.markdown('<div class="section-header">Bingkai Acuan (Frame)</div>', unsafe_allow_html=True)
        col_f1, col_f2, col_f3 = st.columns([1, 2, 1])
        with col_f2:
            st.image(result["frame"], use_container_width=True, caption=f"Bingkai {M}x{M} Grid")
            d1, d2 = st.columns(2)
            with d1:
                st.download_button(
                    label="Unduh Bingkai (PNG)",
                    data=result["frame"],
                    file_name="Bingkai.png",
                    mime="image/png",
                    use_container_width=True,
                )
            with d2:
                st.download_button(
                    label="Unduh Semua (ZIP)",
                    data=result["zip"],
                    file_name=f"Puzzle_{M}x{M}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

        # PIECES GALLERY
        st.markdown(f'<div class="section-header">Galeri Potongan Puzzle - {len(pieces)} Pieces</div>',
                    unsafe_allow_html=True)

        COLS = min(M, 5)
        for idx in range(0, len(pieces), COLS):
            batch = pieces[idx: idx + COLS]
            cols = st.columns(COLS)
            for ci, p in enumerate(batch):
                with cols[ci]:
                    st.image(p["data"], use_container_width=True)
                    rot_tag = f"Rotasi {p['angle']} deg" if p["angle"] else "Tanpa rotasi"
                    st.markdown(
                        f'<div class="piece-label">#{idx + ci + 1:03d} [{p["row"]},{p["col"]}] {rot_tag}</div>',
                        unsafe_allow_html=True
                    )

        # GRID MAP
        with st.expander("Tab/Blank Map (Jigsaw Schema)"):
            if do_jigsaw:
                st.markdown("**Horizontal Edges** (baris = batas antar row, kolom = col; "
                            "1 = tab menonjol ke bawah, -1 = blank/indent)")
                st.dataframe(
                    {"Col " + str(j): [r[j] for r in result["tab_map_h"]] for j in range(M)},
                    use_container_width=True
                )
                st.markdown("**Vertical Edges** (baris = row, kolom = batas antar col; "
                            "1 = tab menonjol ke kanan, -1 = blank/indent)")
                st.dataframe(
                    {"Edge " + str(j): [r[j] for r in result["tab_map_v"]] for j in range(M-1)},
                    use_container_width=True
                )
            else:
                st.info("Jigsaw mode tidak diaktifkan.")
