import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Klinik Yönetimi Pro", layout="wide", page_icon="🩺")

# --- VERİTABANI ---
DB_NAME = 'klinik_v6.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS danisanlar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  tarih TEXT, 
                  ad_soyad TEXT, 
                  cinsiyet TEXT, 
                  yas INTEGER, 
                  boy REAL, 
                  baslangic_kilo REAL, 
                  hedef_kilo REAL,
                  bmi REAL,
                  bmh_mevcut REAL, 
                  tdee REAL, 
                  planlanan_kalori INTEGER, 
                  notlar TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- HESAPLAMA MOTORU ---
def detayli_analiz(cinsiyet, kilo, boy, yas, akt_katsayi):
    # 1. BMI
    boy_m = boy / 100
    bmi = kilo / (boy_m ** 2)
    
    # 2. İdeal Aralık
    i
