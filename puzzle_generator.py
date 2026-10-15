"""
Puzzle World - Puzzle Generator Desktop App (Tkinter)
Tugas Besar Pengolahan Citra Digital
=========================================================
Features:
  - Jigsaw-shaped cuts with tab/blank connectors
  - Random rotation (0/90/180/270 degrees)
  - Per-piece brightness/contrast augmentation
  - Numbered overlay on each piece
  - Frame generation with grid lines
  - Gallery preview with scrollable canvas
  - Save all pieces + frame to output folder
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import random
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageTk
import imageio.v3 as imageio


# ──────────────────────────────────────────────────────────────────────────────
# CORE PUZZLE LOGIC (shared with Streamlit app)
# ──────────────────────────────────────────────────────────────────────────────

def create_jigsaw_mask(h_step, w_step, row, col, M, tab_map_h, tab_map_v, jigsaw_radius_ratio=0.18):
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
    pil = Image.fromarray(rgb_patch)
    pil = ImageEnhance.Brightness(pil).enhance(random.uniform(0.8, 1.2))
    pil = ImageEnhance.Contrast(pil).enhance(random.uniform(0.8, 1.2))
    return np.array(pil)


def rotate_rgba(rgba: np.ndarray, angle: int) -> np.ndarray:
    pil = Image.fromarray(rgba, "RGBA")
    ops = {90: Image.ROTATE_90, 180: Image.ROTATE_180, 270: Image.ROTATE_270}
    if angle in ops:
        pil = pil.transpose(ops[angle])
    return np.array(pil)


def generate_puzzle(image_np, M, do_jigsaw, do_rotation, do_augmentation,
                    do_numbering, jigsaw_radius_ratio, output_dir, progress_cb=None):
    H, W = image_np.shape[:2]
    C = image_np.shape[2] if image_np.ndim == 3 else 1
    rgb = (np.stack([image_np.squeeze()]*3, axis=-1)
           if (image_np.ndim == 2 or C == 1)
           else image_np[:, :, :3].copy())

    h_step, w_step = H // M, W // M

    # ── Frame
    frame = np.ones((H, W, 3), dtype=np.uint8) * 25
    lc = np.array([124, 58, 237], dtype=np.uint8)
    lt = max(1, min(h_step, w_step) // 30)
    for i in range(1, M):
        y = i * h_step
        frame[max(0, y-lt):y+lt, :] = lc
    for j in range(1, M):
        x = j * w_step
        frame[:, max(0, x-lt):x+lt] = lc
    bw = lt * 2
    frame[:bw, :] = lc; frame[-bw:, :] = lc
    frame[:, :bw] = lc; frame[:, -bw:] = lc
    frame_path = os.path.join(output_dir, "Bingkai.png")
    imageio.imwrite(frame_path, frame)

    # ── Tab maps
    tab_map_h = np.random.choice([-1, 1], size=(M-1, M))
    tab_map_v = np.random.choice([-1, 1], size=(M, M-1))

    piece_info = []
    total = M * M
    for idx, (row, col) in enumerate([(r, c) for r in range(M) for c in range(M)]):
        y0, y1 = row * h_step, (row+1) * h_step
        x0, x1 = col * w_step, (col+1) * w_step
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
                ys = max(0, y0 - pad); sh = y0 - ys
                if sh > 0: canvas[pad-sh:pad, pad:pad+w_step] = rgb[ys:y0, x0:x1]
            if row < M-1 and tab_map_h[row, col] == 1:
                ye = min(H, y1+pad); sh = ye - y1
                if sh > 0: canvas[pad+h_step:pad+h_step+sh, pad:pad+w_step] = rgb[y1:ye, x0:x1]
            if col > 0 and tab_map_v[row, col-1] == -1:
                xs = max(0, x0-pad); sw = x0 - xs
                if sw > 0: canvas[pad:pad+h_step, pad-sw:pad] = rgb[y0:y1, xs:x0]
            if col < M-1 and tab_map_v[row, col] == 1:
                xe = min(W, x1+pad); sw = xe - x1
                if sw > 0: canvas[pad:pad+h_step, pad+w_step:pad+w_step+sw] = rgb[y0:y1, x1:xe]
            alpha = (mask * 255).astype(np.uint8)
            rgba = np.dstack((canvas, alpha))
        else:
            alpha = np.full((rgb_patch.shape[0], rgb_patch.shape[1]), 255, dtype=np.uint8)
            rgba = np.dstack((rgb_patch, alpha))

        piece_num = idx + 1
        if do_numbering:
            rgba = draw_number_on_piece(rgba, piece_num)

        angle = 0
        if do_rotation:
            angle = random.choice([0, 90, 180, 270])
            rgba = rotate_rgba(rgba, angle)

        fname = f"Piece_{piece_num:03d}_r{angle}.png"
        fpath = os.path.join(output_dir, fname)
        imageio.imwrite(fpath, rgba)
        piece_info.append((fname, fpath, angle, row, col))

        if progress_cb:
            progress_cb(piece_num, total)

    return frame_path, piece_info


# ──────────────────────────────────────────────────────────────────────────────
# TKINTER GUI
# ──────────────────────────────────────────────────────────────────────────────

DARK_BG   = "#111111"
PANEL_BG  = "#1a1a1a"
CARD_BG   = "#1e1e1e"
ACCENT    = "#3a3a3a"
ACCENT2   = "#2e2e2e"
SUCCESS   = "#1e3a2e"
TEXT      = "#ffffff"
MUTED     = "#888888"
BORDER    = "#2e2e2e"
HIGHLIGHT = "#cccccc"


class ScrollableFrame(tk.Frame):
    """A vertically scrollable frame."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, bg=CARD_BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=CARD_BG)
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_inner_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.inner_id, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class PuzzleGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Puzzle World - Generator")
        self.geometry("1280x800")
        self.minsize(900, 600)
        self.configure(bg=DARK_BG)

        # State
        self.image_path = tk.StringVar()
        self.M_var      = tk.IntVar(value=4)
        self.jigsaw_var = tk.BooleanVar(value=True)
        self.rotate_var = tk.BooleanVar(value=True)
        self.augment_var= tk.BooleanVar(value=True)
        self.number_var = tk.BooleanVar(value=True)
        self.radius_var = tk.DoubleVar(value=0.18)
        self.output_dir = tk.StringVar()

        self._photo_refs = []   # prevent GC
        self._build_styles()
        self._build_layout()

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        # Scrollbar
        style.configure("Vertical.TScrollbar", background=PANEL_BG,
                        troughcolor=DARK_BG, arrowcolor=MUTED, bordercolor=DARK_BG)
        # Scale
        style.configure("TScale", background=PANEL_BG, troughcolor=BORDER)
        # Checkbutton
        style.configure("TCheckbutton", background=PANEL_BG, foreground=TEXT,
                        font=("Segoe UI", 10), focuscolor=PANEL_BG)
        style.map("TCheckbutton", background=[("active", PANEL_BG)])
        # Progressbar
        style.configure("Accent.Horizontal.TProgressbar",
                        troughcolor=BORDER, background="#555555",
                        lightcolor="#555555", darkcolor="#555555", bordercolor=BORDER)

    # ── LAYOUT ────────────────────────────────────────────────────────────────
    def _build_layout(self):
        # Top header
        header = tk.Frame(self, bg=PANEL_BG, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="Puzzle World", bg=PANEL_BG, fg=HIGHLIGHT,
                 font=("Segoe UI", 22, "bold")).pack(side="left", padx=20)
        tk.Label(header, text="Puzzle Generator - Pengolahan Citra Digital",
                 bg=PANEL_BG, fg=MUTED, font=("Segoe UI", 11)).pack(side="left", padx=5)

        # Body: sidebar + main
        body = tk.Frame(self, bg=DARK_BG)
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)
        self._build_main(body)

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=PANEL_BG, width=300)
        sb.pack(side="left", fill="y", padx=(8, 4), pady=8)
        sb.pack_propagate(False)

        def section(label):
            tk.Label(sb, text=label, bg=PANEL_BG, fg=TEXT,
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
            ttk.Separator(sb, orient="horizontal").pack(fill="x", padx=10, pady=(0, 8))

        # ── IMAGE ──
        section("GAMBAR INPUT")
        tk.Label(sb, text="File Gambar:", bg=PANEL_BG, fg=TEXT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=14)
        path_row = tk.Frame(sb, bg=PANEL_BG)
        path_row.pack(fill="x", padx=10, pady=(2, 6))
        tk.Entry(path_row, textvariable=self.image_path, bg=CARD_BG, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Segoe UI", 9),
                 width=24).pack(side="left", fill="x", expand=True, ipady=5, padx=(0,4))
        self._btn(path_row, "Browse", self._browse_image, w=8).pack(side="right")

        # Image preview thumbnail
        self.thumb_label = tk.Label(sb, bg=CARD_BG, text="Belum ada gambar",
                                    fg=MUTED, font=("Segoe UI", 9), height=8)
        self.thumb_label.pack(fill="x", padx=10, pady=(0, 8))

        # ── GRID SIZE ──
        section("UKURAN GRID (M x M)")
        slider_row = tk.Frame(sb, bg=PANEL_BG)
        slider_row.pack(fill="x", padx=10)
        self.m_label = tk.Label(slider_row, text=f"M = {self.M_var.get()}  ({self.M_var.get()**2} pieces)",
                                bg=PANEL_BG, fg=TEXT, font=("Segoe UI", 11, "bold"))
        self.m_label.pack(anchor="w")
        m_slider = tk.Scale(slider_row, from_=2, to=10, orient="horizontal",
                            variable=self.M_var, bg=PANEL_BG, fg=TEXT,
                            troughcolor=BORDER, highlightthickness=0,
                            activebackground=ACCENT, sliderrelief="flat",
                            command=self._on_m_change, font=("Segoe UI", 8))
        m_slider.pack(fill="x", pady=(0, 8))

        # ── OUTPUT ──
        section("OUTPUT")
        tk.Label(sb, text="Folder Output:", bg=PANEL_BG, fg=TEXT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=14)
        out_row = tk.Frame(sb, bg=PANEL_BG)
        out_row.pack(fill="x", padx=10, pady=(2, 6))
        tk.Entry(out_row, textvariable=self.output_dir, bg=CARD_BG, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Segoe UI", 9),
                 width=22).pack(side="left", fill="x", expand=True, ipady=5, padx=(0,4))
        self._btn(out_row, "Browse", self._browse_output, w=8).pack(side="right")

        # ── FEATURES ──
        section("FITUR LANJUTAN")
        checks = [
            ("Bentuk Jigsaw", self.jigsaw_var),
            ("Rotasi Acak", self.rotate_var),
            ("Augmentasi Warna", self.augment_var),
            ("Nomor Potongan", self.number_var),
        ]
        for text, var in checks:
            cb = tk.Checkbutton(sb, text=text, variable=var,
                                bg=PANEL_BG, fg=TEXT, activebackground=PANEL_BG,
                                activeforeground=HIGHLIGHT, selectcolor=ACCENT,
                                font=("Segoe UI", 10), cursor="hand2")
            cb.pack(anchor="w", padx=14, pady=2)

        tk.Label(sb, text="Ukuran Pasak Jigsaw:", bg=PANEL_BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=14, pady=(10, 0))
        self.radius_label = tk.Label(sb, text=f"{self.radius_var.get():.2f}",
                                     bg=PANEL_BG, fg=HIGHLIGHT, font=("Segoe UI", 9, "bold"))
        self.radius_label.pack(anchor="w", padx=14)
        tk.Scale(sb, from_=0.10, to=0.30, resolution=0.02, orient="horizontal",
                 variable=self.radius_var, bg=PANEL_BG, fg=TEXT,
                 troughcolor=BORDER, highlightthickness=0, activebackground=ACCENT,
                 sliderrelief="flat", command=self._on_radius_change,
                 font=("Segoe UI", 8)).pack(fill="x", padx=10, pady=(0, 8))

        # ── GENERATE BUTTON ──
        self._btn(sb, "Generate Puzzle", self._start_generate,
                  bg=ACCENT, height=2).pack(fill="x", padx=10, pady=(8, 4))
        self._btn(sb, "Simpan ke Folder", self._save_output,
                  bg=SUCCESS, height=2).pack(fill="x", padx=10, pady=(0, 8))

        # Progress
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(sb, variable=self.progress_var,
                                            maximum=100,
                                            style="Accent.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 4))
        self.status_label = tk.Label(sb, text="Siap.", bg=PANEL_BG, fg=MUTED,
                                     font=("Segoe UI", 8), wraplength=260)
        self.status_label.pack(anchor="w", padx=14, pady=(0, 8))

    def _build_main(self, parent):
        main = tk.Frame(parent, bg=DARK_BG)
        main.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)

        # Notebook tabs
        nb_style = ttk.Style()
        nb_style.configure("TNotebook", background=DARK_BG, borderwidth=0)
        nb_style.configure("TNotebook.Tab", background=CARD_BG, foreground=MUTED,
                           font=("Segoe UI", 10, "bold"), padding=(16, 6))
        nb_style.map("TNotebook.Tab",
                     background=[("selected", PANEL_BG)],
                     foreground=[("selected", HIGHLIGHT)])

        self.nb = ttk.Notebook(main)
        self.nb.pack(fill="both", expand=True)

        # Tab 1: Original image
        self.tab_original = tk.Frame(self.nb, bg=DARK_BG)
        self.nb.add(self.tab_original, text="Original")
        self.orig_label = tk.Label(self.tab_original, bg=DARK_BG,
                                   text="Upload gambar untuk melihat preview",
                                   fg=MUTED, font=("Segoe UI", 13))
        self.orig_label.pack(expand=True)

        # Tab 2: Frame
        self.tab_frame = tk.Frame(self.nb, bg=DARK_BG)
        self.nb.add(self.tab_frame, text="Bingkai")
        self.frame_label = tk.Label(self.tab_frame, bg=DARK_BG,
                                    text="Bingkai akan muncul setelah generate",
                                    fg=MUTED, font=("Segoe UI", 13))
        self.frame_label.pack(expand=True)

        # Tab 3: Pieces gallery
        self.tab_gallery = tk.Frame(self.nb, bg=DARK_BG)
        self.nb.add(self.tab_gallery, text="Potongan")
        self.gallery_placeholder = tk.Label(self.tab_gallery, bg=DARK_BG,
                                            text="Potongan akan tampil setelah generate",
                                            fg=MUTED, font=("Segoe UI", 13))
        self.gallery_placeholder.pack(expand=True)
        self.gallery_scroll = None   # will be built after generate

        # Tab 4: Info / stats
        self.tab_info = tk.Frame(self.nb, bg=DARK_BG)
        self.nb.add(self.tab_info, text="Info")
        self._build_info_tab()

        # Internal state
        self._generated_frame_path = None
        self._generated_pieces = []
        self._temp_dir = None

    def _build_info_tab(self):
        info_frame = tk.Frame(self.tab_info, bg=CARD_BG, padx=24, pady=20)
        info_frame.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(info_frame, text="Puzzle World - Generator",
                 bg=CARD_BG, fg=TEXT, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(info_frame, text="Tugas Besar Pengolahan Citra Digital",
                 bg=CARD_BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 16))

        info_text = (
            "Cara Penggunaan:\n"
            "  1. Klik Browse dan pilih gambar (JPG/PNG/BMP).\n"
            "  2. Atur ukuran grid M x M (jumlah potongan = M^2).\n"
            "  3. Pilih folder output untuk menyimpan hasil.\n"
            "  4. Aktifkan/nonaktifkan fitur lanjutan sesuai kebutuhan.\n"
            "  5. Klik Generate Puzzle dan tunggu prosesnya.\n"
            "  6. Klik Simpan ke Folder untuk mengekspor hasil.\n\n"
            "Fitur:\n"
            "  - Jigsaw Cuts   : Potongan berbentuk pasak/celah seperti puzzle asli.\n"
            "  - Rotasi Acak   : Tiap potongan dirotasi 0/90/180/270 deg secara acak.\n"
            "  - Augmentasi    : Kecerahan & kontras tiap potongan divariasikan.\n"
            "  - Nomor Piece   : Setiap potongan diberi nomor urut.\n\n"
            "Output:\n"
            "  - Bingkai.png              : Gambar bingkai grid acuan.\n"
            "  - Piece_001_r90.png ...    : Gambar tiap potongan (format RGBA/PNG).\n"
        )
        tk.Label(info_frame, text=info_text, bg=CARD_BG, fg=TEXT,
                 font=("Segoe UI", 10), justify="left", anchor="nw").pack(anchor="w")

        tk.Label(info_frame, text="Kelompok 3 - Pengolahan Citra Digital",
                 bg=CARD_BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(20, 0))

    # ── HELPERS ───────────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, bg=ACCENT2, fg="white", w=None, height=1):
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                      activebackground=ACCENT, activeforeground="white",
                      relief="flat", font=("Segoe UI", 10, "bold"),
                      cursor="hand2", height=height, width=w)
        return b

    def _on_m_change(self, val):
        m = int(float(val))
        self.m_label.config(text=f"M = {m}  ({m**2} pieces)")

    def _on_radius_change(self, val):
        self.radius_label.config(text=f"{float(val):.2f}")

    def _set_status(self, msg, color=MUTED):
        self.status_label.config(text=msg, fg=color)
        self.update_idletasks()

    # ── BROWSING ──────────────────────────────────────────────────────────────
    def _browse_image(self):
        path = filedialog.askopenfilename(
            title="Pilih Gambar",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif"), ("All files", "*.*")]
        )
        if path:
            self.image_path.set(path)
            self._load_preview(path)
            if not self.output_dir.get():
                self.output_dir.set(str(Path(path).parent / "puzzle_output"))

    def _browse_output(self):
        path = filedialog.askdirectory(title="Pilih Folder Output")
        if path:
            self.output_dir.set(path)

    def _load_preview(self, path):
        try:
            img = Image.open(path)
            # Thumbnail for sidebar
            thumb = img.copy()
            thumb.thumbnail((260, 130), Image.LANCZOS)
            photo = ImageTk.PhotoImage(thumb)
            self._photo_refs.append(photo)
            self.thumb_label.config(image=photo, text="", bg=CARD_BG)
            # Large preview in Original tab
            for w in self.tab_original.winfo_children():
                w.destroy()
            max_w = self.winfo_screenwidth() - 380
            max_h = self.winfo_screenheight() - 200
            preview = img.copy()
            preview.thumbnail((max_w, max_h), Image.LANCZOS)
            photo2 = ImageTk.PhotoImage(preview)
            self._photo_refs.append(photo2)
            lbl = tk.Label(self.tab_original, image=photo2, bg=DARK_BG)
            lbl.pack(expand=True)
            info = tk.Label(self.tab_original,
                            text=f"{img.width} × {img.height} px  |  Mode: {img.mode}  |  {Path(path).name}",
                            bg=DARK_BG, fg=MUTED, font=("Segoe UI", 9))
            info.pack(pady=(0, 8))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuka gambar:\n{e}")

    # ── GENERATION ────────────────────────────────────────────────────────────
    def _start_generate(self):
        if not self.image_path.get():
            messagebox.showwarning("Peringatan", "Pilih gambar terlebih dahulu!")
            return
        self.progress_var.set(0)
        self._set_status("Memproses...", HIGHLIGHT)
        threading.Thread(target=self._run_generate, daemon=True).start()

    def _run_generate(self):
        try:
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix="puzzle_")
            self._temp_dir = temp_dir

            img = Image.open(self.image_path.get())
            image_np = np.array(img)

            M = self.M_var.get()
            total_pieces = M * M

            def progress_cb(done, total):
                pct = (done / total) * 100
                self.progress_var.set(pct)
                self._set_status(f"Memproses potongan {done}/{total}...", HIGHLIGHT)

            frame_path, piece_info = generate_puzzle(
                image_np, M,
                do_jigsaw=self.jigsaw_var.get(),
                do_rotation=self.rotate_var.get(),
                do_augmentation=self.augment_var.get(),
                do_numbering=self.number_var.get(),
                jigsaw_radius_ratio=self.radius_var.get(),
                output_dir=temp_dir,
                progress_cb=progress_cb,
            )

            self._generated_frame_path = frame_path
            self._generated_pieces = piece_info
            self.after(0, self._on_generate_done)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"Gagal generate:\n{e}"))
            self.after(0, lambda: self._set_status("Gagal!", "red"))

    def _on_generate_done(self):
        self._set_status(f"✅ Selesai! {len(self._generated_pieces)} potongan dibuat.", SUCCESS)
        self.progress_var.set(100)
        self._show_frame_preview()
        self._show_gallery()
        self.nb.select(2)  # switch to gallery tab

    def _show_frame_preview(self):
        for w in self.tab_frame.winfo_children():
            w.destroy()
        if not self._generated_frame_path:
            return
        img = Image.open(self._generated_frame_path)
        max_w = self.winfo_screenwidth() - 380
        max_h = self.winfo_screenheight() - 200
        preview = img.copy()
        preview.thumbnail((max_w, max_h), Image.LANCZOS)
        photo = ImageTk.PhotoImage(preview)
        self._photo_refs.append(photo)
        lbl = tk.Label(self.tab_frame, image=photo, bg=DARK_BG)
        lbl.pack(expand=True)
        tk.Label(self.tab_frame, text="Bingkai Grid Acuan",
                 bg=DARK_BG, fg=MUTED, font=("Segoe UI", 9)).pack(pady=(0, 8))

    def _show_gallery(self):
        # Clear old gallery
        for w in self.tab_gallery.winfo_children():
            w.destroy()

        scroll_frame = ScrollableFrame(self.tab_gallery, bg=CARD_BG)
        scroll_frame.pack(fill="both", expand=True)
        inner = scroll_frame.inner

        M = self.M_var.get()
        COLS = min(M, 6)
        THUMB_SIZE = max(80, min(160, (self.winfo_width() - 340) // COLS - 20))

        tk.Label(inner, text=f"{len(self._generated_pieces)} Potongan Puzzle (Grid {M}x{M})",
                 bg=CARD_BG, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(pady=(12, 8))

        grid_frame = tk.Frame(inner, bg=CARD_BG)
        grid_frame.pack(padx=10)

        for idx, (fname, fpath, angle, row, col) in enumerate(self._generated_pieces):
            r_idx = idx // COLS
            c_idx = idx % COLS

            cell = tk.Frame(grid_frame, bg=DARK_BG, padx=4, pady=4,
                            relief="flat")
            cell.grid(row=r_idx, column=c_idx, padx=4, pady=4)

            try:
                pil = Image.open(fpath).convert("RGBA")
                # Make white background for thumbnail
                bg_img = Image.new("RGB", pil.size, (30, 20, 60))
                bg_img.paste(pil, mask=pil.split()[3])
                bg_img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
                photo = ImageTk.PhotoImage(bg_img)
                self._photo_refs.append(photo)
                img_lbl = tk.Label(cell, image=photo, bg=DARK_BG)
                img_lbl.pack()
            except Exception:
                tk.Label(cell, text="?", bg=DARK_BG, fg=MUTED,
                         width=8, height=4).pack()

            piece_num = idx + 1
            rot_tag = f"↻{angle}°" if angle else "—"
            tk.Label(cell, text=f"#{piece_num:03d} [{row},{col}]",
                     bg=DARK_BG, fg=TEXT, font=("Segoe UI", 7, "bold")).pack()
            tk.Label(cell, text=rot_tag, bg=DARK_BG, fg=MUTED,
                     font=("Segoe UI", 7)).pack()

    # ── SAVE OUTPUT ───────────────────────────────────────────────────────────
    def _save_output(self):
        if not self._generated_pieces:
            messagebox.showwarning("Peringatan", "Generate puzzle terlebih dahulu!")
            return
        out = self.output_dir.get()
        if not out:
            out = filedialog.askdirectory(title="Pilih Folder Output")
            if not out:
                return
            self.output_dir.set(out)

        try:
            os.makedirs(out, exist_ok=True)
            # Copy frame
            shutil.copy(self._generated_frame_path, os.path.join(out, "Bingkai.png"))
            # Copy pieces
            for fname, fpath, *_ in self._generated_pieces:
                shutil.copy(fpath, os.path.join(out, fname))

            # Also make a ZIP
            zip_base = os.path.join(out, f"Puzzle_{self.M_var.get()}x{self.M_var.get()}")
            shutil.make_archive(zip_base, 'zip', out,
                                base_dir=None)

            count = len(self._generated_pieces) + 1  # +1 for frame
            messagebox.showinfo("Sukses",
                                f"{count} file berhasil disimpan ke:\n{out}\n\n"
                                f"ZIP: {zip_base}.zip")
            self._set_status(f"Disimpan ke {out}", "#aaaaaa")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan:\n{e}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = PuzzleGeneratorApp()
    app.mainloop()
