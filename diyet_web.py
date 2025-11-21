import streamlit as st
import pandas as pd
import sqlite3
import datetime
import altair as alt

# --- AYARLAR ---
st.set_page_config(page_title="Klinik Yönetim v13", layout="wide", page_icon="🥗")

# --- VERİTABANI ---
DB_NAME = 'klinik_v13.db'

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

# --- SQL FONKSİYONLARI ---
def danisan_getir_detay(ad_soyad):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, dogum_yili, boy, cinsiyet, telefon, kayit_tarihi FROM danisanlar WHERE ad_soyad=?", (ad_soyad,))
    res = c.fetchone()
    conn.close()
    return res

def son_olcum_getir(danisan_id):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql(f"SELECT * FROM olcumler WHERE danisan_id={danisan_id} ORDER BY id DESC LIMIT 1", conn)
    conn.close()
    return df.iloc[0] if not df.empty else None

def yeni_danisan_ekle(ad, cins, yil, boy, tel):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # Tarih formatı güncellendi: YYYY-MM-DD HH:MM
        simdi = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute("INSERT INTO danisanlar (ad_soyad, cinsiyet, dogum_yili, boy, telefon, kayit_tarihi) VALUES (?, ?, ?, ?, ?, ?)",
                  (ad, cins, yil, boy, tel, simdi))
        conn.commit()
        nid = c.lastrowid
        conn.close()
        return nid
    except: return None

def olcum_ekle_db(d_id, kilo, hedef, bel, kalca, bmi, bmh, tdee, su, plan, notlar):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # Tarih formatı güncellendi: YYYY-MM-DD HH:MM
        simdi = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute('''INSERT INTO olcumler 
                     (danisan_id, tarih, kilo, hedef_kilo, bel_cevresi, kalca_cevresi, bmi, bmh, tdee, su_ihtiyaci, planlanan_kalori, notlar) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (d_id, simdi, kilo, hedef, bel, kalca, bmi, bmh, tdee, su, plan, notlar))
        conn.commit()
        conn.close()
        return True
    except: return False

def not_guncelle_db(olcum_id, yeni_not):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE olcumler SET notlar=? WHERE id=?", (yeni_not, olcum_id))
        conn.commit()
        conn.close()
        return True
    except: return False

# --- BİLİMSEL HESAPLAMA ---
def analiz_et(cinsiyet, kilo, boy, yas, akt, bel, kalca):
    boy_m = boy / 100.0
    bmi = kilo / (boy_m ** 2)
    
    ideal_min = 18.5 * (boy_m ** 2)
    ideal_max = 24.9 * (boy_m ** 2)
    ideal_ort = (ideal_min + ideal_max) / 2
    
    ideal_bel = 94.0 if cinsiyet == "Erkek" else 80.0
    
    hesap_kilo = kilo
    metod = "Mevcut Ağırlık"
    if bmi > 30:
        hesap_kilo = ideal_ort + 0.25 * (kilo - ideal_ort)
        metod = "AjBW (Düzeltilmiş)"
        
    base = (10 * hesap_kilo) + (6.25 * boy) - (5 * yas)
    bmh = base + 5 if cinsiyet == "Erkek" else base - 161
    tdee = bmh * akt
    su = kilo * 0.035
    
    whr = bel/kalca if kalca > 0 else 0
    risk_limit = 0.9 if cinsiyet == "Erkek" else 0.85
    risk = "Yüksek Risk" if whr > risk_limit else "Düşük Risk"
    
    return {"bmi": bmi, "ideal_aralik": (ideal_min, ideal_max), "ideal_bel": ideal_bel,
            "bmh": bmh, "tdee": tdee, "metod": metod, "risk": risk, "su": su}

# --- ARAYÜZ ---
st.sidebar.title("Diyetisyen Pro v13")
menu = st.sidebar.radio("Klinik Modülü", ["1. Danışan Kabul & Analiz", "2. Danışan Dosyası (Takip)", "3. Diyet Programı Oluştur"])

# ==============================================================================
# 1. TAB: ANALİZ VE KAYIT
# ==============================================================================
if menu == "1. Danışan Kabul & Analiz":
    st.title("🔬 Yeni Seans / Analiz")
    if 'analiz' not in st.session_state: st.session_state['analiz'] = None

    conn = sqlite3.connect(DB_NAME)
    df_d = pd.read_sql("SELECT ad_soyad FROM danisanlar", conn)
    conn.close()
    
    col_sel1, col_sel2 = st.columns([1, 2])
    
    # İSTEK 1: "Yeni Kayıt" en başta ve varsayılan seçili
    mod = col_sel1.radio("Kayıt Tipi", ["Yeni Kayıt", "Mevcut Danışan"])
    
    # Varsayılan Değerler
    ad, cins, yas, boy, tel = "", "Kadın", 30, 170.0, ""
    def_kilo, def_hedef, def_bel, def_kalca = 80.0, 70.0, 90.0, 100.0
    
    if mod == "Mevcut Danışan":
        ad = col_sel2.selectbox("Danışan Seçiniz:", df_d['ad_soyad'].tolist() if not df_d.empty else [])
        if ad:
            bilgi = danisan_getir_detay(ad) # id, yil, boy, cins, tel, tarih
            if bilgi:
                d_id, d_yil, boy, cins, tel, kayit_t = bilgi
                yas = datetime.date.today().year - d_yil
                st.success(f"👤 {ad} | {yas} Yaş | {boy} cm")
                
                son_veri = son_olcum_getir(d_id)
                if son_veri is not None:
                    def_kilo = float(son_veri['kilo'])
                    def_hedef = float(son_veri['hedef_kilo'])
                    def_bel = float(son_veri['bel_cevresi'])
                    def_kalca = float(son_veri['kalca_cevresi'])
                    st.info(f"ℹ️ Son ölçüm ({son_veri['tarih']}) otomatik yüklendi.")
    else:
        st.subheader("Yeni Kimlik Bilgileri")
        c1, c2 = st.columns(2)
        ad = c1.text_input("Ad Soyad")
        cins = c2.selectbox("Cinsiyet", ["Kadın", "Erkek"])
        yas = c1.number_input("Yaş", 10, 90, 30)
        boy = c2.number_input("Boy (cm)", 140.0, 220.0, 170.0)
        tel = c1.text_input("Telefon")

    st.markdown("---")
    st.subheader("📏 Antropometrik Ölçümler")
    
    c_m1, c_m2, c_m3, c_m4 = st.columns(4)
    kilo = c_m1.number_input("Kilo (kg)", 40.0, 250.0, def_kilo, step=0.1)
    hedef = c_m2.number_input("Hedef Kilo (kg)", 40.0, 250.0, def_hedef, step=0.1)
    bel = c_m3.number_input("Bel (cm)", 50.0, 200.0, def_bel, step=0.5)
    kalca = c_m4.number_input("Kalça (cm)", 50.0, 200.0, def_kalca, step=0.5)
    
    akt_opts = {"Sedanter (1.2)": 1.2, "Hafif (1.375)": 1.375, "Orta (1.55)": 1.55, "Yüksek (1.725)": 1.725}
    akt_secim = st.selectbox("Aktivite", list(akt_opts.keys()))
    
    if st.button("Hesapla ve Planla", type="primary", use_container_width=True):
        if not ad: st.error("İsim giriniz."); st.stop()
        res = analiz_et(cins, kilo, boy, yas, akt_opts[akt_secim], bel, kalca)
        st.session_state['analiz'] = {
            'res': res, 'ad': ad, 'mod': mod, 'cins': cins, 'yas': yas, 'boy': boy, 'tel': tel,
            'kilo': kilo, 'hedef': hedef, 'bel': bel, 'kalca': kalca
        }

    # SONUÇ EKRANI
    if st.session_state['analiz']:
        d = st.session_state['analiz']
        r = d['res']
        
        st.markdown("---")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("BMI", f"{r['bmi']:.1f}")
        k2.metric("BMH", f"{int(r['bmh'])}", help=r['metod'])
        k3.metric("TDEE", f"{int(r['tdee'])}")
        k4.metric("Su", f"{r['su']:.1f} Lt")
        
        col_i1, col_i2 = st.columns(2)
        col_i1.info(f"🎯 **İdeal Kilo:** {r['ideal_aralik'][0]:.1f} - {r['ideal_aralik'][1]:.1f} kg")
        icon = "✅" if d['bel'] < r['ideal_bel'] else "⚠️"
        col_i2.warning(f"📏 **İdeal Bel:** < {r['ideal_bel']} cm (Siz: {d['bel']} {icon})")
        
        st.markdown("---")
        st.subheader("🚀 Hedef Planlama")
        
        diff = d['hedef'] - d['kilo']
        mode = "Ver" if diff < 0 else ("Al" if diff > 0 else "Koru")
        
        cp1, cp2 = st.columns([2, 1])
        with cp1:
            plan_cal = int(r['tdee'])
            hafta_str = ""
            
            if mode == "Ver":
                slider = st.select_slider("Defisit Seviyesi", ["Hafif (-250)", "Orta (-500)", "Yüksek (-750)"], value="Orta (-500)")
                val = int(slider.split("(")[1][:-1])
                plan_cal = int(r['tdee'] + val)
                h_degisim = abs(val * 7) / 7700
                if h_degisim > 0:
                    w = abs(diff) / h_degisim
                    tarih = datetime.date.today() + datetime.timedelta(weeks=w)
                    hafta_str = f"📅 Tahmini Süre: {int(w)} Hafta ({tarih.strftime('%d.%m.%Y')})"
                    
            elif mode == "Al":
                plan_cal = int(r['tdee'] + 400)
                h_degisim = (400 * 7) / 7700
                w = abs(diff) / h_degisim
                tarih = datetime.date.today() + datetime.timedelta(weeks=w)
                hafta_str = f"📅 Tahmini Süre: {int(w)} Hafta ({tarih.strftime('%d.%m.%Y')})"

            # İSTEK 2: Tahmini süre kutunun içinde
            st.markdown(f"""
            <div style="background-color:#1E1E1E; padding:20px; border-radius:15px; border:2px solid #4CAF50; text-align:center; box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);">
                <h1 style="margin:0; color:#4CAF50; font-size: 3em;">{plan_cal} kcal</h1>
                <p style="color:#E0E0E0; margin:5px 0; font-size: 1.2em;">Günlük Hedef</p>
                <hr style="border-color: #333; margin: 15px 0;">
                <p style="color:#aaa; margin:0; font-size: 0.9em;">{hafta_str if hafta_str else "Hedef Kilodasınız"}</p>
            </div>
            """, unsafe_allow_html=True)

        with cp2:
            note = st.text_area("Notlar", "Program oluşturuldu.")
            if st.button("💾 SEANSI KAYDET"):
                did = -1
                if d['mod'] == "Yeni Kayıt":
                    res_id = yeni_danisan_ekle(d['ad'], d['cins'], datetime.date.today().year - d['yas'], d['boy'], d['tel'])
                    if res_id: did = res_id
                    else: st.error("İsim zaten var!")
                else:
                    mevcut = danisan_getir_detay(d['ad'])
                    if mevcut: did = mevcut[0]
                
                if did != -1:
                    if olcum_ekle_db(did, d['kilo'], d['hedef'], d['bel'], d['kalca'], r['bmi'], r['bmh'], r['tdee'], r['su'], plan_cal, note):
                        st.success("✅ Kayıt Başarılı!")

# ==============================================================================
# 2. TAB: DANIŞAN DOSYASI
# ==============================================================================
elif menu == "2. Danışan Dosyası (Takip)":
    st.title("📂 Danışan Dosyası")
    
    conn = sqlite3.connect(DB_NAME)
    df_names = pd.read_sql("SELECT ad_soyad FROM danisanlar", conn)
    conn.close()
    
    if not df_names.empty:
        secilen = st.selectbox("Dosya Aç:", ["Seçiniz..."] + df_names['ad_soyad'].tolist())
        
        if secilen != "Seçiniz...":
            bilgi = danisan_getir_detay(secilen) # id, yil, boy, cins, tel, kayit_t
            did = bilgi[0]
            
            conn = sqlite3.connect(DB_NAME)
            df = pd.read_sql(f"SELECT * FROM olcumler WHERE danisan_id={did} ORDER BY id ASC", conn)
            conn.close()
            
            if not df.empty:
                # A. ÜST BİLGİ
                yas = datetime.date.today().year - bilgi[1]
                c1, c2 = st.columns([3, 1])
                c1.info(f"👤 **{secilen}** | {yas} Yaş | {bilgi[2]} cm | {bilgi[3]} | Tel: {bilgi[4]}")
                
                # İSTEK 5: RAPOR OLUŞTURMA BUTONU
                if c2.button("📄 Özet Rapor"):
                    son = df.iloc[-1]
                    with st.expander("YAZDIRILABİLİR RAPOR GÖRÜNÜMÜ", expanded=True):
                        st.markdown(f"""
                        <div style="background-color: white; color: black; padding: 20px; border: 1px solid black; border-radius: 5px;">
                            <h2 style="border-bottom: 2px solid black; padding-bottom: 10px;">Diyetisyen Klinik Raporu</h2>
                            <p><b>Danışan:</b> {secilen} | <b>Tarih:</b> {datetime.date.today().strftime('%d.%m.%Y')}</p>
                            <table style="width:100%; border-collapse: collapse; margin-top: 20px;">
                                <tr style="background-color: #f2f2f2;">
                                    <td style="padding: 8px; border: 1px solid #ddd;">Mevcut Kilo</td>
                                    <td style="padding: 8px; border: 1px solid #ddd;"><b>{son['kilo']} kg</b></td>
                                    <td style="padding: 8px; border: 1px solid #ddd;">Hedef Kilo</td>
                                    <td style="padding: 8px; border: 1px solid #ddd;"><b>{son['hedef_kilo']} kg</b></td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px; border: 1px solid #ddd;">BMI</td>
                                    <td style="padding: 8px; border: 1px solid #ddd;">{son['bmi']:.1f}</td>
                                    <td style="padding: 8px; border: 1px solid #ddd;">Günlük Kalori</td>
                                    <td style="padding: 8px; border: 1px solid #ddd;"><b>{son['planlanan_kalori']} kcal</b></td>
                                </tr>
                                <tr style="background-color: #f2f2f2;">
                                    <td style="padding: 8px; border: 1px solid #ddd;">Bel Çevresi</td>
                                    <td style="padding: 8px; border: 1px solid #ddd;">{son['bel_cevresi']} cm</td>
                                    <td style="padding: 8px; border: 1px solid #ddd;">Su Hedefi</td>
                                    <td style="padding: 8px; border: 1px solid #ddd;">{son['su_ihtiyaci']:.1f} Lt</td>
                                </tr>
                            </table>
                            <br>
                            <p><b>Uzman Notu:</b> {son['notlar']}</p>
                            <div style="text-align: center; margin-top: 30px; font-size: 12px; color: gray;">
                                Bu rapor Diyetisyen Klinik Sistemi tarafından oluşturulmuştur.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        st.caption("Yukarıdaki alanı ekran görüntüsü alarak veya kopyalayarak yazdırabilirsiniz.")

                # B. GRAFİKLER
                st.subheader("📈 Gelişim Grafikleri")
                c1, c2 = st.columns(2)
                with c1:
                    target = df.iloc[-1]['hedef_kilo']
                    line = alt.Chart(df).mark_line(point=True).encode(
                        x=alt.X('tarih', title='Tarih (Saatli)'), 
                        y=alt.Y('kilo', scale=alt.Scale(domain=[0, df['kilo'].max()+10])), 
                        tooltip=['tarih', 'kilo', 'hedef_kilo']
                    ).properties(height=300)
                    rule = alt.Chart(pd.DataFrame({'y': [target]})).mark_rule(color='green', strokeDash=[5,5]).encode(y='y')
                    st.altair_chart(line + rule, use_container_width=True)
                with c2:
                    limit = 94 if bilgi[3] == "Erkek" else 80
                    if df['bel_cevresi'].sum() > 0:
                        bline = alt.Chart(df).mark_line(color='orange', point=True).encode(
                            x='tarih', y=alt.Y('bel_cevresi', scale=alt.Scale(domain=[0, df['bel_cevresi'].max()+10]))
                        ).properties(height=300)
                        brule = alt.Chart(pd.DataFrame({'y': [limit]})).mark_rule(color='red', strokeDash=[3,3]).encode(y='y')
                        st.altair_chart(bline + brule, use_container_width=True)

                # C. KAYIT DETAYLARI VE DÜZENLEME (v10'dan geri gelen özellik)
                st.markdown("---")
                st.subheader("📋 Kayıt Detayları & Düzenleme")
                
                # İSTEK 4: Tarih formatı zaten veritabanında YYYY-MM-DD HH:MM olduğu için tabloda saatli görünecek
                st.dataframe(df[['id', 'tarih',]

