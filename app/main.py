import sqlite3
import os
import datetime
from getpass import getpass
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

# ==============================
# Helper Enkripsi & Hashing
# ==============================


# Fungsi ini tetap sama, untuk menurunkan kunci enkripsi dari password
def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
        backend=default_backend()
    )
    return kdf.derive(password.encode())


# Fungsi untuk mengenkripsi data dengan master password
def encrypt(data: str, password: str) -> str:
    if not data:
        return ""
    salt = os.urandom(16)
    key = derive_key(password, salt)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(data.encode()) + encryptor.finalize()
    return base64.b64encode(salt + iv + ct).decode()


# Fungsi untuk mendekripsi data dengan master password
def decrypt(enc_data: str, password: str) -> str:
    if not enc_data:
        return ""
    try:
        raw = base64.b64decode(enc_data)
        salt, iv, ct = raw[:16], raw[16:32], raw[32:]
        key = derive_key(password, salt)
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        return (decryptor.update(ct) + decryptor.finalize()).decode()
    except Exception:
        # Jika dekripsi gagal (misal, password salah), kembalikan string kosong atau error
        return "DECRYPTION_ERROR"


# ==============================
# Database Setup
# ==============================
conn = sqlite3.connect("app_orang_secure.db")  # Menggunakan file DB baru untuk struktur baru
c = conn.cursor()

# Menambahkan kolom master_password_hash untuk keamanan profil
c.execute('''
CREATE TABLE IF NOT EXISTS orang (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    master_password_hash TEXT NOT NULL
)
''')

# Menghapus kolom password individual, karena sekarang semua diamankan oleh master password
c.execute('''
CREATE TABLE IF NOT EXISTS account (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orang_id INTEGER,
    nama_account TEXT NOT NULL,
    FOREIGN KEY (orang_id) REFERENCES orang(id)
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS kategori (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    tipe TEXT CHECK(tipe IN ('pemasukan', 'pengeluaran'))
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS transaksi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    kategori_id INTEGER,
    tipe TEXT CHECK(tipe IN ('pemasukan', 'pengeluaran')),
    jumlah REAL,
    tanggal TEXT,
    deskripsi TEXT,
    FOREIGN KEY (account_id) REFERENCES account(id),
    FOREIGN KEY (kategori_id) REFERENCES kategori(id)
)
''')

conn.commit()


# ==============================
# Fungsi CRUD (Diperbarui dengan Enkripsi)
# ==============================
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def tambah_orang(nama, master_password):
    # Hash password untuk verifikasi, bukan untuk enkripsi
    salt = os.urandom(16)
    key = derive_key(master_password, salt)
    # Simpan salt bersama hash agar bisa diverifikasi nanti
    password_hash = base64.b64encode(salt + key).decode()
    c.execute("INSERT INTO orang (nama, master_password_hash) VALUES (?, ?)", (nama, password_hash))
    conn.commit()
    return c.lastrowid


def tambah_account(orang_id, nama_account, master_password):
    nama_encrypted = encrypt(nama_account, master_password)
    c.execute("INSERT INTO account (orang_id, nama_account) VALUES (?, ?)",
              (orang_id, nama_encrypted))
    conn.commit()


def tambah_kategori(nama, tipe, master_password):
    nama_encrypted = encrypt(nama, master_password)
    c.execute("INSERT INTO kategori (nama, tipe) VALUES (?, ?)", (nama_encrypted, tipe))
    conn.commit()


def tambah_transaksi(account_id, kategori_id, tipe, jumlah, deskripsi, master_password):
    desc_encrypted = encrypt(deskripsi, master_password)
    tanggal = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO transaksi (account_id, kategori_id, tipe, jumlah, tanggal, deskripsi)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (account_id, kategori_id, tipe, jumlah, tanggal, desc_encrypted))
    conn.commit()


def get_orang():
    c.execute("SELECT id, nama, master_password_hash FROM orang")
    return c.fetchall()


def get_accounts_by_orang(orang_id, master_password):
    c.execute("SELECT id, nama_account FROM account WHERE orang_id=?", (orang_id,))
    encrypted_accounts = c.fetchall()
    decrypted_accounts = []
    for acc_id, enc_nama in encrypted_accounts:
        dec_nama = decrypt(enc_nama, master_password)
        decrypted_accounts.append((acc_id, dec_nama))
    return decrypted_accounts


def get_kategori(tipe, master_password):
    c.execute("SELECT id, nama FROM kategori WHERE tipe=?", (tipe,))
    encrypted_kategori = c.fetchall()
    decrypted_kategori = []
    for kat_id, enc_nama in encrypted_kategori:
        dec_nama = decrypt(enc_nama, master_password)
        decrypted_kategori.append((kat_id, dec_nama))
    return decrypted_kategori

# ==============================
# LOGIC REWORKED BELOW
# ==============================


def display_dashboard_and_menu(accounts, master_password):
    """Fungsi ini menampilkan ringkasan semua akun DAN menu utama."""
    clear_screen()
    print("=== DASHBOARD ===")
    total_saldo = 0
    now = datetime.datetime.now()
    bulan_ini = now.strftime("%Y-%m")
    pemasukan_bulan_ini = 0
    pengeluaran_bulan_ini = 0

    if not accounts:
        print("Anda belum memiliki akun (sumber dana).")
    else:
        for acc_id, acc_name in accounts:
            c.execute("SELECT tipe, jumlah, tanggal FROM transaksi WHERE account_id=?", (acc_id,))
            trans = c.fetchall()
            saldo = sum(t[1] if t[0] == 'pemasukan' else -t[1] for t in trans)
            pemasukan_bulan_ini += sum(t[1] for t in trans if t[0] == 'pemasukan' and t[2].startswith(bulan_ini))
            pengeluaran_bulan_ini += sum(t[1] for t in trans if t[0] == 'pengeluaran' and t[2].startswith(bulan_ini))
            total_saldo += saldo
            print(f"- Akun: {acc_name}, Saldo: Rp{saldo:,.2f}")

    print("-" * 30)
    print(f"Total Saldo Keseluruhan: Rp{total_saldo:,.2f}")
    print(f"Total Pemasukan Bulan Ini: Rp{pemasukan_bulan_ini:,.2f}")
    print(f"Total Pengeluaran Bulan Ini: Rp{pengeluaran_bulan_ini:,.2f}")
    print("=" * 30)
    
    # Langsung tampilkan menu di bawah dashboard
    print("\n=== MENU UTAMA ===")
    print("1. Catat Pemasukan")
    print("2. Catat Pengeluaran")
    print("3. Tambah Akun (Sumber Dana: BCA, Cash, dll)")
    print("4. Tambah Kategori Pemasukan")
    print("5. Tambah Kategori Pengeluaran")
    print("6. Logout (Kembali ke Pilih Profil)")


def login_menu():
    """Memilih profil dan verifikasi master password."""
    while True:
        clear_screen()
        print("=== APLIKASI KEUANGAN PRIBADI (SECURE) ===")
        print("\nPilih Profil:")
        orang_list = get_orang()
        if not orang_list:
            print("Belum ada profil. Silakan buat baru.")
        for o_id, o_nama, _ in orang_list:
            print(f"{o_id}. {o_nama}")
        print("\n" + "-"*20)
        print("0. Buat Profil Baru")
        print("x. Exit")
        
        pilihan = input("Pilih ID Profil: ").lower()
        
        if pilihan == "x":
            exit(0)
        elif pilihan == "0":
            nama = input("Masukkan Nama Profil baru: ")
            while True:
                pw1 = getpass("Buat Master Password: ")
                pw2 = getpass("Konfirmasi Master Password: ")
                if pw1 == pw2 and pw1:
                    tambah_orang(nama, pw1)
                    print(f"Profil '{nama}' berhasil dibuat.")
                    input("Tekan Enter...")
                    break
                else:
                    print("Password tidak cocok atau kosong. Silakan coba lagi.")
        else:
            try:
                orang_id = int(pilihan)
                profil_data = next((o for o in orang_list if o[0] == orang_id), None)
                
                if profil_data:
                    password_hash = profil_data[2]
                    master_password = getpass(f"Masukkan Master Password untuk {profil_data[1]}: ")
                    
                    # Verifikasi password
                    try:
                        raw_hash = base64.b64decode(password_hash)
                        salt, key_stored = raw_hash[:16], raw_hash[16:]
                        key_input = derive_key(master_password, salt)
                        if key_input == key_stored:
                             print("Login berhasil!")
                             input("Tekan Enter...")
                             return orang_id, master_password
                        else:
                            print("Master Password salah!")
                            input("Tekan Enter...")
                    except Exception as e:
                        print(f"Error verifikasi: {e}")
                        input("Tekan Enter...")
                else:
                    print("ID Profil tidak valid.")
                    input("Tekan Enter...")
            except (ValueError, StopIteration):
                print("Input tidak valid.")
                input("Tekan Enter...")


def main_menu(orang_id, master_password):
    """Menu utama untuk mengelola semua akun milik 'Orang' yang login."""
    # Muat data akun setelah login berhasil
    accounts = get_accounts_by_orang(orang_id, master_password)
    
    while True:
        display_dashboard_and_menu(accounts, master_password)
        pilihan = input("Pilih menu: ")

        if pilihan in ["1", "2"]:
            tipe_transaksi = "pemasukan" if pilihan == "1" else "pengeluaran"
            
            if not accounts:
                print("Anda harus memiliki minimal satu akun. Silakan tambah dari menu 3.")
                input("Tekan Enter..."); continue
                
            print(f"\n=== PILIH AKUN UNTUK {tipe_transaksi.upper()} ===")
            for acc_id, acc_nama in accounts:
                print(f"{acc_id}. {acc_nama}")
            
            try:
                acc_id_transaksi = int(input("\nPilih ID Akun: "))
                if not any(acc[0] == acc_id_transaksi for acc in accounts):
                    print("ID Akun tidak valid."); input("Tekan Enter..."); continue

                kategori_list = get_kategori(tipe_transaksi, master_password)
                if not kategori_list:
                    print(f"Belum ada kategori {tipe_transaksi}."); input("Tekan Enter..."); continue

                print(f"\nKategori {tipe_transaksi.capitalize()}:")
                for k_id, k_nama in kategori_list: print(f"{k_id}. {k_nama}")
                
                kat_id = int(input("Pilih ID kategori: "))
                if not any(k[0] == kat_id for k in kategori_list):
                    print("ID Kategori tidak valid."); input("Tekan Enter..."); continue
                
                jumlah = float(input("Jumlah: "))
                deskripsi = input("Deskripsi (opsional): ")
                
                tambah_transaksi(acc_id_transaksi, kat_id, tipe_transaksi, jumlah, deskripsi, master_password)
                print("\nTransaksi berhasil ditambahkan!")
                accounts = get_accounts_by_orang(orang_id, master_password)  # Refresh data
                input("Tekan Enter...")

            except ValueError:
                print("Input jumlah atau ID tidak valid."); input("Tekan Enter...")

        elif pilihan == "3":
            nama_acc = input("Nama Akun baru (contoh: Cash, GoPay): ")
            if nama_acc:
                tambah_account(orang_id, nama_acc, master_password)
                print(f"Akun '{nama_acc}' berhasil ditambahkan.")
                accounts = get_accounts_by_orang(orang_id, master_password)  # Refresh data
            else:
                print("Nama Akun tidak boleh kosong.")
            input("Tekan Enter...")
            
        elif pilihan == "4":
            nama = input("Nama kategori pemasukan baru (contoh: Gaji): ")
            if nama:
                tambah_kategori(nama, "pemasukan", master_password)
                print("Kategori berhasil ditambahkan.")
            input("Tekan Enter...")

        elif pilihan == "5":
            nama = input("Nama kategori pengeluaran baru (contoh: Makanan): ")
            if nama:
                tambah_kategori(nama, "pengeluaran", master_password)
                print("Kategori berhasil ditambahkan.")
            input("Tekan Enter...")
            
        elif pilihan == "6":
            print("Logout berhasil."); input("Tekan Enter..."); return
        else:
            print("Pilihan tidak valid."); input("Tekan Enter...")


# ==============================
# Program Utama
# ==============================
if __name__ == "__main__":
    while True:
        login_result = login_menu()
        if login_result:
            orang_id, master_password = login_result
            main_menu(orang_id, master_password)
