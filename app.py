"""
Puzzle World - Puzzle Generator (Streamlit)
Tugas Besar Pengolahan Citra Digital
Features:
  - Jigsaw-shaped cuts (tab/blank connectors)
  - Random rotation (0/90/180/270 degrees)
  - Per-piece brightness/contrast augmentation
  - Numbered overlay on each piece
  - Frame generation
  - ZIP download
"""

import streamlit as st
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
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

MAX_SIDE = 2000  # sisi terpanjang maksimum agar proses cepat & hemat memori


def downscale(img: np.ndarray, max_side: int = MAX_SIDE) -> np.ndarray:
    """Perkecil citra besar dengan rasio aspek tetap."""
    h, w = img.shape[:2]
    scale = max_side / max(h, w)
    if scale >= 1:
        return img
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return np.array(Image.fromarray(img).resize(size, Image.LANCZOS))


def load_image(uploaded) -> np.ndarray:
    """
    Read the uploaded file and normalise it to uint8 RGB (H,W,3) or Grayscale (H,W).
    Handles palette (P), RGBA/LA (alpha dropped), CMYK and 16-bit images.
    """
    pil = Image.open(uploaded)
    pil.load()
    if pil.mode in ("L", "1"):
        pil = pil.convert("L")
    elif pil.mode in ("I", "I;16", "I;16B", "I;16L", "F"):
        arr = np.asarray(pil, dtype=np.float64)
        rng = arr.max() - arr.min()
        arr = (arr - arr.min()) / rng * 255 if rng > 0 else np.zeros_like(arr)
        pil = Image.fromarray(arr.astype(np.uint8), "L")
    elif pil.mode == "LA":
        pil = pil.convert("L")
    else:
        pil = pil.convert("RGB")
    return np.array(pil)


def compute_bounds(length: int, M: int) -> list:
    """Batas potongan sepanjang satu sumbu; sisa piksel dibagi rata sehingga seluruh citra tercakup."""
    return [round(i * length / M) for i in range(M + 1)]


def create_jigsaw_mask(ph, pw, row, col, M, tab_map_h, tab_map_v, radius):
    """
    Build a boolean mask (ph+2*pad x pw+2*pad) with circular tab/blank connectors
    on each of the 4 edges, creating a true jigsaw silhouette.
    tab_map_h[i,j] = +1 means bottom edge of row-i piece at col-j has a TAB protruding down.
    tab_map_v[i,j] = +1 means right edge of row-i piece at col-j has a TAB protruding right.
    """
    pad = radius + 2
    H_pad = ph + 2 * pad
    W_pad = pw + 2 * pad

    mask = np.zeros((H_pad, W_pad), dtype=bool)
    mask[pad:pad+ph, pad:pad+pw] = True

    Y, X = np.ogrid[:H_pad, :W_pad]

    def add_circle(cy, cx, add: bool):
        mask[(Y - cy)**2 + (X - cx)**2 <= radius**2] = add

    if row > 0:
        add_circle(pad, pad + pw // 2, tab_map_h[row-1, col] == -1)
    if row < M - 1:
        add_circle(pad + ph, pad + pw // 2, tab_map_h[row, col] == 1)
    if col > 0:
        add_circle(pad + ph // 2, pad, tab_map_v[row, col-1] == -1)
    if col < M - 1:
        add_circle(pad + ph // 2, pad + pw, tab_map_v[row, col] == 1)

    return mask, pad


def get_font(size: int):
    """Font scalable yang tersedia di Windows maupun Linux (Streamlit Cloud)."""
    for name in ("arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def draw_number_on_piece(img: Image.Image, number: int, offset: int) -> Image.Image:
    """Overlay a piece number on the piece image (inside the core area)."""
    draw = ImageDraw.Draw(img)
    font_size = max(12, min(img.width, img.height) // 5)
    font = get_font(font_size)
    x = y = offset + 4
    if img.mode == "LA":
        draw.text((x + 2, y + 2), str(number), fill=(0, 180), font=font)
        draw.text((x, y), str(number), fill=(255, 230), font=font)
    else:
        draw.text((x + 2, y + 2), str(number), fill=(0, 0, 0, 180), font=font)
        draw.text((x, y), str(number), fill=(255, 255, 255, 230), font=font)
    return img


def augment_piece(patch: np.ndarray) -> np.ndarray:
    """Apply random brightness & contrast augmentation to a piece."""
    pil = Image.fromarray(patch)
    pil = ImageEnhance.Brightness(pil).enhance(random.uniform(0.8, 1.2))
    pil = ImageEnhance.Contrast(pil).enhance(random.uniform(0.8, 1.2))
    return np.array(pil)


ROTATIONS = {90: Image.ROTATE_90, 180: Image.ROTATE_180, 270: Image.ROTATE_270}


def to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_puzzle(
    image: np.ndarray,
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
    is_gray = image.ndim == 2
    H, W = image.shape[:2]
    ys = compute_bounds(H, M)
    xs = compute_bounds(W, M)

    # 1. CREATE FRAME (ukuran sama persis dengan citra masukan)
    min_step = min(H // M, W // M)
    t = max(1, min_step // 60)
    frame = np.full((H, W), 18, dtype=np.uint8)
    for y in ys:
        y = min(max(y, t), H - t)
        frame[y-t:y+t, :] = 200
    for x in xs:
        x = min(max(x, t), W - t)
        frame[:, x-t:x+t] = 200
    if not is_gray:
        frame = np.stack([frame] * 3, axis=-1)
    frame_img = Image.fromarray(frame)

    # 2. JIGSAW TAB MAPS
    tab_map_h = np.random.choice([-1, 1], size=(M-1, M))
    tab_map_v = np.random.choice([-1, 1], size=(M, M-1))
    radius = max(2, int(min_step * jigsaw_radius_ratio))
    pad = radius + 2 if do_jigsaw else 0
    pad_spec = ((pad, pad), (pad, pad)) + (() if is_gray else ((0, 0),))
    padded = np.pad(image, pad_spec, mode="edge")

    # 3. CUT PIECES
    pieces = []
    counter = 1
    for row in range(M):
        for col in range(M):
            y0, y1 = ys[row], ys[row+1]
            x0, x1 = xs[col], xs[col+1]
            ph, pw = y1 - y0, x1 - x0

            # area potongan + margin pad (berisi piksel tetangga untuk pasak jigsaw)
            patch = padded[y0:y1 + 2*pad, x0:x1 + 2*pad].copy()

            if do_augmentation:
                patch = augment_piece(patch)

            if do_jigsaw:
                mask, _ = create_jigsaw_mask(ph, pw, row, col, M, tab_map_h, tab_map_v, radius)
            else:
                mask = np.ones((ph, pw), dtype=bool)
            alpha = (mask * 255).astype(np.uint8)

            if is_gray:
                img = Image.fromarray(np.dstack((patch, alpha)), "LA")
            else:
                img = Image.fromarray(np.dstack((patch, alpha)), "RGBA")

            if do_numbering:
                img = draw_number_on_piece(img, counter, pad)

            angle = random.choice([0, 90, 180, 270]) if do_rotation else 0
            if angle:
                img = img.transpose(ROTATIONS[angle])

            pieces.append({
                "name": f"Piece_{counter:03d}_r{angle}.png",
                "data": to_png_bytes(img),
                "angle": angle, "row": row, "col": col,
            })
            counter += 1

    frame_bytes = to_png_bytes(frame_img)
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
    Kelompok 3
    </div>
    """, unsafe_allow_html=True)


# MAIN AREA
st.markdown('<div class="hero-title">Puzzle World</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Pengolahan Citra Digital - Puzzle Generator Module</div>', unsafe_allow_html=True)

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
    original_np = load_image(uploaded_file)
    orig_h, orig_w = original_np.shape[:2]
    image_np = downscale(original_np)
    is_gray = image_np.ndim == 2
    img_h, img_w = image_np.shape[:2]

    # Hasil lama dibuang jika gambar/parameter berubah
    settings_key = (uploaded_file.file_id if hasattr(uploaded_file, "file_id") else uploaded_file.name,
                    M, do_jigsaw, do_rotation, do_augment, do_number, jigsaw_ratio)
    if st.session_state.get("settings_key") != settings_key:
        st.session_state.pop("result", None)
        st.session_state["settings_key"] = settings_key

    if image_np.shape[:2] != (orig_h, orig_w):
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
        st.image(image_np, use_container_width=True)
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
                image_np, M,
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
                    {"Col " + str(j): result["tab_map_h"][:, j] for j in range(M)},
                    use_container_width=True
                )
                st.markdown("**Vertical Edges** (baris = row, kolom = batas antar col; "
                            "1 = tab menonjol ke kanan, -1 = blank/indent)")
                st.dataframe(
                    {"Edge " + str(j): result["tab_map_v"][:, j] for j in range(M-1)},
                    use_container_width=True
                )
            else:
                st.info("Jigsaw mode tidak diaktifkan.")
