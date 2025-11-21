import streamlit as st
import pandas as pd
import sqlite3
import datetime
import altair as alt
import json # Yeni modül için gerekli

# --- AYARLAR ---
st.set_page_config(page_title="Klinik Yönetim v13 (Test Modülü Eklendi)", layout="wide", page_icon="🥗")

# --- VERİTABANI --
DB_NAME = 'klinik_v13.db' # Yeni versiyon için yeni DB adı

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Tablo: DANIŞANLAR (v12'den alınmıştır)
    c.execute('''CREATE TABLE IF NOT EXISTS danisanlar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  ad_soyad TEXT UNIQUE, 
                  cinsiyet TEXT, 
                  dogum_yili INTEGER, 
                  boy REAL, 
                  telefon TEXT,
                  kayit_tarihi TEXT)''')
    
    # 2. Tablo: ÖLÇÜMLER (v12'den alınmıştır)
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
                  
    # 3. Tablo: ANAMNEZ TESTLERİ (YENİ EKLENEN)
    c.execute('''CREATE TABLE IF NOT EXISTS anamnez_testleri
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  danisan_id INTEGER,
                  tarih TEXT, 
                  skor INTEGER,
                  cevaplar TEXT, 
                  FOREIGN KEY(danisan_id) REFERENCES danisanlar(id))''')
                  
    conn.commit()
    conn.close()

# DB'yi başlat
init_db()

# --- VERİTABANI FONKSİYONLARI (v12'den alınmıştır) ---

def danisan_getir_detay(ad_soyad):
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT * FROM danisanlar WHERE ad_soyad=?"
    result = conn.execute(query, (ad_soyad,)).fetchone()
    conn.close()
    return result

def son_olcum_getir(danisan_id):
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT * FROM olcumler WHERE danisan_id=? ORDER BY tarih DESC LIMIT 1"
    cursor = conn.execute(query, (danisan_id,))
    cols = [column[0] for column in cursor.description]
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return dict(zip(cols, result))
    return None

def olcum_kaydet_db(data):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''INSERT INTO olcumler (danisan_id, tarih, kilo, hedef_kilo, bel_cevresi, kalca_cevresi, bmi, bmh, tdee, su_ihtiyaci, planlanan_kalori, notlar) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                  (data['danisan_id'], data['tarih'], data['kilo'], data['hedef_kilo'], data['bel_cevresi'], 
                   data['kalca_cevresi'], data['bmi'], data['bmh'], data['tdee'], data['su_ihtiyaci'], 
                   data['planlanan_kalori'], data['notlar']))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Ölçüm kaydı hatası: {e}")
        return False

# --- HESAPLAMA MOTORU (v12'den alınmıştır) ---
AKTIVITE_KAT = {
    "Sedanter (Az/Hiç egzersiz)": 1.2,
    "Hafif Aktif (Haftada 1-3 gün)": 1.375,
    "Orta Aktif (Haftada 3-5 gün)": 1.55,
    "Çok Aktif (Haftada 6-7 gün)": 1.725,
    "Ekstra Aktif (Günde 2 kez/Fiziksel iş)": 1.9
}

def detayli_analiz(cinsiyet, kilo, boy, yas, akt_katsayi_deger):
    boy_m = boy / 100
    bmi = kilo / (boy_m ** 2)
    
    # Mifflin-St Jeor BMH
    base = (10 * kilo) + (6.25 * boy) - (5 * yas)
    bmh = base + 5 if cinsiyet == "Erkek" else base - 161
    
    tdee = bmh * akt_katsayi_deger
    
    # İdeal Kilo Aralığı (BMI 18.5 - 24.9)
    ideal_min_kilo = 18.5 * (boy_m ** 2)
    ideal_max_kilo = 24.9 * (boy_m ** 2)
    
    # Su İhtiyacı (Kilo * 30 ml)
    su_ihtiyaci = kilo * 30 / 1000 # Litre olarak
    
    return {
        'bmi': round(bmi, 1),
        'bmh': round(bmh),
        'tdee': round(tdee),
        'ideal_min': round(ideal_min_kilo, 1),
        'ideal_max': round(ideal_max_kilo, 1),
        'su_ihtiyaci': round(su_ihtiyaci, 1)
    }

# --- YENİ MODÜL: ANAMNEZ TEST SORULARI ve SKORLAMA ---
TEST_SORULARI = {
    "1": {"soru": "Günde kaç öğün yemek yiyorsunuz? (Ara öğünler dahil)", "tip": "slider", "min": 2, "max": 7},
    "2": {"soru": "Yemek yerken çoğunlukla ne hissedersiniz?", "tip": "radio", "seçenekler": ["Çok hızlı ve aceleci", "Normal hızda, tadını çıkararak", "Yavaş ve sakin"]},
    "3": {"soru": "Tatlı isteğiniz sıklıkla ortaya çıkar mı?", "tip": "radio", "seçenekler": ["Hemen hemen her gün", "Haftada birkaç kez", "Ayda birkaç kez veya daha az"]},
    "4": {"soru": "Haftada kaç kez dışarıdan (fast food, restoran vb.) yemek yiyorsunuz?", "tip": "slider", "min": 0, "max": 7},
    "5": {"soru": "Günde ortalama kaç saat uyuyorsunuz?", "tip": "slider", "min": 4, "max": 10},
    "6": {"soru": "Stresli olduğunuzda yeme alışkanlığınız değişir mi?", "tip": "radio", "seçenekler": ["Evet, daha çok yerim", "Hayır, değişmez", "Evet, daha az yerim"]},
    "7": {"soru": "Günde en az 2 litre su tüketiyor musunuz?", "tip": "radio", "seçenekler": ["Evet, düzenli tüketiyorum", "Bazen unutuyorum", "Hayır, çok az içiyorum"]}
}

def skor_hesapla(cevaplar):
    skor = 0
    # Soru 2: Hızlı yemek = 3 puan
    if cevaplar.get('2') == "Çok hızlı ve aceleci": skor += 3
    
    # Soru 3: Tatlı İsteği (Her gün=3, Haftada birkaç kez=1)
    if cevaplar.get('3') == "Hemen hemen her gün": skor += 3
    elif cevaplar.get('3') == "Haftada birkaç kez": skor += 1
    
    # Soru 4: Dışarıdan Yemek (Her yemek 2 puan)
    disari_adet = cevaplar.get('4', 0)
    skor += disari_adet * 2
    
    # Soru 5: Uyku (6 saatten az: 3 puan)
    uyku_saat = cevaplar.get('5', 0)
    if uyku_saat < 6: skor += 3
    
    # Soru 6: Stres (Daha çok yerim: 3 puan)
    if cevaplar.get('6') == "Evet, daha çok yerim": skor += 3
    
    # Soru 7: Su Tüketimi (Çok az: 3 puan, Unutuyorum: 1 puan)
    if cevaplar.get('7') == "Hayır, çok az içiyorum": skor += 3
    elif cevaplar.get('7') == "Bazen unutuyorum": skor += 1
    
    return skor


# --- ANA UYGULAMA YAPISI (v12'den alınmıştır) ---

st.sidebar.title("Diyetisyen Pro v13")
# Yeni modül menüye eklendi:
menu = st.sidebar.radio("Klinik Modülü", 
    ["1. Danışan Kabul & Analiz", "2. Danışan Dosyası (Takip)", "3. Diyet Programı Oluştur", "4. Online Anamnez Testi"]
)

# ==============================================================================
# 1. TAB: DANIŞAN KABUL & ANALİZ
# ==============================================================================
if menu == "1. Danışan Kabul & Analiz":
    st.title("👨‍👩‍👧 Danışan Kabul & Analiz")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Danışan Bilgileri")
        ad_soyad = st.text_input("Ad Soyad (Zorunlu)", key="yeni_ad")
        cinsiyet = st.selectbox("Cinsiyet", ["Erkek", "Kadın"])
        dogum_yili = st.number_input("Doğum Yılı", min_value=1900, max_value=datetime.date.today().year, value=2000)
        boy = st.number_input("Boy (cm)", min_value=100.0, max_value=250.0, value=170.0, step=1.0)
        telefon = st.text_input("Telefon Numarası")
        
        st.subheader("Mevcut Ölçüm & Hedef")
        kilo = st.number_input("Mevcut Kilo (kg)", min_value=30.0, value=70.0, step=0.1)
        hedef_kilo = st.number_input("Hedef Kilo (kg)", min_value=30.0, value=65.0, step=0.1)
        
    with col2:
        st.subheader("Yaşam Tarzı ve Ölçümler")
        aktivite_duzeyi = st.selectbox("Aktivite Düzeyi (TDEE İçin)", list(AKTIVITE_KAT.keys()))
        bel_cevresi = st.number_input("Bel Çevresi (cm)", min_value=50.0, value=90.0, step=1.0)
        kalca_cevresi = st.number_input("Kalça Çevresi (cm)", min_value=50.0, value=100.0, step=1.0)
        notlar = st.text_area("Ek Notlar", max_chars=200)
        
        yas = datetime.date.today().year - dogum_yili
        akt_deger = AKTIVITE_KAT[aktivite_duzeyi]
        analiz = detayli_analiz(cinsiyet, kilo, boy, yas, akt_deger)
        
        st.markdown("---")
        st.subheader("Hesaplama Sonuçları")
        
        c_r1, c_r2, c_r3 = st.columns(3)
        c_r1.metric("BMI", analiz['bmi'])
        c_r2.metric("BMH", f"{analiz['bmh']} kcal")
        c_r3.metric("TDEE (Günlük İhtiyaç)", f"{analiz['tdee']} kcal")
        
        st.info(f"İdeal Kilo Aralığı: {analiz['ideal_min']} kg - {analiz['ideal_max']} kg")
        
        # Hedef Kalori Belirleme
        fark = hedef_kilo - kilo
        kalori_farki = fark * 7700 / 90 # 1 kg ~ 7700 kcal, hedef 90 gün (3 ay) baz alınmıştır.
        hedef_kalori = round(analiz['tdee'] + kalori_farki)
        
        st.markdown(f"**Önerilen Günlük Diyet Kalorisi:** **{hedef_kalori} kcal**")
        st.caption("Not: Otomatik hesaplanan tahmini değerdir.")
        
        planlanan_kalori = st.number_input("Planlanan Kalori", value=hedef_kalori, step=50)

    st.markdown("---")
    if st.button("💾 Danışanı Kaydet ve İlk Ölçümü İşle", type="primary"):
        if not ad_soyad:
            st.error("Lütfen Danışan Adı Soyadı girin.")
            st.stop()
            
        try:
            # 1. Danışan Temel Bilgilerini Kaydet
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute('''INSERT INTO danisanlar (ad_soyad, cinsiyet, dogum_yili, boy, telefon, kayit_tarihi) 
                         VALUES (?, ?, ?, ?, ?, ?)''', 
                      (ad_soyad, cinsiyet, dogum_yili, boy, telefon, datetime.date.today()))
            danisan_id = c.lastrowid # Yeni eklenen danışanın ID'sini al
            conn.commit()
            conn.close()
            
            # 2. İlk Ölçümü Kaydet
            olcum_data = {
                'danisan_id': danisan_id,
                'tarih': str(datetime.date.today()),
                'kilo': kilo,
                'hedef_kilo': hedef_kilo,
                'bel_cevresi': bel_cevresi,
                'kalca_cevresi': kalca_cevresi,
                'bmi': analiz['bmi'],
                'bmh': analiz['bmh'],
                'tdee': analiz['tdee'],
                'su_ihtiyaci': analiz['su_ihtiyaci'],
                'planlanan_kalori': planlanan_kalori,
                'notlar': notlar
            }
            olcum_kaydet_db(olcum_data)
            
            st.success(f"✅ Danışan **{ad_soyad}** başarıyla kaydedildi!")
            st.balloons()
            
        except sqlite3.IntegrityError:
            st.error("Bu isimde bir danışan zaten kayıtlı.")
        except Exception as e:
            st.error(f"Kayıt sırasında bir hata oluştu: {e}")

# ==============================================================================
# 2. TAB: DANIŞAN DOSYASI (TAKİP)
# ==============================================================================
elif menu == "2. Danışan Dosyası (Takip)":
    st.title("📂 Danışan Dosyası ve Takip")
    
    conn = sqlite3.connect(DB_NAME)
    names = pd.read_sql("SELECT ad_soyad FROM danisanlar ORDER BY ad_soyad", conn)
    
    if names.empty:
        st.warning("Henüz kayıtlı danışan bulunmamaktadır.")
        conn.close()
        st.stop()
        
    secilen_danisan = st.selectbox("Danışan Seçin:", names['ad_soyad'].tolist(), key="takip_secim")
    d_bilgi = danisan_getir_detay(secilen_danisan) # (id, ad, cinsiyet, dyili, boy, tel, k_tarihi)
    danisan_id = d_bilgi[0]

    # Ölçüm Geçmişini Çek
    df_olcumler = pd.read_sql(f"SELECT * FROM olcumler WHERE danisan_id={danisan_id} ORDER BY tarih", conn)
    
    # Anamnez Testi Geçmişini Çek (YENİ EKLENEN)
    df_anamnez = pd.read_sql(f"SELECT tarih, skor FROM anamnez_testleri WHERE danisan_id={danisan_id} ORDER BY tarih", conn)
    conn.close()

    if df_olcumler.empty:
        st.warning("Danışanın kayıtlı ölçümü bulunmamaktadır.")
        st.stop()
        
    # --- YENİ ÖLÇÜM GİRİŞ FORMU ---
    with st.expander("➕ Yeni Ölçüm Girişi"):
        col_y1, col_y2 = st.columns(2)
        
        with col_y1:
            y_tarih = st.date_input("Ölçüm Tarihi", datetime.date.today())
            y_kilo = st.number_input("Yeni Kilo (kg)", min_value=30.0, value=df_olcumler.iloc[-1]['kilo'], step=0.1)
            y_hedef = st.number_input("Güncel Hedef Kilo (kg)", min_value=30.0, value=df_olcumler.iloc[-1]['hedef_kilo'], step=0.1)
            
        with col_y2:
            y_bel = st.number_input("Bel Çevresi (cm)", min_value=50.0, value=df_olcumler.iloc[-1]['bel_cevresi'], step=1.0)
            y_kalca = st.number_input("Kalça Çevresi (cm)", min_value=50.0, value=df_olcumler.iloc[-1]['kalca_cevresi'], step=1.0)
            
            y_yas = datetime.date.today().year - d_bilgi[3]
            y_boy = d_bilgi[4]
            # Aktivite faktörü tahmini: son TDEE / yeni BMH
            y_base = (10 * y_kilo) + (6.25 * y_boy) - (5 * y_yas)
            y_bmh = y_base + 5 if d_bilgi[2] == "Erkek" else y_base - 161
            tahmini_aktivite_faktor = df_olcumler.iloc[-1]['tdee'] / df_olcumler.iloc[-1]['bmh'] # Önceki katsayıyı koru
            
            y_analiz = detayli_analiz(d_bilgi[2], y_kilo, y_boy, y_yas, tahmini_aktivite_faktor)
            
            y_kalori = st.number_input("Planlanan Kalori", value=df_olcumler.iloc[-1]['planlanan_kalori'], step=50)
            y_notlar = st.text_area("Seans Notları", max_chars=200)

        if st.button("➕ Yeni Ölçümü Kaydet"):
            y_data = {
                'danisan_id': danisan_id,
                'tarih': str(y_tarih),
                'kilo': y_kilo,
                'hedef_kilo': y_hedef,
                'bel_cevresi': y_bel,
                'kalca_cevresi': y_kalca,
                'bmi': y_analiz['bmi'],
                'bmh': y_analiz['bmh'],
                'tdee': y_analiz['tdee'],
                'su_ihtiyaci': y_analiz['su_ihtiyaci'],
                'planlanan_kalori': y_kalori,
                'notlar': y_notlar
            }
            if olcum_kaydet_db(y_data):
                st.success("Yeni ölçüm kaydedildi! Sayfayı yenileyin.")


    # --- TAKİP BİLGİLERİ VE GRAFİKLER ---
    
    # Son Durum Bilgileri
    son_olcum = df_olcumler.iloc[-1]
    ilk_olcum = df_olcumler.iloc[0]
    fark = son_olcum['kilo'] - ilk_olcum['kilo']
    
    col_t1, col_t2, col_t3, col_t4 = st.columns(4)
    col_t1.metric("Kayıt Tarihi", d_bilgi[6])
    col_t2.metric("Mevcut Kilo", f"{son_olcum['kilo']} kg", f"Başlangıç: {ilk_olcum['kilo']} kg")
    col_t3.metric("Toplam Değişim", f"{abs(fark):.1f} kg", delta=-fark, delta_color="inverse")
    col_t4.metric("Hedef Kilo", f"{son_olcum['hedef_kilo']} kg")

    st.markdown("---")
    
    # Grafikler
    st.subheader("📈 Gelişim Grafikleri (Altair)")
    c_g1, c_g2, c_g3 = st.columns(3) # Yeni Grafik için 3 sütun
    
    # Kilo Grafiği
    with c_g1:
        st.markdown("**Kilo Takibi**")
        df_o = df_olcumler.copy()
        df_o['tarih'] = pd.to_datetime(df_o['tarih'])
        son_hedef = df_o['hedef_kilo'].iloc[-1]
        
        line = alt.Chart(df_o).mark_line(point=True).encode(
            x=alt.X('tarih', title='Tarih'),
            y=alt.Y('kilo', title='Kilo (kg)'),
            tooltip=['tarih', 'kilo', 'hedef_kilo']
        ).properties(height=300)
        
        rule = alt.Chart(pd.DataFrame({'y': [son_hedef]})).mark_rule(color='green', strokeDash=[5, 5]).encode(y='y')
        
        st.altair_chart(line + rule, use_container_width=True)

    # Bel Çevresi Grafiği
    with c_g2:
        st.markdown("**Bel Çevresi Takibi**")
        ideal_bel = 94.0 if d_bilgi[2] == "Erkek" else 80.0
        
        if df_o['bel_cevresi'].sum() > 0:
            line_bel = alt.Chart(df_o).mark_line(color='orange', point=True).encode(
                x='tarih',
                y=alt.Y('bel_cevresi', title='Bel Çevresi (cm)'),
                tooltip=['tarih', 'bel_cevresi']
            ).properties(height=300)
            
            rule_bel = alt.Chart(pd.DataFrame({'y': [ideal_bel]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y')
            
            st.altair_chart(line_bel + rule_bel, use_container_width=True)
        else:
            st.info("Bel ölçümü verisi yetersiz.")
            
    # Anamnez Testi Grafiği (YENİ EKLENEN)
    with c_g3:
        st.markdown("**Hazırbulunuşluk Test Skoru**")
        
        if not df_anamnez.empty:
            df_anamnez['tarih'] = pd.to_datetime(df_anamnez['tarih'])
            line_skor = alt.Chart(df_anamnez).mark_line(color='#0077b6', point=True).encode(
                x='tarih',
                y=alt.Y('skor', title='Risk Skoru'),
                tooltip=['tarih', 'skor']
            ).properties(height=300)
            st.altair_chart(line_skor, use_container_width=True)
            st.caption(f"Son Skor: {df_anamnez['skor'].iloc[-1]}")
        else:
            st.info("Kayıtlı Anamnez Testi yok.")


    # Tablo ve Silme İşlemleri
    st.subheader("📋 Tüm Seanslar")
    # v12'deki sütunları koruyoruz
    gosterim = df_olcumler[['id', 'tarih', 'kilo', 'hedef_kilo', 'bmi', 'planlanan_kalori', 'notlar']]
    st.dataframe(gosterim, use_container_width=True, hide_index=True)
    
    with st.expander("🗑️ Hatalı Kayıt Silme Paneli"):
        c_del1, c_del2 = st.columns([3, 1])
        sil_id = c_del1.number_input("Silinecek Seans ID'si (Tablodan bakınız)", min_value=0, step=1, key="sil_id")
        if c_del2.button("Kayıt Sil", key="sil_btn"):
            conn = sqlite3.connect(DB_NAME)
            cur = conn.cursor()
            cur.execute("DELETE FROM olcumler WHERE id=?", (sil_id,))
            conn.commit()
            conn.close()
            st.success("Kayıt silindi. Sayfayı yenileyin.")


# ==============================================================================
# 3. TAB: DİYET PROGRAMI OLUŞTUR
# ==============================================================================
elif menu == "3. Diyet Programı Oluştur":
    st.title("🥦 Diyet Programı Oluşturucu (BETA)")
    st.info("Bu modül, makro besin dağılımı ve örnek menü oluşturma mantığınızı ekleyebileceğiniz kısımdır.")
    
    conn = sqlite3.connect(DB_NAME)
    names = pd.read_sql("SELECT ad_soyad FROM danisanlar", conn)
    conn.close()
    
    if not names.empty:
        secilen_diyet = st.selectbox("Program Yazılacak Danışan:", names['ad_soyad'])
        
        info = danisan_getir_detay(secilen_diyet)
        did = info[0]
        last_data = son_olcum_getir(did)
        
        if last_data is not None:
            st.markdown("---")
            
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            col_s1.metric("Mevcut Kilo", f"{last_data['kilo']} kg")
            col_s2.metric("Hesaplanan TDEE", f"{int(last_data['tdee'])} kcal")
            col_s3.metric("Hedef Kalori", f"{last_data['planlanan_kalori']} kcal", delta_color="normal")
            col_s4.metric("Su", f"{last_data['su_ihtiyaci']} L")
            
            st.markdown("---")
            
            # Makro Dağılımı Ayarları (Örnek)
            st.subheader("Makro Besin Hedefleri")
            p_yuzde = st.slider("Protein (%)", 15, 40, 25, step=1)
            k_yuzde = st.slider("Karbonhidrat (%)", 30, 60, 50, step=1)
            y_yuzde = st.slider("Yağ (%)", 15, 40, 25, step=1)
            
            if (p_yuzde + k_yuzde + y_yuzde) != 100:
                st.warning(f"Toplam %100 olmalı. Şu an: {p_yuzde + k_yuzde + y_yuzde}%")
            
            # Gramaj Hesaplama
            kalori = last_data['planlanan_kalori']
            p_gram = round((kalori * p_yuzde / 100) / 4)
            k_gram = round((kalori * k_yuzde / 100) / 4)
            y_gram = round((kalori * y_yuzde / 100) / 9)
            
            c_m1, c_m2, c_m3 = st.columns(3)
            c_m1.metric("Protein Hedefi", f"{p_gram} g")
            c_m2.metric("Karb Hedefi", f"{k_gram} g")
            c_m3.metric("Yağ Hedefi", f"{y_gram} g")
            
            st.markdown("---")
            st.subheader("Diyet Programı Metni")
            st.text_area("Buraya diyet programını manuel olarak girebilirsiniz.", height=300)
            
            st.button("📄 Diyet Programı PDF Oluştur (Eklenmeli)")
    else:
        st.warning("Henüz danışan yok.")

# ==============================================================================
# 4. TAB: ONLINE ANAMNEZ TESTİ (YENİ EKLENEN MODÜL)
# ==============================================================================
elif menu == "4. Online Anamnez Testi":
    st.title("🧠 Online Anamnez ve Hazırbulunuşluk Testi")
    
    conn = sqlite3.connect(DB_NAME)
    names = pd.read_sql("SELECT ad_soyad FROM danisanlar ORDER BY ad_soyad", conn)
    conn.close()
    
    if not names.empty:
        secilen_danisan = st.selectbox("Test Uygulanacak Danışan:", ["Seçiniz..."] + names['ad_soyad'].tolist(), key="test_danisan_secim")
        
        if secilen_danisan != "Seçiniz...":
            
            st.markdown("---")
            st.subheader(f"Test Soruları ({secilen_danisan})")
            
            # --- TEST SORULARI VE CEVAPLARI ALMA ---
            cevaplar = {}
            for key, item in TEST_SORULARI.items():
                st.markdown(f"**{key}. {item['soru']}**")
                
                if item['tip'] == 'slider':
                    # Slider'ın başlangıç değerini (varsayılan) minimum yapalım
                    cevaplar[key] = st.slider(f"Soru {key}", item['min'], item['max'], item['min'], step=1, key=f"slider_{key}")
                elif item['tip'] == 'radio':
                    # Radio butonu
                    cevaplar[key] = st.radio(f"Seçiminiz {key}", item['seçenekler'], key=f"radio_{key}")

            # --- SKORLAMA VE KAYIT ---
            if st.button("Testi Bitir ve Kaydet", type="primary"):
                
                toplam_skor = skor_hesapla(cevaplar)
                
                # Danışan ID'sini al
                info = danisan_getir_detay(secilen_danisan)
                did = info[0]
                
                # Veritabanına Kayıt
                try:
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    c.execute('''INSERT INTO anamnez_testleri (danisan_id, tarih, skor, cevaplar) 
                                 VALUES (?, ?, ?, ?)''',
                              (did, datetime.date.today(), toplam_skor, json.dumps(cevaplar)))
                    conn.commit()
                    conn.close()
                    
                    st.success("✅ Anamnez Testi Kaydedildi!")
                    st.balloons()
                    st.markdown(f"**Toplam Risk Skoru:** **`{toplam_skor}`**")
                    
                    # Sonuca göre hızlı değerlendirme
                    if toplam_skor >= 15:
                        st.error("❗ **YÜKSEK RİSK:** Ciddi yaşam tarzı ve beslenme sorunları var. Programı zor uygulayabilir, motivasyon ve alışkanlık değişimi odaklı yaklaşılmalı.")
                    elif toplam_skor >= 8:
                        st.warning("⚠️ **ORTA RİSK:** Bazı alışkanlıkları hedefine ulaşmasını zorlaştırabilir (Örn: stresle yeme, az su). İlk seanslarda bu konulara odaklanılmalı.")
                    else:
                        st.info("✅ **DÜŞÜK RİSK / Yüksek Hazırbulunuşluk:** Danışan genel olarak iyi alışkanlıklara sahip, programı uygulama ihtimali yüksek.")
                        
                except Exception as e:
                    st.error(f"Kayıt sırasında bir hata oluştu: {e}")
            
    else:
        st.warning("Bu modülü kullanmak için öncelikle 'Danışan Kabul' sekmesinden yeni bir danışan kaydetmelisiniz.")
