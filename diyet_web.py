import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Klinik Yönetimi Pro", layout="wide", page_icon="🩺")

# --- VERİTABANI ---
DB_NAME = 'klinik_v5.db'

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
    ideal_min = 18.5 * (boy_m ** 2)
    ideal_max = 24.9 * (boy_m ** 2)
    
    # 3. Mifflin-St Jeor (Mevcut Kilo ile - ALTIN STANDART)
    base_mevcut = (10 * kilo) + (6.25 * boy) - (5 * yas)
    bmh_mevcut = base_mevcut + 5 if cinsiyet == "Erkek" else base_mevcut - 161
    
    # 4. Mifflin-St Jeor (İdeal Kilo ile - Referans Amaçlı)
    # İdeal kilonun ortalamasını alalım (BMI 22)
    ideal_kilo_ref = 22 * (boy_m ** 2)
    base_ideal = (10 * ideal_kilo_ref) + (6.25 * boy) - (5 * yas)
    bmh_ideal = base_ideal + 5 if cinsiyet == "Erkek" else base_ideal - 161
    
    tdee = bmh_mevcut * akt_katsayi
    
    return {
        "bmi": bmi,
        "ideal_aralik": (ideal_min, ideal_max),
        "ideal_kilo_ref": ideal_kilo_ref,
        "bmh_mevcut": bmh_mevcut,
        "bmh_ideal": bmh_ideal, # Bunu ekranda kıyaslama için göstereceğiz
        "tdee": tdee
    }

def tarih_hesapla(hafta_sayisi):
    bugun = datetime.date.today()
    bitis_tarihi = bugun + timedelta(weeks=hafta_sayisi)
    return bitis_tarihi.strftime("%d.%m.%Y")

# --- ARAYÜZ ---
if 'analiz_yapildi' not in st.session_state:
    st.session_state['analiz_yapildi'] = False

menu = st.sidebar.radio("Klinik Paneli", ["1. Danışan Planlama", "2. Veritabanı"])

if menu == "1. Danışan Planlama":
    st.title("🔬 Profesyonel Diyet Planlayıcı v2")
    
    with st.expander("Danışan Profil ve Ölçümleri", expanded=True):
        c1, c2, c3 = st.columns(3)
        ad = c1.text_input("Ad Soyad")
        cinsiyet = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        yas = c3.number_input("Yaş", 10, 90, 30)
        
        c4, c5, c6 = st.columns(3)
        boy = c4.number_input("Boy (cm)", 140, 220, 170)
        kilo = c5.number_input("Mevcut Kilo (kg)", 40.0, 250.0, 100.0, step=0.1)
        
        akt_dict = {"Sedanter (1.2)": 1.2, "Hafif (1.375)": 1.375, "Orta (1.55)": 1.55, "Yüksek (1.725)": 1.725}
        akt_secim = st.selectbox("Aktivite Seviyesi", list(akt_dict.keys()))

        if st.button("Analiz Et", type="primary"):
            sonuclar = detayli_analiz(cinsiyet, kilo, boy, yas, akt_dict[akt_secim])
            st.session_state['data'] = {
                'ad': ad, 'cinsiyet': cinsiyet, 'yas': yas, 'boy': boy, 'kilo': kilo,
                'analiz': sonuclar, 'akt_katsayi': akt_dict[akt_secim]
            }
            st.session_state['analiz_yapildi'] = True

    if st.session_state['analiz_yapildi']:
        d = st.session_state['data']
        a = d['analiz']
        
        st.divider()
        
        # 1. METABOLİK DURUM
        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        
        # BMI Renklendirme
        bmi_val = a['bmi']
        bmi_renk = "off"
        if bmi_val < 18.5: bmi_text="Zayıf"; bmi_renk="off"
        elif 18.5 <= bmi_val < 25: bmi_text="Normal"; bmi_renk="normal"
        elif 25 <= bmi_val < 30: bmi_text="Fazla Kilolu"; bmi_renk="inverse"
        else: bmi_text="Obez"; bmi_renk="inverse"

        c_m1.metric("BMI", f"{bmi_val:.1f}", bmi_text, delta_color=bmi_renk)
        c_m2.metric("Gerçek BMH", f"{int(a['bmh_mevcut'])} kcal", help="Mevcut kilo ile hesaplanan (Mifflin)")
        c_m3.metric("İdeal BMH (Ref)", f"{int(a['bmh_ideal'])} kcal", help="Eğer ideal kilosunda olsaydı BMH'sı bu olacaktı.")
        c_m4.metric("TDEE (Koruma)", f"{int(a['tdee'])} kcal")
        
        st.caption(f"✅ **Tıbbi İdeal Kilo Aralığı:** {a['ideal_aralik'][0]:.1f} kg - {a['ideal_aralik'][1]:.1f} kg")
        
        st.divider()

        # 2. PLANLAMA
        c_h1, c_h2 = st.columns([1, 2])
        
        with c_h1:
            st.subheader("🎯 Hedef")
            hedef_kilo = st.number_input("Hedef Kilo (kg)", 40.0, 250.0, value=d['kilo'], step=0.5)
            kilo_farki = hedef_kilo - d['kilo']
            
            durum = ""
            if kilo_farki < 0: durum = "Vermeli 📉"
            elif kilo_farki > 0: durum = "Almalı 📈"
            else: durum = "Korumalı 🛡️"
            st.info(f"Fark: {abs(kilo_farki):.1f} kg ({durum})")

        with c_h2:
            st.subheader("⚡ Strateji")
            
            final_kalori = int(a['tdee'])
            tahmini_hafta = 0
            
            if kilo_farki < 0: # KİLO VERME
                hiz = st.selectbox("Kilo Verme Hızı", ["Yavaş (-0.25)", "Standart (-0.5)", "Hızlı (-0.75)", "Agresif (-1.0)"], index=1)
                
                acik_map = {"Yavaş (-0.25)": 275, "Standart (-0.5)": 550, "Hızlı (-0.75)": 825, "Agresif (-1.0)": 1100}
                acik = acik_map[hiz]
                final_kalori = int(a['tdee'] - acik)
                
                haftalik_kayip = (acik * 7) / 7700
                tahmini_hafta = abs(kilo_farki) / haftalik_kayip
                
                # --- AKILLI GÜVENLİK KONTROLÜ (BURASI YENİLENDİ) ---
                bmh_siniri = a['bmh_mevcut']
                
                if final_kalori < bmh_siniri:
                    if bmi_val >= 30:
                        st.success(f"✅ Obezite (BMI > 30) durumunda, hedef kalori BMH'nin ({int(bmh_siniri)}) altına inebilir. Tıbbi olarak kabul edilebilir sınırdasınız.")
                    elif bmi_val >= 25:
                         st.warning(f"⚠️ Hedef kalori BMH'nin biraz altında. Fazla kilolu bireylerde bu tolere edilebilir ancak protein alımına dikkat ediniz.")
                    else:
                        st.error(f"⛔ HATA: Zayıf veya Normal kilolu bireylerde BMH ({int(bmh_siniri)}) altına düşülmesi önerilmez! Metabolizma zarar görebilir.")
                else:
                    st.success("✅ Kalori hedefi BMH'nin üzerinde, güvenli.")

            elif kilo_farki > 0: # KİLO ALMA
                hiz = st.selectbox("Kilo Alma Hızı", ["Yavaş (+0.25)", "Standart (+0.5)"])
                fazla_map = {"Yavaş (+0.25)": 275, "Standart (+0.5)": 550}
                fazla = fazla_map[hiz]
                final_kalori = int(a['tdee'] + fazla)
                haftalik_kazanc = (fazla * 7) / 7700
                tahmini_hafta = abs(kilo_farki) / haftalik_kazanc

            # SONUÇ
            tarih_str = tarih_hesapla(tahmini_hafta) if tahmini_hafta > 0 else "Hedefte"
            
            st.markdown(f"""
            <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; border-left: 5px solid #ff4b4b;">
                <h2 style="margin:0; color:#333">{final_kalori} kcal</h2>
                <small>Günlük Hedef</small>
                <p style="margin-top:10px">📅 Hedeflenen Tarih: <b>{tarih_str}</b></p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("💾 Kaydet"):
                try:
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    c.execute('''INSERT INTO danisanlar (tarih, ad_soyad, cinsiyet, yas, boy, 
                                 baslangic_kilo, hedef_kilo, bmi, bmh_mevcut, tdee, planlanan_kalori, notlar)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (datetime.date.today(), d['ad'], d['cinsiyet'], d['yas'], d['boy'], 
                               d['kilo'], hedef_kilo, bmi_val, a['bmh_mevcut'], a['tdee'], final_kalori, "Plan Kaydedildi"))
                    conn.commit()
                    conn.close()
                    st.success("Kaydedildi!")
                except Exception as e:
                    st.error(e)

elif menu == "2. Veritabanı":
    st.title("📂 Danışan Kayıtları")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM danisanlar ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(df)
