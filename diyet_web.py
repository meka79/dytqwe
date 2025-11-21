import streamlit as st
import pandas as pd
import sqlite3
import datetime
from datetime import timedelta

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Asistanı v10", layout="wide", page_icon="🥑")

# --- VERİTABANI (SAĞLAMLAŞTIRILMIŞ) ---
DB_NAME = 'klinik_v10.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Danışanlar Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS danisanlar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  ad_soyad TEXT UNIQUE, 
                  cinsiyet TEXT, 
                  dogum_yili INTEGER, 
                  boy REAL, 
                  telefon TEXT,
                  kayit_tarihi TEXT)''')
    
    # Ölçümler Tablosu
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

# --- BİLİMSEL HESAPLAMA MOTORU ---
def bilimsel_analiz(cinsiyet, kilo, boy, yas, akt_katsayi, bel, kalca):
    # 1. BMI Hesapla
    boy_m = boy / 100.0
    bmi = kilo / (boy_m ** 2)
    
    # 2. İdeal Kilo Aralığı (BMI 18.5 - 24.9 arası)
    # Formül: Kilo = BMI * Boy(m)²
    ideal_min_kilo = 18.5 * (boy_m ** 2)
    ideal_max_kilo = 24.9 * (boy_m ** 2)
    
    # 3. Obezite Kontrolü ve AjBW (Düzeltilmiş Ağırlık)
    hesap_agirligi = kilo
    kullanilan_metod = "Mevcut Kilo"
    
    # Eğer BMI 30'un üzerindeyse matematiksel idealin ortasını baz alarak düzeltme yap
    ideal_ortalama = (ideal_min_kilo + ideal_max_kilo) / 2
    
    if bmi > 30:
        # AjBW = İdeal + 0.25 * (Mevcut - İdeal)
        ajbw = ideal_ortalama + 0.25 * (kilo - ideal_ortalama)
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
        limit = 0.9 if cinsiyet == "Erkek" else 0.85
        risk_text = "Yüksek Risk ⚠️" if whr > limit else "Düşük Risk ✅"

    # 7. Su İhtiyacı (35ml/kg)
    su = kilo * 0.035
    
    return {
        "bmi": bmi,
        "ideal_aralik": (ideal_min_kilo, ideal_max_kilo),
        "bmh": bmh,
        "tdee": tdee,
        "kullanilan_metod": kullanilan_metod,
        "whr": whr,
        "risk_text": risk_text,
        "su": su
    }

# --- YARDIMCI SQL FONKSİYONLARI ---
def danisan_getir_id(d_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM danisanlar WHERE id=?", (d_id,))
    d = c.fetchone()
    conn.close()
    return d

def danisan_kilo_guncelle_ve_id_getir(ad_soyad):
    # İsimden ID bulur
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, dogum_yili, boy, cinsiyet FROM danisanlar WHERE ad_soyad=?", (ad_soyad,))
    result = c.fetchone()
    conn.close()
    return result # (id, dogum, boy, cinsiyet)

def yeni_danisan_kaydet_ve_getir(ad, cinsiyet, d_yili, boy, tel):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO danisanlar (ad_soyad, cinsiyet, dogum_yili, boy, telefon, kayit_tarihi) VALUES (?, ?, ?, ?, ?, ?)",
                  (ad, cinsiyet, d_yili, boy, tel, datetime.date.today()))
        conn.commit()
        # EN ÖNEMLİ DÜZELTME: Kayıt edilen satırın ID'sini anında alıyoruz.
        yeni_id = c.lastrowid 
        conn.close()
        return yeni_id
    except sqlite3.IntegrityError:
        return None # İsim çakışması varsa

def olcum_kaydet_db(d_id, kilo, hedef, bel, kalca, bmi, bmh, tdee, su, plan, notlar):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''INSERT INTO olcumler 
                     (danisan_id, tarih, kilo, hedef_kilo, bel_cevresi, kalca_cevresi, bmi, bmh, tdee, su_ihtiyaci, planlanan_kalori, notlar) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (d_id, datetime.date.today(), kilo, hedef, bel, kalca, bmi, bmh, tdee, su, plan, notlar))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Veritabanı Hatası: {e}")
        return False

# --- ARAYÜZ ---
menu = st.sidebar.radio("Menü", ["1. Danışan Kabul & Analiz", "2. Danışan Dosyası (Takip)"])

# ---------------------------------------------------------
# TAB 1: ANALİZ (GİRİŞ)
# ---------------------------------------------------------
if menu == "1. Danışan Kabul & Analiz":
    st.title("🔬 Yeni Analiz / Seans")
    
    # Session State Başlatma (Verilerin kaybolmaması için)
    if 'analiz_sonucu' not in st.session_state:
        st.session_state['analiz_sonucu'] = None
    
    # İSİM VE MOD SEÇİMİ
    conn = sqlite3.connect(DB_NAME)
    df_d = pd.read_sql("SELECT ad_soyad FROM danisanlar", conn)
    conn.close()
    isimler = df_d['ad_soyad'].tolist()
    
    # GÜNCELLEME 1: Yeni Kayıt SOLDA, Mevcut Danışan SAĞDA
    mod = st.radio("İşlem Türü:", ["Yeni Kayıt", "Mevcut Danışan"], horizontal=True)
    
    # Form Değişkenleri
    ad_soyad_val = ""
    cinsiyet_val = "Kadın"
    yas_val = 30
    boy_val = 170.0
    tel_val = ""
    
    if mod == "Yeni Kayıt":
        st.markdown("##### 📝 Kimlik Bilgileri")
        c1, c2 = st.columns(2)
        ad_soyad_val = c1.text_input("Ad Soyad")
        cinsiyet_val = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        yas_val = c1.number_input("Yaş", 10, 90, 30)
        boy_val = c2.number_input("Boy (cm)", 140.0, 220.0, 170.0, step=1.0)
        tel_val = c1.text_input("Telefon (İsteğe bağlı)")
        
    else: # Mevcut Danışan
        ad_soyad_val = st.selectbox("Danışan Seç:", isimler)
        if ad_soyad_val:
            # Otomatik doldur
            bilgi = danisan_kilo_guncelle_ve_id_getir(ad_soyad_val)
            if bilgi:
                # bilgi = (id, dogum_yili, boy, cinsiyet)
                cinsiyet_val = bilgi[3]
                boy_val = bilgi[2]
                yas_val = datetime.date.today().year - bilgi[1]
                st.info(f"👤 **{ad_soyad_val}** seçildi. | {yas_val} Yaş | {boy_val} cm")

    st.markdown("---")
    
    # ÖLÇÜM GİRİŞİ
    st.markdown("##### ⚖️ Antropometrik Ölçümler")
    col1, col2, col3, col4 = st.columns(4)
    kilo = col1.number_input("Güncel Kilo (kg)", 40.0, 250.0, 80.0, step=0.1)
    hedef = col2.number_input("Hedef (kg)", 40.0, 250.0, 70.0, step=0.1)
    bel = col3.number_input("Bel Çevresi (cm)", 50.0, 200.0, 80.0, step=0.5)
    kalca = col4.number_input("Kalça Çevresi (cm)", 50.0, 200.0, 100.0, step=0.5)
    
    akt_dict = {"Sedanter (1.2)": 1.2, "Hafif (1.375)": 1.375, "Orta (1.55)": 1.55, "Yüksek (1.725)": 1.725}
    akt = st.selectbox("Aktivite Düzeyi", list(akt_dict.keys()))
    
    # HESAPLAMA BUTONU
    # Butona basınca sonucu session_state'e atacağız ki slider oynayınca kaybolmasın
    if st.button("📊 Analiz Et ve Planla", type="primary", use_container_width=True):
        if mod == "Yeni Kayıt" and not ad_soyad_val:
            st.error("Lütfen Ad Soyad giriniz.")
        else:
            # Hesaplamayı yap
            res = bilimsel_analiz(cinsiyet_val, kilo, boy_val, yas_val, akt_dict[akt], bel, kalca)
            
            # Sonucu hafızaya kaydet
            st.session_state['analiz_sonucu'] = {
                'res': res,
                'ad': ad_soyad_val,
                'cinsiyet': cinsiyet_val,
                'yas': yas_val,
                'boy': boy_val,
                'mod': mod,
                'tel': tel_val,
                'kilo': kilo,
                'hedef': hedef,
                'bel': bel,
                'kalca': kalca
            }

    # --- SONUÇLARIN GÖSTERİMİ (Slider oynasa bile burası çalışır) ---
    if st.session_state['analiz_sonucu'] is not None:
        data = st.session_state['analiz_sonucu']
        res = data['res']
        
        st.markdown("---")
        st.markdown("### 📋 Analiz Raporu")
        
        # 1. Satır: Temel Metrikler
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("BMI", f"{res['bmi']:.1f}")
        m2.metric("BMH", f"{int(res['bmh'])} kcal", help=f"Metod: {res['kullanilan_metod']}")
        m3.metric("TDEE (Koruma)", f"{int(res['tdee'])} kcal")
        m4.metric("Su İhtiyacı", f"{res['su']:.1f} Lt")
        
        # 2. Satır: Risk ve İdeal
        r1, r2 = st.columns(2)
        with r1:
            # GÜNCELLEME 3: İdeal Kilo Aralığı
            st.info(f"💎 **İdeal Kilo Aralığı:** {res['ideal_aralik'][0]:.1f} kg - {res['ideal_aralik'][1]:.1f} kg")
        with r2:
            renk = "red" if "Yüksek" in res['risk_text'] else "green"
            st.markdown(f"🩺 **Hastalık Riski (Bel/Kalça):** :{renk}[{res['risk_text']}]")
        
        # PLANLAMA KISMI (SLIDER BURADA)
        st.markdown("---")
        st.subheader("Target & Plan")
        
        fark = data['hedef'] - data['kilo']
        durum = "Koruma"
        if fark < 0: durum = "Kilo Verme"
        elif fark > 0: durum = "Kilo Alma"
        
        p1, p2 = st.columns([2, 1])
        with p1:
            plan_kalori = int(res['tdee'])
            
            if durum == "Kilo Verme":
                # GÜNCELLEME 2: Slider oynayınca form resetlenmemesi için session state kullandık
                hiz = st.select_slider("Defisit (Kalori Açığı) Belirle:", 
                                       options=["Hafif (-250)", "Orta (-500)", "Yüksek (-750)", "Agresif (-1000)"], 
                                       value="Orta (-500)")
                eksilen = int(hiz.split("(")[1].replace(")", ""))
                plan_kalori = int(res['tdee'] + eksilen)
                
            elif durum == "Kilo Alma":
                hiz = st.select_slider("Kalori Fazlası Belirle:", 
                                       options=["Hafif (+250)", "Orta (+500)", "Yüksek (+750)"], 
                                       value="Orta (+500)")
                eklenen = int(hiz.split("(")[1].replace(")", ""))
                plan_kalori = int(res['tdee'] + eklenen)
                
            # Sonuç Kartı
            st.markdown(f"""
            <div style="background-color:#262730; padding:15px; border-radius:10px; border:1px solid #4CAF50; text-align:center;">
                <h2 style="margin:0; color:#4CAF50;">{plan_kalori} kcal</h2>
                <p style="margin:0; color:white;">Hedeflenen Günlük Enerji</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Güvenlik Uyarısı
            if plan_kalori < res['bmh']:
                if res['bmi'] > 30:
                    st.info("Not: Obezite yönetiminde BMH altı planlamalar uzman kontrolünde yapılabilir.")
                else:
                    st.warning(f"⚠️ DİKKAT: {plan_kalori} kcal, kişinin Bazal Metabolizması ({int(res['bmh'])}) altındadır!")

        with p2:
            notlar = st.text_area("Seans Notları", "Diyet programı düzenlendi.")
            
            # GÜNCELLEME 4: Kaydetme İşlemi
            if st.button("💾 SEANSI KAYDET", type="secondary"):
                try:
                    d_id = -1
                    
                    if data['mod'] == "Yeni Kayıt":
                        # 1. Yeni kişiyi kaydet ve ID'sini al
                        yeni_id = yeni_danisan_kaydet_ve_getir(data['ad'], data['cinsiyet'], datetime.date.today().year - data['yas'], data['boy'], data['tel'])
                        if yeni_id:
                            d_id = yeni_id
                            st.toast(f"Yeni hasta kaydı oluşturuldu: {data['ad']}", icon="✅")
                        else:
                            st.error("Bu isimde bir hasta zaten kayıtlı! Lütfen 'Mevcut Danışan' menüsünü kullanın.")
                    else:
                        # 2. Mevcut kişinin ID'sini bul
                        mevcut_bilgi = danisan_kilo_guncelle_ve_id_getir(data['ad'])
                        if mevcut_bilgi:
                            d_id = mevcut_bilgi[0]
                    
                    # 3. Ölçümü kaydet
                    if d_id != -1:
                        if olcum_kaydet_db(d_id, data['kilo'], data['hedef'], data['bel'], data['kalca'], res['bmi'], res['bmh'], res['tdee'], res['su'], plan_kalori, notlar):
                            st.success(f"✅ {data['ad']} için seans başarıyla kaydedildi!")
                            # Başarılı kayıttan sonra session state'i temizleyebiliriz veya bırakabiliriz.
                            # st.session_state['analiz_sonucu'] = None 
                        else:
                            st.error("Kayıt sırasında veritabanı hatası.")
                    else:
                        st.error("Danışan ID bulunamadı. İşlem iptal.")
                        
                except Exception as e:
                    st.error(f"Beklenmeyen hata: {e}")

# ---------------------------------------------------------
# TAB 2: DANIŞAN DOSYASI (TAKİP)
# ---------------------------------------------------------
elif menu == "2. Danışan Dosyası (Takip)":
    st.title("📂 Danışan Dosyası")
    
    conn = sqlite3.connect(DB_NAME)
    df_d = pd.read_sql("SELECT ad_soyad FROM danisanlar", conn)
    conn.close() # Bağlantıyı kapatmayı unutma
    
    if df_d.empty:
        st.warning("Henüz sisteme kayıtlı danışan bulunmamaktadır.")
    else:
        secilen = st.selectbox("Dosyasını Görüntüle:", ["Seçiniz..."] + df_d['ad_soyad'].tolist())
        
        if secilen != "Seçiniz...":
            # ID Bul
            d_bilgi = danisan_kilo_guncelle_ve_id_getir(secilen) # (id, dogum, boy, cins)
            d_id = d_bilgi[0]
            
            conn = sqlite3.connect(DB_NAME)
            # Ölçümleri çek
            df_o = pd.read_sql(f"SELECT * FROM olcumler WHERE danisan_id={d_id} ORDER BY tarih", conn)
            conn.close()
            
            if not df_o.empty:
                # ÜST BİLGİ KARTI
                yas_simdi = datetime.date.today().year - d_bilgi[1]
                
                st.markdown(f"""
                <div style="background-color:#2b2c36; padding:10px; border-radius:5px; border-left: 5px solid #ff4b4b;">
                    <h4>👤 {secilen}</h4>
                    <p>Cinsiyet: {d_bilgi[3]} | Yaş: {yas_simdi} | Boy: {d_bilgi[2]} cm</p>
                </div>
                <br>
                """, unsafe_allow_html=True)
                
                # GRAFİKLER
                c_g1, c_g2 = st.columns(2)
                with c_g1:
                    st.subheader("📉 Kilo Takibi")
                    st.line_chart(df_o.set_index('tarih')['kilo'], color="#4CAF50")
                
                with c_g2:
                    st.subheader("⚠️ Risk (Bel Çevresi)")
                    if df_o['bel_cevresi'].sum() > 0:
                        st.line_chart(df_o.set_index('tarih')['bel_cevresi'], color="#FFA500")
                    else:
                        st.info("Bel verisi girilmemiş.")

                # DETAYLI TABLO
                st.subheader("📋 Tüm Seanslar")
                gosterim = df_o[['id', 'tarih', 'kilo', 'hedef_kilo', 'bmi', 'planlanan_kalori', 'notlar']]
                st.dataframe(gosterim, use_container_width=True, hide_index=True)
                
                # SİLME İŞLEMİ
                with st.expander("🗑️ Yanlış Kayıt Silme Paneli"):
                    c_del1, c_del2 = st.columns([3, 1])
                    sil_id = c_del1.number_input("Silinecek Seans ID'si (Tablodan bakınız)", min_value=0, step=1)
                    if c_del2.button("Kayıt Sil"):
                        conn = sqlite3.connect(DB_NAME)
                        cur = conn.cursor()
                        cur.execute("DELETE FROM olcumler WHERE id=?", (sil_id,))
                        conn.commit()
                        conn.close()
                        st.success("Kayıt silindi. Güncelleniyor...")
                        st.rerun()
                        
            else:
                st.info(f"{secilen} sisteme kayıtlı ancak henüz bir ölçüm/seans girilmemiş.")
