import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Klinik Pro", layout="wide", page_icon="🥗")

# --- VERİTABANI (İLİŞKİSEL & GELİŞMİŞ) ---
DB_NAME = 'klinik_v9_pro.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Tablo: DANIŞANLAR (Sabit Bilgiler)
    c.execute('''CREATE TABLE IF NOT EXISTS danisanlar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  ad_soyad TEXT UNIQUE, 
                  cinsiyet TEXT, 
                  dogum_yili INTEGER, 
                  boy REAL, 
                  telefon TEXT,
                  kayit_tarihi TEXT)''')
    
    # 2. Tablo: ÖLÇÜMLER (Değişken Bilgiler - Bel/Kalça eklendi)
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
    
    conn.commit()
    conn.close()

init_db()

# --- BİLİMSEL HESAPLAMA MOTORU (Academic Engine) ---
def bilimsel_analiz(cinsiyet, kilo, boy, yas, akt_katsayi, bel, kalca):
    # 1. BMI
    boy_m = boy / 100.0
    bmi = kilo / (boy_m ** 2)
    
    # 2. İdeal Kilo (Hamwi Formülü - Klinik Standart)
    # Erkek: 152.4 cm (5 ft) için 48kg + her 2.54cm (1 inch) için 2.7kg
    # Kadın: 152.4 cm (5 ft) için 45.5kg + her 2.54cm (1 inch) için 2.2kg
    boy_inch_farki = (boy - 152.4) / 2.54
    if boy_inch_farki < 0: boy_inch_farki = 0
    
    if cinsiyet == "Erkek":
        ideal_kilo = 48 + (2.7 * boy_inch_farki)
    else:
        ideal_kilo = 45.5 + (2.2 * boy_inch_farki)
        
    # 3. Obezite Kontrolü ve AjBW (Düzeltilmiş Ağırlık)
    hesap_agirligi = kilo
    kullanilan_metod = "Mevcut Kilo"
    
    if bmi > 30:
        # Obez bireylerde Mifflin formülü mevcut kiloyla fazla sonuç verir.
        # AjBW = İdeal + 0.25 * (Mevcut - İdeal)
        ajbw = ideal_kilo + 0.25 * (kilo - ideal_kilo)
        hesap_agirligi = ajbw
        kullanilan_metod = "Düzeltilmiş Ağırlık (AjBW)"
    
    # 4. BMH (Mifflin-St Jeor)
    base = (10 * hesap_agirligi) + (6.25 * boy) - (5 * yas)
    bmh = base + 5 if cinsiyet == "Erkek" else base - 161
    
    # 5. TDEE
    tdee = bmh * akt_katsayi
    
    # 6. Sağlık Risk Analizi (WHR - Bel/Kalça)
    whr = 0
    risk_text = "Veri Yok"
    if bel > 0 and kalca > 0:
        whr = bel / kalca
        if cinsiyet == "Erkek":
            risk_text = "Yüksek Risk ⚠️" if whr > 0.9 else "Düşük Risk ✅"
        else:
            risk_text = "Yüksek Risk ⚠️" if whr > 0.85 else "Düşük Risk ✅"

    # 7. Su İhtiyacı (35ml/kg)
    su = kilo * 0.035
    
    return {
        "bmi": bmi,
        "ideal_kilo": ideal_kilo,
        "bmh": bmh,
        "tdee": tdee,
        "kullanilan_metod": kullanilan_metod,
        "whr": whr,
        "risk_text": risk_text,
        "su": su
    }

# --- YARDIMCI SQL FONKSİYONLARI ---
def danisan_getir_isimle(ad_soyad):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM danisanlar WHERE ad_soyad=?", (ad_soyad,))
    d = c.fetchone()
    conn.close()
    return d

def yeni_danisan_ekle(ad, cinsiyet, d_yili, boy, tel):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO danisanlar (ad_soyad, cinsiyet, dogum_yili, boy, telefon, kayit_tarihi) VALUES (?, ?, ?, ?, ?, ?)",
                  (ad, cinsiyet, d_yili, boy, tel, datetime.date.today()))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def olcum_kaydet(d_id, kilo, hedef, bel, kalca, bmi, bmh, tdee, su, plan, notlar):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO olcumler 
                 (danisan_id, tarih, kilo, hedef_kilo, bel_cevresi, kalca_cevresi, bmi, bmh, tdee, su_ihtiyaci, planlanan_kalori, notlar) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (d_id, datetime.date.today(), kilo, hedef, bel, kalca, bmi, bmh, tdee, su, plan, notlar))
    conn.commit()
    conn.close()

# --- ARAYÜZ ---
menu = st.sidebar.radio("Menü", ["1. Danışan Kabul & Analiz", "2. Danışan Dosyası (Takip)"])

# ---------------------------------------------------------
# TAB 1: ANALİZ (GİRİŞ)
# ---------------------------------------------------------
if menu == "1. Danışan Kabul & Analiz":
    st.title("🔬 Yeni Analiz / Seans")
    
    conn = sqlite3.connect(DB_NAME)
    df_d = pd.read_sql("SELECT ad_soyad FROM danisanlar", conn)
    conn.close()
    isimler = df_d['ad_soyad'].tolist()
    
    mod = st.radio("İşlem Türü:", ["Mevcut Danışan", "Yeni Kayıt"], horizontal=True)
    
    # Değişkenleri Tanımla
    ad_soyad, cinsiyet, yas, boy, telefon = "", "Kadın", 30, 170.0, ""
    
    if mod == "Mevcut Danışan":
        ad_soyad = st.selectbox("Danışan Seç:", isimler)
        if ad_soyad:
            d = danisan_getir_isimle(ad_soyad) # id, ad, cins, dyili, boy, tel, tarih
            cinsiyet = d[2]
            yas = datetime.date.today().year - d[3]
            boy = d[4]
            telefon = d[5]
            st.info(f"👤 **{ad_soyad}** seçildi. | {yas} Yaş | {boy} cm")
    else:
        st.markdown("##### 📝 Kimlik Bilgileri")
        c1, c2 = st.columns(2)
        ad_soyad = c1.text_input("Ad Soyad")
        cinsiyet = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        yas = c1.number_input("Yaş", 10, 90, 30)
        boy = c2.number_input("Boy (cm)", 140.0, 220.0, 170.0, step=1.0)
        telefon = c1.text_input("Telefon (İsteğe bağlı)")

    st.markdown("---")
    
    # ÖLÇÜM GİRİŞİ
    st.markdown("##### ⚖️ Antropometrik Ölçümler")
    col1, col2, col3, col4 = st.columns(4)
    kilo = col1.number_input("Kilo (kg)", 40.0, 250.0, 80.0, step=0.1)
    hedef = col2.number_input("Hedef (kg)", 40.0, 250.0, 70.0, step=0.1)
    bel = col3.number_input("Bel Çevresi (cm)", 50.0, 200.0, 80.0, step=0.5)
    kalca = col4.number_input("Kalça Çevresi (cm)", 50.0, 200.0, 100.0, step=0.5)
    
    akt_dict = {"Sedanter (1.2)": 1.2, "Hafif (1.375)": 1.375, "Orta (1.55)": 1.55, "Yüksek (1.725)": 1.725}
    akt = st.selectbox("Aktivite Düzeyi", list(akt_dict.keys()))
    
    if st.button("Analiz Et ve Planla", type="primary", use_container_width=True):
        if not ad_soyad:
            st.error("İsim boş olamaz!")
        else:
            # HESAPLAMA
            res = bilimsel_analiz(cinsiyet, kilo, boy, yas, akt_dict[akt], bel, kalca)
            
            # GÖRSELLEŞTİRME (DASHBOARD)
            st.markdown("### 📊 Metabolik Rapor")
            
            # 1. Satır: Temel Metrikler
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("BMI", f"{res['bmi']:.1f}")
            m2.metric("BMH", f"{int(res['bmh'])} kcal", help=f"Metod: {res['kullanilan_metod']}")
            m3.metric("TDEE", f"{int(res['tdee'])} kcal")
            m4.metric("Su İhtiyacı", f"{res['su']:.1f} Lt")
            
            # 2. Satır: Risk ve İdeal
            r1, r2 = st.columns(2)
            with r1:
                st.info(f"💎 **İdeal Kilo (Hamwi):** {res['ideal_kilo']:.1f} kg")
            with r2:
                renk = "red" if "Yüksek" in res['risk_text'] else "green"
                st.markdown(f"🩺 **Kronik Hastalık Riski (WHR):** :{renk}[{res['risk_text']}]")
            
            # PLANLAMA KISMI
            st.markdown("---")
            st.subheader("🥗 Kalori Planlama")
            
            fark = hedef - kilo
            durum = "Koruma"
            if fark < 0: durum = "Kilo Verme"
            elif fark > 0: durum = "Kilo Alma"
            
            p1, p2 = st.columns([2, 1])
            with p1:
                plan_kalori = int(res['tdee'])
                if durum == "Kilo Verme":
                    hiz = st.select_slider("Defisit Şiddeti", options=["Hafif (-250)", "Orta (-500)", "Yüksek (-750)"], value="Orta (-500)")
                    eksilen = int(hiz.split("(")[1].replace(")", ""))
                    plan_kalori = int(res['tdee'] + eksilen)
                elif durum == "Kilo Alma":
                    plan_kalori = int(res['tdee'] + 400)
                    
                st.metric("📝 Planlanan Günlük Kalori", f"{plan_kalori} kcal")
                
                # GÜVENLİK KONTROLÜ
                if plan_kalori < res['bmh']:
                    if res['bmi'] > 30:
                        st.success("✅ Obezite yönetiminde BMH altı planlama (kontrollü) uygundur.")
                    else:
                        st.warning(f"⚠️ Dikkat: {plan_kalori} kcal, BMH'nin altında. Uzun süre uygulanmamalıdır.")

            with p2:
                notlar = st.text_area("Klinik Notlar", "İlk görüşme.")
                
                if st.button("💾 SEANSI KAYDET"):
                    # 1. Önce Danışan Kaydı (Eğer Yeniyse)
                    d_id = -1
                    if mod == "Yeni Kayıt":
                        if yeni_danisan_ekle(ad_soyad, cinsiyet, datetime.date.today().year - yas, boy, telefon):
                            yenilenen = danisan_getir_isimle(ad_soyad)
                            d_id = yenilenen[0]
                            st.toast("Yeni danışan profili oluşturuldu.")
                        else:
                            st.error("Bu isimde kayıt zaten var.")
                            st.stop()
                    else:
                        mevcut = danisan_getir_isimle(ad_soyad)
                        d_id = mevcut[0]
                    
                    # 2. Ölçüm Kaydı
                    if d_id != -1:
                        olcum_kaydet(d_id, kilo, hedef, bel, kalca, res['bmi'], res['bmh'], res['tdee'], res['su'], plan_kalori, notlar)
                        st.success("✅ Seans ve ölçümler başarıyla veritabanına işlendi!")

# ---------------------------------------------------------
# TAB 2: DANIŞAN DOSYASI (TAKİP)
# ---------------------------------------------------------
elif menu == "2. Danışan Dosyası (Takip)":
    st.title("📂 Danışan Dosyası")
    
    conn = sqlite3.connect(DB_NAME)
    df_d = pd.read_sql("SELECT ad_soyad FROM danisanlar", conn)
    
    if df_d.empty:
        st.warning("Kayıt yok.")
    else:
        secilen = st.selectbox("Dosyasını Açacağınız Danışan:", df_d['ad_soyad'])
        d_bilgi = danisan_getir_isimle(secilen)
        d_id = d_bilgi[0]
        
        # Verileri Çek
        df_o = pd.read_sql(f"SELECT * FROM olcumler WHERE danisan_id={d_id} ORDER BY tarih", conn)
        
        if not df_o.empty:
            # ÜST BİLGİ KARTI
            col1, col2, col3 = st.columns(3)
            col1.info(f"**Ad:** {d_bilgi[1]} ({d_bilgi[2]})")
            col2.info(f"**Boy:** {d_bilgi[4]} cm")
            col3.info(f"**Kayıt:** {d_bilgi[6]}")
            
            # GRAFİKLER (YAN YANA)
            st.subheader("📈 Gelişim Grafikleri")
            c_g1, c_g2 = st.columns(2)
            
            with c_g1:
                st.caption("Kilo Değişimi")
                st.line_chart(df_o.set_index('tarih')['kilo'])
            
            with c_g2:
                st.caption("Bel Çevresi Değişimi (Risk Takibi)")
                if df_o['bel_cevresi'].sum() > 0: # Veri varsa çiz
                    st.line_chart(df_o.set_index('tarih')['bel_cevresi'], color="#ffaa00")
                else:
                    st.warning("Bel ölçümü verisi yetersiz.")

            # TABLO VE DETAYLAR
            st.subheader("📋 Seans Geçmişi")
            
            # Görünecek kolonları seçelim
            gosterim = df_o[['id', 'tarih', 'kilo', 'hedef_kilo', 'bmi', 'su_ihtiyaci', 'planlanan_kalori', 'notlar']]
            st.dataframe(gosterim, use_container_width=True)
            
            # SİLME FONKSİYONU
            with st.expander("🗑️ Hatalı Kayıt Sil"):
                sil_id = st.number_input("Silinecek ID", min_value=0)
                if st.button("Sil"):
                    cur = conn.cursor()
                    cur.execute("DELETE FROM olcumler WHERE id=?", (sil_id,))
                    conn.commit()
                    st.rerun()
        else:
            st.info("Bu danışanın henüz ölçüm kaydı yok.")
    
    conn.close()
