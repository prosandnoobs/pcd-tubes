# Anggota Kelompok
### Muhammad Ghozy Abdurrahman
### Ameta Noveolyn
### Syahdan Rizqi Ruhendy

# Puzzle World - Tugas Besar Pengolahan Citra Digital (PCD)

Sistem berbasis citra digital untuk pemrosesan teka-teki gambar yang terdiri dari dua modul utama: **Puzzle Generator** (pemotong gambar menjadi kepingan teka-teki) dan **Puzzle Solver** (penyusun kembali kepingan teka-teki menjadi gambar utuh).

> **Catatan Implementasi:** Seluruh algoritma pengolahan citra digital diimplementasikan secara mandiri menggunakan operasi array **NumPy**, tanpa library pengolahan citra siap pakai seperti OpenCV. Pustaka `Pillow` (PIL) hanya digunakan untuk proses I/O membaca (*decode*) dan menulis (*encode*) file gambar.

---

## Fitur Utama

### 1. Puzzle Generator
- **Dukungan Citra**: Mendukung format RGB dan Grayscale (termasuk kedalaman bit tinggi).
- **Pemotongan Grid**: Memotong citra input menjadi $M \times M$ potongan ($N = M^2$).
- **Generasi Bingkai (Frame)**: Membuat citra bingkai acuan yang meniru ukuran dan rasio citra masukan dengan penanda grid.
- **Fitur Tingkat Lanjut (Opsional)**:
  - *Bentuk Jigsaw*: Pemotongan tepi kepingan berpasak (*tab*) dan bertakik (*blank*) berbasis circular mask.
  - *Rotasi Acak*: Merotasi potongan secara acak ($0^\circ, 90^\circ, 180^\circ, 270^\circ$).
  - *Augmentasi Citra*: Variasi kontras dan kecerahan per potongan.
  - *Penomoran*: Pemberian nomor urut pada potongan.
- **Ekspor Praktis**: Mendukung unduhan satu paket arsip `.zip` berisi bingkai dan seluruh potongan.

### 2. Puzzle Solver
- **Deteksi Grid Otomatis**: Mendeteksi ukuran grid $M \times M$ dan batas sel langsung dari citra bingkai menggunakan profil proyeksi intensitas.
- **Analisis & Kompatibilitas Tepi**:
  - Deteksi orientasi dan kecocokan pasak jigsaw (*flat*, *tab*, *blank*).
  - Penghitungan ketidakcocokan (*dissimilarity*) antar sisi potongan dengan selisih piksel batas dan prediksi gradien warna.
- **Penyusunan Cerdas**:
  - Algoritma rekonstruksi *greedy matching* yang mempertimbangkan konsistensi rotasi dan batas tepi.
- **Metrik Evaluasi**: Menghitung skor akurasi posisi, orientasi rotasi, dan ketepatan penempatan tetangga jika disediakan ground truth.
- **Koreksi Rotasi Manual**: Fasilitas rotasi hasil akhir ($90^\circ, 180^\circ, 270^\circ$) pada antarmuka web.

---

## Struktur Berkas

```text
├── app.py              # Antarmuka web utama berbasis Streamlit
├── generator.py        # Logika pemotongan citra dan pembuatan bingkai (NumPy)
├── solver.py           # Logika rekonstruksi citra dan pencocokan potongan, serta fitur susun manual (NumPy)
├── requirements.txt    # Daftar dependensi aplikasi
├── style.css           # Kustomisasi styling tema UI Streamlit
└── README.md           # Dokumentasi proyek
```

---

## Prasyarat & Instalasi

Pastikan komputer Anda telah terpasang **Python 3.9** atau versi yang lebih baru.

1. **Clone repositori atau unduh folder proyek:**
   ```bash
   git clone <URL_REPOSITORI_ANDA>
   cd pcd-tubes
   ```

2. **(Opsional tetapi disarankan) Buat dan aktifkan lingkungan virtual:**
   ```bash
   # Di Linux / macOS:
   python3 -m venv venv
   source venv/bin/activate

   # Di Windows:
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Pasang pustaka dependensi:**
   ```bash
   pip install -r requirements.txt
   ```

---

## Cara Menjalankan Aplikasi

Jalankan aplikasi berbasis antarmuka web melalui perintah:

```bash
streamlit run app.py
```

Setelah perintah dijalankan, antarmuka web akan otomatis terbuka di peramban web (biasanya pada alamat `http://localhost:8501`).

---

## Panduan Penggunaan

### Menggunakan Puzzle Generator
1. Buka tab **Puzzle Generator** di menu navigasi sebelah kiri.
2. Unggah gambar masukan (`.jpg`, `.jpeg`, atau `.png`).
3. Tentukan ukuran grid $M$ (misalnya $M=3$ untuk 9 potongan, $M=4$ untuk 16 potongan).
4. Aktifkan/nonaktifkan fitur lanjutan:
   - Pola pasak/celah Jigsaw
   - Rotasi acak potongan
   - Augmentasi kecerahan & kontras
   - Penomoran potongan
5. Klik **Buat Puzzle**.
6. Periksa pratinjau bingkai dan potongan yang dihasilkan, lalu unduh berkas `.zip`.

### Menggunakan Puzzle Solver
1. Buka tab **Puzzle Solver** di menu navigasi sebelah kiri.
2. Unggah masukan puzzle melalui salah satu opsi:
   - **File ZIP**: Unggah berkas `.zip` hasil generator langsung.
   - **File Terpisah**: Unggah 1 citra `Bingkai.png` dan beberapa citra `Piece_*.png`.
3. Klik tombol **Susun Puzzle**.
4. Sistem akan mendeteksi grid, mencocokkan setiap potongan, dan menampilkan citra utuh yang telah direkonstruksi beserta waktu eksekusi dan metrik akurasinya.
5. Jika orientasi keseluruhan terbalik, gunakan tombol putar $90^\circ, 180^\circ,$ atau $270^\circ$.

