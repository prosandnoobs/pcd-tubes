# Bukti Pengujian Puzzle World

Folder ini berisi skrip dan bukti untuk Dokumen Pengujian. Semua perintah dijalankan dari folder `pcd-tubes`.

## Pengujian fungsional (Tabel 3.1)

```
python pengujian/uji_fungsional.py
```

Membuat ulang folder `fungsional/kasus_01` sampai `kasus_12`, lalu menjalankan setiap kasus. Isi tiap folder:

- `keterangan.md`: kasus uji, langkah, dan hasil yang diharapkan.
- `input/`: berkas masukan. Berkas ini juga bisa diunggah langsung ke aplikasi untuk peragaan.
- `output/`: ZIP yang dihasilkan Generator (kasus 1 sampai 3).
- `hasil.txt`: hasil pengamatan dan status Lulus/Gagal.

Rangkuman seluruh kasus ada di `fungsional/ringkasan.md`.

## Pengujian kinerja (Tabel 3.2 sampai 3.11)

```
python pengujian/uji_kinerja.py
```

Menjalankan 210 pengujian: 2 gambar (`image/landscape.jpeg`, `image/pohon.jpeg`) x 7 nilai M x 5 konfigurasi x 3 seed (11, 22, 33). Hasilnya:

- `kinerja/hasil_kinerja.csv`: satu baris per pengujian.
- `kinerja/ringkasan.txt`: jumlah tersusun sempurna, rata-rata akurasi, dan waktu per konfigurasi dan per M.

Seed tetap membuat potongan yang dihasilkan selalu sama, sehingga akurasi bisa diulang dengan hasil yang sama. Waktu proses bergantung pada komputer yang dipakai.

Untuk membuktikan satu baris tertentu, jalankan ulang pengujian itu saja:

```
python pengujian/uji_kinerja.py --gambar pohon --M 10 --konfigurasi Rotasi --seed 11
```

Perintah ini menyimpan ZIP puzzle dan citra hasil solver ke `kinerja/bukti/`. ZIP tersebut bisa diunggah ke halaman Puzzle Solver di aplikasi untuk melihat hasilnya secara langsung.
