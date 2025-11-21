import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Klinik Yönetimi Pro", layout="wide", page_icon="🥗")

# --- VERİTABANI ---
DB_NAME = 'klinik_v3.db'

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
                  bmh REAL, 
                  tdee REAL, 
                  planlanan_kalori INTEGER, 
                  tahmini_sure_hafta REAL,
                  notlar TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- HESAPLAMA MOTORU ---
def hesapla_bmh_tdee(cinsiyet, kilo, boy, yas, akt_katsayi):
    # Mifflin-St Jeor
    base = (10 * kilo) + (6.25 * boy) - (5 * yas)
    bmh = base + 5 if cinsiyet == "Erkek" else base - 161
    tdee = bmh * akt_katsayi
    
    # İdeal Kilo (Robinson)
    boy_m = boy / 100
    if cinsiyet == "Erkek":
        ideal = 52 + 1.9 * ((boy / 2.54) - 60)
    else:
        ideal = 49 + 1.7 * ((boy / 2.54) - 60)
    return bmh, tdee, ideal

def tarih_hesapla(hafta_sayisi):
    bugun = datetime.date.today()
    bitis_tarihi = bugun + timedelta(weeks=hafta_sayisi)
    return bitis_tarihi.strftime("%d.%m.%Y")

# --- ARAYÜZ ---
if 'analiz_yapildi' not in st.session_state:
    st.session_state['analiz_yapildi'] = False

menu = st.sidebar.radio("Klinik Paneli", ["1. Danışan Planlama", "2. Veritabanı"])

if menu == "1. Danışan Planlama":
    st.title("🎯 Hedef Odaklı Diyet Planlayıcı")
    
    # --- GİRİŞ FORMU ---
    with st.expander("Danışan Bilgileri", expanded=True):
        c1, c2, c3 = st.columns(3)
        ad = c1.text_input("Ad Soyad")
        cinsiyet = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        yas = c3.number_input("Yaş", 10, 90, 30)
        
        c4, c5, c6 = st.columns(3)
        boy = c4.number_input("Boy (cm)", 140, 220, 170)
        kilo = c5.number_input("Mevcut Kilo (kg)", 40.0, 200.0, 85.0, step=0.1)
        hedef_kilo = c6.number_input("🎯 Hedeflenen Kilo (kg)", 40.0, 200.0, 75.0, step=0.1)
        
        akt_dict = {"Sedanter (1.2)": 1.2, "Hafif (1.375)": 1.375, "Orta (1.55)": 1.55, "Yüksek (1.725)": 1.725}
        akt_secim = st.selectbox("Aktivite Seviyesi", list(akt_dict.keys()))

        if st.button("Profili Analiz Et", type="primary"):
            bmh, tdee, ideal = hesapla_bmh_tdee(cinsiyet, kilo, boy, yas, akt_dict[akt_secim])
            st.session_state['data'] = {
                'ad': ad, 'cinsiyet': cinsiyet, 'yas': yas, 'boy': boy, 
                'kilo': kilo, 'hedef_kilo': hedef_kilo,
                'bmh': bmh, 'tdee': tdee, 'ideal': ideal
            }
            st.session_state['analiz_yapildi'] = True

    # --- PLANLAMA EKRANI ---
    if st.session_state['analiz_yapildi']:
        d = st.session_state['data']
        kilo_farki = d['hedef_kilo'] - d['kilo']
        
        st.divider()
        
        # Durum Tespiti (Kilo verecek mi alacak mı?)
        durum = "Koru"
        if kilo_farki < 0: durum = "Ver"
        elif kilo_farki > 0: durum = "Al"
        
        col_info1, col_info2 = st.columns([1, 2])
        
        with col_info1:
            st.subheader("📊 Metabolik Tablo")
            st.write(f"**BMH:** {int(d['bmh'])} kcal")
            st.write(f"**TDEE (Koruma):** {int(d['tdee'])} kcal")
            st.write(f"**İdeal Kilo (Teorik):** {int(d['ideal'])} kg")
            st.metric("Hedefe Uzaklık", f"{abs(kilo_farki):.1f} kg", f"{durum}mesi gerekiyor")

        with col_info2:
            st.subheader("⚙️ Diyet Stratejisi")
            
            secilen_kalori = int(d['tdee'])
            tahmini_hafta = 0
            
            if durum == "Ver":
                st.info("📉 **Kilo Verme Modu Aktif**")
                # Kilo verme hız seçenekleri (Bilimsel Defisitler)
                hiz_secenekleri = {
                    "Çok Yavaş ve Güvenli (Haftada -0.25 kg)": 275,
                    "Standart Önerilen (Haftada -0.5 kg)": 550,
                    "Hızlı (Haftada -0.75 kg)": 825,
                    "Agresif (Haftada -1.0 kg)": 1100
                }
                
                secim = st.radio("Hedeflenen Hız Nedir?", list(hiz_secenekleri.keys()), index=1)
                kalori_acigi = hiz_secenekleri[secim]
                
                # Kalori Hesabı
                secilen_kalori = int(d['tdee'] - kalori_acigi)
                
                # Süre Hesabı: (Toplam Fark * 7700) / Günlük Açık / 7 Gün
                gunluk_yag_yakimi_gr = (kalori_acigi / 7700) * 1000 # Örn: 550/7700 = 0.07kg = 71gr
                haftalik_kayip_kg = (kalori_acigi * 7) / 7700
                tahmini_hafta = abs(kilo_farki) / haftalik_kayip_kg
                
                # Güvenlik Kontrolü
                if secilen_kalori < d['bmh']:
                    st.error(f"⚠️ DİKKAT: Hesaplanan {secilen_kalori} kcal, BMH'nin ({int(d['bmh'])}) altındadır! Metabolizmayı yavaşlatabilir.")
                elif (d['cinsiyet'] == 'Kadın' and secilen_kalori < 1200) or (d['cinsiyet'] == 'Erkek' and secilen_kalori < 1500):
                    st.warning("⚠️ Kalori çok düşük seviyede. Vitamin/Mineral desteği gerekebilir.")
                else:
                    st.success("✅ Kalori güvenli aralıkta.")

            elif durum == "Al":
                st.info("📈 **Kilo Alma Modu Aktif**")
                hiz_secenekleri_al = {
                    "Temiz Büyüme (Haftada +0.25 kg)": 275,
                    "Standart (Haftada +0.5 kg)": 550
                }
                secim = st.radio("Hız Seçimi", list(hiz_secenekleri_al.keys()))
                fazlalik = hiz_secenekleri_al[secim]
                secilen_kalori = int(d['tdee'] + fazlalik)
                
                haftalik_kazanc = (fazlalik * 7) / 7700
                tahmini_hafta = abs(kilo_farki) / haftalik_kazanc

            else:
                st.success("✨ Mevcut kiloyu koruma hedefindesiniz.")
                secilen_kalori = int(d['tdee'])

            # SONUÇ KUTUSU
            st.markdown(f"""
            <div style="background-color:#d4edda;padding:15px;border-radius:10px;color:black">
                <h3>🥗 Diyet Kalorisi: <b>{secilen_kalori} kcal</b></h3>
                <p>📅 Tahmini Hedef Tarihi: <b>{tarih_hesapla(tahmini_hafta)}</b> ({int(tahmini_hafta)} Hafta)</p>
            </div>
            """, unsafe_allow_html=True)
            
            notlar = st.text_area("Özel Klinik Notlar")
            
            if st.button("💾 Planı Onayla ve Kaydet"):
                try:
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    c.execute('''INSERT INTO danisanlar (tarih, ad_soyad, cinsiyet, yas, boy, 
                                 baslangic_kilo, hedef_kilo, bmh, tdee, planlanan_kalori, tahmini_sure_hafta, notlar)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (datetime.date.today(), d['ad'], d['cinsiyet'], d['yas'], d['boy'], 
                               d['kilo'], d['hedef_kilo'], d['bmh'], d['tdee'], secilen_kalori, round(tahmini_hafta, 1), notlar))
                    conn.commit()
                    conn.close()
                    st.balloons()
                    st.success("Kayıt Başarılı!")
                except Exception as e:
                    st.error(f"Hata: {e}")

elif menu == "2. Veritabanı":
    st.title("📂 Danışan Takibi")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM danisanlar ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(df)
