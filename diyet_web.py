import streamlit as st
import pandas as pd
import sqlite3
import datetime
import altair as alt
import json # Yeni modül için gerekli

# --- AYARLAR ---
st.set_page_config(page_title="Klinik Yönetim v13 (Renkli Kart)", layout="wide", page_icon="🥗")

# --- VERİTABANI --
DB_NAME = 'klinik_v13_r.db' # Yeni versiyon için yeni DB adı

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Tablo: DANIŞANLAR (v12'den alınmıştır)
    c.execute('''CREATE TABLE IF NOT EXISTS danisanlar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  ad_soyad TEXT UNIQUE, 
                  cinsiyet TEXT, 
                  dogum_yili INTEGER, 
                  boy REAL, 
                  telefon TEXT,
                  kayit_tarihi TEXT)''')
    
    # 2. Tablo: ÖLÇÜMLER (v12'den alınmıştır)
    c.execute('''CREATE TABLE IF NOT EXISTS olcumler
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  danisan_id INTEGER,
                  tarih TEXT, 
                  kilo REAL, 
                  hedef_kilo REAL,
                  bel_cevresi REAL,
                  kalca_cevresi REAL,
                  bmi REAL,
                  bmh REAL,
                  tdee REAL,
                  su_ihtiyaci REAL,
                  planlanan_kalori INTEGER,
                  notlar TEXT,
                  FOREIGN KEY(danisan_id) REFERENCES danisanlar(id))''')
                  
    # 3. Tablo: ANAMNEZ TESTLERİ (YENİ EKLENEN)
    c.execute('''CREATE TABLE IF NOT EXISTS anamnez_testleri
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  danisan_id INTEGER,
                  tarih TEXT, 
                  skor INTEGER,
                  cevaplar TEXT, 
                  FOREIGN KEY(danisan_id) REFERENCES danisanlar(id))''')
                  
    conn.commit()
    conn.close()

# DB'yi başlat
init_db()

# --- VERİTABANI FONKSİYONLARI (v12'den alınmıştır) ---

def danisan_getir_detay(ad_soyad):
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT * FROM danisanlar WHERE ad_soyad=?"
    result = conn.execute(query, (ad_soyad,)).fetchone()
    conn.close()
    return result

def son_olcum_getir(danisan_id):
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT * FROM olcumler WHERE danisan_id=? ORDER BY tarih DESC LIMIT 1"
    cursor = conn.execute(query, (danisan_id,))
    cols = [column[0] for column in cursor.description]
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return dict(zip(cols, result))
    return None

def olcum_kaydet_db(data):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''INSERT INTO olcumler (danisan_id, tarih, kilo, hedef_kilo, bel_cevresi, kalca_cevresi, bmi, bmh, tdee, su_ihtiyaci, planlanan_kalori, notlar) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                  (data['danisan_id'], data['tarih'], data['kilo'], data['hedef_kilo'], data['bel_cevresi'], 
                   data['kalca_cevresi'], data['bmi'], data['bmh'], data['tdee'], data['su_ihtiyaci'], 
                   data['planlanan_kalori'], data['notlar']))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Ölçüm kaydı hatası: {e}")
        return False

# --- HESAPLAMA MOTORU (v12'den alınmıştır) ---
AKTIVITE_KAT = {
    "Sedanter (Az/Hiç egzersiz)": 1.2,
    "Hafif Aktif (Haftada 1-3 gün)": 1.375,
    "Orta Aktif (Haftada 3-5 gün)": 1.55,
    "Çok Aktif (Haftada 6-7 gün)": 1.725,
    "Ekstra Aktif (Günde 2 kez/Fiziksel iş)": 1.9
}

def detayli_analiz(cinsiyet, kilo, boy, yas, akt_katsayi_deger):
    boy_m = boy / 100
    bmi = kilo / (boy_m ** 2)
    
    # Mifflin-St Jeor BMH
    base = (10 * kilo) + (6.25 * boy) - (5 * yas)
    bmh = base + 5 if cinsiyet == "Erkek" else base - 161
    
    tdee = bmh * akt_katsayi_deger
    
    # İdeal Kilo Aralığı (BMI 18.5 - 24.9)
    ideal_min_kilo = 18.5 * (boy_m ** 2)
    ideal_max_kilo = 24.9 * (boy_m ** 2)
    
    # Su İhtiyacı (Kilo * 30 ml)
    su_ihtiyaci = kilo * 30 / 1000 # Litre olarak
    
    return {
        'bmi': round(bmi, 1),
        'bmh': round(bmh),
        'tdee': round(tdee),
        'ideal_min': round(ideal_min_kilo, 1),
        'ideal_max': round(ideal_max_kilo, 1),
        'su_ihtiyaci': round(su_ihtiyaci, 1)
    }

# --- YENİ MODÜL: ANAMNEZ TEST SORULARI ve SKORLAMA (v13'ten alınmıştır) ---
TEST_SORULARI = {
    "1": {"soru": "Günde kaç öğün yemek yiyorsunuz? (Ara öğünler dahil)", "tip": "slider", "min": 2, "max": 7},
    "2": {"soru": "Yemek yerken çoğunlukla ne hissedersiniz?", "tip": "radio", "se
