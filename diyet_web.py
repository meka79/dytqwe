import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Klinik Yönetimi Pro", layout="wide", page_icon="🥑")

# --- VERİTABANI (İLİŞKİSEL YAPIYA GEÇİŞ) ---
DB_NAME = 'klinik_v9.db'  # Versiyonu değiştirdim ki temiz başlasın

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Tablo: DANISANLAR (Sabit Bilgiler - İsim değişti)
    c.execute('''CREATE TABLE IF NOT EXISTS danisanlar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  ad_soyad TEXT UNIQUE, 
                  cinsiyet TEXT, 
                  dogum_yili INTEGER, 
                  boy REAL, 
                  kayit_tarihi TEXT)''')
    
    # 2. Tablo: OLCUMLER (Değişken Bilgiler)
    c.execute('''CREATE TABLE IF NOT EXISTS olcumler
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  danisan_id INTEGER,
                  tarih TEXT, 
                  kilo REAL, 
                  hedef_kilo REAL,
                  bmi REAL,
                  bmh REAL,
                  tdee REAL,
                  planlanan_kalori INTEGER,
                  notlar TEXT,
                  FOREIGN KEY(danisan_id) REFERENCES danisanlar(id))''')
    
    conn.commit()
    conn.close()

init_db()

# --- YARDIMCI FONKSİYONLAR ---
def danisan_getir_isimle(ad_soyad):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM danisanlar WHERE ad_soyad=?", (ad_soyad,))
    danisan = c.fetchone()
    conn.close()
    return danisan # (id, ad, cinsiyet, d_yili, boy, tarih)

def yeni_danisan_ekle(ad, cinsiyet, d_yili, boy):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO danisanlar (ad_soyad, cinsiyet, dogum_yili, boy, kayit_tarihi) VALUES (?, ?, ?, ?, ?)",
                  (ad, cinsiyet, d_yili, boy, datetime.date.today()))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False # İsim zaten varsa

def olcum_ekle(danisan_id, kilo, hedef, bmi, bmh, tdee, plan, notlar):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO olcumler (danisan_id, tarih, kilo, hedef_kilo, bmi, bmh, tdee, planlanan_kalori, notlar) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (danisan_id, datetime.date.today(), kilo, hedef, bmi, bmh, tdee, plan, notlar))
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

# --- ARAYÜZ ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3050/3050525.png", width=100)
st.sidebar.title("Diyetisyen Asistanı")
menu = st.sidebar.radio("Menü", ["1. Yeni Analiz / Ölçüm", "2. Danışan Takip & Grafik"])

# ---------------------------------------------------------
# TAB 1: ANALİZ VE VERİ GİRİŞİ
# ---------------------------------------------------------
if menu == "1. Yeni Analiz / Ölçüm":
    st.header("🔬 Analiz ve Veri Girişi")
    
    # Otomatik tamamlama için isimleri çek
    conn = sqlite3.connect(DB_NAME)
    df_danisanlar = pd.read_sql("SELECT ad_soyad FROM danisanlar", conn)
    conn.close()
    mevcut_isimler = df_danisanlar['ad_soyad'].tolist() if not df_danisanlar.empty else []
    
    # --- İSTEK: YENİ DANIŞAN SOLDA, MEVCUT SAĞDA ---
    secim_modu = st.radio("Danışan Durumu:", ["Yeni Danışan", "Mevcut Danışan"], horizontal=True)
    
    # Değişkenleri başlangıç değerleriyle tanımla
    ad_soyad = ""
    boy = 170.0
    yas = 30
    cinsiyet = "Kadın"
    
    # --- MODA GÖRE ARAYÜZ ---
    if secim_modu == "Yeni Danışan":
        st.markdown("##### 👤 Yeni Danışan Bilgileri")
        c1, c2 = st.columns(2)
        ad_soyad = c1.text_input("Ad Soyad Giriniz")
        cinsiyet = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        yas = c1.number_input("Yaş", min_value=10, max_value=90, value=30, step=1)
        
        # --- HATA ÇÖZÜMÜ BURADA ---
        # 140 -> 140.0 ve 220 -> 220.0 yaparak float uyumsuzluğunu giderdik.
        boy = c2.number_input("Boy (cm)", min_value=140.0, max_value=220.0, value=170.0, step=1.0)
        
    else: # Mevcut Danışan
        st.markdown("##### 📂 Kayıtlı Danışan Seçimi")
        ad_soyad = st.selectbox("Danışan Arayınız:", mevcut_isimler)
        if ad_soyad:
            h = danisan_getir_isimle(ad_soyad) # (id, ad, cins, dyili, boy...)
            if h:
                cinsiyet = h[2]
                yas = datetime.date.today().year - h[3]
                boy = h[4]
                st.success(f"✅ Seçilen: **{ad_soyad}** | {yas} Yaş | {boy} cm | {cinsiyet}")
            else:
                st.error("Veritabanı hatası: Danışan bulunamadı.")

    st.markdown("---")
    
    # ÖLÇÜM VERİLERİ
    st.markdown("##### ⚖️ Ölçüm Verileri")
    col_k1, col_k2 = st.columns(2)
    kilo = col_k1.number_input("Güncel Kilo (kg)", 40.0, 250.0, 80.0, step=0.1)
    hedef_kilo = col_k2.number_input("Hedef Kilo (kg)", 40.0, 250.0, 70.0, step=0.1)
    
    akt_dict = {"Sedanter (1.2)": 1.2, "Hafif (1.375)": 1.375, "Orta (1.55)": 1.55, "Yüksek (1.725)": 1.725}
    akt_secim = st.selectbox("Aktivite Seviyesi", list(akt_dict.keys()))
    
    # HESAPLAMA BUTONU VE SONUÇLAR
    if st.button("Hesapla ve Önizle", type="primary", use_container_width=True):
        if not ad_soyad:
            st.warning("Lütfen bir isim giriniz.")
        else:
            sonuc = analiz_motoru(cinsiyet, kilo, boy, yas, akt_dict[akt_secim])
            
            # Sonuç Kartları
            st.markdown("#### 📊 Analiz Sonuçları")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("BMI", f"{sonuc['bmi']:.1f}")
            c2.metric("BMH (Bazal)", f"{int(sonuc['bmh'])}")
            c3.metric("TDEE (Günlük)", f"{int(sonuc['tdee'])}")
            
            kilo_farki = hedef_kilo - kilo
            # Basit Kalori Planı
            if kilo_farki < 0: plan = int(sonuc['tdee'] - 500) # Kilo ver
            elif kilo_farki > 0: plan = int(sonuc['tdee'] + 400) # Kilo al
            else: plan = int(sonuc['tdee']) # Koru
            
            c4.metric("Önerilen Kalori", f"{plan} kcal", help="Bazal + Aktivite +/- Hedef")
            
            # KAYIT ALANI
            st.write("---")
            notlar = st.text_area("Diyetisyen Notları:", "Rutin kontrol yapıldı, diyet listesi güncellendi.")
            
            # Verileri oturum durumunda (session state) saklayabiliriz ama 
            # basitlik için iç içe button kullanıyoruz (Streamlit'te bazen trick gerektirir, 
            # ama burada form submit mantığı daha temiz olurdu. Şimdilik basit bırakıyorum)
            
            if st.button("💾 KAYDET VE BİTİR"):
                # 1. Eğer yeni danışansa önce onu kaydet
                danisan_id = -1
                if secim_modu == "Yeni Danışan":
                    if yeni_danisan_ekle(ad_soyad, cinsiyet, datetime.date.today().year - yas, boy):
                        st.toast("Yeni danışan profili oluşturuldu!", icon="👤")
                        yenilenen_h = danisan_getir_isimle(ad_soyad)
                        danisan_id = yenilenen_h[0]
                    else:
                        st.error("Bu isimde danışan zaten var! 'Mevcut Danışan' moduna geçin.")
                        st.stop()
                else:
                    mevcut_h = danisan_getir_isimle(ad_soyad)
                    if mevcut_h:
                        danisan_id = mevcut_h[0]
                
                # 2. Ölçümü kaydet
                if danisan_id != -1:
                    olcum_ekle(danisan_id, kilo, hedef_kilo, sonuc['bmi'], sonuc['bmh'], sonuc['tdee'], plan, notlar)
                    st.success(f"✅ {ad_soyad} için ölçüm başarıyla kaydedildi!")
                    # Sayfayı yenilemeye gerek yok, veri girdi.
                else:
                    st.error("Bir hata oluştu, ID bulunamadı.")

# ---------------------------------------------------------
# TAB 2: DANIŞAN TAKİP (CRM)
# ---------------------------------------------------------
elif menu == "2. Danışan Takip & Grafik":
    st.header("📈 Danışan İlerleme Takibi")
    
    conn = sqlite3.connect(DB_NAME)
    df_danisanlar = pd.read_sql("SELECT * FROM danisanlar", conn)
    
    if df_danisanlar.empty:
        st.warning("Henüz kayıtlı danışan yok.")
    else:
        # 1. Danışan Seçimi
        secilen_danisan = st.selectbox("Danışan Seçin:", df_danisanlar['ad_soyad'])
        danisan_bilgi = df_danisanlar[df_danisanlar['ad_soyad'] == secilen_danisan].iloc[0]
        danisan_id = danisan_bilgi['id']
        
        # 2. Ölçüm Geçmişini Çek
        df_olcumler = pd.read_sql(f"SELECT * FROM olcumler WHERE danisan_id={danisan_id} ORDER BY tarih", conn)
        
        if not df_olcumler.empty:
            # İLERLEME GRAFİĞİ
            st.subheader(f"{secilen_danisan} - Kilo Değişimi")
            
            chart_data = df_olcumler[['tarih', 'kilo']].set_index('tarih')
            st.line_chart(chart_data, color="#29b5e8") # Renkli grafik
            
            # ÖZET KARTLAR
            son_olcum = df_olcumler.iloc[-1]
            ilk_olcum = df_olcumler.iloc[0]
            fark = son_olcum['kilo'] - ilk_olcum['kilo']
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Başlangıç", f"{ilk_olcum['kilo']} kg")
            c2.metric("Son Durum", f"{son_olcum['kilo']} kg")
            c3.metric("Toplam Fark", f"{fark:.1f} kg", delta=f"{fark:.1f} kg", delta_color="inverse")
            
            # TABLO
            st.subheader("Geçmiş Ölçüm Detayları")
            gosterim_df = df_olcumler[['id', 'tarih', 'kilo', 'hedef_kilo', 'bmi', 'planlanan_kalori', 'notlar']]
            st.dataframe(gosterim_df, use_container_width=True, hide_index=True)
            
            # VERİ SİLME
            with st.expander("🗑️ Hatalı Kayıt Silme"):
                col_del1, col_del2 = st.columns([3, 1])
                silinecek_id = col_del1.number_input("Silinecek Ölçüm ID (Tablodan bakınız)", min_value=0, step=1)
                if col_del2.button("Sil", type="primary"):
                    c = conn.cursor()
                    c.execute("DELETE FROM olcumler WHERE id=?", (silinecek_id,))
                    conn.commit()
                    st.warning("Ölçüm silindi. Güncel tabloyu görmek için sayfayı yenileyin.")
                    st.rerun()
                
        else:
            st.info("Bu danışana ait henüz ölçüm girilmemiş.")
            
    conn.close()
