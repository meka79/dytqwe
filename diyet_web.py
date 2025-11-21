import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Diyetisyen Asistanı Pro", layout="wide")

# --- VERİTABANI ---
BESINLER = {
    "Yumurta (1 adet)": {"kcal": 75, "p": 6.3, "k": 0.6, "y": 5.3},
    "Yulaf (100g)": {"kcal": 370, "p": 13, "k": 59, "y": 7},
    "Tavuk Göğsü (100g)": {"kcal": 165, "p": 31, "k": 0, "y": 3.6},
    "Pirinç Pilavı (100g)": {"kcal": 130, "p": 2.7, "k": 28, "y": 0.3},
    "Zeytinyağı (1 tk)": {"kcal": 40, "p": 0, "k": 0, "y": 4.5},
    "Salata (Kase)": {"kcal": 25, "p": 1, "k": 4, "y": 0},
    "Elma (Orta)": {"kcal": 52, "p": 0.3, "k": 14, "y": 0.2},
    "Tam Buğday Ekmeği (Dilim)": {"kcal": 69, "p": 3.5, "k": 11, "y": 1},
    "Yoğurt (Kase)": {"kcal": 120, "p": 6, "k": 9, "y": 6},
    "Ceviz (1 adet)": {"kcal": 26, "p": 0.6, "k": 0.6, "y": 2.5},
    "Beyaz Peynir (30g)": {"kcal": 50, "p": 5, "k": 1, "y": 3}
}

# --- FONKSİYONLAR ---
def bmh_hesapla(cinsiyet, kilo, boy, yas):
    if cinsiyet == "Erkek":
        return (10 * kilo) + (6.25 * boy) - (5 * yas) + 5
    else:
        return (10 * kilo) + (6.25 * boy) - (5 * yas) - 161

def pdf_indir(ad, bmh, tdee, hedef_kal, df_menu):
    pdf = FPDF()
    pdf.add_page()
    
    # Font ayarları (Türkçe karakter sorunu yaşamamak için basit çözüm)
    def tr(text):
        return text.encode('latin-1', 'replace').decode('latin-1')

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, tr(f"DIYET PROGRAMI: {ad}"), ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, tr(f"BMH: {int(bmh)} kcal | Gunluk Ihtiyac: {int(tdee)} kcal"), ln=True)
    pdf.cell(0, 10, tr(f"Hedeflenen Kalori: {hedef_kal} kcal"), ln=True)
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "MENU PLANI", ln=True)
    pdf.set_font("Arial", 'B', 10)
    
    # Tablo Başlık
    col_w = [80, 30, 30, 40]
    pdf.cell(col_w[0], 10, "Besin", 1)
    pdf.cell(col_w[1], 10, "Miktar", 1)
    pdf.cell(col_w[2], 10, "Kalori", 1)
    pdf.cell(col_w[3], 10, "Makro (P/K/Y)", 1)
    pdf.ln()
    
    # Tablo İçerik
    pdf.set_font("Arial", '', 10)
    for index, row in df_menu.iterrows():
        besin_adi = tr(row['Besin'])
        pdf.cell(col_w[0], 10, besin_adi, 1)
        pdf.cell(col_w[1], 10, str(row['Miktar']), 1)
        pdf.cell(col_w[2], 10, str(int(row['Kalori'])), 1)
        pdf.cell(col_w[3], 10, f"{int(row['Prot'])}/{int(row['Karb'])}/{int(row['Yag'])}", 1)
        pdf.ln()
        
    return pdf.output(dest="S").encode("latin-1")

# --- ARAYÜZ ---
st.title("🥗 Diyetisyen Asistanı Pro")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("Danışan Bilgileri")
    ad = st.text_input("Ad Soyad")
    cinsiyet = st.selectbox("Cinsiyet", ["Kadın", "Erkek"])
    yas = st.number_input("Yaş", 10, 100, 25)
    boy = st.number_input("Boy (cm)", 100, 250, 170)
    kilo = st.number_input("Kilo (kg)", 30, 200, 70)
    
    aktivite_secenekleri = {
        "Hareketsiz (Masa başı)": 1.2,
        "Az Hareketli (1-3 gün spor)": 1.375,
        "Orta Hareketli (3-5 gün spor)": 1.55,
        "Çok Hareketli (6-7 gün spor)": 1.725,
        "Sporcu (Çift idman)": 1.9
    }
    aktivite_adi = st.selectbox("Aktivite Seviyesi", list(aktivite_secenekleri.keys()))
    aktivite_katsayisi = aktivite_secenekleri[aktivite_adi]

    st.divider()
    
    # Hesaplamalar
    bmh = bmh_hesapla(cinsiyet, kilo, boy, yas)
    tdee = bmh * aktivite_katsayisi
    
    st.info(f"🔥 **BMH:** {int(bmh)} kcal")
    st.info(f"⚡ **Günlük İhtiyaç:** {int(tdee)} kcal")

with col2:
    st.header("Hedef ve Menü")
    
    hedef_kalori = st.number_input("Hedef Kalori", value=int(tdee))
    
    # Makro Hedefleri (Slider)
    k_yuzde, p_yuzde, y_yuzde = st.columns(3)
    h_karb_y = k_yuzde.number_input("% Karb", value=50)
    h_prot_y = p_yuzde.number_input("% Prot", value=20)
    h_yag_y = y_yuzde.number_input("% Yağ", value=30)
    
    if h_karb_y + h_prot_y + h_yag_y != 100:
        st.error("Yüzdeler toplamı 100 olmalı!")
    else:
        h_g_k = int((hedef_kalori * h_karb_y / 100) / 4)
        h_g_p = int((hedef_kalori * h_prot_y / 100) / 4)
        h_g_y = int((hedef_kalori * h_yag_y / 100) / 9)
        st.caption(f"🎯 Hedef Makrolar: **{h_g_k}g Karb | {h_g_p}g Prot | {h_g_y}g Yağ**")

    st.divider()
    
    # Menü Oluşturma
    if 'menu' not in st.session_state:
        st.session_state.menu = []

    c_besin, c_miktar, c_buton = st.columns([2, 1, 1])
    secilen_besin = c_besin.selectbox("Besin Ekle", list(BESINLER.keys()))
    miktar = c_miktar.number_input("Çarpan (1=Porsiyon)", 0.1, 10.0, 1.0, step=0.5)
    
    if c_buton.button("Ekle"):
        degerler = BESINLER[secilen_besin]
        st.session_state.menu.append({
            "Besin": secilen_besin,
            "Miktar": miktar,
            "Kalori": degerler['kcal'] * miktar,
            "Prot": degerler['p'] * miktar,
            "Karb": degerler['k'] * miktar,
            "Yag": degerler['y'] * miktar
        })

    # Tablo Gösterimi
    if st.session_state.menu:
        df = pd.DataFrame(st.session_state.menu)
        st.dataframe(df, use_container_width=True)
        
        toplam_kcal = df['Kalori'].sum()
        toplam_p = df['Prot'].sum()
        toplam_k = df['Karb'].sum()
        toplam_y = df['Yag'].sum()
        
        # İlerleme Çubuğu Mantığı
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Kalori", f"{int(toplam_kcal)}", delta=f"{int(toplam_kcal - hedef_kalori)}")
        col_m2.metric("Protein", f"{int(toplam_p)}g", delta=f"{int(toplam_p - h_g_p)}")
        col_m3.metric("Karb", f"{int(toplam_k)}g", delta=f"{int(toplam_k - h_g_k)}")
        col_m4.metric("Yağ", f"{int(toplam_y)}g", delta=f"{int(toplam_y - h_g_y)}")
        
        if st.button("Listeyi Temizle"):
            st.session_state.menu = []
            st.rerun()
            
        # PDF Butonu
        if ad:
            pdf_data = pdf_indir(ad, bmh, tdee, hedef_kalori, df)
            st.download_button(label="📄 PDF Raporunu İndir", data=pdf_data, file_name=f"diyet_{ad}.pdf", mime="application/pdf")
    else:
        st.info("Henüz menüye besin eklemediniz.")