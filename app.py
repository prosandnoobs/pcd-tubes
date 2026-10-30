"""
Puzzle World - Antarmuka Streamlit (Versi NumPy)
Tugas Besar Pengolahan Citra Digital

  - Puzzle Generator : citra -> 1 Bingkai + M x M Potongan (jigsaw, rotasi, augmentasi, nomor)
  - Puzzle Solver    : Bingkai + Potongan -> citra utuh

Pengolahan citra ada di generator.py dan solver.py (NumPy);
file ini hanya berisi tampilan.
"""

import time
from pathlib import Path

import streamlit as st

from generator import load_image, to_png_bytes, generate_puzzle
from solver import solve_puzzle, read_solver_input, rotate_result, evaluate, manual_page

st.set_page_config(page_title="Puzzle World", layout="wide", initial_sidebar_state="expanded")
st.markdown(f"<style>{(Path(__file__).parent / 'style.css').read_text()}</style>",
            unsafe_allow_html=True)

load_image_cached = st.cache_data(show_spinner="Membaca gambar...")(load_image)


# ──────────────────────────────────────────────────────────────────────────────
# KOMPONEN TAMPILAN
# ──────────────────────────────────────────────────────────────────────────────

def html(content):
    st.markdown(content, unsafe_allow_html=True)


def header(subtitle):
    html('<div class="hero-title">Puzzle World</div>')
    html(f'<div class="hero-sub">Pengolahan Citra Digital - {subtitle} (NumPy)</div>')


def section(title):
    html(f'<div class="section-header">{title}</div>')


def stat_row(stats):
    """Deretan kotak statistik: stats = [(nilai, label), ...]."""
    for col, (value, label) in zip(st.columns(len(stats)), stats):
        with col:
            html(f'<div class="stat-box"><div class="stat-num">{value}</div>'
                 f'<div class="stat-label">{label}</div></div>')
    html("<br>")


def empty_state(title, text):
    """Kartu petunjuk saat belum ada file yang diunggah."""
    with st.columns([1, 2, 1])[1]:
        html(f'<div class="puzzle-card" style="text-align:center;padding:3rem 2rem;">'
             f'<div style="font-size:1.3rem;font-weight:700;color:#ffffff;margin-bottom:0.6rem;">{title}</div>'
             f'<div style="color:#777777;font-size:0.9rem;">{text}</div></div>')


def reset_on_change(state_key, result_key, value):
    """Buang hasil lama jika input atau pengaturan berubah."""
    if st.session_state.get(state_key) != value:
        st.session_state.pop(result_key, None)
        st.session_state[state_key] = value


def yes_no(flag):
    return "Ya" if flag else "Tidak"


def sidebar_footer():
    st.markdown("---")
    html("<div style='color:#666666;font-size:0.78rem;'>"
         "Tugas Besar PCD - Puzzle World<br>Versi NumPy<br><br>"
         "Ameta Noveolyn (103012300240)<br>"
         "Muhammad Ghozy Abdurrahman (103012330264)<br>"
         "Syahdan Rizqi Ruhendy (103012330308)</div>")


# ──────────────────────────────────────────────────────────────────────────────
# HALAMAN PUZZLE GENERATOR
# ──────────────────────────────────────────────────────────────────────────────

def generator_page():
    with st.sidebar:
        st.markdown("## Pengaturan Puzzle")
        st.markdown("---")
        uploaded = st.file_uploader("Upload Gambar", type=["jpg", "jpeg", "png", "bmp", "tiff"],
                                    help="Supported: JPG, PNG, BMP, TIFF")
        M = st.slider("Ukuran Grid (M x M)", 2, 10, 4, help="Gambar akan dipotong menjadi M x M bagian")
        st.markdown("### Fitur Lanjutan")
        opts = {
            "jigsaw": st.toggle("Bentuk Jigsaw", value=True),
            "rotation": st.toggle("Rotasi Acak", value=True),
            "augment": st.toggle("Augmentasi Warna", value=True),
            "number": st.toggle("Nomor Potongan", value=False,
                                help="Nomor menunjukkan urutan asli; matikan agar solver diuji secara adil"),
        }
        ratio = 0.18
        if opts["jigsaw"]:
            ratio = st.slider("Ukuran Pasak Jigsaw", 0.10, 0.30, 0.18, 0.02,
                              help="Rasio radius pasak terhadap ukuran potongan")
        sidebar_footer()

    header("Puzzle Generator Module")
    badges = {"jigsaw": "Jigsaw Cuts", "rotation": "Random Rotation",
              "augment": "Color Augmentation", "number": "Numbered Pieces"}
    badge_html = "".join(f'<span class="badge">{badges[k]}</span>' for k, on in opts.items() if on)
    if badge_html:
        html(f'<div style="text-align:center;margin-bottom:1.5rem;">{badge_html}</div>')

    if uploaded is None:
        empty_state("Upload Gambar", "Pilih file gambar dari sidebar kiri untuk memulai.<br>"
                                     "Format yang didukung: JPG, PNG, BMP, TIFF")
        return

    image, orig_w, orig_h = load_image_cached(uploaded.getvalue())
    w, h, mode = image["w"], image["h"], "Grayscale" if image["gray"] else "RGB"
    reset_on_change("settings_key", "result", (uploaded.file_id, M, ratio, *opts.values()))

    if (w, h) != (orig_w, orig_h):
        st.info(f"Gambar {orig_w}x{orig_h} diperkecil menjadi {w}x{h} (rasio tetap) agar proses lebih cepat.")
    stat_row([(f"{w}x{h}", "Resolusi"), (M * M, "Jumlah Potongan"), (mode, "Mode Warna"),
              (f"{M}x{M}", "Grid Size")])

    col_img, col_btn = st.columns([3, 1])
    with col_img:
        section("Gambar Original")
        st.image(to_png_bytes(image["px"]), use_container_width=True)
    with col_btn:
        section("Aksi")
        generate_btn = st.button("Generate Puzzle", use_container_width=True)
        summary = [("Grid", f"{M}x{M}"), ("Potongan", M * M), ("Jigsaw", yes_no(opts["jigsaw"])),
                   ("Rotasi", yes_no(opts["rotation"])), ("Augmentasi", yes_no(opts["augment"])),
                   ("Nomor", yes_no(opts["number"]))]
        html('<div class="puzzle-card" style="font-size:0.85rem;color:#aaaaaa;margin-top:1rem;">'
             '<b style="color:#ffffff;">Ringkasan</b><br><br>'
             + "".join(f'{k}: <b style="color:#ffffff;">{v}</b><br>' for k, v in summary) + "</div>")

    if generate_btn:
        with st.spinner(f"Memotong gambar menjadi {M * M} potongan..."):
            st.session_state["result"] = generate_puzzle(
                image, M, opts["jigsaw"], opts["rotation"], opts["augment"], opts["number"], ratio)

    result = st.session_state.get("result")
    if not result:
        return
    pieces = result["pieces"]
    st.success(f"Selesai! {len(pieces)} potongan puzzle berhasil dibuat.")

    section("Bingkai Acuan (Frame)")
    with st.columns([1, 2, 1])[1]:
        st.image(result["frame"], use_container_width=True, caption=f"Bingkai {M}x{M} Grid")
        d1, d2 = st.columns(2)
        d1.download_button("Unduh Bingkai (PNG)", result["frame"], "Bingkai.png", "image/png",
                           use_container_width=True)
        d2.download_button("Unduh Semua (ZIP)", result["zip"], f"Puzzle_{M}x{M}.zip", "application/zip",
                           use_container_width=True)

    section(f"Galeri Potongan Puzzle - {len(pieces)} Pieces")
    n_cols = min(M, 5)
    for start in range(0, len(pieces), n_cols):
        for col, p in zip(st.columns(n_cols), pieces[start:start + n_cols]):
            with col:
                st.image(p["data"], use_container_width=True)
                rot = f"Rotasi {p['angle']} deg" if p["angle"] else "Tanpa rotasi"
                html(f'<div class="piece-label">{p["name"]} [{p["row"]},{p["col"]}] {rot}</div>')

    with st.expander("Tab/Blank Map (Jigsaw Schema)"):
        if not opts["jigsaw"]:
            st.info("Jigsaw mode tidak diaktifkan.")
            return
        st.markdown("**Horizontal Edges** (baris = batas antar row, kolom = col; "
                    "1 = tab menonjol ke bawah, -1 = blank/indent)")
        st.dataframe({f"Col {j}": [r[j] for r in result["tab_map_h"]] for j in range(M)},
                     use_container_width=True)
        st.markdown("**Vertical Edges** (baris = row, kolom = batas antar col; "
                    "1 = tab menonjol ke kanan, -1 = blank/indent)")
        st.dataframe({f"Edge {j}": [r[j] for r in result["tab_map_v"]] for j in range(M - 1)},
                     use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# HALAMAN PUZZLE SOLVER
# ──────────────────────────────────────────────────────────────────────────────

def solver_page():
    with st.sidebar:
        st.markdown("## Pengaturan Solver")
        st.markdown("---")
        uploads = st.file_uploader(
            "Upload ZIP hasil generator, atau Bingkai + Potongan", type=["zip", "png", "json"],
            accept_multiple_files=True,
            help="ZIP dari Puzzle Generator (berisi Bingkai.png, Pieces/, answer.json), "
                 "atau pilih file Bingkai.png dan semua Piece_xxx.png sekaligus")
        allow_rotation = st.toggle("Potongan mungkin terotasi", value=True,
                                   help="Matikan jika potongan dibuat tanpa rotasi acak (lebih cepat & akurat)")
        sidebar_footer()

    header("Puzzle Solver Module")
    if not uploads:
        empty_state("Upload Bingkai &amp; Potongan",
                    "Upload file ZIP hasil Puzzle Generator, atau file Bingkai.png<br>"
                    "beserta seluruh potongan Piece_xxx.png dari sidebar kiri.")
        return

    files = [(f.name, f.getvalue()) for f in uploads]
    data = read_solver_input(files)
    if data["frame"] is None or not data["pieces"]:
        st.error("Input belum lengkap: dibutuhkan 1 citra bingkai dan minimal 1 potongan.")
        return
    reset_on_change("solver_key", "solver_result", (tuple((n, len(b)) for n, b in files), allow_rotation))

    stat_row([(len(data["pieces"]), "Jumlah Potongan"),
              ("Ada" if data["answer"] else "Tidak ada", "Kunci Jawaban"),
              (yes_no(allow_rotation), "Cek Rotasi")])

    col_in, col_btn = st.columns([3, 1])
    with col_in:
        section("Bingkai")
        st.image(data["frame"][1], use_container_width=True)
    with col_btn:
        section("Aksi")
        solve_btn = st.button("Susun Puzzle", use_container_width=True)

    with st.expander(f"Potongan masukan ({len(data['pieces'])})"):
        cols = st.columns(8)
        for i, (name, b) in enumerate(data["pieces"]):
            cols[i % 8].image(b, caption=name.rsplit("/", 1)[-1], use_container_width=True)

    if solve_btn:
        bar = st.progress(0.0, text="Memulai...")
        t0 = time.time()
        try:
            result = solve_puzzle(data["frame"][1], data["pieces"], allow_rotation,
                                  progress=lambda f, txt: bar.progress(f, text=txt))
        except ValueError as e:
            st.error(str(e))
            return
        finally:
            bar.empty()
        result["elapsed"] = time.time() - t0
        result["eval"] = evaluate(result["layout"], data["answer"], result["M"]) if data["answer"] else None
        st.session_state["solver_result"] = result

    result = st.session_state.get("solver_result")
    if not result:
        return

    M = result["M"]
    st.success(f"Selesai! Grid {M}x{M} tersusun dalam {result['elapsed']:.1f} detik.")
    ev = result["eval"]
    if ev:
        e1, e2, e3 = st.columns(3)
        e1.metric("Akurasi Posisi", f"{ev['position'] * 100:.1f}%")
        e2.metric("Akurasi Rotasi", f"{ev['rotation'] * 100:.1f}%")
        e3.metric("Rotasi Global Hasil", f"{ev['global_rotation']} deg")
        if ev["global_rotation"]:
            st.info("Susunan benar tetapi seluruh gambar terputar (puzzle tanpa acuan arah). "
                    "Gunakan tombol putar di bawah untuk meluruskan.")

    section("Hasil Penyusunan")
    col_r1, col_r2, _ = st.columns([1, 3, 1])
    with col_r1:
        for label, angle in (("Putar 90 deg kiri", 90), ("Putar 90 deg kanan", 270)):
            if st.button(label, use_container_width=True):
                result["image"] = rotate_result(result["image"], angle)
                st.rerun()
    with col_r2:
        st.image(result["image"], use_container_width=True, caption="Citra utuh hasil solver")
        st.download_button("Unduh Hasil (PNG)", result["image"], "Hasil_Puzzle.png", "image/png",
                           use_container_width=True)

    with st.expander("Susunan potongan (nama file & rotasi koreksi)"):
        st.dataframe({f"Col {c}": [f"{row[c][0]} ({row[c][1]} deg)" for row in result["layout"]]
                      for c in range(M)}, use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# NAVIGASI
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Puzzle World")
    page = st.radio("Modul", ["Puzzle Generator", "Puzzle Solver", "Susun Manual"],
                    label_visibility="collapsed")

if page == "Puzzle Generator":
    generator_page()
elif page == "Puzzle Solver":
    solver_page()
else:
    manual_page(header, section, empty_state, sidebar_footer)
