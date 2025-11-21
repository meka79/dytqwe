import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Klinik Yönetimi Pro", layout="wide", page_icon="🩺")

# --- VERİTABANI ---
DB_NAME = 'klinik_v4.db'

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
                  bmh REAL, 
                  tdee REAL, 
                  planlanan_kalori INTEGER, 
                  notlar TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- GELİŞMİŞ HESAPLAMA MOTORU ---
def detayli_analiz(cinsiyet, kilo, boy, yas, akt_katsayi):
    # 1. BMI Hesapla
    boy_m = boy / 100
    bmi = kilo / (boy_m ** 2)
    
    # 2. İdeal Kilo Aralığı (BMI 18.5 - 24.9)
    ideal_min = 18.5 * (boy_m ** 2)
    ideal_max = 24.9 * (boy_m ** 2)
    ideal_ort = 22.0 * (boy_m ** 2) # Ortalama ideal
    
    # 3. İdeal Kilo (Hamwi Formülü - Eski ama yaygın pratik referans)
    if cinsiyet == "Erkek":
        ibw_hamwi = 50 + 2.3 * ((boy / 2.54) - 60)
    else:
        ibw_hamwi = 45.5 + 2.3 * ((boy / 2.54) - 60)
        
    # 4. Formüle Ağırlık (Adjusted Body Weight)
    # Formül: IBW + 0.25 * (Mevcut - IBW)
    # Genelde Obezite (BMI > 30) durumunda BMH hesaplarken kullanılması önerilir.
    ajbw = ibw_hamwi + 0.25 * (kilo - ibw_hamwi)
    
    # 5. BMH Hesapla (Mifflin-St Jeor)
    # Standart olarak mevcut kiloyu kullanırız, ancak obezitede uzman formüle ağırlığı tercih edebilir.
    # Biz varsayılan olarak Mevcut Kilo ile hesaplıyoruz, kararı diyetisyene bırakıyoruz.
    base = (10 * kilo) + (6.25 * boy) - (5 * yas)
    bmh = base + 5 if cinsiyet == "Erkek" else base - 161
    
    tdee = bmh * akt_katsayi
    
    return {
        "bmi": bmi,
        "ideal_aralik": (ideal_min, ideal_max),
        "ideal_ort": ideal_ort,
        "formule_agirlik": ajbw,
        "bmh": bmh,
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
    st.title("🔬 Profesyonel Diyet Planlayıcı")
    
    # --- GİRİŞ FORMU ---
    with st.expander("Danışan Profil ve Ölçümleri", expanded=True):
        c1, c2, c3 = st.columns(3)
        ad = c1.text_input("Ad Soyad")
        cinsiyet = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        yas = c3.number_input("Yaş", 10, 90, 30)
        
        c4, c5, c6 = st.columns(3)
        boy = c4.number_input("Boy (cm)", 140, 220, 170)
        kilo = c5.number_input("Mevcut Kilo (kg)", 40.0, 250.0, 85.0, step=0.1)
        
        akt_dict = {"Sedanter (1.2)": 1.2, "Hafif (1.375)": 1.375, "Orta (1.55)": 1.55, "Yüksek (1.725)": 1.725}
        akt_secim = st.selectbox("Aktivite Seviyesi", list(akt_dict.keys()))

        if st.button("Analiz Et", type="primary"):
            sonuclar = detayli_analiz(cinsiyet, kilo, boy, yas, akt_dict[akt_secim])
            st.session_state['data'] = {
                'ad': ad, 'cinsiyet': cinsiyet, 'yas': yas, 'boy': boy, 'kilo': kilo,
                'analiz': sonuclar, 'akt_katsayi': akt_dict[akt_secim]
            }
            st.session_state['analiz_yapildi'] = True

    # --- SONUÇ VE PLANLAMA ---
    if st.session_state['analiz_yapildi']:
        d = st.session_state['data']
        a = d['analiz'] # Analiz sonuçları
        
        st.divider()
        
        # 1. METABOLİK TABLO (GELİŞTİRİLMİŞ)
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        # BMI Rengi
        bmi_renk = "off"
        if a['bmi'] < 18.5: bmi_durum = "Zayıf"; bmi_renk="off"
        elif 18.5 <= a['bmi'] < 25: bmi_durum = "Normal"; bmi_renk="normal"
        elif 25 <= a['bmi'] < 30: bmi_durum = "Fazla Kilolu"; bmi_renk="inverse"
        else: bmi_durum = "Obez"; bmi_renk="inverse"

        col_m1.metric("Mevcut BMI", f"{a['bmi']:.1f}", bmi_durum, delta_color=bmi_renk)
        col_m2.metric("BMH (Mifflin)", f"{int(a['bmh'])} kcal")
        col_m3.metric("TDEE (Koruma)", f"{int(a['tdee'])} kcal")
        
        # Formüle Ağırlık Gösterimi (Sadece Obezite durumunda mantıklı ama hep gösterelim bilgi olsun)
        if a['bmi'] > 25:
            col_m4.metric("Formüle Ağırlık (AjBW)", f"{a['formule_agirlik']:.1f} kg", "Düzeltilmiş")
            st.caption("ℹ️ *Danışan kilolu olduğu için 'Formüle Ağırlık' hesaplandı. Enerji ihtiyacını hesaplarken bu ağırlığı referans alabilirsiniz.*")
        else:
            col_m4.metric("İdeal Kilo (Ort)", f"{a['ideal_ort']:.1f} kg")

        st.success(f"✅ **Tıbbi İdeal Kilo Aralığı (BMI 18.5-24.9):** {a['ideal_aralik'][0]:.1f} kg - {a['ideal_aralik'][1]:.1f} kg")
        
        st.divider()

        # 2. HEDEF BELİRLEME
        col_hedef1, col_hedef2 = st.columns([1, 2])
        
        with col_hedef1:
            st.subheader("🎯 Hedef Kilo")
            # Slider yerine number input daha hassas
            hedef_kilo = st.number_input("Hedeflenen Kilo (kg)", 40.0, 250.0, value=d['kilo'], step=0.5)
            kilo_farki = hedef_kilo - d['kilo']
            
            durum_text = ""
            if kilo_farki < 0: durum_text = "Vermesi Gerekiyor 📉"
            elif kilo_farki > 0: durum_text = "Alması Gerekiyor 📈"
            else: durum_text = "Koruması Gerekiyor 🛡️"
            
            st.info(f"Durum: **{abs(kilo_farki):.1f} kg** {durum_text}")

        with col_hedef2:
            st.subheader("⚡ Kalori ve Hız Ayarı")
            
            planlanan_kalori = int(a['tdee'])
            tahmini_hafta = 0
            
            if kilo_farki < 0: # Kilo Verme
                hiz_opsiyonlari = {
                    "Yavaş (-0.25 kg/h)": 275,
                    "Standart (-0.5 kg/h)": 550,
                    "Hızlı (-0.75 kg/h)": 825,
                    "Agresif (-1.0 kg/h)": 1100
                }
                secim = st.selectbox("Kilo Verme Hızı", list(hiz_opsiyonlari.keys()), index=1)
                acik = hiz_opsiyonlari[secim]
                planlanan_kalori = int(a['tdee'] - acik)
                
                haftalik_kayip = (acik * 7) / 7700
                tahmini_hafta = abs(kilo_farki) / haftalik_kayip
                
                # Güvenlik Kontrolü
                if planlanan_kalori < a['bmh']:
                    st.error(f"⚠️ Uyarı: Hedef kalori ({planlanan_kalori}), BMH'nin ({int(a['bmh'])}) altında. Formüle ağırlığı göz önünde bulundurun.")

            elif kilo_farki > 0: # Kilo Alma
                hiz_opsiyonlari_al = {
                    "Yavaş (+0.25 kg/h)": 275,
                    "Standart (+0.5 kg/h)": 550
                }
                secim = st.selectbox("Kilo Alma Hızı", list(hiz_opsiyonlari_al.keys()))
                fazla = hiz_opsiyonlari_al[secim]
                planlanan_kalori = int(a['tdee'] + fazla)
                
                haftalik_kazanc = (fazla * 7) / 7700
                tahmini_hafta = abs(kilo_farki) / haftalik_kazanc
            
            # SONUÇ KARTI
            tarih_str = tarih_hesapla(tahmini_hafta) if tahmini_hafta > 0 else "Hedefte"
            st.markdown(f"""
            <div style="border: 2px solid #4CAF50; padding: 15px; border-radius: 10px; text-align: center;">
                <h2 style="margin:0; color:#4CAF50">{planlanan_kalori} kcal</h2>
                <p style="margin:0;">Günlük Beslenme Hedefi</p>
                <hr>
                <p>📅 Tahmini Bitiş: <b>{tarih_str}</b> ({int(tahmini_hafta)} Hafta)</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("💾 Veritabanına Kaydet"):
                try:
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    c.execute('''INSERT INTO danisanlar (tarih, ad_soyad, cinsiyet, yas, boy, 
                                 baslangic_kilo, hedef_kilo, bmi, bmh, tdee, planlanan_kalori, notlar)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (datetime.date.today(), d['ad'], d['cinsiyet'], d['yas'], d['boy'], 
                               d['kilo'], hedef_kilo, a['bmi'], a['bmh'], a['tdee'], planlanan_kalori, "Auto-Save"))
                    conn.commit()
                    conn.close()
                    st.success("Danışan planı kaydedildi!")
                except Exception as e:
                    st.error(e)

elif menu == "2. Veritabanı":
    st.title("📂 Danışan Listesi")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM danisanlar ORDER BY id DESC", conn)
    conn.close()
    st.dataframe(df)
