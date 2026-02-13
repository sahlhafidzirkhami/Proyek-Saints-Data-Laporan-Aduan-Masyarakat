import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import time
import streamlit.components.v1 as components
from pathlib import Path
from datetime import datetime, timedelta
import base64
import numpy as np
import google.generativeai as genai

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Dashboard Analisis Pengaduan Masyarakat Kab. Bandung", layout="wide")

# --- KONFIGURASI GEMINI ---
# Masukkan API KEY Anda di sini
genai.configure(api_key="AIzaSyDkBAbzV-h_tIveVGk9zvtjZz2HjZWPxGM")

def initialize_gemini():
    try:
        # Cari model yang tersedia secara dinamis
        available_models = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        
        # Urutan prioritas model yang ingin kita pakai
        priority_list = [
            'models/gemini-1.5-flash', 
            'models/gemini-1.5-pro', 
            'models/gemini-pro'
        ]
        
        # Pilih model pertama yang cocok dari daftar prioritas yang tersedia di akunmu
        selected_model = next((m for m in priority_list if m in available_models), None)
        
        if selected_model:
            return genai.GenerativeModel(selected_model)
        else:
            # Jika tidak ada yang cocok di list, ambil yang pertama tersedia di API
            return genai.GenerativeModel(available_models[0])
            
    except Exception as e:
        st.error(f"Koneksi API Gagal: {e}")
        return None

# Inisialisasi Model
model = initialize_gemini()

# --- KONSTANTA ---
SLA_HARI = 5
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASS = "admin123"

def icon(path, size=20):
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"""
            <img 
                src="data:image/png;base64,{data}"
                width="{size}"
                height="{size}"
                style="vertical-align:middle; margin-right:6px;"
            >
        """
    return ""

def section(gap=6):
    st.markdown(f"<div style='height:{gap}px;'></div>", unsafe_allow_html=True)

def icon_title(path, text, size=28):
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        img_html = f'<img src="data:image/png;base64,{data}" width="{size}" height="{size}" style="display:block;">'
    else:
        img_html = ""
    
    return f"""
    <div style="display:flex; align-items:center; gap:10px;">
        {img_html}
        <span style="font-size:32px; font-weight:700; line-height:1;">{text}</span>
    </div>
    """

def kpi(icon_path, title, value):
    if os.path.exists(icon_path):
        with open(icon_path, "rb") as f:
            icon_data = base64.b64encode(f.read()).decode()
        img_html = f'<img src="data:image/png;base64,{icon_data}" width="18">'
    else:
        img_html = ""

    return f"""
    <div style="padding:16px 18px;">
        <div style="display:flex; align-items:center; gap:8px; font-size:15px; font-weight:600; opacity:0.85;">
            {img_html}<span>{title}</span>
        </div>
        <div style="margin-top:8px; font-size:34px; font-weight:700;">{value}</div>
    </div>
    """

# --- FUNGSI PEMBERSIHAN ---
def clean_category_name(text):
    if pd.isna(text) or str(text).strip() in ["-", "", "nan"]: return "Tidak Diketahui"
    text = str(text).strip()
    for prefix in ["Lainnya terkait ", "Permintaan Informasi ", "Pengaduan ", "Aspirasi "]:
        text = text.replace(prefix, "")
    return text

def clean_agency_name(text):
    if pd.isna(text): return "Umum"
    text = str(text).lower()
    if "pekerjaan umum" in text or "pupr" in text: return "Dinas PUTR"
    if "lingkungan hidup" in text or "dlh" in text: return "DLH (Lingkungan Hidup)"
    if "kependudukan" in text or "capil" in text: return "Disdukcapil"
    if "sosial" in text or "dinsos" in text: return "Dinas Sosial"
    if "kesehatan" in text or "dinkes" in text: return "Dinas Kesehatan"
    if "polisi pamong" in text or "satpol" in text: return "Satpol PP"
    if "pendidikan" in text or "disdik" in text: return "Dinas Pendidikan"
    if "perhubungan" in text or "dishub" in text: return "Dinas Perhubungan"
    return str(text).title()

def clean_kecamatan(text):
    if pd.isna(text) or str(text).strip() in ["-", "", "nan"]: return "Tidak Diketahui"
    return str(text).title().strip()

# --- FUNGSI MENCARI FILE ---
def get_file_path():
    possible_files = [
        "sp4n-lapor_2021-2024.xlsx - Sheet1.csv",
        "sp4n-lapor_2021-2024.csv",
        "sp4n-lapor_2021-2024.xlsx"
    ]
    return next((f for f in possible_files if os.path.exists(f)), None)

# --- FUNGSI LOAD DATA ---
@st.cache_data
def load_data():
    file_path = get_file_path()
    if not file_path: return pd.DataFrame()

    try:
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path, engine='openpyxl')
        else:
            df = pd.read_csv(file_path)

        col_map = {
            'tanggal_masuk': 'Tanggal Laporan Masuk',
            'kategori': 'Kategori',
            'dinas_tujuan': 'Instansi Terdisposisi',
            'isi_laporan_awal': 'Isi Laporan Awal',
            'isi_laporan_akhir': 'Isi Laporan Akhir', 
            'tracking_id': 'Tracking ID',
            'status_final': 'Status Final',
            'kecamatan_final': 'Kecamatan'
        }
        df.rename(columns=col_map, inplace=True)
        
        required = ['Tanggal Laporan Masuk', 'Kategori', 'Isi Laporan Awal', 'Status Final']
        for c in required:
            if c not in df.columns: df[c] = "-"

        if 'Tracking ID' not in df.columns: 
            df['Tracking ID'] = df.index.astype(str)
        else:
            df['Tracking ID'] = df['Tracking ID'].astype(str).str.replace(r'\.0$', '', regex=True)

        if 'Isi Laporan Akhir' not in df.columns: df['Isi Laporan Akhir'] = "-"
        if 'Kecamatan' not in df.columns: df['Kecamatan'] = "Tidak Diketahui"

        df['Status_Clean'] = df['Status Final'].astype(str).str.title().str.strip()
        df['Status_Clean'] = df['Status_Clean'].replace(['Nan', 'nan', '-', ''], 'Diproses')

        df['Tanggal_Parsed'] = pd.to_datetime(df['Tanggal Laporan Masuk'], errors='coerce')
        df['Tahun'] = df['Tanggal_Parsed'].dt.year
        df['Bulan'] = df['Tanggal_Parsed'].dt.to_period('M').astype(str)
        
        df['Target_Selesai'] = df['Tanggal_Parsed'] + pd.Timedelta(days=SLA_HARI)
        today = pd.Timestamp.now()
        df['Sisa_Hari'] = (df['Target_Selesai'] - today).dt.days
        
        def get_time_status(row):
            if row['Status_Clean'] == 'Selesai': return "✅ Selesai"
            if row['Sisa_Hari'] < 0: return "🔥 TERLAMBAT"
            if row['Sisa_Hari'] <= 2: return "⚠️ Warning"
            return "🟢 Aman"
            
        df['Status_Waktu'] = df.apply(get_time_status, axis=1)

        df['Kategori_Clean'] = df['Kategori'].apply(clean_category_name)
        df['Instansi_Clean'] = df['Instansi Terdisposisi'].apply(clean_agency_name)
        df['Kecamatan_Clean'] = df['Kecamatan'].apply(clean_kecamatan)
        df['Isi_Laporan'] = df['Isi Laporan Awal'].astype(str)

        # 5. SCORING PRIORITY & SENTIMENT
        keywords_critical = {'banjir':30, 'kebakaran':40, 'longsor':40, 'kecelakaan':35, 'meninggal':50, 'korban':40}
        keywords_complaint = {'parah':10, 'lambat':5, 'rusak':10, 'bau':10, 'macet':10, 'sampah':10, 'pungli':20}
        negative_words = ['parah', 'kecewa', 'lambat', 'rusak', 'bau', 'macet', 'pungli', 'bodoh', 'malas', 'susah', 'emosi', 'lama', 'ribet']

        def calculate_priority(row):
            text = str(row['Isi_Laporan']).lower()
            score = 0
            sentiment_score = 1
            
            for w, v in keywords_critical.items(): 
                if w in text: score += v
            for w, v in keywords_complaint.items(): 
                if w in text: score += v
            
            for w in negative_words:
                if w in text: sentiment_score += 0.5
            
            if row['Sisa_Hari'] < 0 and row['Status_Clean'] != 'Selesai':
                score += 50 
                sentiment_score += 1
            
            final = min(score, 100)
            final_sent = min(sentiment_score, 5)
            label = "🔴 CRITICAL" if final >= 50 else "🟡 WARNING" if final >= 20 else "🟢 NORMAL"
            return pd.Series([final, label, final_sent])

        df[['Final_Score', 'Label_Prioritas', 'Sentiment_Score']] = df.apply(calculate_priority, axis=1)
        return df

    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# --- FUNGSI UPDATE STATUS ---
def update_laporan(tracking_id, bukti_text):
    path = get_file_path()
    try:
        if path.endswith('.xlsx'):
            df_orig = pd.read_excel(path, engine='openpyxl')
        else:
            df_orig = pd.read_csv(path)
            
        col_id = next((c for c in df_orig.columns if 'tracking' in c.lower()), 'tracking_id')
        col_stat = next((c for c in df_orig.columns if 'status' in c.lower() and 'final' in c.lower()), 'status_final')
        col_bukti = next((c for c in df_orig.columns if 'akhir' in c.lower()), 'isi_laporan_akhir')
        
        df_orig[col_id] = df_orig[col_id].astype(str).str.replace(r'\.0$', '', regex=True)
        tracking_id = str(tracking_id)
        
        mask = df_orig[col_id] == tracking_id
        if mask.any():
            df_orig.loc[mask, col_stat] = 'Selesai'
            df_orig.loc[mask, col_bukti] = bukti_text
            
            if path.endswith('.xlsx'):
                df_orig.to_excel(path, index=False)
            else:
                df_orig.to_csv(path, index=False)
            return True, "Data berhasil disimpan!"
        else:
            return False, f"ID {tracking_id} tidak ditemukan di file asli."
            
    except Exception as e:
        return False, str(e)

# --- FUNGSI AI INSIGHT GENERATOR ---
def get_gemini_prediction(df, year):
    if model is None:
        return "AI tidak tersedia karena masalah konfigurasi API."
    # 1. DATA PREPARATION
    
    # A. Tren per Bulan
    trend_df = df.groupby('Bulan').size().reset_index(name='Jumlah')
    trend_text = trend_df.to_string(index=False)
    
    # B. Top 5 Masalah
    top_issues = df['Kategori_Clean'].value_counts().head(5).to_dict()
    
    # C. Kecamatan Paling Rawan
    top_loc = df['Kecamatan_Clean'].value_counts().head(3).to_dict()
    
    # D. Contoh Laporan Kritis (Ambil 3 terbaru)
    critical_samples = df[df['Label_Prioritas'] == '🔴 CRITICAL']['Isi_Laporan'].head(3).tolist()

    # 2. PROMPT ENGINEERING
    prompt = f"""
    Bertindaklah sebagai Konsultan Analis Data Pemerintahan untuk SP4N LAPOR.
    
    Data Laporan Tahun {year}:
    
    [DATA TREN BULANAN]
    {trend_text}
    
    [TOP 5 MASALAH]
    {top_issues}
    
    [LOKASI TERBANYAK]
    {top_loc}
    
    [CONTOH LAPORAN KRITIS WARGA]
    {critical_samples}
    
    TUGAS ANALISIS:
    1. **Prediksi Tren**: Berdasarkan pola bulanan di atas, prediksi apakah bulan depan laporan akan NAIK atau TURUN? Jelaskan alasannya singkat.
    2. **Pola Masalah**: Apa korelasi antara masalah teratas dengan lokasi terbanyak? (Misal: Banjir di kecamatan X).
    3. **Rekomendasi Strategis**: Berikan 3 langkah konkret yang harus dilakukan Pemkab bulan depan untuk mencegah lonjakan laporan.
    
    Gunakan bahasa Indonesia yang profesional, tegas, dan berbasis data. Jangan gunakan format markdown tabel, gunakan bullet points.
    """
    
    try:
        # Gunakan model yang sudah divalidasi
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error saat generate: {str(e)}"

# --- MAIN APP ---
df = load_data()

if df.empty:
    st.warning("Data tidak ditemukan.")
    st.stop()

# --- SESSION STATE UNTUK LOGIN ---
if 'is_admin' not in st.session_state:  
    st.session_state['is_admin'] = False

# ================= SIDEBAR =================
LOGO_PATH = "assets/img/pemkab.png"  

with st.sidebar:
    if Path(LOGO_PATH).exists():
        col1, col2, col3 = st.columns([1,5,1])
        with col2:
            st.image(LOGO_PATH, width=200)

    st.markdown("""
    <h2 style='text-align: center; color: #2A9D8F; margin-top:-10px;'>SP4N LAPOR</h2>
    <p style='text-align: center; font-size: 14px; color: gray; margin-bottom: 20px;'>Dashboard Monitoring</p>
    """, unsafe_allow_html=True)

    st.divider()

    years = sorted(df['Tahun'].dropna().astype(int).unique().tolist(), reverse=True)
    st.markdown(
        icon("assets/img/calendar.png", 18) + "<b>Filter Tahun</b>",
        unsafe_allow_html=True
    )
    sel_year = st.selectbox("", ["Semua Tahun"] + years)
    df_view = df if sel_year == "Semua Tahun" else df[df['Tahun'] == sel_year]

# --- TABS UTAMA ---
tab1, tab2, tab3, tab4 = st.tabs([" Dashboard & Reminder", " Admin", " Peta Sebaran", " AI Insight"])

# ================= TAB 1: DASHBOARD =================
with tab1:
    st.markdown(
        icon_title("assets/img/analytics.png", f"Monitoring Laporan ({sel_year})", size=30),
        unsafe_allow_html=True
    )
    st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
        
    overdue = len(df_view[(df_view['Sisa_Hari'] < 0) & (df_view['Status_Clean'] != 'Selesai')])
    selesai = len(df_view[df_view['Status_Clean'] == 'Selesai'])
    persen = (selesai/len(df_view)*100) if len(df_view) > 0 else 0
    noise = ["Tidak Diketahui", "Lainnya"]
    valid_cat = df_view[~df_view['Kategori_Clean'].isin(noise)]
    top_isu = valid_cat['Kategori_Clean'].mode()[0] if not valid_cat.empty else "-"
    
    with c1:
        st.markdown(icon("assets/img/report.png") + "<b>Total Laporan</b>", unsafe_allow_html=True)
        st.metric("", len(df_view))

    with c2:
        st.markdown(icon("assets/img/overdue.png") + "<b>Overdue (Terlambat)</b>", unsafe_allow_html=True)
        st.metric("", overdue, delta_color="inverse")

    with c3:
        st.markdown(icon("assets/img/check.png") + "<b>Tingkat Penyelesaian</b>", unsafe_allow_html=True)
        st.metric("", f"{persen:.1f}%")

    with c4:
        st.markdown(icon("assets/img/issue.png") + "<b>Isu Terbanyak</b>", unsafe_allow_html=True)
        st.metric("", top_isu)
    
    if top_isu != "-":
        with st.expander(f"🧐 Bedah Isu: Apa isi laporan '{top_isu}'?"):
            df_isu = df_view[df_view['Kategori_Clean'] == top_isu]
            for i, row in df_isu.head(3).iterrows():
                st.info(f"📅 **{str(row['Tanggal_Parsed'])[:10]}** | \"{row['Isi_Laporan'][:200]}...\"")
    
    st.divider()

    col_g1, col_g2 = st.columns([2, 1])
    with col_g1:
        st.markdown(icon_title("assets/img/trend.png", "Tren Laporan Masuk", size=24), unsafe_allow_html=True)
        if not df_view.empty:
            trend = df_view.groupby('Bulan').size().reset_index(name='Jumlah')
            fig = px.line(trend, x='Bulan', y='Jumlah', markers=True, template='plotly_white', height=350)
            st.plotly_chart(fig, use_container_width=True)
            
    with col_g2:
        st.markdown(icon_title("assets/img/pie-chart.png", "Instansi Top 5", size=24), unsafe_allow_html=True)
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        if not df_view.empty:
            ignore_instansi = ["Umum", "Tidak Diketahui", "Nan", "nan"]
            pie_data = df_view[~df_view['Instansi_Clean'].isin(ignore_instansi)]
            pie_df = pie_data['Instansi_Clean'].value_counts().head(5).reset_index()
            pie_df.columns = ['Instansi', 'Jumlah']
            fig = px.pie(pie_df, values='Jumlah', names='Instansi', hole=0.4, height=350)
            fig.update_traces(textinfo='value') 
            fig.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)
            
    st.divider()
    st.markdown(icon_title("assets/img/kanban.png", "Papan Kontrol: Laporan Dalam Proses", size=26), unsafe_allow_html=True)
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    
    df_kanban_base = df_view[df_view['Status_Clean'] != 'Selesai'].copy()
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown(icon("assets/img/category.png") + "<b>Filter Kategori</b>", unsafe_allow_html=True)
        pilih_kategori = st.multiselect("label1", sorted(df_kanban_base['Kategori_Clean'].dropna().unique()), label_visibility="collapsed")
    with col_f2:
        st.markdown(icon("assets/img/location.png") + "<b>Filter Kecamatan</b>", unsafe_allow_html=True)
        pilih_kecamatan = st.multiselect("label2", sorted(df_kanban_base['Kecamatan_Clean'].dropna().unique()), label_visibility="collapsed")
    
    df_kanban_filtered = df_kanban_base.copy()
    if pilih_kategori: df_kanban_filtered = df_kanban_filtered[df_kanban_filtered['Kategori_Clean'].isin(pilih_kategori)]
    if pilih_kecamatan: df_kanban_filtered = df_kanban_filtered[df_kanban_filtered['Kecamatan_Clean'].isin(pilih_kecamatan)]

    if df_kanban_filtered.empty:
        st.info("Tidak ada laporan yang sesuai dengan filter Anda.")
    else:
        col_crit, col_warn, col_norm = st.columns(3)
        def card(row, color):
            border = "5px solid red" if row['Sisa_Hari'] < 0 else "0px"
            msg_waktu = f"🔥 Telat {abs(row['Sisa_Hari'])} hari" if row['Sisa_Hari'] < 0 else f"⏳ Sisa {row['Sisa_Hari']} hari"
            st.markdown(f"""
            <div style="background-color: {color}; padding: 15px; border-radius: 10px; border-left: {border}; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="display:flex; justify-content:space-between; font-weight:bold; margin-bottom:5px;">
                    <span style="background-color:rgba(255,255,255,0.7); padding:2px 6px; border-radius:4px; font-size:12px; color:#333333;">ID: {row['Tracking ID']}</span>
                    <span style="color:{'red' if row['Sisa_Hari'] < 0 else '#555'}; font-size:12px;">{msg_waktu}</span>
                </div>
                <small style="color:#333333;">📅 {str(row['Tanggal_Parsed'])[:10]}</small><br>
                <div style="font-size:11px; margin-top:2px; margin-bottom:4px; color:#2A9D8F; font-weight:bold;">📍 {row['Kecamatan_Clean']}</div>
                <i style="color:#333333; font-size:13px; line-height:1.4;">"{str(row['Isi_Laporan'])[:65]}..."</i>
            </div>""", unsafe_allow_html=True)
            with st.popover("📖 Baca Selengkapnya"):
                st.write(row['Isi_Laporan'])

        with col_crit:
            st.error(f"🔴 KRITIS ({len(df_kanban_filtered[df_kanban_filtered['Label_Prioritas'] == '🔴 CRITICAL'])})")
            for _, r in df_kanban_filtered[(df_kanban_filtered['Label_Prioritas'] == '🔴 CRITICAL') | (df_kanban_filtered['Sisa_Hari'] < 0)].head(5).iterrows(): card(r, "#ffebeb")
        with col_warn:
            st.warning(f"🟡 WARNING ({len(df_kanban_filtered[df_kanban_filtered['Label_Prioritas'] == '🟡 WARNING'])})")
            for _, r in df_kanban_filtered[(df_kanban_filtered['Label_Prioritas'] == '🟡 WARNING') & (df_kanban_filtered['Sisa_Hari'] >= 0)].head(5).iterrows(): card(r, "#fff8db")
        with col_norm:
            st.success(f"🟢 NORMAL ({len(df_kanban_filtered[df_kanban_filtered['Label_Prioritas'] == '🟢 NORMAL'])})")
            for _, r in df_kanban_filtered[(df_kanban_filtered['Label_Prioritas'] == '🟢 NORMAL') & (df_kanban_filtered['Sisa_Hari'] >= 0)].head(5).iterrows(): card(r, "#e6fffa")
            
    st.divider()
    st.markdown(icon_title("assets/img/bar.png", "Top 10 Kategori Masalah", size=24), unsafe_allow_html=True)
    if not df_view.empty:
        cat_clean = df_view[~df_view['Kategori_Clean'].isin(noise)]
        top_cat_df = cat_clean['Kategori_Clean'].value_counts().head(10).reset_index()
        top_cat_df.columns = ['Kategori', 'Jumlah']
        fig_bar = px.bar(top_cat_df, x='Jumlah', y='Kategori', orientation='h', text='Jumlah', color='Jumlah', color_continuous_scale='Blues')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
        st.plotly_chart(fig_bar, use_container_width=True)

# ================= TAB 2: ACTION CENTER =================
with tab2:
    if not st.session_state['is_admin']:
        st.markdown(icon_title("assets/img/profile.png", "Login Admin", size=26), unsafe_allow_html=True)
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        st.info("Fitur ini khusus untuk Admin yang berwenang mengubah data.")
        with st.form("login_form"):
            email_input = st.text_input("Email")
            pass_input = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if email_input == ADMIN_EMAIL and pass_input == ADMIN_PASS:
                    st.session_state['is_admin'] = True
                    st.success("Login Berhasil!")
                    st.rerun()
                else: st.error("Email atau Password salah.")
    else:
        col_header, col_btn = st.columns([4, 1])
        with col_header:
            st.markdown(icon_title("assets/img/action.png", "Admin Center: Update Status & Bukti", size=26), unsafe_allow_html=True)
        with col_btn:
            if st.button("Logout"):
                st.session_state['is_admin'] = False
                st.rerun()
        
        st.success(f"👋 Halo, Admin ({ADMIN_EMAIL})")
        df_open = df[df['Status_Clean'] != 'Selesai'].sort_values('Sisa_Hari')
        if df_open.empty: st.success("Tidak ada laporan yang perlu diproses.")
        else:
            c_sel, c_input = st.columns([1, 2])
            with c_sel:
                st.markdown("### 1. Pilih Laporan")
                options = df_open['Tracking ID'].unique().tolist()
                pilihan = st.selectbox("Pilih ID Laporan:", options)
                rows = df[df['Tracking ID'] == pilihan]
                if not rows.empty:
                    row_sel = rows.iloc[0]
                    st.warning(f"Status: **{row_sel['Status_Clean']}**")
                    if row_sel['Sisa_Hari'] < 0: st.error(f"⚠️ OVERDUE {abs(row_sel['Sisa_Hari'])} HARI")
                    else: st.success(f"Sisa Waktu: {row_sel['Sisa_Hari']} Hari")
                    st.caption("Isi Laporan:")
                    st.text_area("", value=row_sel['Isi_Laporan'], height=150, disabled=True)
                else: st.error("Data ID tidak ditemukan."); st.stop()
            with c_input:
                st.markdown("### 2. Input Penyelesaian")
                with st.form("form_update"):
                    st.write(f"Menindaklanjuti Laporan ID: **{pilihan}**")
                    bukti_input = st.text_area("📝 Bukti Penyelesaian:", placeholder="Jelaskan tindakan yang diambil...")
                    konfirmasi = st.checkbox("Saya menyatakan laporan ini selesai ditangani.")
                    if st.form_submit_button("💾 Simpan & Tandai Selesai", type="primary"):
                        if not bukti_input: st.error("Harap isi bukti penyelesaian!")
                        elif not konfirmasi: st.error("Harap centang konfirmasi!")
                        else:
                            with st.spinner("Menyimpan ke database..."):
                                sukses, pesan = update_laporan(pilihan, bukti_input)
                                if sukses:
                                    st.balloons()
                                    st.success("✅ KERJA BAGUS! " + pesan)
                                    time.sleep(2)
                                    st.cache_data.clear()
                                    st.rerun()
                                else: st.error(pesan)

# ================= TAB 3: PETA =================
with tab3:
    st.markdown(icon_title("assets/img/map.png", "Peta Sebaran Laporan per Kecamatan", size=26), unsafe_allow_html=True)
    st.caption("Visualisasi sebaran aduan masyarakat berdasarkan wilayah kecamatan.")
    gis_csv = "data_gis_kecamatan_improved.csv"
    if os.path.exists(gis_csv):
        df_gis = pd.read_csv(gis_csv)
        # --- PERBAIKAN LOGIKA PETA: Filter 'Tidak Diketahui' agar peta tetap muncul ---
        df_gis = df_gis[~df_gis['kecamatan'].astype(str).str.contains("Tidak Diketahui", case=False, na=False)]
        
        col_map, col_table = st.columns([2, 1])
        with col_map:
            try:
                import folium
                valid = df_gis.dropna(subset=['lat', 'lon'])
                if not valid.empty:
                    m = folium.Map(location=[valid['lat'].mean(), valid['lon'].mean()], zoom_start=10, tiles='CartoDB positron')
                    for _, r in valid.iterrows():
                        folium.CircleMarker([r['lat'], r['lon']], radius=5 + (r['count']/valid['count'].max()*20), color='#2a9d8f', fill=True, popup=f"<b>{r['kecamatan']}</b><br>Jumlah: {r['count']}", max_width=200).add_to(m)
                    components.html(m.get_root().render(), height=500)
            except Exception as e: st.error(f"Gagal memuat peta: {e}")
        with col_table:
            st.subheader("Data Kecamatan")
            st.dataframe(df_gis[['kecamatan', 'count']].sort_values('count', ascending=False).head(15), use_container_width=True, hide_index=True)
    else: st.warning("Data GIS tidak ditemukan.")
    st.divider()
    st.markdown(icon("assets/img/folder.png") + "<b>Data Lengkap</b>", unsafe_allow_html=True)
    with st.expander(""): st.dataframe(df_view)

# ================= TAB 4: AI INSIGHT (FINAL FIX SESSION STATE) =================
with tab4:
    st.markdown(icon_title("assets/img/ai.png", "AI Strategic Intelligence", 28), unsafe_allow_html=True)
    st.caption("Analisis prediktif menggunakan Generative AI membaca pola historis laporan warga.")
    section(20)
    
    col_ai1, col_ai2 = st.columns([1.8, 1.2])
    
    # 1. INISIALISASI SESSION STATE UNTUK HASIL AI
    if 'ai_insight_result' not in st.session_state:
        st.session_state['ai_insight_result'] = None

    # --- BAGIAN KIRI: GEMINI ANALYSIS ---
    with col_ai1:
        st.subheader("Prediksi & Rekomendasi AI")
        
        # Tombol untuk generate
        if st.button("Jalankan Analisis AI", type="primary"):
            with st.spinner("Gemini sedang membaca data laporan & menghitung prediksi..."):
                # Panggil fungsi Gemini yang baru
                result = get_gemini_prediction(df_view, sel_year)
                # SIMPAN HASIL KE SESSION STATE AGAR TIDAK HILANG SAAT RERUN
                st.session_state['ai_insight_result'] = result
        
        # TAMPILKAN HASIL DARI SESSION STATE (JIKA ADA)
        if st.session_state['ai_insight_result']:
            st.markdown(f"""
            <div style="background-color:#f0f2f6; padding:20px; border-radius:10px; border-left:5px solid #2A9D8F; color:#333;">
                {st.session_state['ai_insight_result']}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Tekan tombol di atas untuk meminta AI menganalisis data terbaru.")

    # --- BAGIAN KANAN: STATISTIK PENDUKUNG ---
    with col_ai2:
        st.markdown(icon("assets/img/gauge.png") + "<b>Sentimen Warga (Realtime)</b>", unsafe_allow_html=True)
        
        # Gauge Chart
        avg_sentiment = df_view['Sentiment_Score'].mean()
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", value = avg_sentiment, title = {'text': "Skala Ketidakpuasan"},
            gauge = {
                'axis': {'range': [1, 5]}, 'bar': {'color': "#EF4444"},
                'steps': [
                    {'range': [1, 2.0], 'color': "#D1FAE5"},
                    {'range': [2.0, 3.5], 'color': "#FEF3C7"},
                    {'range': [3.5, 5], 'color': "#FEE2E2"}],
                'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': avg_sentiment}
            }
        ))
        fig_gauge.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_gauge, use_container_width=True)
        
        # Keterangan Gauge
        st.markdown("""
        <div style="background-color: #f8f9fa; padding: 12px; border-radius: 8px; border: 1px solid #ddd; font-size: 13px; line-height: 1.5; color:#333333;">
            <b>📋 Keterangan Skor:</b><br>
            <span style="color: #16A34A;">● 1.0 - 1.5 :</span> <b>Sangat Puas</b><br>
            <span style="color: #4ADE80;">● 1.6 - 2.5 :</span> <b>Puas</b><br>
            <span style="color: #FACC15;">● 2.6 - 3.5 :</span> <b>Netral</b><br>
            <span style="color: #FB923C;">● 3.6 - 4.5 :</span> <b>Tidak Puas</b><br>
            <span style="color: #EF4444;">● 4.6 - 5.0 :</span> <b>Sangat Tidak Puas</b>
        </div>""", unsafe_allow_html=True)
        
        st.divider()
        
        # Tampilkan Raw Data kecil untuk verifikasi
        st.markdown("<b>Data Masukan ke AI:</b>", unsafe_allow_html=True)
        st.dataframe(df_view[['Tanggal_Parsed', 'Kategori_Clean', 'Kecamatan_Clean']].head(5), hide_index=True)