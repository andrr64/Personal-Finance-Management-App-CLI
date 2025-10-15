# app/main.py

import os
import datetime
from getpass import getpass
import base64
import math
import csv

import database as db
from lib.crypt import derive_key

# ==============================
# UI & Application Flow
# ==============================


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def display_dashboard_and_menu(accounts):
    """Displays the financial summary dashboard and the main menu."""
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
            trans = db.get_transactions_for_dashboard(acc_id)
            saldo = sum(t['jumlah'] if t['tipe'] == 'pemasukan' else -t['jumlah'] for t in trans)
            pemasukan_bulan_ini += sum(t['jumlah'] for t in trans if t['tipe'] == 'pemasukan' and t['tanggal'].startswith(bulan_ini))
            pengeluaran_bulan_ini += sum(t['jumlah'] for t in trans if t['tipe'] == 'pengeluaran' and t['tanggal'].startswith(bulan_ini))
            total_saldo += saldo
            print(f"- Akun: {acc_name}, Saldo: Rp{saldo:,.2f}")

    print("-" * 30)
    print(f"Total Saldo Keseluruhan: Rp{total_saldo:,.2f}")
    print(f"Total Pemasukan Bulan Ini: Rp{pemasukan_bulan_ini:,.2f}")
    print(f"Total Pengeluaran Bulan Ini: Rp{pengeluaran_bulan_ini:,.2f}")
    print("=" * 30)
    
    print("\n=== MENU UTAMA ===")
    print("1. Catat Pemasukan")
    print("2. Catat Pengeluaran")
    print("3. Tambah Akun (Sumber Dana)")
    print("4. Tambah Kategori Pemasukan")
    print("5. Tambah Kategori Pengeluaran")
    print("6. Lihat Riwayat Pemasukan")
    print("7. Lihat Riwayat Pengeluaran")
    print("8. Transfer Antar Akun")
    print("9. Export Laporan ke .csv")
    print("10. Logout (Kembali ke Pilih Profil)")


def export_to_csv(orang_id, master_password):
    """Handles the logic for exporting user transactions to a CSV file."""
    clear_screen()
    print("=== EXPORT LAPORAN KE CSV ===")
    
    transactions = db.get_all_transactions_for_export(orang_id, master_password)
    
    if not transactions:
        print("Tidak ada data transaksi untuk di-export.")
        input("\nTekan Enter untuk kembali..."); return

    # Membuat nama file default
    profil = db.get_orang_by_id(orang_id)
    nama_profil = profil['nama'].replace(" ", "_")
    tanggal_str = datetime.datetime.now().strftime("%Y-%m-%d")
    default_filename = f"Laporan_{nama_profil}_{tanggal_str}.csv"
    
    filename_input = input(f"Masukkan nama file (default: {default_filename}): ")
    filename = filename_input if filename_input else default_filename
    if not filename.lower().endswith(".csv"):
        filename += ".csv"

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Sesuai permintaan kolom
            header = ['nama', 'tipe', 'kategori', 'jumlah', 'deskripsi', 'tanggal']
            writer = csv.DictWriter(csvfile, fieldnames=header)
            
            writer.writeheader()
            writer.writerows(transactions)
        
        print(f"\nLaporan berhasil disimpan ke file '{filename}'")
    except IOError as e:
        print(f"\nTerjadi error saat menyimpan file: {e}")
    
    input("Tekan Enter untuk kembali...");


def view_transactions_paged(orang_id, master_password, tipe):
    """Handles the UI for viewing paginated transactions."""
    page = 1
    page_size = 20
    
    while True:
        clear_screen()
        print(f"=== RIWAYAT {tipe.upper()} ===")
        
        total_items = db.count_transactions(orang_id, tipe)
        if total_items == 0:
            print("Tidak ada data transaksi.")
            input("\nTekan Enter untuk kembali..."); return

        total_pages = math.ceil(total_items / page_size)
        
        transactions = db.get_transactions_paginated(orang_id, master_password, tipe, page, page_size)
        
        for t in transactions:
            print("-" * 30)
            print(f"Tanggal   : {t['tanggal']}")
            print(f"Akun      : {t['nama_account']}")
            print(f"Kategori  : {t['nama_kategori']}")
            print(f"Jumlah    : Rp{t['jumlah']:,.2f}")
            if t['deskripsi']:
                print(f"Deskripsi : {t['deskripsi']}")
        
        print("-" * 30)
        print(f"Halaman {page}/{total_pages} ({total_items} total data)")
        print("\n[N] Halaman Berikutnya, [P] Halaman Sebelumnya, [E] Keluar ke Menu")
        
        nav = input("Pilihan: ").lower()
        if nav == 'n' and page < total_pages:
            page += 1
        elif nav == 'p' and page > 1:
            page -= 1
        elif nav == 'e':
            break


def login_menu():
    """Handles profile selection and master password verification."""
    while True:
        clear_screen()
        print("=== APLIKASI KEUANGAN PRIBADI (SECURE) ===")
        print("\nPilih Profil:")
        orang_list = db.get_orang()
        if not orang_list:
            print("Belum ada profil. Silakan buat baru.")
        for o in orang_list:
            print(f"{o['id']}. {o['nama']}")
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
                    db.tambah_orang(nama, pw1)
                    print(f"Profil '{nama}' berhasil dibuat.")
                    input("Tekan Enter..."); break
                else:
                    print("Password tidak cocok atau kosong. Coba lagi.")
        else:
            try:
                orang_id = int(pilihan)
                profil_data = next((o for o in orang_list if o['id'] == orang_id), None)
                
                if profil_data:
                    password_hash = profil_data['master_password_hash']
                    master_password = getpass(f"Masukkan Master Password untuk {profil_data['nama']}: ")
                    
                    raw_hash = base64.b64decode(password_hash)
                    salt, key_stored = raw_hash[:16], raw_hash[16:]
                    key_input = derive_key(master_password, salt)
                    
                    if key_input == key_stored:
                         print("Login berhasil!"); input("Tekan Enter...")
                         return orang_id, master_password
                    else:
                        print("Master Password salah!"); input("Tekan Enter...")
                else:
                    print("ID Profil tidak valid."); input("Tekan Enter...")
            except (ValueError, StopIteration):
                print("Input tidak valid."); input("Tekan Enter...")


def main_menu(orang_id, master_password):
    """The main application loop after a user has logged in."""
    accounts = db.get_accounts_by_orang(orang_id, master_password)
    
    while True:
        display_dashboard_and_menu(accounts)
        pilihan = input("Pilih menu: ")

        if pilihan in ["1", "2"]:
            # ... (kode tidak berubah) ...
            tipe = "pemasukan" if pilihan == "1" else "pengeluaran"
            if not accounts:
                print("\nAnda harus memiliki akun. Silakan tambah dari menu 3."); input("Tekan Enter..."); continue
            
            print(f"\n=== PILIH AKUN UNTUK {tipe.upper()} ===")
            for acc_id, acc_nama in accounts: print(f"{acc_id}. {acc_nama}")
            
            try:
                acc_id = int(input("\nPilih ID Akun: "))
                if not any(acc[0] == acc_id for acc in accounts):
                    print("ID Akun tidak valid."); input("Tekan Enter..."); continue
                
                kategori_list = db.get_kategori(tipe, master_password)
                if not kategori_list:
                    print(f"\nBelum ada kategori {tipe}."); input("Tekan Enter..."); continue
                
                print(f"\nKategori {tipe.capitalize()}:")
                for k_id, k_nama in kategori_list: print(f"{k_id}. {k_nama}")
                
                kat_id = int(input("Pilih ID kategori: "))
                if not any(k[0] == kat_id for k in kategori_list):
                    print("ID Kategori tidak valid."); input("Tekan Enter..."); continue
                
                jumlah = float(input("Jumlah: "))
                deskripsi = input("Deskripsi (opsional): ")
                
                db.tambah_transaksi(acc_id, kat_id, tipe, jumlah, deskripsi, master_password)
                accounts = db.get_accounts_by_orang(orang_id, master_password)  # Refresh data
                print("\nTransaksi berhasil ditambahkan!"); input("Tekan Enter...")
            except ValueError:
                print("Input jumlah atau ID tidak valid."); input("Tekan Enter...")

        elif pilihan == "3":
            # ... (kode tidak berubah) ...
            nama_acc = input("Nama Akun baru (cth: Cash, GoPay): ")
            if nama_acc:
                db.tambah_account(orang_id, nama_acc, master_password)
                print(f"Akun '{nama_acc}' berhasil ditambahkan.")
                accounts = db.get_accounts_by_orang(orang_id, master_password)
            else:
                print("Nama Akun tidak boleh kosong.")
            input("Tekan Enter...")
            
        elif pilihan == "4":
            # ... (kode tidak berubah) ...
            nama = input("Nama kategori pemasukan baru (cth: Gaji): ")
            if nama: db.tambah_kategori(nama, "pemasukan", master_password); print("Kategori ditambahkan.")
            input("Tekan Enter...")

        elif pilihan == "5":
            # ... (kode tidak berubah) ...
            nama = input("Nama kategori pengeluaran baru (cth: Makanan): ")
            if nama: db.tambah_kategori(nama, "pengeluaran", master_password); print("Kategori ditambahkan.")
            input("Tekan Enter...")
        
        elif pilihan == "6":
            view_transactions_paged(orang_id, master_password, "pemasukan")

        elif pilihan == "7":
            view_transactions_paged(orang_id, master_password, "pengeluaran")
            
        elif pilihan == "8":
            # ... (kode tidak berubah) ...
            if len(accounts) < 2:
                print("\nAnda harus memiliki minimal 2 akun untuk melakukan transfer.")
                input("Tekan Enter..."); continue

            try:
                print("\n--- Transfer Dana ---")
                print("Pilih akun sumber (DARI):")
                for acc_id, acc_nama in accounts: print(f"{acc_id}. {acc_nama}")
                from_id = int(input("ID Akun Sumber: "))
                
                print("\nPilih akun tujuan (KE):")
                for acc_id, acc_nama in accounts: 
                    if acc_id != from_id: print(f"{acc_id}. {acc_nama}")
                to_id = int(input("ID Akun Tujuan: "))

                if from_id == to_id:
                    print("\nAkun sumber dan tujuan tidak boleh sama."); input("Tekan Enter..."); continue
                if not any(acc[0] == from_id for acc in accounts) or not any(acc[0] == to_id for acc in accounts):
                    print("\nID Akun tidak valid."); input("Tekan Enter..."); continue

                jumlah = float(input("Jumlah yang akan ditransfer: "))
                
                saldo_sumber = db.get_account_balance(from_id)
                if saldo_sumber < jumlah:
                    print(f"\nSaldo tidak mencukupi! Saldo saat ini: Rp{saldo_sumber:,.2f}"); input("Tekan Enter..."); continue
                
                db.transfer_dana(from_id, to_id, jumlah, master_password)
                accounts = db.get_accounts_by_orang(orang_id, master_password)  # Refresh data
                print("\nTransfer berhasil!"); input("Tekan Enter...")

            except ValueError:
                print("\nInput ID atau jumlah tidak valid."); input("Tekan Enter...")
        
        elif pilihan == "9":
            export_to_csv(orang_id, master_password)

        elif pilihan == "10":
            print("Logout berhasil."); input("Tekan Enter..."); return
        else:
            print("Pilihan tidak valid."); input("Tekan Enter...")

# ==============================
# Program Utama
# ==============================


if __name__ == "__main__":
    db.setup_database()  # Ensure tables exist before starting
    while True:
        login_result = login_menu()
        if login_result:
            main_menu(*login_result)
