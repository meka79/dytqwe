import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Pro Paneli", layout="wide", page_icon="🥗")

# --- VERİTABANI ---
DB_NAME = 'klinik_v7_pro.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tablo yapısı aynen korundu
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
    boy_m = boy / 100
    bmi = kilo / (boy_m ** 2)
    
    ideal_min = 18.5 * (boy_m ** 2)
    ideal_max = 24.9 * (boy_m ** 2)
    
    base_mevcut = (10 * kilo) + (6.25 * boy) - (5 * yas)
    bmh_mevcut = base_mevcut + 5 if cinsiyet == "Erkek" else base_mevcut - 161
    
    ideal_kilo_ref = 22 * (boy_m ** 2)
    base_ideal = (10 * ideal_kilo_ref) + (6.25 * boy) - (5 * yas)
    bmh_ideal = base_ideal + 5 if cinsiyet == "Erkek" else base_ideal - 161
    
    tdee = bmh_mevcut * akt_katsayi
    
    return {
        "bmi": bmi,
        "ideal_aralik": (ideal_min, ideal_max),
        "bmh_mevcut": bmh_mevcut,
        "bmh_ideal": bmh_ideal,
        "tdee": tdee
    }

def makro_hesapla(kalori, oran_tipi):
    # Oranlar: (Karb, Protein, Yağ)
    oranlar = {
        "Dengeli (%50 K, %30 P, %20 Y)": (0.50, 0.30, 0.20),
        "Düşük Karb (%25 K, %40 P, %35 Y)": (0.25, 0.40, 0.35),
        "Sporcu/Yüksek K (%60 K, %25 P, %15 Y)": (0.60, 0.25, 0.15)
    }
    k_oran, p_oran, y_oran = oranlar[oran_tipi]
    
    # 1g Karb = 4kcal, 1g Protein = 4kcal, 1g Yağ = 9kcal
    k_gr = (kalori * k_oran) / 4
    p_gr = (kalori * p_oran) / 4
    y_gr = (kalori * y_oran) / 9
    
    return int(k_gr), int(p_gr), int(y_gr)

def tarih_hesapla(hafta_sayisi):
    bugun = datetime.date.today()
    bitis_tarihi = bugun + timedelta(weeks=hafta_sayisi)
    return bitis_tarihi.strftime("%d.%m.%Y")

# --- ARAYÜZ ---
if 'analiz_yapildi' not in st.session_state:
    st.session_state['analiz_yapildi'] = False

# Sidebar Tasarım
st.sidebar.header("Diyetisyen Paneli v7")
menu = st.sidebar.radio("Mod Seçimi", ["1. Yeni Analiz & Planlama", "2. Danışan Takip & Düzenleme"])

# ---------------------------------------------------------
# TAB 1: YENİ ANALİZ VE PLANLAMA
# ---------------------------------------------------------
if menu == "1. Yeni Analiz & Planlama":
    st.title("🔬 Profesyonel Diyet Planlayıcı")
    
    with st.expander("Danışan Veri Girişi", expanded=True):
        # Daha kompakt tasarım
        c1, c2 = st.columns([3, 1])
        ad = c1.text_input("Danışan Adı Soyadı (Takip için önemli)")
        cinsiyet = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        
        c3, c4, c5, c6 = st.columns(4)
        yas = c3.number_input("Yaş", 10, 90, 30)
        boy = c4.number_input("Boy (cm)", 140, 220, 170)
        kilo = c5.number_input("Güncel Kilo (kg)", 40.0, 250.0, 80.0, step=0.1)
        
        akt_dict = {"Sedanter (1.2)": 1.2, "Hafif (1.375)": 1.375, "Orta (1.55)": 1.55, "Yüksek (1.725)": 1.725}
        akt_secim = c6.selectbox("Aktivite", list(akt_dict.keys()))

        if st.button("Analiz Et", type="primary", use_container_width=True):
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
        st.markdown("### 1. Metabolik Analiz")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        bmi_val = a['bmi']
        # Renkli BMI göstergesi
        if bmi_val < 18.5: renk="blue"; dur="Zayıf"
        elif 18.5 <= bmi_val < 25: renk="green"; dur="Normal"
        elif 25 <= bmi_val < 30: renk="orange"; dur="Fazla Kilolu"
        else: renk="red"; dur="Obez"

        col_m1.metric("BMI", f"{bmi_val:.1f}", dur, delta_color="off")
        col_m2.metric("Bazal Metabolizma", f"{int(a['bmh_mevcut'])} kcal")
        col_m3.metric("Günlük Enerji (TDEE)", f"{int(a['tdee'])} kcal")
        col_m4.info(f"İdeal Aralık: {a['ideal_aralik'][0]:.1f} - {a['ideal_aralik'][1]:.1f} kg")
        
        st.divider()

        # 2. HEDEF VE STRATEJİ
        st.markdown("### 2. Hedef Belirleme")
        c_h1, c_h2 = st.columns([1, 2])
        
        with c_h1:
            hedef_kilo = st.number_input("Hedef Kilo (kg)", 40.0, 250.0, value=d['kilo'], step=0.5)
            kilo_farki = hedef_kilo - d['kilo']
            
            # Hedef Kartı
            bg_color = "#e8f5e9" if kilo_farki == 0 else ("#ffebee" if kilo_farki < 0 else "#e3f2fd")
            msg = "KORUMA" if kilo_farki == 0 else ("VERİLECEK" if kilo_farki < 0 else "ALINACAK")
            st.markdown(f"""
            <div style="background-color:{bg_color}; padding:10px; border-radius:5px; text-align:center; color:black;">
                <h3 style="margin:0">{abs(kilo_farki):.1f} kg</h3>
                <small>{msg}</small>
            </div>
            """, unsafe_allow_html=True)

        with c_h2:
            final_kalori = int(a['tdee'])
            tahmini_hafta = 0
            
            # Kalori Hesap Mantığı
            if kilo_farki < 0: # Kilo Ver
                hiz = st.select_slider("Kilo Verme Hızı", options=["Yavaş", "Standart", "Hızlı", "Agresif"], value="Standart")
                acik_map = {"Yavaş": 250, "Standart": 500, "Hızlı": 750, "Agresif": 1000}
                final_kalori = int(a['tdee'] - acik_map[hiz])
                tahmini_hafta = abs(kilo_farki) / ((acik_map[hiz] * 7) / 7700)
            elif kilo_farki > 0: # Kilo Al
                final_kalori = int(a['tdee'] + 400) # Sabit +400 kcal fazlası
                tahmini_hafta = abs(kilo_farki) / ((400 * 7) / 7700)

            # Güvenlik Uyarısı
            if final_kalori < a['bmh_mevcut'] and bmi_val < 30:
                st.warning(f"⚠️ Dikkat: {final_kalori} kcal, danışanın Bazal Metabolizmasının ({int(a['bmh_mevcut'])}) altında!")

            # SONUÇ KARTI (Makro Eklenmiş)
            makro_tipi = st.selectbox("Makro Dağılım Tipi", ["Dengeli (%50 K, %30 P, %20 Y)", "Düşük Karb (%25 K, %40 P, %35 Y)", "Sporcu/Yüksek K (%60 K, %25 P, %15 Y)"])
            k_g, p_g, y_g = makro_hesapla(final_kalori, makro_tipi)
            
            st.markdown(f"""
            <div style="border: 2px solid #4CAF50; border-radius: 10px; background-color: #1E1E1E; padding: 15px; color: white;">
                <div style="display:flex; justify-content:space-around; align-items:center;">
                    <div style="text-align:center;">
                        <h1 style="margin:0; color:#66bb6a;">{final_kalori}</h1>
                        <small>HEDEF KCAL</small>
                    </div>
                    <div style="text-align:left; border-left: 1px solid gray; padding-left: 15px;">
                        <div>🍞 <b>{k_g}g</b> Karb</div>
                        <div>🥩 <b>{p_g}g</b> Protein</div>
                        <div>🥑 <b>{y_g}g</b> Yağ</div>
                    </div>
                </div>
                <hr style="border-color: #4CAF50; opacity:0.3;">
                <div style="text-align:center; font-size:14px;">
                    📅 Tahmini Hedef Tarihi: <b>{tarih_hesapla(tahmini_hafta)}</b> ({int(tahmini_hafta)} Hafta)
                </div>
            </div>
            """, unsafe_allow_html=True)

            # KAYDET BUTONU
            st.write("")
            notlar = st.text_area("Danışan Notu:", placeholder="Örn: Gluten hassasiyeti var.")
            
            if st.button("💾 Analizi Veritabanına Kaydet", use_container_width=True):
                if not d['ad']:
                    st.error("Lütfen isim giriniz.")
                else:
                    try:
                        conn = sqlite3.connect(DB_NAME)
                        c = conn.cursor()
                        # Makroları notlara ekleyelim ki kaybolmasın
                        final_not = f"{notlar} | Makro: K:{k_g}g P:{p_g}g Y:{y_g}g"
                        c.execute('''INSERT INTO danisanlar (tarih, ad_soyad, cinsiyet, yas, boy, 
                                     baslangic_kilo, hedef_kilo, bmi, bmh_mevcut, tdee, planlanan_kalori, notlar)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                                  (datetime.date.today(), d['ad'], d['cinsiyet'], d['yas'], d['boy'], 
                                   d['kilo'], hedef_kilo, bmi_val, a['bmh_mevcut'], a['tdee'], final_kalori, final_not))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ {d['ad']} veritabanına başarıyla kaydedildi!")
                    except Exception as e:
                        st.error(f"Hata: {e}")

# ---------------------------------------------------------
# TAB 2: VERİTABANI & TAKİP (GELİŞTİRİLMİŞ)
# ---------------------------------------------------------
elif menu == "2. Danışan Takip & Düzenleme":
    st.title("📂 Danışan Yönetim Merkezi")
    
    conn = sqlite3.connect(DB_NAME)
    # Tüm veriyi çek
    df = pd.read_sql_query("SELECT * FROM danisanlar ORDER BY tarih DESC", conn)
    
    if df.empty:
        st.warning("Henüz kayıt bulunmamaktadır.")
    else:
        # A. FİLTRELEME ALANI
        st.markdown("##### 🔍 Danışan Bul")
        isim_listesi = ["Tümü"] + df['ad_soyad'].unique().tolist()
        secilen_isim = st.selectbox("İsme Göre Filtrele:", isim_listesi)
        
        if secilen_isim != "Tümü":
            # KİŞİYE ÖZEL GÖRÜNÜM
            kisi_df = df[df['ad_soyad'] == secilen_isim].sort_values(by='tarih')
            
            # 1. Grafik
            st.subheader(f"📈 {secilen_isim} - Kilo İlerlemesi")
            if len(kisi_df) > 1:
                chart_data = kisi_df[['tarih', 'baslangic_kilo']].set_index('tarih')
                chart_data.columns = ['Kilo'] # Grafik lejantı için
                st.line_chart(chart_data)
                
                ilk = kisi_df.iloc[0]['baslangic_kilo']
                son = kisi_df.iloc[-1]['baslangic_kilo']
                fark = son - ilk
                st.caption(f"Toplam Değişim: {fark:.1f} kg")
            else:
