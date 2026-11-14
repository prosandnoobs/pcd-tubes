"""
Puzzle World - Antarmuka Streamlit
Tugas Besar Pengolahan Citra Digital

  - Puzzle Generator : gambar -> 1 Bingkai + M x M Potongan
  - Puzzle Solver    : Bingkai + Potongan -> gambar utuh

File ini hanya berisi tampilan. Pengolahan citra ada di generator.py dan solver.py.
"""

import time
from pathlib import Path

import streamlit as st

from generator import baca_citra, generate_puzzle, simpan_png
from solver import baca_input, hitung_akurasi, solve_puzzle

st.set_page_config(page_title="Puzzle World", layout="wide")
st.markdown(f"<style>{(Path(__file__).parent / 'style.css').read_text()}</style>",
            unsafe_allow_html=True)


def judul(subjudul):
    st.markdown('<div class="hero-title">Puzzle World</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="hero-sub">Pengolahan Citra Digital - {subjudul}</div>',
                unsafe_allow_html=True)


def subjudul(teks):
    st.markdown(f'<div class="section-header">{teks}</div>', unsafe_allow_html=True)


def identitas_kelompok():
    st.markdown("---")
    st.caption("Tugas Besar PCD - Puzzle World  \n"
               "Ameta Noveolyn (103012300240)  \n"
               "Muhammad Ghozy Abdurrahman (103012330264)  \n"
               "Syahdan Rizqi Ruhendy (103012330308)")


# ──────────────────────────────────────────────────────────────────────────────
# HALAMAN PUZZLE GENERATOR
# ──────────────────────────────────────────────────────────────────────────────

def halaman_generator():
    with st.sidebar:
        file_gambar = st.file_uploader("Upload Gambar", type=["jpg", "jpeg", "png", "bmp", "tiff"])
        M = st.slider("Ukuran Grid (M x M)", 2, 10, 4)
        identitas_kelompok()

    judul("Puzzle Generator")
    if file_gambar is None:
        st.info("Upload gambar dari sidebar kiri untuk memulai (JPG, PNG, BMP, TIFF).")
        return

    px, lebar_asli, tinggi_asli = baca_citra(file_gambar.getvalue())
    mode = "Grayscale" if px.shape[2] == 1 else "RGB"
    st.write(f"Ukuran asli {lebar_asli}x{tinggi_asli}, diperkecil menjadi "
             f"{px.shape[1]}x{px.shape[0]} | Mode warna: {mode} | Jumlah potongan: {M * M}")

    subjudul("Gambar Asli")
    st.image(simpan_png(px), width=500)

    # Hapus hasil lama jika gambar atau M berubah
    pengaturan = (file_gambar.name, file_gambar.size, M)
    if st.session_state.get("pengaturan") != pengaturan:
        st.session_state["pengaturan"] = pengaturan
        st.session_state.pop("hasil_generator", None)

    if st.button("Generate Puzzle"):
        try:
            st.session_state["hasil_generator"] = generate_puzzle(px, M)
        except ValueError as e:
            st.error(str(e))

    hasil = st.session_state.get("hasil_generator")
    if hasil is None:
        return

    lebar_potong, tinggi_potong = hasil["ukuran_potongan"]
    subjudul("Bingkai")
    st.write(f"Tebal bingkai {hasil['tebal']} piksel | Ukuran tiap potongan "
             f"{lebar_potong}x{tinggi_potong} piksel")
    st.image(hasil["bingkai"], width=500)
    st.download_button("Unduh Semua (ZIP)", hasil["zip"], "Puzzle.zip", "application/zip")

    subjudul(f"Potongan ({len(hasil['potongan'])} buah, urutan sudah diacak)")
    kolom = st.columns(8)
    for i, p in enumerate(hasil["potongan"]):
        kolom[i % 8].image(p["png"], caption=p["nama"], use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# HALAMAN PUZZLE SOLVER
# ──────────────────────────────────────────────────────────────────────────────

def halaman_solver():
    with st.sidebar:
        daftar_upload = st.file_uploader("Upload ZIP hasil generator, atau Bingkai + Potongan",
                                         type=["zip", "png", "json"], accept_multiple_files=True)
        identitas_kelompok()

    judul("Puzzle Solver")
    if not daftar_upload:
        st.info("Upload file ZIP hasil Puzzle Generator, atau Bingkai.png beserta semua Piece_xxx.png.")
        return

    data = baca_input([(f.name, f.getvalue()) for f in daftar_upload])
    if data["bingkai"] is None or not data["potongan"]:
        st.error("Input belum lengkap: dibutuhkan 1 Bingkai.png dan potongan-potongannya.")
        return

    subjudul("Bingkai")
    st.image(data["bingkai"], width=500)
    st.write(f"Jumlah potongan: {len(data['potongan'])}")

    if not st.button("Susun Puzzle"):
        return

    waktu_mulai = time.time()
    try:
        hasil = solve_puzzle(data["bingkai"], data["potongan"])
    except ValueError as e:
        st.error(str(e))
        return
    lama = time.time() - waktu_mulai

    st.success(f"Grid {hasil['M']}x{hasil['M']} tersusun dalam {lama:.2f} detik.")
    if data["kunci"]:
        akurasi = hitung_akurasi(hasil["susunan"], data["kunci"])
        st.metric("Akurasi Posisi", f"{akurasi * 100:.1f}%")

    subjudul("Hasil Penyusunan")
    st.image(hasil["gambar"], width=500)
    st.download_button("Unduh Hasil (PNG)", hasil["gambar"], "Hasil_Puzzle.png", "image/png")


# ──────────────────────────────────────────────────────────────────────────────
# NAVIGASI
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    halaman = st.radio("Modul", ["Puzzle Generator", "Puzzle Solver"])

if halaman == "Puzzle Generator":
    halaman_generator()
else:
    halaman_solver()
