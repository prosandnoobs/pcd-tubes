"""
Pengujian kinerja Puzzle Solver (Dokumen Pengujian BAB 3.2 - 3.5).

Skenario: 2 gambar x 7 nilai M x 5 konfigurasi x 3 seed = 210 pengujian.
Setiap baris hasil disimpan ke kinerja/hasil_kinerja.csv, ringkasannya ke
kinerja/ringkasan.txt.

Cara pakai (dari folder pcd-tubes):
  python pengujian/uji_kinerja.py
      menjalankan seluruh 210 pengujian.
  python pengujian/uji_kinerja.py --gambar pohon --M 10 --konfigurasi Rotasi --seed 11
      menjalankan ulang satu pengujian saja dan menyimpan ZIP puzzle serta citra
      hasil solver ke kinerja/bukti/, untuk dibuka di aplikasi atau dilihat langsung.
"""

import argparse
import csv
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from generator import load_image, generate_puzzle          # noqa: E402
from solver import read_solver_input, solve_puzzle, evaluate  # noqa: E402

GAMBAR = {"landscape": ROOT / "image" / "landscape.jpeg", "pohon": ROOT / "image" / "pohon.jpeg"}
M_LIST = (2, 3, 4, 5, 6, 8, 10)
SEEDS = (11, 22, 33)
KONFIGURASI = {  # jigsaw, rotasi, augmentasi
    "Polos": (False, False, False),
    "Jigsaw": (True, False, False),
    "Rotasi": (False, True, False),
    "Augmentasi": (False, False, True),
    "Semua": (True, True, True),
}
OUT = Path(__file__).resolve().parent / "kinerja"


def satu_uji(img, M, konfigurasi, seed):
    """Buat puzzle dengan seed tetap, susun dengan solver, lalu nilai hasilnya."""
    jigsaw, rotasi, augmentasi = KONFIGURASI[konfigurasi]
    random.seed(seed)
    np.random.seed(seed)
    puzzle = generate_puzzle(img, M, jigsaw, rotasi, augmentasi, False, 0.18)
    data = read_solver_input([("puzzle.zip", puzzle["zip"])])
    t0 = time.perf_counter()
    hasil = solve_puzzle(data["frame"][1], data["pieces"], allow_rotation=rotasi)
    waktu = time.perf_counter() - t0
    nilai = evaluate(hasil["layout"], data["answer"], hasil["M"])
    return puzzle, hasil, nilai, waktu


def ringkas(rows):
    pct = lambda v: f"{v * 100:.1f}".replace(".", ",")
    lines = [f"Jumlah pengujian: {len(rows)}"]
    sempurna = [r for r in rows if r["tetangga"] == 1.0]
    lines.append(f"Tersusun sempurna: {len(sempurna)} dari {len(rows)} ({pct(len(sempurna) / len(rows))}%)")
    lines.append(f"M terdeteksi benar: {sum(r['M'] == r['M_terdeteksi'] for r in rows)} dari {len(rows)}")
    terlama = max(rows, key=lambda r: r["waktu_detik"])
    lines.append(f"Waktu solver terlama: {terlama['waktu_detik']:.2f} detik "
                 f"({terlama['gambar']}, M={terlama['M']}, {terlama['konfigurasi']}, seed {terlama['seed']})")
    lines.append("")
    lines.append("Tersusun sempurna per konfigurasi:")
    for k in KONFIGURASI:
        rs = [r for r in rows if r["konfigurasi"] == k]
        n = sum(r["tetangga"] == 1.0 for r in rs)
        lines.append(f"  {k:<11} {n:>3} dari {len(rs)} ({pct(n / len(rs))}%)")
    for kolom, judul in (("tetangga", "Rata-rata akurasi tetangga (%)"),
                         ("posisi", "Rata-rata akurasi posisi (%)"),
                         ("waktu_detik", "Rata-rata waktu solver (detik)")):
        lines.append("")
        lines.append(judul + ":")
        lines.append("  " + f"{'':<11}" + "".join(f"{'M=' + str(m):>8}" for m in M_LIST))
        for k in KONFIGURASI:
            sel = []
            for m in M_LIST:
                rs = [r[kolom] for r in rows if r["konfigurasi"] == k and r["M"] == m]
                v = sum(rs) / len(rs)
                sel.append(f"{v:.2f}".replace(".", ",") if kolom == "waktu_detik" else pct(v))
            lines.append(f"  {k:<11}" + "".join(f"{s:>8}" for s in sel))
    return "\n".join(lines)


def jalankan_semua():
    OUT.mkdir(exist_ok=True)
    rows = []
    for nama, path in GAMBAR.items():
        img, w, h = load_image(path.read_bytes())
        print(f"{nama}: {w}x{h} -> {img['w']}x{img['h']}", flush=True)
        for M in M_LIST:
            for k in KONFIGURASI:
                for seed in SEEDS:
                    _, hasil, nilai, waktu = satu_uji(img, M, k, seed)
                    rows.append({"gambar": nama, "M": M, "konfigurasi": k, "seed": seed,
                                 "M_terdeteksi": hasil["M"], "tetangga": nilai["neighbor"],
                                 "posisi": nilai["position"], "rotasi": nilai["rotation"],
                                 "rotasi_global": nilai["global_rotation"], "waktu_detik": round(waktu, 3)})
            print(f"  M={M} selesai", flush=True)
    with open(OUT / "hasil_kinerja.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    teks = ringkas(rows)
    (OUT / "ringkasan.txt").write_text(teks, encoding="utf-8")
    print(teks)


def jalankan_satu(nama, M, k, seed):
    img, _, _ = load_image(GAMBAR[nama].read_bytes())
    puzzle, hasil, nilai, waktu = satu_uji(img, M, k, seed)
    folder = OUT / "bukti"
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{nama}_M{M}_{k}_seed{seed}"
    (folder / f"{stem}_puzzle.zip").write_bytes(puzzle["zip"])
    (folder / f"{stem}_hasil.png").write_bytes(hasil["image"])
    print(f"{stem}: tetangga {nilai['neighbor'] * 100:.1f}%, posisi {nilai['position'] * 100:.1f}%, "
          f"rotasi {nilai['rotation'] * 100:.1f}%, rotasi global {nilai['global_rotation']} derajat, "
          f"waktu {waktu:.2f} detik")
    print(f"Disimpan ke {folder}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gambar", choices=GAMBAR)
    ap.add_argument("--M", type=int, choices=M_LIST)
    ap.add_argument("--konfigurasi", choices=KONFIGURASI)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    if a.gambar and a.M and a.konfigurasi:
        jalankan_satu(a.gambar, a.M, a.konfigurasi, a.seed)
    else:
        jalankan_semua()
