# app/database.py

import sqlite3
import datetime
import base64
from lib.crypt import derive_key, encrypt, decrypt
import os

DB_FILE = "app_orang_secure.db"


def get_db_connection():
    """Establishes and returns a database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    """Creates all necessary tables if they don't exist."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS orang (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        master_password_hash TEXT NOT NULL
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS account (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        orang_id INTEGER,
        nama_account TEXT NOT NULL,
        FOREIGN KEY (orang_id) REFERENCES orang(id)
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS kategori (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        tipe TEXT CHECK(tipe IN ('pemasukan', 'pengeluaran'))
    )''')
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
    )''')
    conn.commit()
    conn.close()

# --- CRUD Functions ---


def tambah_orang(nama, master_password):
    conn = get_db_connection()
    c = conn.cursor()
    salt = os.urandom(16)
    key = derive_key(master_password, salt)
    password_hash = base64.b64encode(salt + key).decode()
    c.execute("INSERT INTO orang (nama, master_password_hash) VALUES (?, ?)", (nama, password_hash))
    conn.commit()
    last_id = c.lastrowid
    conn.close()
    return last_id


def tambah_account(orang_id, nama_account, master_password):
    nama_encrypted = encrypt(nama_account, master_password)
    conn = get_db_connection()
    conn.execute("INSERT INTO account (orang_id, nama_account) VALUES (?, ?)", (orang_id, nama_encrypted))
    conn.commit()
    conn.close()


def tambah_kategori(nama, tipe, master_password):
    nama_encrypted = encrypt(nama, master_password)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO kategori (nama, tipe) VALUES (?, ?)", (nama_encrypted, tipe))
    conn.commit()
    last_id = c.lastrowid
    conn.close()
    return last_id


def tambah_transaksi(account_id, kategori_id, tipe, jumlah, deskripsi, master_password):
    desc_encrypted = encrypt(deskripsi, master_password)
    tanggal = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO transaksi (account_id, kategori_id, tipe, jumlah, tanggal, deskripsi)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (account_id, kategori_id, tipe, jumlah, tanggal, desc_encrypted))
    conn.commit()
    conn.close()

# --- Getter Functions ---


def get_orang():
    conn = get_db_connection()
    orang_list = conn.execute("SELECT id, nama, master_password_hash FROM orang").fetchall()
    conn.close()
    return orang_list

    
def get_orang_by_id(orang_id):
    """Fetches a single user profile by ID."""
    conn = get_db_connection()
    orang = conn.execute("SELECT id, nama FROM orang WHERE id=?", (orang_id,)).fetchone()
    conn.close()
    return orang


def get_accounts_by_orang(orang_id, master_password):
    conn = get_db_connection()
    encrypted_accounts = conn.execute("SELECT id, nama_account FROM account WHERE orang_id=?", (orang_id,)).fetchall()
    conn.close()
    decrypted = [(acc['id'], decrypt(acc['nama_account'], master_password)) for acc in encrypted_accounts]
    return decrypted


def get_account_details(account_id, master_password):
    conn = get_db_connection()
    acc = conn.execute("SELECT id, nama_account FROM account WHERE id=?", (account_id,)).fetchone()
    conn.close()
    if not acc:
        return None
    return {
        "id": acc["id"],
        "nama": decrypt(acc["nama_account"], master_password)
    }


def get_kategori(tipe, master_password):
    conn = get_db_connection()
    encrypted_kategori = conn.execute("SELECT id, nama FROM kategori WHERE tipe=?", (tipe,)).fetchall()
    conn.close()
    decrypted = [(kat['id'], decrypt(kat['nama'], master_password)) for kat in encrypted_kategori]
    return decrypted


def get_transactions_for_dashboard(account_id):
    conn = get_db_connection()
    trans = conn.execute("SELECT tipe, jumlah, tanggal FROM transaksi WHERE account_id=?", (account_id,)).fetchall()
    conn.close()
    return trans


def get_account_balance(account_id):
    """Calculates and returns the current balance for a single account."""
    conn = get_db_connection()
    trans = conn.execute("SELECT tipe, jumlah FROM transaksi WHERE account_id=?", (account_id,)).fetchall()
    conn.close()
    saldo = sum(t['jumlah'] if t['tipe'] == 'pemasukan' else -t['jumlah'] for t in trans)
    return saldo


def count_transactions(orang_id, tipe):
    """Counts total transactions for a user of a specific type for pagination."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(t.id) 
        FROM transaksi t
        JOIN account a ON t.account_id = a.id
        WHERE a.orang_id = ? AND t.tipe = ?
    """, (orang_id, tipe))
    count = c.fetchone()[0]
    conn.close()
    return count


def get_transactions_paginated(orang_id, master_password, tipe, page=1, page_size=20):
    """Retrieves a paginated list of transactions, decrypting them on the fly."""
    offset = (page - 1) * page_size
    conn = get_db_connection()
    query = """
        SELECT t.tanggal, a.nama_account, k.nama as nama_kategori, t.jumlah, t.deskripsi
        FROM transaksi t
        JOIN account a ON t.account_id = a.id
        JOIN kategori k ON t.kategori_id = k.id
        WHERE a.orang_id = ? AND t.tipe = ?
        ORDER BY t.tanggal DESC
        LIMIT ? OFFSET ?
    """
    encrypted_rows = conn.execute(query, (orang_id, tipe, page_size, offset)).fetchall()
    conn.close()
    
    decrypted_rows = []
    for row in encrypted_rows:
        decrypted_rows.append({
            "tanggal": row["tanggal"],
            "nama_account": decrypt(row["nama_account"], master_password),
            "nama_kategori": decrypt(row["nama_kategori"], master_password),
            "jumlah": row["jumlah"],
            "deskripsi": decrypt(row["deskripsi"], master_password)
        })
    return decrypted_rows

# --- Fitur Transfer ---


def get_or_create_transfer_kategori(tipe, master_password):
    """Finds the 'Transfer' category or creates it if it doesn't exist."""
    nama_kategori = "Transfer Masuk" if tipe == "pemasukan" else "Transfer Keluar"
    
    kategori_list = get_kategori(tipe, master_password)
    for kat_id, kat_nama in kategori_list:
        if kat_nama == nama_kategori:
            return kat_id

    return tambah_kategori(nama_kategori, tipe, master_password)


def transfer_dana(from_account_id, to_account_id, jumlah, master_password):
    """Creates two transactions to simulate a transfer."""
    from_acc_name = get_account_details(from_account_id, master_password)['nama']
    to_acc_name = get_account_details(to_account_id, master_password)['nama']

    kat_keluar_id = get_or_create_transfer_kategori("pengeluaran", master_password)
    kat_masuk_id = get_or_create_transfer_kategori("pemasukan", master_password)

    deskripsi_keluar = f"Transfer ke akun {to_acc_name}"
    deskripsi_masuk = f"Transfer dari akun {from_acc_name}"

    tambah_transaksi(from_account_id, kat_keluar_id, "pengeluaran", jumlah, deskripsi_keluar, master_password)
    tambah_transaksi(to_account_id, kat_masuk_id, "pemasukan", jumlah, deskripsi_masuk, master_password)

# --- Fitur Export CSV ---


def get_all_transactions_for_export(orang_id, master_password):
    """Retrieves all transactions for a user for CSV export."""
    conn = get_db_connection()
    query = """
        SELECT a.nama_account, t.tipe, k.nama as nama_kategori, t.jumlah, t.deskripsi, t.tanggal
        FROM transaksi t
        JOIN account a ON t.account_id = a.id
        JOIN kategori k ON t.kategori_id = k.id
        WHERE a.orang_id = ?
        ORDER BY t.tanggal ASC
    """
    encrypted_rows = conn.execute(query, (orang_id,)).fetchall()
    conn.close()
    
    decrypted_rows = []
    for row in encrypted_rows:
        decrypted_rows.append({
            "nama": decrypt(row["nama_account"], master_password),
            "tipe": row["tipe"],
            "kategori": decrypt(row["nama_kategori"], master_password),
            "jumlah": row["jumlah"],
            "deskripsi": decrypt(row["deskripsi"], master_password),
            "tanggal": row["tanggal"]
        })
    return decrypted_rows
