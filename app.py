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
import os, random, shutil, tempfile
import imageio.v3 as imageio

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
.stat-num { font-size: 1.6rem; font-weight: 700; color: #ffffff; }
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

def create_jigsaw_mask(h_step, w_step, row, col, M, tab_map_h, tab_map_v, jigsaw_radius_ratio=0.18):
    """
    Build a boolean mask (h_step x w_step) with circular tab/blank connectors
    on each of the 4 edges, creating a true jigsaw silhouette.
    tab_map_h[i,j] = +1 means bottom edge of row-i piece at col-j has a TAB protruding down.
    tab_map_v[i,j] = +1 means right edge of row-i piece at col-j has a TAB protruding right.
    """
    radius = int(min(h_step, w_step) * jigsaw_radius_ratio)
    pad = radius + 2
    H_pad = h_step + 2 * pad
    W_pad = w_step + 2 * pad

    mask = np.zeros((H_pad, W_pad), dtype=bool)
    mask[pad:pad+h_step, pad:pad+w_step] = True

    Y, X = np.ogrid[:H_pad, :W_pad]

    def add_circle(cy, cx, add: bool):
        dist2 = (Y - cy)**2 + (X - cx)**2
        if add:
            mask[dist2 <= radius**2] = True
        else:
            mask[dist2 <= radius**2] = False

    if row > 0:
        add_circle(pad, pad + w_step // 2, tab_map_h[row-1, col] == -1)
    if row < M - 1:
        add_circle(pad + h_step, pad + w_step // 2, tab_map_h[row, col] == 1)
    if col > 0:
        add_circle(pad + h_step // 2, pad, tab_map_v[row, col-1] == -1)
    if col < M - 1:
        add_circle(pad + h_step // 2, pad + w_step, tab_map_v[row, col] == 1)

    return mask, pad


def draw_number_on_piece(rgba_img: np.ndarray, number: int) -> np.ndarray:
    """Overlay a piece number on the piece image."""
    pil = Image.fromarray(rgba_img, "RGBA")
    draw = ImageDraw.Draw(pil)
    font_size = max(12, min(pil.width, pil.height) // 5)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    draw.text((6, 6), str(number), fill=(0, 0, 0, 180), font=font)
    draw.text((4, 4), str(number), fill=(255, 255, 255, 230), font=font)
    return np.array(pil)


def augment_piece(rgb_patch: np.ndarray) -> np.ndarray:
    """Apply random brightness & contrast augmentation to a piece."""
    pil = Image.fromarray(rgb_patch)
    pil = ImageEnhance.Brightness(pil).enhance(random.uniform(0.8, 1.2))
    pil = ImageEnhance.Contrast(pil).enhance(random.uniform(0.8, 1.2))
    return np.array(pil)


def rotate_rgba(rgba: np.ndarray, angle: int) -> np.ndarray:
    """Rotate RGBA image by angle degrees (0/90/180/270)."""
    pil = Image.fromarray(rgba, "RGBA")
    if angle == 90:
        pil = pil.transpose(Image.ROTATE_90)
    elif angle == 180:
        pil = pil.transpose(Image.ROTATE_180)
    elif angle == 270:
        pil = pil.transpose(Image.ROTATE_270)
    return np.array(pil)


def generate_puzzle(
    image: np.ndarray,
    M: int,
    do_jigsaw: bool,
    do_rotation: bool,
    do_augmentation: bool,
    do_numbering: bool,
    jigsaw_radius_ratio: float,
    output_dir: str,
):
    """
    Main generation function.
    Returns (frame_path, piece_info, tab_map_h, tab_map_v).
    piece_info is a list of (filename, abs_path, rotation_angle, row, col) tuples.
    """
    H, W = image.shape[:2]
    C = image.shape[2] if image.ndim == 3 else 1
    is_grayscale = (image.ndim == 2 or C == 1)

    if is_grayscale:
        rgb = np.stack([image.squeeze()]*3, axis=-1)
    else:
        rgb = image[:, :, :3].copy()

    h_step = H // M
    w_step = W // M

    # 1. CREATE FRAME
    frame = np.ones((H, W, 3), dtype=np.uint8) * 18
    line_color = np.array([200, 200, 200], dtype=np.uint8)
    line_thickness = max(1, min(h_step, w_step) // 30)
    for i in range(1, M):
        y = i * h_step
        frame[max(0, y-line_thickness):y+line_thickness, :] = line_color
    for j in range(1, M):
        x = j * w_step
        frame[:, max(0, x-line_thickness):x+line_thickness] = line_color
    bw = line_thickness * 2
    frame[:bw, :] = line_color
    frame[-bw:, :] = line_color
    frame[:, :bw] = line_color
    frame[:, -bw:] = line_color

    frame_path = os.path.join(output_dir, "Bingkai.png")
    imageio.imwrite(frame_path, frame)

    # 2. JIGSAW TAB MAPS
    tab_map_h = np.random.choice([-1, 1], size=(M-1, M))
    tab_map_v = np.random.choice([-1, 1], size=(M, M-1))

    # 3. CUT PIECES
    piece_info = []
    counter = 1

    for row in range(M):
        for col in range(M):
            y0 = row * h_step
            y1 = (row + 1) * h_step
            x0 = col * w_step
            x1 = (col + 1) * w_step

            rgb_patch = rgb[y0:y1, x0:x1].copy()

            if do_augmentation:
                rgb_patch = augment_piece(rgb_patch)

            if do_jigsaw:
                mask, pad = create_jigsaw_mask(h_step, w_step, row, col, M,
                                               tab_map_h, tab_map_v, jigsaw_radius_ratio)
                canvas_h, canvas_w = h_step + 2*pad, w_step + 2*pad
                canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
                canvas[pad:pad+h_step, pad:pad+w_step] = rgb_patch

                if row > 0 and tab_map_h[row-1, col] == -1:
                    y_src_start = max(0, y0 - pad)
                    src_h = y0 - y_src_start
                    if src_h > 0:
                        canvas[pad - src_h:pad, pad:pad+w_step] = rgb[y_src_start:y0, x0:x1]
                if row < M-1 and tab_map_h[row, col] == 1:
                    y_src_end = min(H, y1 + pad)
                    src_h = y_src_end - y1
                    if src_h > 0:
                        canvas[pad+h_step:pad+h_step+src_h, pad:pad+w_step] = rgb[y1:y_src_end, x0:x1]
                if col > 0 and tab_map_v[row, col-1] == -1:
                    x_src_start = max(0, x0 - pad)
                    src_w = x0 - x_src_start
                    if src_w > 0:
                        canvas[pad:pad+h_step, pad-src_w:pad] = rgb[y0:y1, x_src_start:x0]
                if col < M-1 and tab_map_v[row, col] == 1:
                    x_src_end = min(W, x1 + pad)
                    src_w = x_src_end - x1
                    if src_w > 0:
                        canvas[pad:pad+h_step, pad+w_step:pad+w_step+src_w] = rgb[y0:y1, x1:x_src_end]

                alpha = (mask * 255).astype(np.uint8)
                rgba = np.dstack((canvas, alpha))
            else:
                alpha = np.full((rgb_patch.shape[0], rgb_patch.shape[1]), 255, dtype=np.uint8)
                rgba = np.dstack((rgb_patch, alpha))

            if do_numbering:
                rgba = draw_number_on_piece(rgba, counter)

            angle = 0
            if do_rotation:
                angle = random.choice([0, 90, 180, 270])
                rgba = rotate_rgba(rgba, angle)

            fname = f"Piece_{counter:03d}_r{angle}.png"
            fpath = os.path.join(output_dir, fname)
            imageio.imwrite(fpath, rgba)
            piece_info.append((fname, fpath, angle, row, col))
            counter += 1

    return frame_path, piece_info, tab_map_h, tab_map_v


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
    image_pil = Image.open(uploaded_file)
    image_np = np.array(image_pil)
    is_gray = (image_np.ndim == 2 or (image_np.ndim == 3 and image_np.shape[2] == 1))

    # Stats row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-num">{image_pil.width}x{image_pil.height}</div>
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
        st.image(image_pil, use_container_width=True)
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
            temp_dir = tempfile.mkdtemp()
            frame_path, piece_info, tab_map_h, tab_map_v = generate_puzzle(
                image_np, M,
                do_jigsaw=do_jigsaw,
                do_rotation=do_rotation,
                do_augmentation=do_augment,
                do_numbering=do_number,
                jigsaw_radius_ratio=jigsaw_ratio,
                output_dir=temp_dir,
            )
            zip_path = shutil.make_archive(temp_dir + "_puzzle", 'zip', temp_dir)

        st.success(f"Selesai! {M*M} potongan puzzle berhasil dibuat.")

        # FRAME
        st.markdown('<div class="section-header">Bingkai Acuan (Frame)</div>', unsafe_allow_html=True)
        col_f1, col_f2, col_f3 = st.columns([1, 2, 1])
        with col_f2:
            st.image(frame_path, use_container_width=True, caption=f"Bingkai {M}x{M} Grid")
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="Unduh Semua Potongan (ZIP)",
                    data=f,
                    file_name=f"Puzzle_{M}x{M}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

        # PIECES GALLERY
        st.markdown(f'<div class="section-header">Galeri Potongan Puzzle - {M*M} Pieces</div>',
                    unsafe_allow_html=True)

        COLS = min(M, 5)
        for idx in range(0, len(piece_info), COLS):
            batch = piece_info[idx: idx + COLS]
            cols = st.columns(COLS)
            for ci, (fname, fpath, angle, row, col) in enumerate(batch):
                with cols[ci]:
                    st.image(fpath, use_container_width=True)
                    piece_num = idx + ci + 1
                    rot_tag = f"Rotasi {angle} deg" if angle else "Tanpa rotasi"
                    st.markdown(
                        f'<div class="piece-label">#{piece_num:03d} [{row},{col}] {rot_tag}</div>',
                        unsafe_allow_html=True
                    )

        # GRID MAP
        with st.expander("Tab/Blank Map (Jigsaw Schema)"):
            if do_jigsaw:
                st.markdown("**Horizontal Edges** (1 = tab protrudes down, -1 = blank/indent)")
                st.dataframe(
                    {"Row " + str(j): tab_map_h[:, j] for j in range(M)},
                    use_container_width=True
                )
                st.markdown("**Vertical Edges** (1 = tab protrudes right, -1 = blank/indent)")
                st.dataframe(
                    {"Col " + str(j): tab_map_v[:, j] for j in range(M-1)},
                    use_container_width=True
                )
            else:
                st.info("Jigsaw mode tidak diaktifkan.")