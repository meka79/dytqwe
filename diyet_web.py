import streamlit as st
import pandas as pd
from fpdf import FPDF

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Diyetisyen Asistanı Pro", layout="wide", page_icon="🥗")

# --- VERİTABANI (Genişletilebilir) ---
BESINLER = {
    "Yumurta (Haşlanmış, 1 adet)": {"kcal": 75, "p": 6.3, "k": 0.6, "y": 5.3},
    "Yulaf Ezmesi (100g)": {"kcal": 370, "p": 13, "k": 59, "y": 7},
    "Tavuk Göğsü (100g)": {"kcal": 165, "p": 31, "k": 0, "y": 3.6},
    "Pirinç Pilavı (Pişmiş, 100g)": {"kcal": 130, "p": 2.7, "k": 28, "y": 0.3},
    "Zeytinyağı (1 Tatlı Kaşığı)": {"kcal": 40, "p": 0, "k": 0, "y": 4.5},
    "Mevsim Salata (Yağsız, Kase)": {"kcal": 25, "p": 1, "k": 4, "y": 0},
    "Elma (Orta Boy)": {"kcal": 52, "p": 0.3, "k": 14, "y": 0.2},
    "Tam Buğday Ekmeği (1 Dilim)": {"kcal": 69, "p": 3.5, "k": 11, "y": 1},
    "Yoğurt (Tam Yağlı, 1 Kase)": {"kcal": 120, "p": 6, "k": 9, "y": 6},
    "Ceviz (1 adet)": {"kcal": 26, "p": 0.6, "k": 0.6, "y": 2.5},
    "Beyaz Peynir (30g)": {"kcal": 50, "p": 5, "k": 1, "y": 3},
    "Muz (Orta Boy)": {"kcal": 105, "p": 1.3, "k": 27, "y": 0.4},
    "Mercimek Çorbası (1 Kase)": {"kcal": 150, "p": 9, "k": 20, "y": 3}
}

# --- FONKSİYONLAR ---
def bmh_hesapla(cinsiyet, kilo, boy, yas):
    # Mifflin-St Jeor Denklemi
    if cinsiyet == "Erkek":
        return (10 * kilo) + (6.25 * boy) - (5 * yas) + 5
    else:
        return (10 * kilo) + (6.25 * boy) - (5 * yas) - 161

def pdf_indir(ad, bmh, tdee, hedef_kal, hedef_aciklama, df_menu):
    pdf = FPDF()
    pdf.add_page()
    
    # Türkçe karakter düzeltme fonksiyonu
    def tr(text):
        return text.encode('latin-1', 'replace').decode('latin-1')

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, tr(f"DIYETISYEN RAPORU: {ad}"), ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, tr(f"BMH (Bazal Metabolizma): {int(bmh)} kcal"), ln=True)
    pdf.cell(0, 8, tr(f"Gunluk Enerji Harcamasi: {int(tdee)} kcal"), ln=True)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, tr(f"HEDEF: {hedef_aciklama}"), ln=True)
    pdf.cell(0, 8, tr(f"Planlanan Kalori: {hedef_kal} kcal"), ln=True)
    pdf.ln(10)
    
    # Tablo
    pdf.set_font("Arial", 'B', 10)
    col_w = [80, 30, 30, 40]
    pdf.cell(col_w[0], 10, "Besin", 1)
    pdf.cell(col_w[1], 10, "Miktar", 1)
    pdf.cell(col_w[2], 10, "Kalori", 1)
    pdf.cell(col_w[3], 10, "P / K / Y", 1)
    pdf.ln()
    
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
st.title("🥗 Diyetisyen Asistanı Pro v2.0")
st.markdown("Bu uygulama **Mifflin-St Jeor** formülünü ve **7700 kcal kuralını** kullanır.")

# 1. SOL SÜTUN: KİŞİSEL BİLGİLER
col_sol, col_sag = st.columns([1, 2])

with col_sol:
    st.subheader("1. Danışan Profili")
    ad = st.text_input("Ad Soyad")
    cinsiyet = st.selectbox("Cinsiyet", ["Kadın", "Erkek"])
    yas = st.number_input("Yaş", 10, 100, 30)
    boy = st.number_input("Boy (cm)", 100, 250, 170)
    kilo = st.number_input("Kilo (kg)", 30, 200, 80)
    
    aktivite_dict = {
        "Hareketsiz (Masa başı)": 1.2,
        "Az Hareketli (1-3 gün spor)": 1.375,
        "Orta Hareketli (3-5 gün spor)": 1.55,
        "Çok Hareketli (6-7 gün spor)": 1.725,
        "Sporcu (Çift idman)": 1.9
    }
    akt_secim = st.selectbox("Aktivite Durumu", list(aktivite_dict.keys()))
    katsayi = aktivite_dict[akt_secim]
    
    # Temel Hesaplama
    bmh = bmh_hesapla(cinsiyet, kilo, boy, yas)
    tdee = bmh * katsayi
    
    st.info(f"**BMH:** {int(bmh)} kcal\n\n**TDEE (Günlük Harcama):** {int(tdee)} kcal")

# 2. SAĞ SÜTUN: HEDEF VE PLANLAMA
with col_sag:
    st.subheader("2. Hedef Belirleme")
    
    hedef_tipi = st.radio("Diyet Amacı Nedir?", ["Kilo Vermek", "Kiloyu Korumak", "Kilo Almak"], horizontal=True)
    
    hedef_kalori = int(tdee)
    aciklama = "Mevcut kiloyu koruma"
    
    if hedef_tipi == "Kilo Vermek":
        st.write("📉 **Haftalık Kilo Kaybı Hedefi:**")
        # Bilimsel veriye göre seçenekler
        kayip_secenekleri = {
            "Haftada 0.25 kg (Hafif)": -275,
            "Haftada 0.50 kg (Standart/Önerilen)": -550,
            "Haftada 0.75 kg (Hızlı)": -825,
            "Haftada 1.00 kg (Zorlu)": -1100,
            "Haftada 1.25 kg (Agresif)": -1375,
            "Haftada 1.50 kg (Çok Agresif - Uzman Kontrolü)": -1650
        }
        secilen_hiz = st.selectbox("Hız Seçiniz:", list(kayip_secenekleri.keys()), index=1)
        kalori_farki = kayip_secenekleri[secilen_hiz]
        hedef_kalori = int(tdee + kalori_farki)
        aciklama = f"{secilen_hiz} hedefleniyor."
        
        # Güvenlik Uyarısı
        if cinsiyet == "Kadın" and hedef_kalori < 1200:
            st.error(f"⚠️ DİKKAT: Hesaplanan {hedef_kalori} kcal, kadınlar için önerilen güvenli sınırın (1200 kcal) altındadır!")
        elif cinsiyet == "Erkek" and hedef_kalori < 1500:
            st.error(f"⚠️ DİKKAT: Hesaplanan {hedef_kalori} kcal, erkekler için önerilen güvenli sınırın (1500 kcal) altındadır!")
        elif hedef_kalori < bmh:
            st.warning("⚠️ Uyarı: Hedef kalori Bazal Metabolizma Hızının (BMH) altında. Uzun vadede metabolik adaptasyona sebep olabilir.")
            
    elif hedef_tipi == "Kilo Almak":
        st.write("📈 **Haftalık Kilo Alma Hedefi:**")
        kazanc_secenekleri = {
            "Haftada 0.25 kg (Temiz Büyüme)": 275,
            "Haftada 0.50 kg (Standart)": 550,
            "Haftada 1.00 kg (Dirty Bulk)": 1100
        }
        secilen_hiz = st.selectbox("Hız Seçiniz:", list(kazanc_secenekleri.keys()))
        kalori_farki = kazanc_secenekleri[secilen_hiz]
        hedef_kalori = int(tdee + kalori_farki)
        aciklama = f"{secilen_hiz} hedefleniyor."

    st.success(f"🎯 **Günlük Hedef Kalori: {hedef_kalori} kcal**")
    
    st.divider()
    
    # MAKRO AYARLARI
    st.subheader("3. Makro Dağılımı")
    mk1, mk2, mk3 = st.columns(3)
    k_yuzde = mk1.number_input("% Karbonhidrat", value=50, step=5)
    p_yuzde = mk2.number_input("% Protein", value=20, step=5)
    y_yuzde = mk3.number_input("% Yağ", value=30, step=5)
    
    if k_yuzde + p_yuzde + y_yuzde != 100:
        st.error("Yüzdeler toplamı 100 olmalı!")
    else:
        h_k_g = int((hedef_kalori * k_yuzde / 100) / 4)
        h_p_g = int((hedef_kalori * p_yuzde / 100) / 4)
        h_y_g = int((hedef_kalori * y_yuzde / 100) / 9)
        st.caption(f"Plan: **{h_k_g}g Karb | {h_p_g}g Prot | {h_y_g}g Yağ**")

st.divider()

# 3. ALT KISIM: MENÜ OLUŞTURMA
st.subheader("4. Menü Planlama")

if 'menu' not in st.session_state:
    st.session_state.menu = []

c_besin, c_miktar, c_btn = st.columns([2, 1, 1])
secilen_besin = c_besin.selectbox("Besin Ekle", list(BESINLER.keys()))
miktar = c_miktar.number_input("Porsiyon Çarpanı", 0.25, 10.0, 1.0, step=0.25)

if c_btn.button("Listeye Ekle"):
    vals = BESINLER[secilen_besin]
    st.session_state.menu.append({
        "Besin": secilen_besin,
        "Miktar": miktar,
        "Kalori": vals['kcal'] * miktar,
        "Prot": vals['p'] * miktar,
        "Karb": vals['k'] * miktar,
        "Yag": vals['y'] * miktar
    })

# Tablo ve Hesaplar
if st.session_state.menu:
    df = pd.DataFrame(st.session_state.menu)
    st.dataframe(df, use_container_width=True)
    
    top_kal = df['Kalori'].sum()
    top_p = df['Prot'].sum()
    top_k = df['Karb'].sum()
    top_y = df['Yag'].sum()
    
    # Durum Göstergeleri
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Kalori", f"{int(top_kal)}", f"{int(top_kal - hedef_kalori)}")
    m2.metric("Protein", f"{int(top_p)}g", f"{int(top_p - h_p_g)}")
    m3.metric("Karb", f"{int(top_k)}g", f"{int(top_k - h_k_g)}")
    m4.metric("Yağ", f"{int(top_y)}g", f"{int(top_y - h_y_g)}")
    
    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("🗑️ Menüyü Temizle"):
        st.session_state.menu = []
        st.rerun()
        
    if ad:
        pdf_data = pdf_indir(ad, bmh, tdee, hedef_kalori, aciklama, df)
        col_btn2.download_button(label="📄 PDF Raporu İndir", data=pdf_data, file_name=f"diyet_{ad}.pdf", mime="application/pdf")
else:
    st.info("Henüz menüye bir besin eklenmedi.")
