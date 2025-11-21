import streamlit as st
import pandas as pd
import sqlite3
import datetime

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Klinik Yönetimi", layout="wide", page_icon="🩺")

# --- 1. VERİTABANI YÖNETİMİ ---
# Veritabanı adını değiştirdim (v2) ki eski tabloyla çakışmasın.
DB_NAME = 'klinik_v2.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tablo yoksa oluştur
    c.execute('''CREATE TABLE IF NOT EXISTS danisanlar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  tarih TEXT, 
                  ad_soyad TEXT, 
                  cinsiyet TEXT, 
                  yas INTEGER, 
                  boy REAL, 
                  kilo REAL, 
                  hedef_kilo REAL,
                  bmh REAL, 
                  tdee REAL, 
                  planlanan_kalori INTEGER, 
                  notlar TEXT)''')
    conn.commit()
    conn.close()

def danisan_kaydet_db(data):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''INSERT INTO danisanlar (tarih, ad_soyad, cinsiyet, yas, boy, kilo, hedef_kilo, bmh, tdee, planlanan_kalori, notlar)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                  (datetime.date.today(), data['ad'], data['cinsiyet'], data['yas'], data['boy'], 
                   data['kilo'], data['hedef_kilo'], data['bmh'], data['tdee'], data['planlanan_kalori'], data['not']))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

# Başlangıçta veritabanını kontrol et
init_db()

# --- 2. HESAPLAMA MOTORU ---
def hesapla_bmh_tdee(cinsiyet, kilo, boy, yas, akt_katsayi):
    # Mifflin-St Jeor
    base = (10 * kilo) + (6.25 * boy) - (5 * yas)
    bmh = base + 5 if cinsiyet == "Erkek" else base - 161
    tdee = bmh * akt_katsayi
    
    # İdeal Kilo (Robinson Formülü - Referans için)
    boy_m = boy / 100
    if cinsiyet == "Erkek":
        ideal = 52 + 1.9 * ((boy / 2.54) - 60)
    else:
        ideal = 49 + 1.7 * ((boy / 2.54) - 60)
        
    return bmh, tdee, ideal

# --- 3. ARAYÜZ VE MANTIK ---

# Session State Başlatma (Hafıza)
# Sayfa yenilense bile bu veriler kaybolmasın diye buraya yazıyoruz.
if 'analiz_yapildi' not in st.session_state:
    st.session_state['analiz_yapildi'] = False
if 'sonuc' not in st.session_state:
    st.session_state['sonuc'] = {}

# Yan Menü
menu = st.sidebar.radio("Menü", ["1. Danışan Analizi", "2. Danışan Kayıtları"])

if menu == "1. Danışan Analizi":
    st.title("🩺 Yeni Danışan Analizi")
    
    # --- GİRİŞ FORMU ---
    with st.container():
        c1, c2, c3 = st.columns(3)
        ad = c1.text_input("Ad Soyad")
        cinsiyet = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        yas = c3.number_input("Yaş", 10, 90, 30)
        
        c4, c5, c6 = st.columns(3)
        boy = c4.number_input("Boy (cm)", 140, 220, 170)
        kilo = c5.number_input("Mevcut Kilo (kg)", 40.0, 200.0, 80.0, step=0.1)
        
        st.write("---")
        
        # Aktivite
        akt_dict = {
            "Sedanter (1.2)": 1.2, 
            "Hafif Aktif (1.375)": 1.375, 
            "Orta Aktif (1.55)": 1.55, 
            "Çok Aktif (1.725)": 1.725
        }
        akt_secim = st.selectbox("Aktivite Seviyesi", list(akt_dict.keys()))
        
        # ANALİZ ET BUTONU
        if st.button("Analiz Et ve Hesapla", type="primary"):
            # Hesaplamaları yapıp hafızaya atıyoruz
            bmh, tdee, ideal_ref = hesapla_bmh_tdee(cinsiyet, kilo, boy, yas, akt_dict[akt_secim])
            
            st.session_state['sonuc'] = {
                'ad': ad, 'cinsiyet': cinsiyet, 'yas': yas, 'boy': boy, 'kilo': kilo,
                'bmh': bmh, 'tdee': tdee, 'ideal_ref': ideal_ref,
                'akt_secim': akt_secim
            }
            st.session_state['analiz_yapildi'] = True

    # --- SONUÇ EKRANI (SADECE ANALİZ YAPILDIYSA GÖZÜKÜR) ---
    if st.session_state['analiz_yapildi']:
        data = st.session_state['sonuc']
        st.divider()
        
        st.subheader(f"Analiz Sonuçları: {data['ad']}")
        
        # Bilgi Kartları
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Mevcut Kilo", f"{data['kilo']} kg")
        m2.metric("BMH", f"{int(data['bmh'])} kcal")
        m3.metric("TDEE (Günlük)", f"{int(data['tdee'])} kcal")
        m4.metric("Teorik İdeal", f"{int(data['ideal_ref'])} kg", help="Formüle göre olması gereken teorik kilo")
        
        st.info("💡 **Not:** Teorik ideal kilo her zaman gerçekçi hedef olmayabilir. Aşağıdan danışanla anlaştığınız hedefi giriniz.")
        
        # --- HEDEF VE AYARLAMA ---
        col_hedef1, col_hedef2 = st.columns([1, 2])
        
        with col_hedef1:
            st.markdown("#### 🎯 Hedef Ayarları")
            # Kullanıcı burada kendi hedefini belirler
            gercek_hedef_kilo = st.number_input("Hedeflenen Kilo (kg)", value=data['kilo'])
            
            diyet_tipi = st.radio("Plan", ["Kilo Ver", "Koru", "Kilo Al"], horizontal=True)
            
        with col_hedef2:
            st.markdown("#### 🔥 Kalori Ayarı")
            
            final_kalori = int(data['tdee']) # Varsayılan koruma
            
            if diyet_tipi == "Kilo Ver":
                # Slider artık bağımsız çalışıyor, sayfayı yenilese de veriler gitmiyor
                acik = st.slider("Günlük Kalori Açığı (Defisit)", 100, 1000, 500, step=50)
                final_kalori = int(data['tdee'] - acik)
                st.warning(f"Tahmini Kayıp: Haftada ortalama **{acik/1100:.2f} kg**")
                
            elif diyet_tipi == "Kilo Al":
                fazla = st.slider("Günlük Kalori Fazlası", 100, 1000, 300, step=50)
                final_kalori = int(data['tdee'] + fazla)
                st.success(f"Tahmini Kazanç: Haftada ortalama **{fazla/1100:.2f} kg**")
            
            st.markdown(f"### 📝 Yazılacak Diyet: **{final_kalori} kcal**")

        # --- KAYIT BÖLÜMÜ ---
        st.divider()
        col_save1, col_save2 = st.columns([3, 1])
        
        notlar = col_save1.text_area("Danışan Hakkında Notlar", placeholder="Örn: İnsülin direnci var, yumurta sevmiyor...")
        
        if col_save2.button("💾 DANIŞANI KAYDET"):
            # Kayıt için tüm verileri paketle
            kayit_verisi = {
                'ad': data['ad'], 'cinsiyet': data['cinsiyet'], 'yas': data['yas'], 
                'boy': data['boy'], 'kilo': data['kilo'], 
                'hedef_kilo': gercek_hedef_kilo, # Manuel girilen hedef
                'bmh': data['bmh'], 'tdee': data['tdee'], 
                'planlanan_kalori': final_kalori, 'not': notlar
            }
            
            if danisan_kaydet_db(kayit_verisi):
                st.success("✅ Kayıt Başarılı! 'Danışan Kayıtları' sekmesinden görebilirsiniz.")
            else:
                st.error("Kayıt sırasında bir sorun oluştu.")

elif menu == "2. Danışan Kayıtları":
    st.title("📂 Kayıtlı Danışanlar Veritabanı")
    
    # Verileri Çek
    conn = sqlite3.connect(DB_NAME)
    try:
        df = pd.read_sql_query("SELECT * FROM danisanlar ORDER BY id DESC", conn)
        
        if not df.empty:
            # Tabloyu düzenle (İngilizce sütunları Türkçeleştirme vs gerekirse)
            df.columns = ["ID", "Tarih", "Ad Soyad", "Cinsiyet", "Yaş", "Boy", "Başlangıç Kg", "Hedef Kg", "BMH", "TDEE", "Diyet Kalorisi", "Notlar"]
            
            st.dataframe(df, use_container_width=True)
            
            st.download_button(
                label="📥 Excel (CSV) Olarak İndir",
                data=df.to_csv(index=False).encode('utf-8'),
                file_name='danisan_listesi.csv',
                mime='text/csv',
            )
            
            st.info("Silme işlemi için veritabanı yöneticisi kullanmanız önerilir.")
        else:
            st.warning("Henüz kayıtlı danışan yok. Analiz sayfasından kayıt ekleyin.")
            
    except Exception as e:
        st.error("Veritabanı okunamadı.")
    finally:
        conn.close()
