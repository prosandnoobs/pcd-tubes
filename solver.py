"""
Puzzle World - Puzzle Solver
Tugas Besar Pengolahan Citra Digital

Masukan : 1 citra Bingkai dan N citra Potongan (hasil Puzzle Generator).
Keluaran: citra utuh yang telah tersusun.

Langkah:
  1. baca_input     : ambil bingkai, potongan, dan kunci jawaban (jika ada) dari file.
  2. deteksi_lubang : cari letak area kosong di dalam bingkai, lalu hitung M.
  3. hitung_biaya   : ukur seberapa cocok sebuah potongan di sebuah slot, dengan
                      membandingkan piksel tepinya dengan tetangga (bingkai atau
                      potongan yang sudah dipasang).
  4. susun_potongan : isi slot satu per satu mulai dari pojok kiri atas bingkai,
                      baris demi baris, dengan potongan yang biayanya paling kecil.
  5. tempel_potongan: tempel semua potongan ke lubang bingkai sehingga gambar utuh.
  6. hitung_akurasi : bandingkan susunan dengan kunci jawaban (answer.json).

NumPy dipakai untuk mengolah piksel. PIL hanya untuk membuka dan menyimpan file gambar.
"""

import io
import json
import zipfile

import numpy as np
from PIL import Image  # hanya untuk membuka dan menyimpan file gambar

from generator import WARNA_GARIS, WARNA_LUBANG, simpan_png


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 1: BACA INPUT
# ──────────────────────────────────────────────────────────────────────────────

def baca_png(isi_file):
    """Buka file gambar menjadi array tinggi x lebar x kanal (1 = grayscale, 3 = RGB)."""
    gambar = Image.open(io.BytesIO(isi_file))
    if gambar.mode in ("1", "L", "LA"):
        return np.array(gambar.convert("L"))[:, :, np.newaxis]
    return np.array(gambar.convert("RGB"))


def baca_input(daftar_file):
    """
    daftar_file: list (nama_file, isi_file). Boleh berisi ZIP hasil generator,
    atau file terpisah: Bingkai.png, Piece_xxx.png, dan answer.json (opsional).
    Mengembalikan dict {bingkai, potongan [(nama, isi)], kunci}.
    """
    # Buka isi ZIP menjadi daftar file biasa
    semua = []
    for nama, isi in daftar_file:
        if nama.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(isi)) as zf:
                for nama_di_zip in zf.namelist():
                    if not nama_di_zip.endswith("/"):
                        semua.append((nama_di_zip, zf.read(nama_di_zip)))
        else:
            semua.append((nama, isi))

    bingkai, potongan, kunci = None, [], None
    for nama, isi in semua:
        nama_file = nama.split("/")[-1].lower()
        if nama_file.endswith(".json"):
            kunci = json.loads(isi.decode("utf-8"))
        elif nama_file.startswith("bingkai"):
            bingkai = isi
        elif nama_file.endswith((".png", ".bmp", ".tif", ".tiff")):
            potongan.append((nama.split("/")[-1], isi))
    potongan.sort()
    return {"bingkai": bingkai, "potongan": potongan, "kunci": kunci}


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 2: DETEKSI LUBANG DI DALAM BINGKAI
# ──────────────────────────────────────────────────────────────────────────────

def deteksi_lubang(bingkai):
    """
    Piksel lubang berwarna WARNA_LUBANG atau WARNA_GARIS (dibuat oleh generator).
    Baris yang hampir seluruh lebarnya berisi piksel lubang adalah baris lubang;
    begitu juga kolom. Lubang = baris lubang pertama s.d. terakhir dan
    kolom lubang pertama s.d. terakhir.
    Mengembalikan (atas, bawah, kiri, kanan); bawah dan kanan tidak termasuk.
    """
    warna = bingkai[:, :, 0]
    sama_semua_kanal = (bingkai == bingkai[:, :, :1]).all(axis=2)
    piksel_lubang = sama_semua_kanal & ((warna == WARNA_LUBANG) | (warna == WARNA_GARIS))

    jumlah_per_baris = piksel_lubang.sum(axis=1)
    jumlah_per_kolom = piksel_lubang.sum(axis=0)
    baris_lubang = np.where(jumlah_per_baris >= 0.9 * jumlah_per_baris.max())[0]
    kolom_lubang = np.where(jumlah_per_kolom >= 0.9 * jumlah_per_kolom.max())[0]
    return baris_lubang[0], baris_lubang[-1] + 1, kolom_lubang[0], kolom_lubang[-1] + 1


def hitung_M(lubang, ukuran_potongan, jumlah_potongan):
    """M = lebar lubang / lebar potongan, dicek dengan N = M x M."""
    atas, bawah, kiri, kanan = lubang
    tinggi_potong, lebar_potong = ukuran_potongan
    M = round((kanan - kiri) / lebar_potong)
    if M * M != jumlah_potongan or round((bawah - atas) / tinggi_potong) != M:
        raise ValueError(f"Ukuran lubang bingkai tidak cocok dengan {jumlah_potongan} potongan.")
    return M


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 3: BIAYA (KETIDAKCOCOKAN) SEBUAH POTONGAN DI SEBUAH SLOT
# ──────────────────────────────────────────────────────────────────────────────

def selisih(garis_a, garis_b):
    """Rata-rata |a - b| dari dua deret piksel yang bersentuhan. Kecil = cocok."""
    return np.abs(garis_a.astype(float) - garis_b.astype(float)).mean()


def hitung_biaya(px, baris, kolom, susunan, bingkai, lubang, M):
    """
    Bandingkan keempat tepi potongan px dengan apa yang ada di sebelahnya:
      - kiri  : tepi kanan potongan di kiri, atau kolom bingkai tepat di kiri lubang
      - atas  : tepi bawah potongan di atas, atau baris bingkai tepat di atas lubang
      - kanan : kolom bingkai tepat di kanan lubang (hanya untuk kolom terakhir)
      - bawah : baris bingkai tepat di bawah lubang (hanya untuk baris terakhir)
    Biaya = rata-rata selisih dari semua tetangga yang tersedia.
    """
    atas, bawah, kiri, kanan = lubang
    tinggi, lebar = px.shape[0], px.shape[1]
    y = atas + baris * tinggi   # posisi slot di dalam bingkai
    x = kiri + kolom * lebar
    daftar_selisih = []

    # Tetangga kiri
    if kolom == 0:
        daftar_selisih.append(selisih(px[:, 0], bingkai[y:y + tinggi, kiri - 1]))
    else:
        daftar_selisih.append(selisih(px[:, 0], susunan[baris][kolom - 1][:, -1]))

    # Tetangga atas
    if baris == 0:
        daftar_selisih.append(selisih(px[0], bingkai[atas - 1, x:x + lebar]))
    else:
        daftar_selisih.append(selisih(px[0], susunan[baris - 1][kolom][-1]))

    # Tetangga kanan dan bawah hanya diketahui jika itu bingkai
    if kolom == M - 1:
        daftar_selisih.append(selisih(px[:, -1], bingkai[y:y + tinggi, kanan]))
    if baris == M - 1:
        daftar_selisih.append(selisih(px[-1], bingkai[bawah, x:x + lebar]))

    return sum(daftar_selisih) / len(daftar_selisih)


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 4: SUSUN POTONGAN DARI POJOK KIRI ATAS
# ──────────────────────────────────────────────────────────────────────────────

def susun_potongan(daftar_px, bingkai, lubang, M):
    """
    Isi slot (0,0), (0,1), ... (0,M-1), lalu (1,0), dan seterusnya.
    Untuk setiap slot, coba semua potongan yang belum dipakai, lalu pilih
    yang biayanya paling kecil.
    Mengembalikan grid M x M berisi nomor potongan.
    """
    belum_dipakai = list(range(len(daftar_px)))
    grid = [[None] * M for _ in range(M)]      # nomor potongan di tiap slot
    susunan = [[None] * M for _ in range(M)]   # piksel potongan di tiap slot

    for baris in range(M):
        for kolom in range(M):
            terbaik, biaya_terbaik = None, float("inf")
            for nomor in belum_dipakai:
                biaya = hitung_biaya(daftar_px[nomor], baris, kolom, susunan, bingkai, lubang, M)
                if biaya < biaya_terbaik:
                    terbaik, biaya_terbaik = nomor, biaya
            grid[baris][kolom] = terbaik
            susunan[baris][kolom] = daftar_px[terbaik]
            belum_dipakai.remove(terbaik)
    return grid


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 5: TEMPEL POTONGAN KE BINGKAI
# ──────────────────────────────────────────────────────────────────────────────

def tempel_potongan(bingkai, grid, daftar_px, lubang):
    """Salin setiap potongan ke slotnya di dalam lubang bingkai."""
    hasil = bingkai.copy()
    atas, _, kiri, _ = lubang
    for baris, isi_baris in enumerate(grid):
        for kolom, nomor in enumerate(isi_baris):
            px = daftar_px[nomor]
            y = atas + baris * px.shape[0]
            x = kiri + kolom * px.shape[1]
            hasil[y:y + px.shape[0], x:x + px.shape[1]] = px
    return hasil


# ──────────────────────────────────────────────────────────────────────────────
# LANGKAH 6: HITUNG AKURASI
# ──────────────────────────────────────────────────────────────────────────────

def hitung_akurasi(susunan_nama, kunci):
    """Persentase slot yang berisi potongan yang benar menurut answer.json."""
    benar = 0
    total = 0
    for baris, isi_baris in enumerate(susunan_nama):
        for kolom, nama in enumerate(isi_baris):
            posisi_asli = kunci["pieces"][nama]
            if posisi_asli["baris"] == baris and posisi_asli["kolom"] == kolom:
                benar += 1
            total += 1
    return benar / total


# ──────────────────────────────────────────────────────────────────────────────
# FUNGSI UTAMA
# ──────────────────────────────────────────────────────────────────────────────

def solve_puzzle(bingkai_png, potongan):
    """
    bingkai_png : isi file Bingkai.png
    potongan    : list (nama_file, isi_file)
    Mengembalikan dict {gambar (PNG), M, susunan (grid nama file)}.
    """
    bingkai = baca_png(bingkai_png)
    daftar_px = [baca_png(isi) for _, isi in potongan]

    lubang = deteksi_lubang(bingkai)
    M = hitung_M(lubang, daftar_px[0].shape[:2], len(daftar_px))
    grid = susun_potongan(daftar_px, bingkai, lubang, M)
    hasil = tempel_potongan(bingkai, grid, daftar_px, lubang)

    susunan_nama = [[potongan[nomor][0] for nomor in isi_baris] for isi_baris in grid]
    return {"gambar": simpan_png(hasil), "M": M, "susunan": susunan_nama}
