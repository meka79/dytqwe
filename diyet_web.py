import streamlit as st
import pandas as pd
import sqlite3
import datetime
import altair as alt # Gelişmiş grafikler için

# --- AYARLAR ---
st.set_page_config(page_title="Diyetisyen Klinik v11", layout="wide", page_icon="🩺")

# --- VERİTABANI ---
DB_NAME = 'klinik_v11.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS danisanlar
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  ad_soyad TEXT UNIQUE, 
                  cinsiyet TEXT, 
                  dogum_yili INTEGER, 
                  boy REAL, 
                  telefon TEXT,
                  kayit_tarihi TEXT)''')
    
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
    # 1. BMI
    boy_m = boy / 100.0
    bmi = kilo / (boy_m ** 2)
    
    # 2. İdeal Kilo Aralığı (WHO: 18.5 - 24.9)
    ideal_min_kilo = 18.5 * (boy_m ** 2)
    ideal_max_kilo = 24.9 * (boy_m ** 2)
    ideal_ortalama = (ideal_min_kilo + ideal_max_kilo) / 2
    
    # 3. İdeal Bel Çevresi (IDF Standartları)
    # Erkek: < 94 cm (Risk Başlangıcı), Kadın: < 80 cm
    if cinsiyet == "Erkek":
        ideal_bel_limit = 94.0
    else:
        ideal_bel_limit = 80.0

    # 4. Obezite Kontrolü ve AjBW
    hesap_agirligi = kilo
    kullanilan_metod = "Mevcut Kilo"
    
    if bmi > 30:
        ajbw = ideal_ortalama + 0.25 * (kilo - ideal_ortalama)
        hesap_agirligi = ajbw
        kullanilan_metod = "Düzeltilmiş Ağırlık (AjBW)"
    
    # 5. BMH & TDEE
    base = (10 * hesap_agirligi) + (6.25 * boy) - (5 * yas)
    bmh = base + 5 if cinsiyet == "Erkek" else base - 161
    tdee = bmh * akt_katsayi
    
    # 6. Risk Analizi (WHR)
    whr = 0
    risk_text = "Veri Yok"
    if bel > 0 and kalca > 0:
        whr = bel / kalca
        limit = 0.9 if cinsiyet == "Erkek" else 0.85
        risk_text = "Yüksek Risk ⚠️" if whr > limit else "Düşük Risk ✅"

    su = kilo * 0.035
    
    return {
        "bmi": bmi,
        "ideal_aralik": (ideal_min_kilo, ideal_max_kilo),
        "ideal_bel": ideal_bel_limit,
        "bmh": bmh,
        "tdee": tdee,
        "kullanilan_metod": kullanilan_metod,
        "whr": whr,
        "risk_text": risk_text,
        "su": su
    }

# --- SQL FONKSİYONLARI ---
def danisan_kilo_guncelle_ve_id_getir(ad_soyad):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, dogum_yili, boy, cinsiyet FROM danisanlar WHERE ad_soyad=?", (ad_soyad,))
    result = c.fetchone()
    conn.close()
    return result

def yeni_danisan_kaydet_ve_getir(ad, cinsiyet, d_yili, boy, tel):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO danisanlar (ad_soyad, cinsiyet, dogum_yili, boy, telefon, kayit_tarihi) VALUES (?, ?, ?, ?, ?, ?)",
                  (ad, cinsiyet, d_yili, boy, tel, datetime.date.today()))
        conn.commit()
        yeni_id = c.lastrowid 
        conn.close()
        return yeni_id
    except sqlite3.IntegrityError:
        return None

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
        return False

# --- ARAYÜZ ---
st.sidebar.header("Diyetisyen Asistanı v11")
menu = st.sidebar.radio("Menü", ["1. Danışan Kabul & Analiz", "2. Danışan Dosyası (Takip)"])

# ---------------------------------------------------------
# TAB 1: ANALİZ
# ---------------------------------------------------------
if menu == "1. Danışan Kabul & Analiz":
    st.title("🔬 Yeni Analiz / Seans")
    
    if 'analiz_sonucu' not in st.session_state:
        st.session_state['analiz_sonucu'] = None
    
    conn = sqlite3.connect(DB_NAME)
    df_d = pd.read_sql("SELECT ad_soyad FROM danisanlar", conn)
    conn.close()
    isimler = df_d['ad_soyad'].tolist()
    
    mod = st.radio("İşlem Türü:", ["Yeni Kayıt", "Mevcut Danışan"], horizontal=True)
    
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
        tel_val = c1.text_input("Telefon")
        
    else:
        ad_soyad_val = st.selectbox("Danışan Seç:", isimler)
        if ad_soyad_val:
            bilgi = danisan_kilo_guncelle_ve_id_getir(ad_soyad_val)
            if bilgi:
                cinsiyet_val = bilgi[3]
                boy_val = bilgi[2]
                yas_val = datetime.date.today().year - bilgi[1]
                st.info(f"👤 **{ad_soyad_val}** | {yas_val} Yaş | {boy_val} cm")

    st.markdown("---")
    st.markdown("##### ⚖️ Antropometrik Ölçümler")
    col1, col2, col3, col4 = st.columns(4)
    kilo = col1.number_input("Güncel Kilo (kg)", 40.0, 250.0, 80.0, step=0.1)
    hedef = col2.number_input("Hedef (kg)", 40.0, 250.0, 70.0, step=0.1)
    bel = col3.number_input("Bel Çevresi (cm)", 50.0, 200.0, 85.0, step=0.5)
    kalca = col4.number_input("Kalça Çevresi (cm)", 50.0, 200.0, 100.0, step=0.5)
    
    akt_dict = {"Sedanter (1.2)": 1.2, "Hafif (1.375)": 1.375, "Orta (1.55)": 1.55, "Yüksek (1.725)": 1.725}
    akt = st.selectbox("Aktivite Düzeyi", list(akt_dict.keys()))
    
    if st.button("📊 Analiz Et ve Planla", type="primary", use_container_width=True):
        if mod == "Yeni Kayıt" and not ad_soyad_val:
            st.error("İsim giriniz.")
        else:
            res = bilimsel_analiz(cinsiyet_val, kilo, boy_val, yas_val, akt_dict[akt], bel, kalca)
            st.session_state['analiz_sonucu'] = {
                'res': res, 'ad': ad_soyad_val, 'cinsiyet': cinsiyet_val, 'yas': yas_val,
                'boy': boy_val, 'mod': mod, 'tel': tel_val, 'kilo': kilo,
                'hedef': hedef, 'bel': bel, 'kalca': kalca
            }

    if st.session_state['analiz_sonucu'] is not None:
        data = st.session_state['analiz_sonucu']
        res = data['res']
        
        st.markdown("---")
        st.markdown("### 📋 Analiz Raporu")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("BMI", f"{res['bmi']:.1f}")
        m2.metric("BMH", f"{int(res['bmh'])} kcal", help=f"Metod: {res['kullanilan_metod']}")
        m3.metric("TDEE", f"{int(res['tdee'])} kcal")
        m4.metric("Su İhtiyacı", f"{res['su']:.1f} Lt")
        
        # --- YENİ KISIM: İDEAL ÖLÇÜLER ---
        st.markdown("##### 💎 İdeal Vücut Hedefleri")
        r1, r2 = st.columns(2)
        with r1:
            st.info(f"**İdeal Kilo Aralığı:** {res['ideal_aralik'][0]:.1f} kg - {res['ideal_aralik'][1]:.1f} kg")
        with r2:
            # Bel hedefi gösterimi
            icon = "✅" if data['bel'] < res['ideal_bel'] else "⚠️"
            st.warning(f"**İdeal Bel Çevresi:** < {res['ideal_bel']} cm (Sizinki: {data['bel']} cm {icon})")
            
        # Planlama Slider...
        st.markdown("---")
        st.subheader("🎯 Hedef Planlama")
        
        fark = data['hedef'] - data['kilo']
        durum = "Kilo Verme" if fark < 0 else ("Kilo Alma" if fark > 0 else "Koruma")
        
        p1, p2 = st.columns([2, 1])
        with p1:
            plan_kalori = int(res['tdee'])
            if durum == "Kilo Verme":
                hiz = st.select_slider("Defisit (Kalori Açığı):", ["Hafif (-250)", "Orta (-500)", "Yüksek (-750)"], value="Orta (-500)")
                eksilen = int(hiz.split("(")[1].replace(")", ""))
                plan_kalori = int(res['tdee'] + eksilen)
            elif durum == "Kilo Alma":
                plan_kalori = int(res['tdee'] + 400)
                
            st.markdown(f"""
            <div style="background-color:#262730; padding:15px; border-radius:10px; border:1px solid #4CAF50; text-align:center;">
                <h2 style="margin:0; color:#4CAF50;">{plan_kalori} kcal</h2>
                <p style="margin:0; color:white;">Hedef Günlük Kalori</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Güvenlik uyarısı
            if plan_kalori < res['bmh'] and res['bmi'] < 30:
                 st.warning(f"⚠️ Dikkat: BMH ({int(res['bmh'])}) altına iniyorsunuz.")

        with p2:
            notlar = st.text_area("Seans Notları", "Rutin kontrol.")
            if st.button("💾 SEANSI KAYDET", type="secondary"):
                d_id = -1
                if data['mod'] == "Yeni Kayıt":
                    yeni_id = yeni_danisan_kaydet_ve_getir(data['ad'], data['cinsiyet'], datetime.date.today().year - data['yas'], data['boy'], data['tel'])
                    if yeni_id: d_id = yeni_id
                    else: st.error("İsim kayıtlı!")
                else:
                    mevcut_bilgi = danisan_kilo_guncelle_ve_id_getir(data['ad'])
                    if mevcut_bilgi: d_id = mevcut_bilgi[0]
                
                if d_id != -1:
                    if olcum_kaydet_db(d_id, data['kilo'], data['hedef'], data['bel'], data['kalca'], res['bmi'], res['bmh'], res['tdee'], res['su'], plan_kalori, notlar):
                        st.success("✅ Kayıt Başarılı!")

# ---------------------------------------------------------
# TAB 2: DANIŞAN DOSYASI (GELİŞMİŞ GRAFİKLER)
# ---------------------------------------------------------
elif menu == "2. Danışan Dosyası (Takip)":
    st.title("📂 Danışan Dosyası")
    
    conn = sqlite3.connect(DB_NAME)
    df_d = pd.read_sql("SELECT ad_soyad FROM danisanlar", conn)
    conn.close()
    
    if not df_d.empty:
        secilen = st.selectbox("Dosya Seç:", ["Seçiniz..."] + df_d['ad_soyad'].tolist())
        if secilen != "Seçiniz...":
            d_bilgi = danisan_kilo_guncelle_ve_id_getir(secilen)
            d_id = d_bilgi[0]
            
            conn = sqlite3.connect(DB_NAME)
            df_o = pd.read_sql(f"SELECT * FROM olcumler WHERE danisan_id={d_id} ORDER BY tarih", conn)
            conn.close()
            
            if not df_o.empty:
                # 1. BİLGİ KARTI
                yas = datetime.date.today().year - d_bilgi[1]
                st.info(f"👤 **{secilen}** | {yas} Yaş | {d_bilgi[2]} cm | Cinsiyet: {d_bilgi[3]}")
                
                # 2. GELİŞMİŞ GRAFİKLER (ALTAIR) - 0 TABANLI & HEDEF ÇİZGİLİ
                st.subheader("📈 Gelişim Analizi")
                c_g1, c_g2 = st.columns(2)
                
                # Son hedef kiloyu alalım (Grafiğe çizgi eklemek için)
                son_hedef = df_o.iloc[-1]['hedef_kilo']
                
                with c_g1:
                    st.markdown("**Kilo ve Hedef Grafiği**")
                    # Ana Kilo Çizgisi
                    line = alt.Chart(df_o).mark_line(point=True).encode(
                        x=alt.X('tarih', title='Tarih'),
                        y=alt.Y('kilo', title='Kilo (kg)', scale=alt.Scale(domain=[0, df_o['kilo'].max() + 20])),
                        tooltip=['tarih', 'kilo', 'hedef_kilo']
                    ).properties(height=300)
                    
                    # Hedef Çizgisi (Yeşil Kesikli)
                    rule = alt.Chart(pd.DataFrame({'y': [son_hedef]})).mark_rule(color='green', strokeDash=[5, 5]).encode(y='y')
                    
                    st.altair_chart(line + rule, use_container_width=True)
                    st.caption(f"Yeşil Çizgi: Hedef ({son_hedef} kg)")

                with c_g2:
                    st.markdown("**Bel Çevresi ve İdeal Sınır**")
                    ideal_bel = 94.0 if d_bilgi[3] == "Erkek" else 80.0
                    
                    if df_o['bel_cevresi'].sum() > 0:
                        # Bel Çizgisi
                        line_bel = alt.Chart(df_o).mark_line(color='orange', point=True).encode(
                            x='tarih',
                            y=alt.Y('bel_cevresi', title='Bel (cm)', scale=alt.Scale(domain=[0, df_o['bel_cevresi'].max() + 20])),
                            tooltip=['tarih', 'bel_cevresi']
                        ).properties(height=300)
                        
                        # İdeal Bel S
