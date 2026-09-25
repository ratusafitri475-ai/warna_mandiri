from functools import wraps
from pprint import pp
from flask import Flask, render_template, request, redirect, session, url_for
import json
import os
import uuid
from datetime import datetime
from urllib.parse import quote
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("WARNA_MANDIRI_SECRET", "warna-mandiri-local-secret")


# =========================================================
# PENGATURAN FOLDER
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Folder untuk gambar barang
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
BUKTI_FOLDER = os.path.join(UPLOAD_FOLDER, "bukti_pembayaran")

# Folder khusus untuk logo website
LOGO_FOLDER = os.path.join(BASE_DIR, "static", "images")

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["BUKTI_FOLDER"] = BUKTI_FOLDER
app.config["LOGO_FOLDER"] = LOGO_FOLDER


# Membuat folder jika belum tersedia
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(BUKTI_FOLDER):
    os.makedirs(BUKTI_FOLDER)

if not os.path.exists(LOGO_FOLDER):
    os.makedirs(LOGO_FOLDER)


# =========================================================
# NAMA FILE JSON
# =========================================================

DATA_FILE = os.path.join(BASE_DIR, "data_barang.json")
PENGATURAN_FILE = os.path.join(BASE_DIR, "pengaturan.json")
PESANAN_FILE = os.path.join(BASE_DIR, "pesanan.json")
ALAMAT_TOKO = "Jl. Opu Daeng Risadju No.204/214, Mario, Kec. Mariso, Kota Makassar, Sulawesi Selatan 90125"
METODE_PEMBAYARAN = ("Cash", "BNI", "BCA", "MANDIRI", "QRIS")
METODE_LAMA = ("Transfer",)
PEMILIK_REKENING = "MUH SYAFWAN ZHAFRAN"
WHATSAPP_ADMIN = "081244759936"
REKENING_PEMBAYARAN = (
    {"bank": "BNI", "nomor": "2006122112"},
    {"bank": "BCA", "nomor": "7058024896"},
    {"bank": "MANDIRI", "nomor": "1740010995777"}
)
QRIS_FILENAME = "qris.png"
ADMIN_PASSWORD = os.environ.get("WARNA_MANDIRI_ADMIN_PASSWORD", "admin123")
ADMIN_ENDPOINTS = {
    "index",
    "tambah_barang",
    "detail_barang",
    "edit_barang",
    "hapus_barang",
    "hapus_pesanan",
    "ubah_status_pesanan",
    "upload_logo",
    "upload_qris"
}


# =========================================================
# FUNGSI MEMBACA DATA BARANG
# =========================================================

def baca_data():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        data_barang = json.load(file)

    return data_barang


# =========================================================
# FUNGSI MENYIMPAN DATA BARANG
# =========================================================

def simpan_data(data_barang):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(
            data_barang,
            file,
            indent=4,
            ensure_ascii=False
        )


# =========================================================
# FUNGSI MEMBACA PENGATURAN
# =========================================================

def baca_pengaturan():

    # Jika pengaturan.json belum ada
    if not os.path.exists(PENGATURAN_FILE):

        # Membuat pengaturan awal
        pengaturan = {
            "logo": ""
        }

        with open(
            PENGATURAN_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                pengaturan,
                file,
                indent=4
            )

        return pengaturan

    # Membaca pengaturan yang sudah ada
    with open(
        PENGATURAN_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        pengaturan = json.load(file)

    return pengaturan


# =========================================================
# FUNGSI MENYIMPAN PENGATURAN
# =========================================================

def simpan_pengaturan(pengaturan):

    with open(
        PENGATURAN_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            pengaturan,
            file,
            indent=4,
            ensure_ascii=False
        )


def baca_pesanan():
    if not os.path.exists(PESANAN_FILE):
        return []

    with open(PESANAN_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def simpan_pesanan(pesanan):
    with open(PESANAN_FILE, "w", encoding="utf-8") as file:
        json.dump(
            pesanan,
            file,
            indent=4,
            ensure_ascii=False
        )


@app.before_request
def lindungi_dashboard_admin():
    if request.endpoint in ADMIN_ENDPOINTS and not session.get("admin_login"):
        return redirect(url_for("login_admin"))


@app.route("/admin-login", methods=["GET", "POST"])
def login_admin():
    pesan_error = ""

    if request.method == "POST":
        if request.form.get("password", "") == ADMIN_PASSWORD:
            session["admin_login"] = True
            return redirect(url_for("index"))

        pesan_error = "Password admin salah."

    return render_template(
        "login_admin.html",
        pesan_error=pesan_error,
        pengaturan=baca_pengaturan()
    )


@app.route("/admin-logout")
def logout_admin():
    session.pop("admin_login", None)
    return redirect(url_for("dashboard_pembeli"))




@app.route("/pembeli")
def dashboard_pembeli():
    """Menampilkan katalog yang hanya dapat digunakan untuk pemesanan."""
    return render_template(
        "pembeli.html",
        data_barang=baca_data(),
        pengaturan=baca_pengaturan(),
        alamat_toko=ALAMAT_TOKO,
        rekening_pembayaran=REKENING_PEMBAYARAN,
        pemilik_rekening=PEMILIK_REKENING,
        qris_filename=QRIS_FILENAME,
        qris_tersedia=os.path.exists(os.path.join(app.config["LOGO_FOLDER"], QRIS_FILENAME))
    )


@app.route("/pesan/<int:index>", methods=["GET", "POST"])
def pesan_barang(index):
    data_barang = baca_data()

    if not 0 <= index < len(data_barang):
        return redirect(url_for("dashboard_pembeli"))

    barang = data_barang[index]
    pesan_error = ""
    pesanan = None

    if request.method == "POST":
        try:
            jumlah = int(request.form.get("jumlah", "0"))
        except ValueError:
            jumlah = 0

        metode = request.form.get("metode_pembayaran", "")
        nama_pemesan = request.form.get("nama_pemesan", "").strip()
        nomor_telepon = request.form.get("nomor_telepon", "").strip()
        file_bukti = request.files.get("bukti_pembayaran")
        bukti_filename = ""

        if not nama_pemesan or not nomor_telepon:
            pesan_error = "Nama dan nomor telepon wajib diisi."
        elif jumlah < 1:
            pesan_error = "Jumlah pesanan minimal 1."
        elif jumlah > barang.get("stok", 0):
            pesan_error = "Jumlah pesanan melebihi stok yang tersedia."
        elif metode not in METODE_PEMBAYARAN + METODE_LAMA:
            pesan_error = "Pilih metode pembayaran yang tersedia."
        elif metode != "Cash" and (not file_bukti or not file_bukti.filename):
            pesan_error = "Bukti pembayaran wajib diunggah untuk pembayaran non-cash."
        else:
            if file_bukti and file_bukti.filename:
                nama_asli = secure_filename(file_bukti.filename)
                ekstensi = os.path.splitext(nama_asli)[1].lower()

                if ekstensi not in (".jpg", ".jpeg", ".png", ".webp"):
                    pesan_error = "Bukti pembayaran harus berupa JPG, PNG, atau WEBP."
                else:
                    bukti_filename = f"{uuid.uuid4().hex}{ekstensi}"
                    file_bukti.save(
                        os.path.join(app.config["BUKTI_FOLDER"], bukti_filename)
                    )

            if pesan_error:
                return render_template(
                    "pesanan.html",
                    barang=barang,
                    index=index,
                    pesanan=pesanan,
                    pesan_error=pesan_error,
                    metode_pembayaran=METODE_PEMBAYARAN,
                    rekening_pembayaran=REKENING_PEMBAYARAN,
                    pemilik_rekening=PEMILIK_REKENING,
                    qris_filename=QRIS_FILENAME,
                    qris_tersedia=os.path.exists(os.path.join(app.config["LOGO_FOLDER"], QRIS_FILENAME)),
                    whatsapp_admin=WHATSAPP_ADMIN,
                    pengaturan=baca_pengaturan(),
                    alamat_toko=ALAMAT_TOKO
                )

            pesanan = {
                "id": uuid.uuid4().hex,
                "waktu_pemesanan": datetime.now().isoformat(timespec="seconds"),
                "nama_barang": barang.get("nama", ""),
                "kode_barang": barang.get("kode", ""),
                "nama_pemesan": nama_pemesan,
                "nomor_telepon": nomor_telepon,
                "jumlah": jumlah,
                "metode_pembayaran": metode,
                "total": jumlah * barang.get("harga", 0),
                "bukti_filename": bukti_filename,
                "status": "Masih Proses"
            }

            semua_pesanan = baca_pesanan()
            semua_pesanan.append(pesanan)
            simpan_pesanan(semua_pesanan)

    return render_template(
        "pesanan.html",
        barang=barang,
        index=index,
        pesanan=pesanan,
        pesan_error=pesan_error,
        metode_pembayaran=METODE_PEMBAYARAN,
        rekening_pembayaran=REKENING_PEMBAYARAN,
        pemilik_rekening=PEMILIK_REKENING,
        qris_filename=QRIS_FILENAME,
        qris_tersedia=os.path.exists(os.path.join(app.config["LOGO_FOLDER"], QRIS_FILENAME)),
        whatsapp_admin=WHATSAPP_ADMIN,
        pengaturan=baca_pengaturan(),
        alamat_toko=ALAMAT_TOKO
    )


# =========================================================
# HALAMAN UTAMA
# =========================================================

@app.route("/", methods=["GET", "POST"])
def index():

    # Membaca data barang
    data_barang = baca_data()

    # Membaca pengaturan logo
    pengaturan = baca_pengaturan()

    # Variabel hasil pencarian
    hasil_pencarian = None

    # Pesan pencarian
    pesan = ""


    # =====================================================
    # PROSES PENCARIAN
    # =====================================================

    if request.method == "POST":

        kata_kunci = request.form["kata_kunci"].strip().lower()

        # Linear Search
        for index, barang in enumerate(data_barang):

            nama = barang["nama"].lower()
            kode = barang["kode"].lower()
            kategori = barang["kategori"].lower()

            if (
                kata_kunci in nama
                or kata_kunci in kode
                or kata_kunci in kategori
            ):

                hasil_pencarian = barang.copy()

                hasil_pencarian["index"] = index

                break


        # Jika data tidak ditemukan
        if hasil_pencarian is None:

            pesan = "Data barang tidak ditemukan."


    # =====================================================
    # DASHBOARD
    # =====================================================

    jumlah_barang = len(data_barang)

    total_stok = 0

    stok_menipis = 0

    stok_habis = 0

    daftar_pesanan = []
    for pesanan in reversed(baca_pesanan()):
        daftar_pesanan.append(pesanan.copy())


    # Menghitung stok
    for barang in data_barang:

        total_stok += barang["stok"]

        if barang["stok"] == 0:

            stok_habis += 1

        elif barang["stok"] <= 10:

            stok_menipis += 1


    # =====================================================
    # MENAMPILKAN HALAMAN
    # =====================================================

    return render_template(
        "index.html",

        data_barang=data_barang,

        hasil=hasil_pencarian,

        pesan=pesan,

        jumlah_barang=jumlah_barang,

        total_stok=total_stok,

        stok_menipis=stok_menipis,

        stok_habis=stok_habis,

        daftar_pesanan=daftar_pesanan,
        whatsapp_admin=WHATSAPP_ADMIN,

        pengaturan=pengaturan
    )


# =========================================================
# TAMBAH BARANG
# =========================================================

@app.route("/tambah", methods=["POST"])
def tambah_barang():

    data_barang = baca_data()


    # Mengambil gambar barang
    file_gambar = request.files.get("gambar")

    nama_gambar = ""


    # Jika pengguna memilih gambar
    if file_gambar and file_gambar.filename:

        nama_gambar = secure_filename(
            file_gambar.filename
        )

        file_gambar.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                nama_gambar
            )
        )


    # Membuat data barang baru
    barang_baru = {

        "nama": request.form["nama"],

        "kode": request.form["kode"],

        "kategori": request.form["kategori"],

        "harga": int(request.form["harga"]),

        "stok": int(request.form["stok"]),

        "satuan": request.form["satuan"],

        "kondisi": request.form["kondisi"],

        "lokasi": request.form["lokasi"],

        "gambar": nama_gambar
    }


    # Memasukkan barang ke list
    data_barang.append(barang_baru)


    # Menyimpan ke JSON
    simpan_data(data_barang)


    return redirect(
        url_for("index")
    )


# =========================================================
# EDIT BARANG
# =========================================================

@app.route("/barang/<int:index>")
def detail_barang(index):

    data_barang = baca_data()

    if not 0 <= index < len(data_barang):
        return redirect(url_for("index", _anchor="daftar"))

    return render_template(
        "detail.html",
        barang=data_barang[index],
        index=index,
        pengaturan=baca_pengaturan(),
        alamat_toko=ALAMAT_TOKO
    )


# =========================================================
# EDIT BARANG
# =========================================================

@app.route("/edit/<int:index>", methods=["GET", "POST"])
def edit_barang(index):

    data_barang = baca_data()

    if not 0 <= index < len(data_barang):
        return redirect(url_for("index"))

    barang = data_barang[index]

    if request.method == "POST":

        barang["nama"] = request.form["nama"]
        barang["kode"] = request.form["kode"]
        barang["kategori"] = request.form["kategori"]
        barang["harga"] = int(request.form["harga"])
        barang["stok"] = int(request.form["stok"])
        barang["satuan"] = request.form["satuan"]
        barang["kondisi"] = request.form["kondisi"]
        barang["lokasi"] = request.form["lokasi"]

        file_gambar = request.files.get("gambar")

        if file_gambar and file_gambar.filename:
            nama_gambar = secure_filename(file_gambar.filename)
            file_gambar.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    nama_gambar
                )
            )
            barang["gambar"] = nama_gambar

        simpan_data(data_barang)

        return redirect(url_for("index", _anchor="daftar"))

    return render_template(
        "edit.html",
        barang=barang,
        index=index
    )


# =========================================================
# HAPUS BARANG
# =========================================================

@app.route("/hapus/<int:index>")
def hapus_barang(index):

    data_barang = baca_data()


    # Memastikan index tersedia
    if 0 <= index < len(data_barang):

        # Menghapus data berdasarkan index
        data_barang.pop(index)

        # Menyimpan kembali JSON
        simpan_data(data_barang)

    return redirect(
        url_for("index")
    )

#=======================================================
#HAPUS DATA PESANAN
#=======================================================
@app.route("/ubah-status-pesanan/<string:id>", methods=["POST"])
def ubah_status_pesanan(id):

    status_baru = request.form.get("status", "")
    if status_baru not in ("Masih Proses", "Selesai"):
        return redirect(url_for("index", _anchor="pesanan"))

    semua_pesanan = baca_pesanan()
    for pesanan in semua_pesanan:
        if pesanan.get("id") == id:
            pesanan["status"] = status_baru
            simpan_pesanan(semua_pesanan)
            break

    return redirect(url_for("index", _anchor="pesanan"))


@app.route("/hapus-pesanan/<string:id>", methods=["POST"])
def hapus_pesanan(id):

    semua_pesanan = baca_pesanan()

    # Mencari pesanan berdasarkan ID
    pesanan_ditemukan = False
    for i, pesanan in enumerate(semua_pesanan):
        if pesanan.get("id") == id:
            pesanan_ditemukan = True
            # Menghapus bukti pembayaran jika ada
            bukti_filename = pesanan.get("bukti_filename", "")
            if bukti_filename:
                bukti_path = os.path.join(app.config["BUKTI_FOLDER"], bukti_filename)
                if os.path.exists(bukti_path):
                    os.remove(bukti_path)
            # Menghapus pesanan dari daftar
            semua_pesanan.pop(i)
            break

    if pesanan_ditemukan:
        simpan_pesanan(semua_pesanan)

    return redirect(url_for("index", _anchor="daftar-pesanan"))

# =========================================================
# UPLOAD LOGO
# =========================================================

@app.route("/upload-logo", methods=["POST"])
def upload_logo():

    # Mengambil file logo dari form
    file_logo = request.files.get("logo")


    # Memastikan file dipilih
    if file_logo and file_logo.filename:

        # Mengamankan nama file
        nama_logo = secure_filename(
            file_logo.filename
        )


        # Menyimpan logo ke static/images
        file_logo.save(
            os.path.join(
                app.config["LOGO_FOLDER"],
                nama_logo
            )
        )


        # Membaca pengaturan
        pengaturan = baca_pengaturan()


        # Menyimpan nama logo
        pengaturan["logo"] = nama_logo


        # Menyimpan pengaturan ke JSON
        simpan_pengaturan(pengaturan)


    # Kembali ke halaman dashboard
    return redirect(
        url_for("index")
    )


@app.route("/upload-qris", methods=["POST"])
def upload_qris():
    """Menyimpan gambar QRIS resmi dengan nama yang stabil untuk pembeli."""
    file_qris = request.files.get("qris")

    if file_qris and file_qris.filename:
        nama_file = secure_filename(file_qris.filename).lower()
        ekstensi_diizinkan = (".png", ".jpg", ".jpeg", ".webp")

        if nama_file.endswith(ekstensi_diizinkan):
            file_qris.save(
                os.path.join(
                    app.config["LOGO_FOLDER"],
                    QRIS_FILENAME
                )
            )

    return redirect(url_for("index", _anchor="logo"))


# =========================================================
# MENJALANKAN PROGRAM
# =========================================================

if __name__ == "__main__":

    app.run(debug=True)