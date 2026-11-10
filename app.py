# ============================================================
# Pencarian Ruang Kelas Kosong POLINES
# Streamlit + SQLite — Kelompok 2 (tanpa login)
# Data: simulasi, bukan data resmi POLINES
# ============================================================
import sqlite3
from datetime import date, time
import pandas as pd
import streamlit as st

DB_PATH = "ruang_kelas.db"

# ---------------- Database ----------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS gedung (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_gedung TEXT UNIQUE NOT NULL,
        lokasi TEXT
    );
    CREATE TABLE IF NOT EXISTS ruang_kelas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kode_ruang TEXT UNIQUE NOT NULL,
        nama_ruang TEXT,
        kapasitas INTEGER NOT NULL,
        lantai INTEGER NOT NULL,
        gedung_id INTEGER NOT NULL REFERENCES gedung(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS dosen (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_dosen TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS jadwal_kuliah (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mata_kuliah TEXT NOT NULL,
        hari TEXT NOT NULL,
        jam_mulai TEXT NOT NULL,
        jam_selesai TEXT NOT NULL,
        dosen_id INTEGER NOT NULL REFERENCES dosen(id),
        ruang_id INTEGER NOT NULL REFERENCES ruang_kelas(id)
    );
    CREATE TABLE IF NOT EXISTS pengguna (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        peran TEXT DEFAULT 'mahasiswa'
    );
    CREATE TABLE IF NOT EXISTS pencarian_kelas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal_pencarian TEXT,
        gedung_id INTEGER,
        lantai INTEGER,
        jam_mulai TEXT,
        jam_selesai TEXT,
        kapasitas_min INTEGER,
        jumlah_hasil INTEGER,
        waktu_pencarian TEXT
    );
    """)
    conn.commit()

    # --- Data contoh (sesuai PDF: 3 gedung, 24 ruang, 10 dosen, 5 jadwal, 1 pengguna) ---
    gedung = [
        ("Gedung A", "Sayap Barat Kampus"),
        ("Gedung B", "Sayap Timur Kampus"),
        ("Gedung C", "Gedung Tengah Kampus"),
    ]
    for g, l in gedung:
        cur.execute("INSERT OR IGNORE INTO gedung (nama_gedung, lokasi) VALUES (?,?)", (g, l))
    conn.commit()

    gmap = {r["nama_gedung"]: r["id"] for r in conn.execute("SELECT * FROM gedung")}
    if conn.execute("SELECT COUNT(*) c FROM ruang_kelas").fetchone()["c"] == 0:
        # A: 9 ruang (A101..A301), B: 8 ruang (B101..B204), C: 7 ruang (C101..C203)
        ruang = []
        for lantai in (1, 2, 3):
            for i in (1, 2, 3):
                ruang.append((f"A{lantai}0{i}", f"Ruang A{lantai}0{i}", 20 + lantai * 5 + i * 2, lantai, gmap["Gedung A"]))
        for lantai in (1, 2):
            for i in (1, 2, 3, 4):
                ruang.append((f"B{lantai}0{i}", f"Ruang B{lantai}0{i}", 18 + lantai * 4 + i * 3, lantai, gmap["Gedung B"]))
        for lantai in (1, 2):
            for i in (1, 2, 3):
                ruang.append((f"C{lantai}0{i}", f"Ruang C{lantai}0{i}", 22 + lantai * 3 + i * 2, lantai, gmap["Gedung C"]))
        # 1 ruang lagi Gedung C lantai 3 supaya total 24: 9+8+7
        ruang.append(("C301", "Ruang C301", 30, 3, gmap["Gedung C"]))
        cur.executemany(
            "INSERT OR IGNORE INTO ruang_kelas (kode_ruang, nama_ruang, kapasitas, lantai, gedung_id) VALUES (?,?,?,?,?)",
            ruang,
        )
        conn.commit()

    if conn.execute("SELECT COUNT(*) c FROM dosen").fetchone()["c"] == 0:
        for huruf in "ABCDEFGHIJ":
            cur.execute("INSERT OR IGNORE INTO dosen (nama_dosen) VALUES (?)", (f"Dosen {huruf}",))
        conn.commit()

    dmap = {r["nama_dosen"]: r["id"] for r in conn.execute("SELECT * FROM dosen")}
    rmap = {r["kode_ruang"]: r["id"] for r in conn.execute("SELECT * FROM ruang_kelas")}
    if conn.execute("SELECT COUNT(*) c FROM jadwal_kuliah").fetchone()["c"] == 0:
        jadwal = [
            ("Pengantar Bisnis", "Senin", "08:00", "10:00", dmap["Dosen A"], rmap["A101"]),
            ("Manajemen", "Senin", "10:00", "12:00", dmap["Dosen B"], rmap["A102"]),
            ("Administrasi Bisnis", "Selasa", "08:00", "12:00", dmap["Dosen C"], rmap["B101"]),
            ("Komunikasi Bisnis", "Rabu", "13:00", "15:00", dmap["Dosen A"], rmap["A201"]),
            ("Kewirausahaan", "Kamis", "09:00", "11:00", dmap["Dosen B"], rmap["C101"]),
        ]
        cur.executemany(
            "INSERT INTO jadwal_kuliah (mata_kuliah, hari, jam_mulai, jam_selesai, dosen_id, ruang_id) VALUES (?,?,?,?,?,?)",
            jadwal,
        )
        conn.commit()

    if conn.execute("SELECT COUNT(*) c FROM pengguna").fetchone()["c"] == 0:
        cur.execute("INSERT INTO pengguna (nama, peran) VALUES (?,?)", ("Contoh Pengguna", "mahasiswa"))
        conn.commit()
    conn.close()

# ---------------- Helper pencarian ----------------
HARI_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

def cari_ruang_kosong(gedung_id=None, lantai=None, tgl=None, jam_mulai="10:00", jam_selesai="12:00", kap_min=0):
    """Ruaangan ditampilkan jika tidak ada jadwal bentrok.
    Bentrok: jam_mulai < selesai_jadwal DAN jam_selesai > mulai_jadwal (tepat bersebelahan = tidak bentrok)."""
    conn = get_conn()
    hari = HARI_ID[tgl.weekday()] if tgl else None
    query = """
        SELECT r.kode_ruang, r.nama_ruang, r.kapasitas, r.lantai, g.nama_gedung
        FROM ruang_kelas r JOIN gedung g ON g.id = r.gedung_id
        WHERE r.kapasitas >= ?
          AND NOT EXISTS (
            SELECT 1 FROM jadwal_kuliah j
            WHERE j.ruang_id = r.id AND j.hari = ?
              AND ? < j.jam_selesai AND ? > j.jam_mulai
          )
    """
    params = [kap_min, hari, jam_mulai, jam_selesai]
    if gedung_id:
        query += " AND r.gedung_id = ?"; params.append(gedung_id)
    if lantai:
        query += " AND r.lantai = ?"; params.append(lantai)
    query += " ORDER BY g.nama_gedung, r.lantai, r.kode_ruang"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def simpan_pencarian(gedung_id, lantai, tgl, jam_mulai, jam_selesai, kap_min, jumlah):
    conn = get_conn()
    conn.execute(
        "INSERT INTO pencarian_kelas (tanggal_pencarian, gedung_id, lantai, jam_mulai, jam_selesai, kapasitas_min, jumlah_hasil, waktu_pencarian) "
        "VALUES (?,?,?,?,?,?,?, datetime('now','localtime'))",
        (tgl.isoformat() if tgl else None, gedung_id, lantai, jam_mulai, jam_selesai, kap_min, jumlah),
    )
    conn.commit()
    conn.close()

def load_df(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df

# ---------------- App ----------------
init_db()

st.set_page_config(page_title="Pencarian Ruang Kelas POLINES", page_icon="🏫", layout="wide")
st.title("🏫 Selamat Datang — Sistem Informasi Ruang Kelas POLINES")
st.caption("Temukan ruang kelas yang tersedia dan lihat informasi dosen serta jadwal mata kuliah dalam satu halaman. (Data simulasi)")

conn = get_conn()
n_gedung = conn.execute("SELECT COUNT(*) c FROM gedung").fetchone()["c"]
n_ruang = conn.execute("SELECT COUNT(*) c FROM ruang_kelas").fetchone()["c"]
n_dosen = conn.execute("SELECT COUNT(*) c FROM dosen").fetchone()["c"]
n_jadwal = conn.execute("SELECT COUNT(*) c FROM jadwal_kuliah").fetchone()["c"]
conn.close()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Gedung", n_gedung); m2.metric("Ruang Kelas", n_ruang)
m3.metric("Dosen", n_dosen); m4.metric("Jadwal Kuliah", n_jadwal)

st.divider()

# ---- Form pencarian ----
st.header("🔍 Pencarian Ruang Kelas")
st.subheader("Kriteria Pencarian")

gedung_df = load_df("SELECT * FROM gedung ORDER BY nama_gedung")
pilihan_gedung = {"Semua Gedung": None}
for _, r in gedung_df.iterrows():
    pilihan_gedung[r["nama_gedung"]] = int(r["id"])

with st.form("form_cari"):
    lantai_pil = st.radio(
        "Pilih Lantai",
        ["Semua Lantai", "1", "2", "3"],
        horizontal=True, index=0,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        gedung_pil = st.selectbox("Pilih Gedung", list(pilihan_gedung.keys()))
    with c2:
        jam_m = st.text_input("Jam mulai", value="10:00")
    with c3:
        kap_min = st.number_input("Kapasitas minimal mahasiswa", min_value=0, value=20, step=1)
    c4, c5 = st.columns(2)
    with c4:
        tgl = st.date_input("Tanggal penggunaan", value=date.today())
    with c5:
        jam_s = st.text_input("Jam selesai", value="12:00")
    cari = st.form_submit_button("🔎 Cari Ruang Kelas", type="primary", use_container_width=True)

if cari:
    if jam_m >= jam_s:
        st.error("Jam mulai harus lebih kecil dari jam selesai.")
    else:
        lantai = None if lantai_pil == "Semua Lantai" else int(lantai_pil)
        hasil = cari_ruang_kosong(pilihan_gedung[gedung_pil], lantai, tgl, jam_m, jam_s, int(kap_min))
        simpan_pencarian(pilihan_gedung[gedung_pil], lantai, tgl, jam_m, jam_s, int(kap_min), len(hasil))
        st.session_state["hasil"] = hasil
        st.session_state["kriteria"] = f"{HARI_ID[tgl.weekday()]}, {tgl} pukul {jam_m}–{jam_s} | {gedung_pil} | {lantai_pil} | kapasitas ≥ {kap_min}"

if "hasil" in st.session_state:
    hasil = st.session_state["hasil"]
    st.subheader(f"Hasil pencarian ({st.session_state.get('kriteria', '')})")
    st.write(f"**{len(hasil)} ruang kosong ditemukan.**")
    if hasil.empty:
        st.warning("Tidak ada ruang yang memenuhi kriteria / semua bentrok jadwal.")
    else:
        st.dataframe(hasil, hide_index=True, use_container_width=True)
        with st.expander("Detail ruang yang tersedia"):
            for _, r in hasil.iterrows():
                st.markdown(f"- **{r['kode_ruang']}** — {r['nama_ruang']} | {r['nama_gedung']} lantai {r['lantai']} | kapasitas {r['kapasitas']}")

st.divider()

# ---- Dashboard ----
st.header("📊 Dashboard Ruang Kelas")
# Hari default = hari dari tanggal hari ini
hari_ini = HARI_ID[date.today().weekday()]
if "hasil" in st.session_state:
    df_pakai = load_df(
        "SELECT r.kode_ruang, g.nama_gedung FROM ruang_kelas r JOIN gedung g ON g.id=r.gedung_id "
    )
    ruang_terpakai = set(load_df(
        "SELECT DISTINCT r.kode_ruang FROM jadwal_kuliah j JOIN ruang_kelas r ON r.id=j.ruang_id WHERE j.hari=?", (hari_ini,)
    )["kode_ruang"])
    df_pakai["status"] = df_pakai["kode_ruang"].apply(lambda k: "Terpakai" if k in ruang_terpakai else "Tersedia")
else:
    df_pakai = load_df(
        "SELECT r.kode_ruang, g.nama_gedung FROM ruang_kelas r JOIN gedung g ON g.id=r.gedung_id"
    )
    df_pakai["status"] = "Tersedia"

ringkas = df_pakai.groupby(["nama_gedung", "status"]).size().reset_index(name="jumlah")
ringkas = ringkas.pivot_table(index="nama_gedung", columns="status", values="jumlah", fill_value=0)
for col in ("Tersedia", "Terpakai"):
    if col not in ringkas.columns:
        ringkas[col] = 0
ringkas["Total"] = ringkas["Tersedia"] + ringkas["Terpakai"]
ringkas = ringkas.reset_index().rename(columns={"nama_gedung": "Gedung"})

total = int(ringkas["Total"].sum())
tersedia = int(ringkas["Tersedia"].sum())
terpakai = int(ringkas["Terpakai"].sum())
d1, d2, d3 = st.columns(3)
d1.metric("Total Ruang", total); d2.metric("Tersedia", tersedia); d3.metric("Terpakai", terpakai)

g1, g2 = st.columns(2)
with g1:
    st.subheader("Grafik Ketersediaan per Gedung")
    st.bar_chart(ringkas.set_index("Gedung")[["Tersedia", "Terpakai"]])
with g2:
    st.subheader("Ringkasan per Gedung")
    st.dataframe(ringkas[["Gedung", "Total", "Tersedia", "Terpakai"]], hide_index=True)

st.subheader(f"Penggunaan Ruangan — {hari_ini}")
jadwal_hari = load_df("""
    SELECT j.jam_mulai || '-' || j.jam_selesai AS Jam, j.mata_kuliah AS "Mata Kuliah",
           d.nama_dosen AS Dosen, r.kode_ruang AS Ruang, g.nama_gedung AS Gedung, r.lantai AS Lantai
    FROM jadwal_kuliah j JOIN dosen d ON d.id=j.dosen_id
    JOIN ruang_kelas r ON r.id=j.ruang_id JOIN gedung g ON g.id=r.gedung_id
    WHERE j.hari=? ORDER BY j.jam_mulai
""", (hari_ini,))
st.dataframe(jadwal_hari, hide_index=True, use_container_width=True)

st.divider()

# ---- Data dosen & jadwal ----
st.header("Data Dosen dan Jadwal Mata Kuliah")
tab1, tab2 = st.tabs(["Data Dosen", "Jadwal Mata Kuliah"])
with tab1:
    st.dataframe(load_df("SELECT id AS \"ID Dosen\", nama_dosen AS \"Nama Dosen\" FROM dosen"), hide_index=True, use_container_width=True)
with tab2:
    st.dataframe(load_df("""
        SELECT j.hari AS Hari, j.jam_mulai || '-' || j.jam_selesai AS Jam,
               j.mata_kuliah AS "Mata Kuliah", d.nama_dosen AS Dosen,
               r.kode_ruang AS Ruang, g.nama_gedung AS Gedung, r.lantai AS Lantai
        FROM jadwal_kuliah j JOIN dosen d ON d.id=j.dosen_id
        JOIN ruang_kelas r ON r.id=j.ruang_id JOIN gedung g ON g.id=r.gedung_id
        ORDER BY j.hari, j.jam_mulai
    """), hide_index=True, use_container_width=True)

with st.expander("Tentang Sistem dan Cara Kerja Aplikasi"):
    st.markdown("""
1. Pilih lantai, gedung, tanggal, jam mulai, jam selesai, dan kapasitas minimum.
2. Tekan **Cari Ruang Kelas**.
3. Aplikasi menyaring ruang menurut gedung, lantai, dan kapasitas.
4. Aplikasi membandingkan hari serta rentang waktu pencarian dengan jadwal mata kuliah di setiap ruang. Ruang ditampilkan jika tidak ada jadwal yang bertabrakan.

**Aturan bentrokan jadwal:** Jadwal dianggap bentrok jika waktu pencarian dimulai sebelum jadwal kuliah selesai dan berakhir setelah jadwal kuliah dimulai. Jadwal yang tepat bersebelahan tanpa tumpang tindih tidak dianggap bentrok.
""")

with st.expander("Ringkasan Data Aplikasi"):
    st.markdown("""
- Gedung: 3 data contoh
- Ruang kelas: 24 data contoh
- Dosen: 10 data contoh
- Jadwal kuliah: 5 data contoh
- Pengguna: 1 data contoh
- Tabel `pencarian_kelas` mencatat setiap pencarian yang dilakukan pengguna.
""")

st.caption("Catatan: Data di atas adalah data simulasi, bukan jadwal resmi POLINES.")
