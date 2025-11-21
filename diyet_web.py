import streamlit as st
import pandas as pd
import sqlite3
import datetime
from fpdf import FPDF

# --- AYARLAR VE VERİTABANI KURULUMU ---
st.set_page_config(page_title="Diyetisyen Klinik Yönetimi", layout="wide", page_icon="🩺")

# Veritabanı Bağlantısı ve Tablo Oluşturma
def init_db():
    conn = sqlite3.connect('klinik_veritabani.db')
    c = conn.cursor()
    # Danışanlar Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS danisanlar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  tarih TEXT, 
                  ad_soyad TEXT, 
                  cinsiyet TEXT, 
                  yas INTEGER, 
                  boy REAL, 
                  kilo REAL, 
                  bmh REAL, 
                  tdee REAL, 
                  hedef_kalori INTEGER, 
                  ideal_kilo REAL,
                  notlar TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- PROFESYONEL HESAPLAMA MOTORU ---
class MetabolikMotor:
    def __init__(self, cinsiyet, kilo, boy, yas, aktivite_katsayisi):
        self.cinsiyet = cinsiyet
        self.kilo = kilo
        self.boy = boy
        self.yas = yas
        self.akt = aktivite_katsayisi

    def bmh_hesapla(self):
        # Mifflin-St Jeor Denklemi (Altın Standart)
        base = (10 * self.kilo) + (6.25 * self.boy) - (5 * self.yas)
        if self.cinsiyet == "Erkek":
            return base + 5
        return base - 161

    def ideal_kilo_hesapla(self):
        # Robinson Formülü (Alternatif: BMI 22 hedefi)
        # Boya göre sağlıklı aralığın ortası (BMI 22) en güvenli yöntemdir.
        boy_m = self.boy / 100
        return round(22 * (boy_m ** 2), 1)

    def su_ihtiyaci(self):
        # Kg başına 33ml (Ortalama klinik yaklaşım)
        return round(self.kilo * 0.033, 2)

    def bmi_analiz(self):
        boy_m = self.boy / 100
        bmi = self.kilo / (boy_m ** 2)
        if bmi < 18.5: return bmi, "Zayıf", "warning"
        elif 18.5 <= bmi < 24.9: return bmi, "Normal", "success"
        elif 25 <= bmi < 29.9: return bmi, "Fazla Kilolu", "warning"
        elif 30 <= bmi < 34.9: return bmi, "Obez (Sınıf 1)", "error"
        elif 35 <= bmi < 39.9: return bmi, "Obez (Sınıf 2)", "error"
        else: return bmi, "Morbid Obez", "error"

# --- YARDIMCI FONKSİYONLAR ---
def danisan_kaydet(data):
    conn = sqlite3.connect('klinik_veritabani.db')
    c = conn.cursor()
    c.execute('''INSERT INTO danisanlar (tarih, ad_soyad, cinsiyet, yas, boy, kilo, bmh, tdee, hedef_kalori, ideal_kilo, notlar)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
              (datetime.date.today(), data['ad'], data['cinsiyet'], data['yas'], data['boy'], 
               data['kilo'], data['bmh'], data['tdee'], data['hedef'], data['ideal'], data['not']))
    conn.commit()
    conn.close()
    st.success(f"✅ {data['ad']} başarıyla veritabanına kaydedildi!")

# --- SAYFA YAPISI (SIDEBAR) ---
menu = st.sidebar.radio("Menü", ["1. Yeni Analiz & Diyet", "2. Kayıtlı Danışanlar", "3. Klinik Bilgileri"])

st.sidebar.info("💡 Mifflin-St Jeor Formülü kullanılmaktadır.")

# --- SAYFA 1: YENİ ANALİZ VE DİYET YAZMA ---
if menu == "1. Yeni Analiz & Diyet":
    st.title("🩺 Profesyonel Metabolik Analiz")
    
    # Giriş Formu
    with st.form("analiz_formu"):
        c1, c2, c3 = st.columns(3)
        ad_soyad = c1.text_input("Danışan Adı Soyadı")
        cinsiyet = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        yas = c3.number_input("Yaş", 10, 90, 30)
        
        c4, c5, c6 = st.columns(3)
        boy = c4.number_input("Boy (cm)", 140, 220, 170)
        kilo = c5.number_input("Kilo (kg)", 40.0, 200.0, 70.0, step=0.1)
        bel_cevresi = c6.number_input("Bel Çevresi (cm) [Opsiyonel]", 0, 150, 0)
        
        st.markdown("### 🏃 Aktivite & Yaşam Tarzı")
        aktivite_secenekleri = {
            "Sedanter (Masa başı, spor yok)": 1.2,
            "Hafif Aktif (Haftada 1-3 gün hafif egzersiz)": 1.375,
            "Orta Aktif (Haftada 3-5 gün orta egzersiz)": 1.55,
            "Çok Aktif (Haftada 6-7 gün ağır egzersiz)": 1.725,
            "Ekstra Aktif (Fiziksel iş + Çift antrenman)": 1.9
        }
        secilen_akt = st.selectbox("Fiziksel Aktivite Düzeyi (PAL)", list(aktivite_secenekleri.keys()))
        katsayi = aktivite_secenekleri[secilen_akt]
        
        ozel_not = st.text_area("Klinik Notlar (Hastalık, Alerji vb.)")
        
        hesapla_btn = st.form_submit_button("Analizi Başlat")

    # Sonuç Ekranı
    if hesapla_btn and ad_soyad:
        motor = MetabolikMotor(cinsiyet, kilo, boy, yas, katsayi)
        bmh = motor.bmh_hesapla()
        tdee = bmh * katsayi
        bmi, bmi_durum, renk = motor.bmi_analiz()
        ideal_kilo = motor.ideal_kilo_hesapla()
        su = motor.su_ihtiyaci()

        # Verileri Session State'e atalım (Kaydetme butonu için)
        st.session_state['sonuc_data'] = {
            'ad': ad_soyad, 'cinsiyet': cinsiyet, 'yas': yas, 'boy': boy, 
            'kilo': kilo, 'bmh': bmh, 'tdee': tdee, 'ideal': ideal_kilo, 'not': ozel_not
        }

        st.divider()
        st.subheader(f"📊 Rapor: {ad_soyad}")
        
        # Metrikler
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("VKİ (BMI)", f"{bmi:.1f}", bmi_durum)
        col2.metric("İdeal Kilo", f"{ideal_kilo} kg", f"{kilo - ideal_kilo:.1f} kg fark")
        col3.metric("BMH", f"{int(bmh)} kcal")
        col4.metric("Günlük Enerji", f"{int(tdee)} kcal")
        
        # Detaylı Bilgi Kutusu
        st.info(f"💧 **Günlük Su Hedefi:** {su} Litre | 🩺 **Bel Risk Analizi:** {'Girilmedi' if bel_cevresi==0 else ('Riskli' if bel_cevresi > (102 if cinsiyet=='Erkek' else 88) else 'Normal')}")

        # Hedef Belirleme Kısmı
        st.markdown("### 🎯 Diyet Planlaması")
        hedef_tipi = st.selectbox("Hedef Seçimi", ["Kilo Vermek", "Korumak", "Kilo Almak"])
        
        hedef_kalori = int(tdee)
        if hedef_tipi == "Kilo Vermek":
            kalori_acigi = st.slider("Kalori Açığı (Defisit)", 200, 1000, 500, step=50)
            hedef_kalori = int(tdee - kalori_acigi)
            st.warning(f"Planlanan: Günlük -{kalori_acigi} kcal açık ile haftada yaklaşık {kalori_acigi/1100:.1f} kg kayıp.")
        elif hedef_tipi == "Kilo Almak":
            kalori_fazlasi = st.slider("Kalori Fazlası (Surplus)", 200, 1000, 300, step=50)
            hedef_kalori = int(tdee + kalori_fazlasi)
        
        st.session_state['sonuc_data']['hedef'] = hedef_kalori
        
        st.success(f"🥗 **Yazılacak Diyet Kalorisi: {hedef_kalori} kcal**")
        
        # Kaydet Butonu
        if st.button("💾 Bu Danışanı Veritabanına Kaydet"):
            danisan_kaydet(st.session_state['sonuc_data'])

# --- SAYFA 2: KAYITLI DANIŞANLAR (CRM) ---
elif menu == "2. Kayıtlı Danışanlar":
    st.title("📂 Hasta / Danışan Kayıtları")
    
    conn = sqlite3.connect('klinik_veritabani.db')
    df = pd.read_sql_query("SELECT * FROM danisanlar ORDER BY tarih DESC", conn)
    conn.close()
    
    if not df.empty:
        # Arama Kutusu
        arama = st.text_input("İsimle Ara:")
        if arama:
            df = df[df['ad_soyad'].str.contains(arama, case=False)]
        
        st.dataframe(df)
        
        st.markdown("### 📥 Veri İşlemleri")
        col1, col2 = st.columns(2)
        
        # Excel İndirme
        csv = df.to_csv(index=False).encode('utf-8')
        col1.download_button("Listeyi Excel (CSV) Olarak İndir", csv, "danisan_listesi.csv", "text/csv")
        
        # Silme İşlemi
        silinecek_id = col2.number_input("Silinecek ID Numarası", min_value=0, step=1)
        if col2.button("Kaydı Sil"):
            conn = sqlite3.connect('klinik_veritabani.db')
            c = conn.cursor()
            c.execute("DELETE FROM danisanlar WHERE id=?", (silinecek_id,))
            conn.commit()
            conn.close()
            st.warning(f"ID {silinecek_id} silindi. Sayfayı yenileyin.")
            st.rerun()
    else:
        st.info("Henüz kayıtlı danışan bulunmamaktadır.")

# --- SAYFA 3: KLİNİK BİLGİLERİ ---
elif menu == "3. Klinik Bilgileri":
    st.title("ℹ️ Bilimsel Referanslar")
    st.markdown("""
    Bu program aşağıdaki bilimsel kılavuzları baz alır:
    
    1.  **BMH Hesaplaması:** Mifflin-St Jeor Denklemi (2005 yılında ADA tarafından en doğru formül kabul edilmiştir).
    2.  **Aktivite Çarpanları (PAL):** WHO (Dünya Sağlık Örgütü) fiziksel aktivite seviyeleri.
    3.  **İdeal Kilo:** Hamwi Yöntemi ve BMI 22 (Sağlıklı Aralık Ortası) baz alınmıştır.
    4.  **Sıvı İhtiyacı:** 30-35 ml/kg genel klinik yaklaşımı.
    
    **Geliştirici Notu:** Bu yazılım klinik karar destek sistemidir. Kesin tanı ve tedavi için hekim onayı ve diyetisyen yorumu esastır.
    """)
