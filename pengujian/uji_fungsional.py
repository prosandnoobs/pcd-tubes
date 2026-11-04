"""
Pengujian fungsional Puzzle World (Dokumen Pengujian Tabel 3.1).

Membuat 12 folder fungsional/kasus_01 ... kasus_12. Setiap folder berisi:
  input/          berkas masukan kasus uji (bisa juga diunggah langsung ke aplikasi)
  output/         ZIP hasil Generator (khusus kasus Generator 1-3)
  keterangan.md   tujuan, langkah, dan hasil yang diharapkan
  hasil.txt       hasil pengamatan saat skrip dijalankan, beserta status Lulus/Gagal

Cara pakai (dari folder pcd-tubes):
  python pengujian/uji_fungsional.py
"""

import io
import random
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from generator import load_image, generate_puzzle  # noqa: E402
import solver as S                                # noqa: E402

OUT = Path(__file__).resolve().parent / "fungsional"
GAMBAR = ROOT / "image" / "landscape.jpeg"


def buat_puzzle(img, M, jigsaw, rotasi, augmentasi, nomor, seed):
    random.seed(seed)
    np.random.seed(seed)
    return generate_puzzle(img, M, jigsaw, rotasi, augmentasi, nomor, 0.18)


def isi_zip(zip_bytes):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


def tulis_input(folder, berkas, sub="input"):
    """berkas: dict {nama_file: bytes}"""
    d = folder / sub
    d.mkdir(parents=True, exist_ok=True)
    for nama, data in berkas.items():
        (d / nama).write_bytes(data)


def baca_input(folder, sub="input"):
    return [(p.name, p.read_bytes()) for p in sorted((folder / sub).iterdir())]


def pct(v):
    return f"{v * 100:.1f}%"


# ──────────────────────────────────────────────────────────────────────────────
# DEFINISI KASUS UJI
# ──────────────────────────────────────────────────────────────────────────────

KASUS = {
    1: ("Generator, citra RGB, M=4, semua fitur aktif",
        "Membuat puzzle 4 x 4 dari foto berwarna dengan jigsaw, rotasi, dan augmentasi aktif.",
        "ZIP berisi 1 Bingkai.png, 16 potongan, dan answer.json. Ukuran bingkai sama dengan citra (600 x 450)."),
    2: ("Generator dan solver, citra grayscale, M=3, jigsaw",
        "Membuat dan menyusun puzzle 3 x 3 dari foto hitam-putih.",
        "Mode grayscale tetap sampai hasil akhir (potongan LA, hasil L) dan puzzle tersusun benar."),
    3: ("Generator, fitur nomor potongan",
        "Membuat puzzle 3 x 3 dua kali dengan seed sama: sekali dengan nomor, sekali tanpa nomor.",
        "Isi potongan bernomor berbeda dari potongan tanpa nomor."),
    4: ("Solver, masukan ZIP, M=4, semua fitur aktif",
        "Mengunggah ZIP dari kasus 1 ke Puzzle Solver.",
        "M=4 terdeteksi dan citra tersusun dengan akurasi posisi dan rotasi 100%."),
    5: ("Solver, masukan file terpisah tanpa answer.json",
        "Mengunggah Bingkai.png dan 16 potongan sebagai file terpisah, tanpa answer.json.",
        "Solver tetap menyusun citra utuh berukuran 600 x 450; akurasi tidak dihitung karena tidak ada kunci jawaban."),
    6: ("Solver, file bingkai tidak bernama Bingkai",
        "Bingkai diberi nama acuan.png, lalu diunggah bersama 16 potongan.",
        "acuan.png dikenali sebagai bingkai dari isi citranya, dan 16 potongan terbaca."),
    7: ("Solver, 15 potongan (bukan kuadrat)",
        "Mengunggah Bingkai.png dan hanya 15 dari 16 potongan.",
        "Muncul pesan kesalahan bahwa jumlah potongan bukan bilangan kuadrat; aplikasi tidak berhenti."),
    8: ("Solver, hanya bingkai tanpa potongan",
        "Mengunggah Bingkai.png saja.",
        "Terbaca 0 potongan, sehingga aplikasi menampilkan pesan masukan belum lengkap."),
    9: ("Solver, tombol putar hasil 90 derajat",
        "Memutar citra hasil kasus 4 sebesar 90 derajat.",
        "Lebar dan tinggi citra bertukar: 600 x 450 menjadi 450 x 600."),
    10: ("Susun Manual, memulai permainan M=3",
         "Mengunggah ZIP puzzle 3 x 3 dengan rotasi ke Susun Manual.",
         "Grid 3 x 3 kosong dan 9 potongan berada di tray."),
    11: ("Susun Manual, seluruh potongan dipasang benar",
         "Memasang setiap potongan ke slot yang benar dengan arah yang benar, lalu menekan Periksa.",
         "Tray kosong, akurasi posisi dan rotasi 100%."),
    12: ("Susun Manual, melepas dan menukar dua potongan",
         "Dari susunan benar pada kasus 11, melepas potongan slot (0,0), lalu menukarnya dengan potongan slot (0,1).",
         "Potongan yang dilepas menjadi potongan terpilih (tidak terpasang); setelah ditukar, skor turun."),
}


def siapkan(img, gray_img):
    """Buat seluruh berkas masukan untuk 12 kasus."""
    p1 = buat_puzzle(img, 4, True, True, True, False, 1)
    berkas1 = isi_zip(p1["zip"])
    tulis_input(OUT / "kasus_01", {"landscape.jpeg": GAMBAR.read_bytes()})
    tulis_input(OUT / "kasus_01", {"Puzzle_4x4.zip": p1["zip"]}, "output")

    buf = io.BytesIO()
    Image.open(GAMBAR).convert("L").save(buf, "PNG")
    p2 = buat_puzzle(gray_img, 3, True, False, False, False, 2)
    tulis_input(OUT / "kasus_02", {"landscape_grayscale.png": buf.getvalue()})
    tulis_input(OUT / "kasus_02", {"Puzzle_3x3.zip": p2["zip"]}, "output")

    pn = buat_puzzle(img, 3, False, False, False, True, 3)
    pt = buat_puzzle(img, 3, False, False, False, False, 3)
    tulis_input(OUT / "kasus_03", {"landscape.jpeg": GAMBAR.read_bytes()})
    tulis_input(OUT / "kasus_03", {"dengan_nomor.zip": pn["zip"], "tanpa_nomor.zip": pt["zip"]}, "output")

    tulis_input(OUT / "kasus_04", {"Puzzle_4x4.zip": p1["zip"]})

    pieces = {n.split("/")[-1]: b for n, b in berkas1.items() if n.startswith("Pieces/")}
    tulis_input(OUT / "kasus_05", {"Bingkai.png": berkas1["Bingkai.png"], **pieces})
    tulis_input(OUT / "kasus_06", {"acuan.png": berkas1["Bingkai.png"], **pieces})
    lima_belas = dict(list(sorted(pieces.items()))[:15])
    tulis_input(OUT / "kasus_07", {"Bingkai.png": berkas1["Bingkai.png"], **lima_belas})
    tulis_input(OUT / "kasus_08", {"Bingkai.png": berkas1["Bingkai.png"]})
    tulis_input(OUT / "kasus_09", {"Puzzle_4x4.zip": p1["zip"]})

    pm = buat_puzzle(img, 3, False, True, False, False, 4)
    for k in (10, 11, 12):
        tulis_input(OUT / f"kasus_{k:02d}", {"Puzzle_3x3.zip": pm["zip"]})


# ──────────────────────────────────────────────────────────────────────────────
# PELAKSANAAN KASUS UJI
# ──────────────────────────────────────────────────────────────────────────────

def solve_folder(folder, rotasi=True, sub="input"):
    data = S.read_solver_input(baca_input(folder, sub))
    hasil = S.solve_puzzle(data["frame"][1], data["pieces"], allow_rotation=rotasi)
    return data, hasil


def pasang_semua_benar(game):
    ans = game["answer"]["pieces"]
    for k, p in enumerate(game["pieces"]):
        t = ans[p["name"]]
        p["rot"] = (360 - t["angle"]) % 360
        game["selected"] = k
        S.click_slot(game, t["row"], t["col"])


def jalankan(no):
    f = OUT / f"kasus_{no:02d}"
    if no == 1:
        zf = isi_zip((f / "output" / "Puzzle_4x4.zip").read_bytes())
        n_pot = sum(n.startswith("Pieces/") for n in zf)
        ukuran = Image.open(io.BytesIO(zf["Bingkai.png"])).size
        ok = "Bingkai.png" in zf and "answer.json" in zf and n_pot == 16 and ukuran == (600, 450)
        return ok, (f"Isi ZIP: Bingkai.png={'Bingkai.png' in zf}, potongan={n_pot}, "
                    f"answer.json={'answer.json' in zf}; ukuran bingkai {ukuran[0]} x {ukuran[1]}")
    if no == 2:
        zf = isi_zip((f / "output" / "Puzzle_3x3.zip").read_bytes())
        mode_pot = Image.open(io.BytesIO(next(b for n, b in zf.items() if n.startswith("Pieces/")))).mode
        data, hasil = solve_folder(f, rotasi=False, sub="output")
        mode_hasil = Image.open(io.BytesIO(hasil["image"])).mode
        e = S.evaluate(hasil["layout"], data["answer"], hasil["M"])
        (f / "hasil_solver.png").write_bytes(hasil["image"])
        ok = mode_pot == "LA" and mode_hasil == "L" and e["position"] == 1.0
        return ok, f"Mode potongan {mode_pot}, mode hasil {mode_hasil}, akurasi posisi {pct(e['position'])}"
    if no == 3:
        a = isi_zip((f / "output" / "dengan_nomor.zip").read_bytes())
        b = isi_zip((f / "output" / "tanpa_nomor.zip").read_bytes())
        beda = sum(a[n] != b[n] for n in a if n.startswith("Pieces/"))
        return beda == 9, f"{beda} dari 9 file potongan bernomor berbeda dari potongan tanpa nomor"
    if no in (4, 9):
        data, hasil = solve_folder(f)
        e = S.evaluate(hasil["layout"], data["answer"], hasil["M"])
        if no == 4:
            (f / "hasil_solver.png").write_bytes(hasil["image"])
            ok = hasil["M"] == 4 and e["position"] == 1.0 and e["rotation"] == 1.0
            return ok, (f"M terdeteksi {hasil['M']}, akurasi posisi {pct(e['position'])}, "
                        f"akurasi rotasi {pct(e['rotation'])}, rotasi global {e['global_rotation']} derajat")
        sebelum = Image.open(io.BytesIO(hasil["image"])).size
        diputar = S.rotate_result(hasil["image"], 90)
        sesudah = Image.open(io.BytesIO(diputar)).size
        (f / "sebelum_diputar.png").write_bytes(hasil["image"])
        (f / "sesudah_diputar.png").write_bytes(diputar)
        return sesudah == sebelum[::-1], f"{sebelum[0]} x {sebelum[1]} menjadi {sesudah[0]} x {sesudah[1]}"
    if no == 5:
        data, hasil = solve_folder(f)
        ukuran = Image.open(io.BytesIO(hasil["image"])).size
        (f / "hasil_solver.png").write_bytes(hasil["image"])
        ok = data["answer"] is None and hasil["M"] == 4 and ukuran == (600, 450)
        return ok, (f"answer.json tidak ada ({data['answer'] is None}), M terdeteksi {hasil['M']}, "
                    f"hasil berukuran {ukuran[0]} x {ukuran[1]}")
    if no == 6:
        data = S.read_solver_input(baca_input(f))
        ok = data["frame"][0] == "acuan.png" and len(data["pieces"]) == 16
        return ok, f"Bingkai dikenali: {data['frame'][0]}, potongan terbaca: {len(data['pieces'])}"
    if no == 7:
        data = S.read_solver_input(baca_input(f))
        try:
            S.solve_puzzle(data["frame"][1], data["pieces"], True)
            return False, "Tidak ada pesan kesalahan"
        except ValueError as e:
            return True, f"Pesan kesalahan: {e}"
    if no == 8:
        data = S.read_solver_input(baca_input(f))
        n = len(data["pieces"])
        return data["frame"] is not None and n == 0, (
            f"Bingkai terbaca, potongan terbaca {n}. Pada aplikasi, kondisi ini menampilkan pesan "
            f"'Input belum lengkap: dibutuhkan 1 citra bingkai dan minimal 1 potongan.'")
    game = S.new_game(S.read_solver_input(baca_input(f)))
    if no == 10:
        kosong = all(k is None for row in game["grid"] for k in row)
        n = len(S.tray(game))
        return game["M"] == 3 and kosong and n == 9, f"M={game['M']}, grid kosong={kosong}, tray berisi {n} potongan"
    pasang_semua_benar(game)
    if no == 11:
        e = S.check_game(game)
        n = len(S.tray(game))
        ok = n == 0 and e["position"] == 1.0 and e["rotation"] == 1.0
        return ok, f"Tray berisi {n} potongan, akurasi posisi {pct(e['position'])}, akurasi rotasi {pct(e['rotation'])}"
    a, b = game["grid"][0][0], game["grid"][0][1]
    game["selected"] = None
    S.click_slot(game, 0, 0)                     # lepas potongan slot (0,0)
    lepas = game["selected"] == a and game["grid"][0][0] is None
    S.click_slot(game, 0, 1)                     # pasang ke slot (0,1), potongan lama terpilih
    S.click_slot(game, 0, 0)                     # pasang potongan lama ke slot (0,0)
    tukar = game["grid"][0][0] == b and game["grid"][0][1] == a
    e = S.check_game(game)
    ok = lepas and tukar and e["position"] < 1.0
    return ok, (f"Potongan dilepas menjadi potongan terpilih: {lepas}; dua potongan tertukar: {tukar}; "
                f"setelah ditukar akurasi posisi {pct(e['position'])}")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    img, _, _ = load_image(GAMBAR.read_bytes())
    buf = io.BytesIO()
    Image.open(GAMBAR).convert("L").save(buf, "PNG")
    gray_img, _, _ = load_image(buf.getvalue())
    siapkan(img, gray_img)

    ringkasan = ["| No | Kasus Uji | Hasil Pengamatan | Status |", "| --- | --- | --- | --- |"]
    for no, (judul, langkah, harapan) in KASUS.items():
        f = OUT / f"kasus_{no:02d}"
        (f / "keterangan.md").write_text(
            f"# Kasus {no}: {judul}\n\n**Langkah:** {langkah}\n\n**Hasil yang diharapkan:** {harapan}\n\n"
            f"**Berkas masukan:** folder `input/`, bisa diunggah langsung ke aplikasi. "
            f"Folder `output/` (jika ada) berisi ZIP yang dihasilkan Generator.\n",
            encoding="utf-8")
        ok, amatan = jalankan(no)
        status = "Lulus" if ok else "Gagal"
        (f / "hasil.txt").write_text(f"Kasus {no}: {judul}\nHasil pengamatan: {amatan}\nStatus: {status}\n",
                                     encoding="utf-8")
        ringkasan.append(f"| {no} | {judul} | {amatan} | {status} |")
        print(f"Kasus {no:2d} {status}: {amatan}", flush=True)
    (OUT / "ringkasan.md").write_text("# Hasil Pengujian Fungsional\n\n" + "\n".join(ringkasan) + "\n",
                                      encoding="utf-8")


if __name__ == "__main__":
    main()
