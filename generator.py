"""
Puzzle World - Puzzle Generator
Tugas Besar Pengolahan Citra Digital

Masukan : 1 gambar (RGB atau grayscale) dan bilangan M.
Keluaran: 1 citra Bingkai dan M x M citra Potongan.

Langkah:
  1. baca_citra      : baca gambar lalu perkecil agar proses cepat.
  2. hitung_ukuran   : tentukan tebal bingkai (10% sisi terpendek) dan ukuran tiap potongan.
  3. buat_bingkai    : salin gambar, lalu kosongkan area dalam dan beri garis kontur slot.
                       Tepi gambar yang tidak dipotong menjadi bingkai (acuan penyusunan).
  4. potong_citra    : potong area dalam menjadi M x M potongan berukuran sama.
  5. generate_puzzle : acak urutan potongan lalu simpan semuanya ke file ZIP.

NumPy dipakai untuk mengolah piksel. PIL hanya untuk membuka dan menyimpan file gambar.
"""

import io
import json
import random
import zipfile

import numpy as np
from PIL import Image  # hanya untuk membuka dan menyimpan file gambar

SISI_MAKS = 600        # sisi terpanjang gambar setelah diperkecil (piksel)
RASIO_BINGKAI = 0.10   # tebal bingkai = 10% dari sisi terpendek gambar
WARNA_LUBANG = 40      # warna area kosong di dalam bingkai
WARNA_GARIS = 200      # warna garis kontur antar slot


# ──────────────────────────────────────────────────────────────────────────────
# BANTUAN: SIMPAN GAMBAR
# ──────────────────────────────────────────────────────────────────────────────

def simpan_png(px):
    """Ubah array piksel (tinggi x lebar x kanal) menjadi isi file PNG."""
    if px.shape[2] == 1:
        px = px[:, :, 0]  # grayscale disimpan sebagai array 2 dimensi
    buffer = io.BytesIO()
    Image.fromarray(px).save(buffer, format="PNG")
    return buffer.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 1: BACA CITRA
# ──────────────────────────────────────────────────────────────────────────────

def baca_citra(isi_file):
    """
    Baca gambar menjadi array piksel tinggi x lebar x kanal
    (kanal = 1 untuk grayscale, 3 untuk RGB), lalu perkecil jika sisi
    terpanjangnya lebih dari SISI_MAKS.
    Mengembalikan (px, lebar_asli, tinggi_asli).
    """
    gambar = Image.open(io.BytesIO(isi_file))
    if gambar.mode in ("I", "I;16", "I;16B", "I;16L"):
        # Grayscale 16-bit (0..65535) diubah ke 8-bit (0..255) dengan membagi 256
        px = (np.array(gambar) // 256).astype(np.uint8)
        px = px[:, :, np.newaxis]
    elif gambar.mode in ("1", "L", "LA"):
        px = np.array(gambar.convert("L"))
        px = px[:, :, np.newaxis]  # tambah sumbu kanal agar bentuknya sama dengan RGB
    else:
        px = np.array(gambar.convert("RGB"))

    tinggi, lebar = px.shape[0], px.shape[1]
    # Faktor perkecil f (bilangan bulat): setiap blok f x f piksel menjadi 1 piksel.
    # Contoh: lebar 4032, SISI_MAKS 600 -> f = 7 -> lebar baru 4032 // 7 = 576.
    f = -(-max(tinggi, lebar) // SISI_MAKS)  # pembagian dibulatkan ke atas
    if f > 1:
        tinggi_baru, lebar_baru = tinggi // f, lebar // f
        jumlah = np.zeros((tinggi_baru, lebar_baru, px.shape[2]))
        # Jumlahkan f x f piksel di tiap blok, lalu bagi f x f (rata-rata).
        # Rata-rata membuat tepi potongan halus sehingga mudah dicocokkan solver.
        for dy in range(f):
            for dx in range(f):
                jumlah += px[dy:tinggi_baru * f:f, dx:lebar_baru * f:f]
        px = np.round(jumlah / (f * f)).astype(np.uint8)
    return px, lebar, tinggi


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 2: HITUNG UKURAN BINGKAI DAN POTONGAN
# ──────────────────────────────────────────────────────────────────────────────

def hitung_ukuran(tinggi, lebar, M):
    """
    tebal          = 10% dari sisi terpendek gambar
    tinggi_potong  = (tinggi - 2 x tebal) // M
    lebar_potong   = (lebar  - 2 x tebal) // M
    Pembagian bulat (//) membuat semua potongan berukuran sama. Sisa piksel
    yang tidak habis dibagi ikut menjadi bagian bingkai kanan dan bawah.
    """
    tebal = round(RASIO_BINGKAI * min(tinggi, lebar))
    tinggi_potong = (tinggi - 2 * tebal) // M
    lebar_potong = (lebar - 2 * tebal) // M
    if tinggi_potong < 4 or lebar_potong < 4:
        raise ValueError("Gambar terlalu kecil untuk dipotong menjadi M x M potongan.")
    return tebal, tinggi_potong, lebar_potong


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 3: BUAT BINGKAI
# ──────────────────────────────────────────────────────────────────────────────

def buat_bingkai(px, M, tebal, tinggi_potong, lebar_potong):
    """
    Bingkai = salinan gambar asli yang area dalamnya dikosongkan.
    Area dalam dimulai di (tebal, tebal) dan berukuran
    (M x tinggi_potong) x (M x lebar_potong).
    """
    bingkai = px.copy()
    atas, kiri = tebal, tebal
    bawah = atas + M * tinggi_potong
    kanan = kiri + M * lebar_potong

    # Kosongkan area dalam
    bingkai[atas:bawah, kiri:kanan] = WARNA_LUBANG

    # Garis kontur di antara slot (setebal 2 piksel)
    for i in range(1, M):
        y = atas + i * tinggi_potong
        bingkai[y - 1:y + 1, kiri:kanan] = WARNA_GARIS
        x = kiri + i * lebar_potong
        bingkai[atas:bawah, x - 1:x + 1] = WARNA_GARIS
    return bingkai


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 4: POTONG CITRA
# ──────────────────────────────────────────────────────────────────────────────

def potong_citra(px, M, tebal, tinggi_potong, lebar_potong):
    """Potong area dalam menjadi M x M potongan, dibaca baris demi baris."""
    potongan = []
    for baris in range(M):
        for kolom in range(M):
            y = tebal + baris * tinggi_potong
            x = tebal + kolom * lebar_potong
            isi = px[y:y + tinggi_potong, x:x + lebar_potong].copy()
            potongan.append({"px": isi, "baris": baris, "kolom": kolom})
    return potongan


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 5: FUNGSI UTAMA
# ──────────────────────────────────────────────────────────────────────────────

def generate_puzzle(px, M):
    """
    Jalankan langkah 2 sampai 4, acak urutan potongan, lalu simpan ke ZIP:
      Bingkai.png, Pieces/Piece_001.png ... , answer.json (kunci jawaban).
    """
    tinggi, lebar = px.shape[0], px.shape[1]
    tebal, tinggi_potong, lebar_potong = hitung_ukuran(tinggi, lebar, M)
    bingkai = buat_bingkai(px, M, tebal, tinggi_potong, lebar_potong)
    potongan = potong_citra(px, M, tebal, tinggi_potong, lebar_potong)

    # Acak urutan agar nama file tidak membocorkan posisi asli
    random.shuffle(potongan)
    kunci = {}
    for nomor, p in enumerate(potongan, start=1):
        p["nama"] = f"Piece_{nomor:03d}.png"
        p["png"] = simpan_png(p["px"])
        kunci[p["nama"]] = {"baris": p["baris"], "kolom": p["kolom"]}

    bingkai_png = simpan_png(bingkai)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Bingkai.png", bingkai_png)
        for p in potongan:
            zf.writestr("Pieces/" + p["nama"], p["png"])
        zf.writestr("answer.json", json.dumps({"M": M, "pieces": kunci}, indent=2))

    return {
        "bingkai": bingkai_png,
        "potongan": potongan,
        "tebal": tebal,
        "ukuran_potongan": (lebar_potong, tinggi_potong),
        "zip": buffer.getvalue(),
    }
