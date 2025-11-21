import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Klinik Yönetimi Pro", layout="wide", page_icon="🩺")

# --- VERİTABANI (İLİŞKİSEL YAPIYA GEÇİŞ) ---
DB_NAME = 'klinik_v8.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Tablo: HASTALAR (Sabit Bilgiler)
    c.execute('''CREATE TABLE IF NOT EXISTS hastalar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  ad_soyad TEXT UNIQUE, 
                  cinsiyet TEXT, 
                  dogum_yili INTEGER, 
                  boy REAL, 
                  kayit_tarihi TEXT)''')
    
    # 2. Tablo: OLCUMLER (Değişken Bilgiler)
    # hasta_id ile yukarıdaki tabloya bağlanır
    c.execute('''CREATE TABLE IF NOT EXISTS olcumler
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  hasta_id INTEGER,
                  tarih TEXT, 
                  kilo REAL, 
                  hedef_kilo REAL,
                  bmi REAL,
                  bmh REAL,
                  tdee REAL,
                  planlanan_kalori INTEGER,
                  notlar TEXT,
                  FOREIGN KEY(hasta_id) REFERENCES hastalar(id))''')
    
    conn.commit()
    conn.close()

init_db()

# --- YARDIMCI FONKSİYONLAR ---
def hasta_getir_isimle(ad_soyad):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM hastalar WHERE ad_soyad=?", (ad_soyad,))
    hasta = c.fetchone()
    conn.close()
    return hasta # (id, ad, cinsiyet, d_yili, boy, tarih)

def yeni_hasta_ekle(ad, cinsiyet, d_yili, boy):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO hastalar (ad_soyad, cinsiyet, dogum_yili, boy, kayit_tarihi) VALUES (?, ?, ?, ?, ?)",
                  (ad, cinsiyet, d_yili, boy, datetime.date.today()))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False # İsim zaten varsa

def olcum_ekle(hasta_id, kilo, hedef, bmi, bmh, tdee, plan, notlar):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO olcumler (hasta_id, tarih, kilo, hedef_kilo, bmi, bmh, tdee, planlanan_kalori, notlar) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (hasta_id, datetime.date.today(), kilo, hedef, bmi, bmh, tdee, plan, notlar))
    conn.commit()
    conn.close()

# --- HESAPLAMA MOTORU ---
def analiz_motoru(cinsiyet, kilo, boy, yas, akt_katsayi):
    # BMI
    boy_m = boy / 100
    bmi = kilo / (boy_m ** 2)
    
    # İdeal Aralık
    ideal_min = 18.5 * (boy_m ** 2)
    ideal_max = 24.9 * (boy_m ** 2)
    
    # Mifflin-St Jeor
    base = (10 * kilo) + (6.25 * boy) - (5 * yas)
    bmh = base + 5 if cinsiyet == "Erkek" else base - 161
    tdee = bmh * akt_katsayi
    
    return {"bmi": bmi, "bmh": bmh, "tdee": tdee, "ideal_aralik": (ideal_min, ideal_max)}

def tarih_hesapla(hafta_sayisi):
    return (datetime.date.today() + timedelta(weeks=hafta_sayisi)).strftime("%d.%m.%Y")

# --- ARAYÜZ ---
menu = st.sidebar.radio("Klinik Paneli", ["1. Yeni Analiz / Ölçüm", "2. Hasta Takip & Grafik"])

# ---------------------------------------------------------
# TAB 1: ANALİZ VE VERİ GİRİŞİ
# ---------------------------------------------------------
if menu == "1. Yeni Analiz / Ölçüm":
    st.title("🔬 Analiz ve Veri Girişi")
    
    # HASTA SEÇİMİ VEYA YENİ OLUŞTURMA
    st.info("Mevcut bir hastaya ölçüm girmek için ismini aratın, yeni hasta ise bilgilerini girin.")
    
    # Otomatik tamamlama için tüm isimleri çek
    conn = sqlite3.connect(DB_NAME)
    df_hastalar = pd.read_sql("SELECT ad_soyad FROM hastalar", conn)
    conn.close()
    mevcut_isimler = df_hastalar['ad_soyad'].tolist() if not df_hastalar.empty else []
    
    secim_modu = st.radio("Hasta Durumu:", ["Mevcut Hasta", "Yeni Hasta"], horizontal=True)
    
    ad_soyad = ""
    boy = 170.0
    yas = 30
    cinsiyet = "Kadın"
    
    if secim_modu == "Mevcut Hasta":
        ad_soyad = st.selectbox("Hasta Seçiniz:", mevcut_isimler)
        if ad_soyad:
            h = hasta_getir_isimle(ad_soyad) # (id, ad, cins, dyili, boy...)
            # Veritabanından gelen bilgileri doldur
            cinsiyet = h[2]
            yas = datetime.date.today().year - h[3]
            boy = h[4]
            st.success(f"✅ Kayıtlı Hasta: {ad_soyad} | {yas} Yaş | {boy} cm")
    else:
        c1, c2 = st.columns(2)
        ad_soyad = c1.text_input("Ad Soyad Giriniz")
        cinsiyet = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        yas = c1.number_input("Yaş", 10, 90, 30)
        boy = c2.number_input("Boy (cm)", 140, 220, 170.0)
    
    st.markdown("---")
    
    # ÖLÇÜM VERİLERİ
    col_k1, col_k2 = st.columns(2)
    kilo = col_k1.number_input("Güncel Kilo (kg)", 40.0, 250.0, 80.0, step=0.1)
    hedef_kilo = col_k2.number_input("Hedef Kilo (kg)", 40.0, 250.0, 70.0, step=0.1)
    
    akt_dict = {"Sedanter (1.2)": 1.2, "Hafif (1.375)": 1.375, "Orta (1.55)": 1.55, "Yüksek (1.725)": 1.725}
    akt_secim = st.selectbox("Aktivite Seviyesi", list(akt_dict.keys()))
    
    if st.button("Hesapla ve Önizle", type="primary"):
        sonuc = analiz_motoru(cinsiyet, kilo, boy, yas, akt_dict[akt_secim])
        
        # Basit Hesap Gösterimi
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("BMI", f"{sonuc['bmi']:.1f}")
        c2.metric("BMH", f"{int(sonuc['bmh'])}")
        c3.metric("TDEE", f"{int(sonuc['tdee'])}")
        kilo_farki = hedef_kilo - kilo
        
        # Planlanan Kalori (Basit Mantık)
        if kilo_farki < 0: plan = int(sonuc['tdee'] - 500)
        elif kilo_farki > 0: plan = int(sonuc['tdee'] + 400)
        else: plan = int(sonuc['tdee'])
        
        c4.metric("Önerilen", f"{plan} kcal")
        
        # KAYIT ALANI
        st.write("---")
        notlar = st.text_area("Bu seans için notlar:", "Rutin kontrol.")
        
        if st.button("💾 ÖLÇÜMÜ KAYDET"):
            if secim_modu == "Yeni Hasta":
                # Önce hastayı kaydet
                if yeni_hasta_ekle(ad_soyad, cinsiyet, datetime.date.today().year - yas, boy):
                    st.success("Yeni hasta profili oluşturuldu.")
                else:
                    st.error("Bu isimde hasta zaten var! Mevcut hasta moduna geçin.")
                    st.stop()
            
            # Şimdi ölçümü kaydet
            h_kayit = hasta_getir_isimle(ad_soyad)
            if h_kayit:
                olcum_ekle(h_kayit[0], kilo, hedef_kilo, sonuc['bmi'], sonuc['bmh'], sonuc['tdee'], plan, notlar)
                st.success(f"✅ {ad_soyad} için ölçüm başarıyla veritabanına işlendi!")
            else:
                st.error("Hasta ID bulunamadı.")

# ---------------------------------------------------------
# TAB 2: HASTA TAKİP (CRM)
# ---------------------------------------------------------
elif menu == "2. Hasta Takip & Grafik":
    st.title("📈 Danışan İlerleme Takibi")
    
    conn = sqlite3.connect(DB_NAME)
    df_hastalar = pd.read_sql("SELECT * FROM hastalar", conn)
    
    if df_hastalar.empty:
        st.warning("Henüz kayıtlı hasta yok.")
    else:
        # 1. Hasta Seçimi
        secilen_hasta = st.selectbox("Hasta Seçin:", df_hastalar['ad_soyad'])
        hasta_bilgi = df_hastalar[df_hastalar['ad_soyad'] == secilen_hasta].iloc[0]
        hasta_id = hasta_bilgi['id']
        
        # 2. Ölçüm Geçmişini Çek
        df_olcumler = pd.read_sql(f"SELECT * FROM olcumler WHERE hasta_id={hasta_id} ORDER BY tarih", conn)
        
        if not df_olcumler.empty:
            # İLERLEME GRAFİĞİ
            st.subheader(f"{secilen_hasta} - Kilo Değişim Grafiği")
            
            # Streamlit native chart
            chart_data = df_olcumler[['tarih', 'kilo']].set_index('tarih')
            st.line_chart(chart_data)
            
            # DETAYLI TABLO (EDİTLENEBİLİR)
            st.subheader("Geçmiş Ölçümler")
            st.info("Tablo üzerindeki verileri değiştiremezsiniz, silme işlemi için aşağıyı kullanın.")
            
            # Tabloyu Göster
            gosterim_df = df_olcumler[['id', 'tarih', 'kilo', 'hedef_kilo', 'bmi', 'planlanan_kalori', 'notlar']]
            st.dataframe(gosterim_df, use_container_width=True)
            
            # SON DURUM KARTLARI
            son_olcum = df_olcumler.iloc[-1]
            ilk_olcum = df_olcumler.iloc[0]
            fark = son_olcum['kilo'] - ilk_olcum['kilo']
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Başlangıç", f"{ilk_olcum['kilo']} kg", f"{ilk_olcum['tarih']}")
            c2.metric("Son Durum", f"{son_olcum['kilo']} kg", f"{son_olcum['tarih']}")
            c3.metric("Toplam Değişim", f"{fark:.1f} kg", delta_color="inverse")
            
            # VERİ SİLME / DÜZENLEME
            st.markdown("### 🛠️ Yönetim")
            col_del1, col_del2 = st.columns(2)
            silinecek_id = col_del1.number_input("Silinecek Ölçüm ID", min_value=0, step=1)
            if col_del2.button("Seçili Ölçümü Sil"):
                c = conn.cursor()
                c.execute("DELETE FROM olcumler WHERE id=?", (silinecek_id,))
                conn.commit()
                st.warning("Ölçüm silindi. Sayfayı yenileyin.")
                st.rerun()
                
        else:
            st.info("Bu hastaya ait henüz ölçüm girilmemiş.")
            
    conn.close()
