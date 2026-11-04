# Hasil Pengujian Fungsional

| No | Kasus Uji | Hasil Pengamatan | Status |
| --- | --- | --- | --- |
| 1 | Generator, citra RGB, M=4, semua fitur aktif | Isi ZIP: Bingkai.png=True, potongan=16, answer.json=True; ukuran bingkai 600 x 450 | Lulus |
| 2 | Generator dan solver, citra grayscale, M=3, jigsaw | Mode potongan LA, mode hasil L, akurasi posisi 100.0% | Lulus |
| 3 | Generator, fitur nomor potongan | 9 dari 9 file potongan bernomor berbeda dari potongan tanpa nomor | Lulus |
| 4 | Solver, masukan ZIP, M=4, semua fitur aktif | M terdeteksi 4, akurasi posisi 100.0%, akurasi rotasi 100.0%, rotasi global 180 derajat | Lulus |
| 5 | Solver, masukan file terpisah tanpa answer.json | answer.json tidak ada (True), M terdeteksi 4, hasil berukuran 600 x 450 | Lulus |
| 6 | Solver, file bingkai tidak bernama Bingkai | Bingkai dikenali: acuan.png, potongan terbaca: 16 | Lulus |
| 7 | Solver, 15 potongan (bukan kuadrat) | Pesan kesalahan: Jumlah potongan (15) bukan bilangan kuadrat dan grid bingkai tidak terdeteksi. | Lulus |
| 8 | Solver, hanya bingkai tanpa potongan | Bingkai terbaca, potongan terbaca 0. Pada aplikasi, kondisi ini menampilkan pesan 'Input belum lengkap: dibutuhkan 1 citra bingkai dan minimal 1 potongan.' | Lulus |
| 9 | Solver, tombol putar hasil 90 derajat | 600 x 450 menjadi 450 x 600 | Lulus |
| 10 | Susun Manual, memulai permainan M=3 | M=3, grid kosong=True, tray berisi 9 potongan | Lulus |
| 11 | Susun Manual, seluruh potongan dipasang benar | Tray berisi 0 potongan, akurasi posisi 100.0%, akurasi rotasi 100.0% | Lulus |
| 12 | Susun Manual, melepas dan menukar dua potongan | Potongan dilepas menjadi potongan terpilih: True; dua potongan tertukar: True; setelah ditukar akurasi posisi 77.8% | Lulus |
