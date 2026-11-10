# Pencarian Ruang Kelas POLINES

Aplikasi web sederhana untuk mencari ruang kelas yang kosong di Politeknik Negeri Semarang (POLINES), dibangun dengan **Streamlit** dan **SQLite**. Tanpa login.

> Data yang digunakan adalah **data simulasi**, bukan jadwal resmi POLINES.

## Fitur

- **Pencarian ruang kelas**: filter lantai, gedung, tanggal, jam mulai, jam selesai, dan kapasitas minimum.
- **Deteksi bentrok jadwal**: ruang ditampilkan hanya jika tidak ada jadwal kuliah yang bertabrakan.
- **Dashboard**: total ruang, ketersediaan per gedung, grafik, dan penggunaan ruangan hari ini.
- **Data dosen dan jadwal mata kuliah** dalam tab terpisah.
- **Riwayat pencarian** tersimpan otomatis di tabel `pencarian_kelas`.

## Struktur Database

| Tabel | Keterangan |
|---|---|
| `gedung` | Data gedung kampus |
| `ruang_kelas` | Data ruang kelas (kode, kapasitas, lantai, gedung) |
| `dosen` | Data dosen |
| `jadwal_kuliah` | Jadwal mata kuliah beserta dosen dan ruang |
| `pengguna` | Data pengguna contoh |
| `pencarian_kelas` | Log setiap pencarian yang dilakukan |

Data contoh: 3 gedung, 24 ruang kelas, 10 dosen, 5 jadwal kuliah, 1 pengguna.

## Menjalankan Aplikasi

```bash
# 1. Buat virtual environment
python -m venv venv

# 2. Aktifkan (Windows)
venv\Scripts\activate
# (Linux/macOS: source venv/bin/activate)

# 3. Install dependensi
pip install -r requirements.txt

# 4. Jalankan
streamlit run app.py
```

Lalu buka http://localhost:8501.

Database `ruang_kelas.db` akan dibuat otomatis beserta data contohnya saat aplikasi pertama kali dijalankan.

## Aturan Bentrok Jadwal

Sebuah jadwal dianggap bentrok bila:

```text
jam_mulai_pencarian < jam_selesai_jadwal  DAN  jam_selesai_pencarian > jam_mulai_jadwal
```

Jadwal yang tepat bersebelahan (misalnya jadwal selesai 10:00 dan pencarian mulai 10:00) **tidak** dianggap bentrok.
