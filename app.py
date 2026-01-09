import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
from datetime import datetime

# --- 1. SETUP HALAMAN ---
st.set_page_config(
    page_title="Analisis Aduan Masyarakat",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS CUSTOM (TEMA TERANG / DISKOMINFO) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap');

    :root {
        --bg-color: #F4F6F9;
        --card-color: #FFFFFF;
        --text-color: #333333;
        --accent-color: #007BFF;
        --border-color: #E0E0E0;
    }
    
    .stApp { background-color: var(--bg-color); color: var(--text-color); font-family: 'Poppins', sans-serif; }
    
    /* Dashboard Card */
    .dashboard-card {
        background-color: var(--card-color);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border: 1px solid var(--border-color);
    }
    
    /* KPI */
    .kpi-container {
        background-color: var(--card-color);
        border-radius: 10px;
        padding: 20px;
        border-left: 5px solid var(--accent-color);
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .kpi-label { font-size: 14px; color: #666666; margin-bottom: 8px; font-weight: 500; }
    .kpi-val { font-size: 28px; font-weight: 700; color: #000000; }
    .kpi-note { font-size: 12px; color: #28a745; margin-top: 5px; font-weight: 600; }
    
    /* --- KANBAN CARD STYLES (WARNA TEGAS) --- */
    .kanban-card {
        padding: 15px;
        border-radius: 8px 8px 0 0; 
        margin-bottom: 0px; 
        box-shadow: 0 -1px 3px rgba(0,0,0,0.05);
        color: #333; 
    }
    
    /* CRITICAL: Merah Jelas */
    .card-critical { 
        background-color: #ffcccc; /* Latar Merah Muda Pekat */
        border: 1px solid #ff9999;
        border-left: 5px solid #cc0000; /* Garis Kiri Merah Tua */
    }
    
    /* WARNING: Kuning Jelas */
    .card-warning { 
        background-color: #fff3cd; /* Latar Kuning Pekat */
        border: 1px solid #ffeeba;
        border-left: 5px solid #ffc107; /* Garis Kiri Kuning Emas */
    }
    
    /* NORMAL: Hijau Jelas (Opsional, agar konsisten) */
    .card-normal { 
        background-color: #d4edda; /* Latar Hijau Muda */
        border: 1px solid #c3e6cb;
        border-left: 5px solid #28a745; /* Garis Kiri Hijau */
    }

    /* Tombol Baca Selengkapnya - Bagian Bawah */
    div[data-testid="stButton"] button {
        width: 100%;
        border-radius: 0 0 8px 8px; 
        font-size: 12px;
        font-weight: 600;
        margin-top: -8px; 
        border: 1px solid rgba(0,0,0,0.1);
        border-top: none;
        background-color: #ffffff;
        color: #007BFF;
        transition: all 0.2s;
        box-shadow: 0 2px 2px rgba(0,0,0,0.05);
    }
    div[data-testid="stButton"] button:hover {
        background-color: #f0f7ff;
        color: #0056b3;
        border-color: #007BFF;
    }

    h1, h2, h3, h4, h5 { color: #212529 !important; }
    [data-testid="stDataFrame"] { background-color: var(--card-color); }
    
    div[data-testid="stDateInput"] label p, 
    div[data-testid="stMultiSelect"] label p {
        color: #333333 !important; font-size: 14px !important; font-weight: 600 !important;
    }
    
    /* Popup Styles */
    .popup-label { font-size: 12px; color: #888; margin-bottom: 0px; }
    .popup-value { font-size: 14px; font-weight: 600; color: #333; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 3. REFERENSI KOORDINAT ---
DEFAULT_COORD = [-7.0252, 107.5259] 
KECAMATAN_COORDS = {
    'baleendah': [-6.9996, 107.6216], 'margahayu': [-6.9717, 107.5847], 'cileunyi': [-6.9400, 107.7300],
    'soreang': [-7.0252, 107.5259], 'bojongsoang': [-6.9892, 107.6444], 'majalaya': [-7.0349, 107.7533],
    'margaasih': [-6.9480, 107.5400], 'banjaran': [-7.0450, 107.5900], 'rancaekek': [-6.9600, 107.7700],
    'cicalengka': [-6.9875, 107.8401], 'cangkuang': [-7.0700, 107.5500], 'ciparay': [-7.0350, 107.6500],
    'katapang': [-7.0000, 107.5600], 'arjasari': [-7.0800, 107.6300], 'cimenyan': [-6.8787, 107.6646],
    'ciwidey': [-7.0990, 107.4337], 'cilengkrang': [-6.9050, 107.6941], 'paseh': [-7.0313, 107.7905],
    'kutawaringin': [-6.9992, 107.5066], 'solokanjeruk': [-7.0100, 107.7300], 'solokan jeruk': [-7.0100, 107.7300],
    'pameungpeuk': [-7.0175, 107.6042], 'cikancung': [-7.0050, 107.8250], 'dayeuhkolot': [-6.9855, 107.6223],
    'pangalengan': [-7.1783, 107.5645], 'ibun': [-7.1000, 107.7800], 'cimaung': [-7.0600, 107.5500],
    'pasirjambu': [-7.0900, 107.4700], 'pacet': [-7.0800, 107.7300], 'nagreg': [-7.0300, 107.8900],
    'kertasari': [-7.2100, 107.6700], 'rancabali': [-7.1500, 107.3900]
}

# --- 4. FUNGSI CLEANING & LOAD DATA ---
def normalize_text(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    text = re.sub(r'\bkecamatan\b|\bkec\.|\bkota\b|\bkabupaten\b', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

@st.cache_data
def load_data():
    # Otomatis Cari File Lokal (Tanpa Upload)
    possible_files = [
        "sp4n-lapor_2021-2024.xlsx - Sheet1.csv", 
        "sp4n-lapor_2021-2024.csv",
        "sp4n-lapor_2021-2024.xlsx"
    ]
    file_path = None
    for f in possible_files:
        if os.path.exists(f):
            file_path = f
            break
    
    if file_path is None: return pd.DataFrame()

    try:
        if file_path.endswith('.csv'): df = pd.read_csv(file_path)
        else: df = pd.read_excel(file_path)
    except: return pd.DataFrame()

    try:
        col_rename = {
            'tanggal_masuk': 'Tanggal', 'dinas_tujuan': 'Instansi',
            'kecamatan_final': 'Lokasi', 'status': 'Status',
            'kategori': 'Kategori', 'isi_laporan_awal': 'Isi Laporan',
            'tracking_id': 'ID'
        }
        df = df.rename(columns=col_rename)
        
        for col in ['Tanggal', 'Instansi', 'Lokasi', 'Status', 'Kategori', 'Isi Laporan', 'ID']:
            if col not in df.columns: df[col] = '-'

        df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
        df = df.dropna(subset=['Tanggal'])
        df['Bulan'] = df['Tanggal'].dt.to_period('M').astype(str)
        
        for col in ['Instansi', 'Lokasi', 'Status', 'Kategori']:
            df[col] = df[col].astype(str).str.strip().str.title()
            df[col] = df[col].replace({'Nan': '-', 'Nat': '-', '': '-'})

        keywords_critical = {'banjir':30, 'kebakaran':40, 'longsor':40, 'kecelakaan':35, 'meninggal':50, 'korban':40, 'darurat':30, 'tewas':50}
        keywords_complaint = {'parah':10, 'kecewa':10, 'lambat':5, 'rusak':10, 'bau':10, 'macet':10, 'sampah':10, 'pungli':20}

        def calculate_priority(row):
            text = str(row['Isi Laporan']).lower()
            score = 0
            for w, v in keywords_critical.items():
                if w in text: score += v
            for w, v in keywords_complaint.items():
                if w in text: score += v
            if 'Selesai' not in str(row['Status']):
                days = (pd.to_datetime('today') - row['Tanggal']).days
                score += (days * 0.05)
            final = min(score, 100)
            label = "🔴 CRITICAL" if final >= 40 else "🟡 WARNING" if final >= 15 else "🟢 NORMAL"
            return pd.Series([final, label])

        df[['Final_Score', 'Label_Prioritas']] = df.apply(calculate_priority, axis=1)

        def get_coords(row):
            loc_clean = normalize_text(str(row['Lokasi']))
            if loc_clean in KECAMATAN_COORDS: return KECAMATAN_COORDS[loc_clean]
            for k, v in KECAMATAN_COORDS.items():
                if k in loc_clean: return v
            return None, None

        coords = df.apply(get_coords, axis=1)
        df['Lat'] = coords.apply(lambda x: x[0])
        df['Lon'] = coords.apply(lambda x: x[1])

        return df
    except: return pd.DataFrame()

# --- 5. FUNGSI DIALOG (POPUP DETAIL) ---
@st.dialog("📋 Detail Laporan Masyarakat")
def show_detail_dialog(row):
    # Header Info
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown('<p class="popup-label">Nomor Tiket (ID)</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="popup-value">#{row["ID"]}</p>', unsafe_allow_html=True)
    with c2:
        st.markdown('<p class="popup-label" style="text-align:right;">Tanggal Masuk</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="popup-value" style="text-align:right;">{row["Tanggal"].strftime("%d %B %Y")}</p>', unsafe_allow_html=True)
    
    st.divider()
    
    # Detail Info
    c3, c4 = st.columns(2)
    with c3:
        st.markdown('<p class="popup-label">📍 Lokasi Kejadian</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="popup-value">{row["Lokasi"]}</p>', unsafe_allow_html=True)
        st.markdown('<p class="popup-label">🏷️ Kategori Laporan</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="popup-value">{row["Kategori"]}</p>', unsafe_allow_html=True)
    with c4:
        st.markdown('<p class="popup-label">🏢 Instansi Tujuan</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="popup-value">{row["Instansi"]}</p>', unsafe_allow_html=True)
        st.markdown('<p class="popup-label">📌 Status Terakhir</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="popup-value">{row["Status"]}</p>', unsafe_allow_html=True)
    
    st.divider()
    
    # Isi Laporan
    st.markdown('<p class="popup-label">📝 Isi Aduan Lengkap</p>', unsafe_allow_html=True)
    st.info(row['Isi Laporan'])
    
    # Footer Status
    if "CRITICAL" in row['Label_Prioritas']:
        st.error(f"⚠️ **Prioritas: TINGGI ({row['Label_Prioritas']})**")
    elif "WARNING" in row['Label_Prioritas']:
        st.warning(f"⚡ **Prioritas: MENENGAH ({row['Label_Prioritas']})**")
    else:
        st.success(f"✅ **Prioritas: NORMAL ({row['Label_Prioritas']})**")

# --- 6. MAIN APP ---
# Otomatis Load Data
df = load_data()

# HEADER
LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Logo_of_Ministry_of_Communication_and_Information_Technology_of_the_Republic_of_Indonesia.svg/1200px-Logo_of_Ministry_of_Communication_and_Information_Technology_of_the_Republic_of_Indonesia.svg.png"
c_head1, c_head2 = st.columns([0.5, 4.5])
with c_head1: st.image(LOGO_URL, width=80)
with c_head2:
    st.markdown("<h2 style='margin:0; padding-top:10px;'>Analisis Aduan Masyarakat</h2>", unsafe_allow_html=True)
    st.markdown("<div style='color:#666;'>Dashboard Monitoring & Evaluasi - Kabupaten Bandung</div>", unsafe_allow_html=True)

st.markdown("---")

if not df.empty:
    # FILTER
    st.markdown('<div class="dashboard-card" style="padding:15px;">', unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1: date_range = st.date_input("📅 Rentang Tanggal", [df['Tanggal'].min(), df['Tanggal'].max()])
    with f2: cat_f = st.multiselect("🏷️ Kategori", sorted(df['Kategori'].unique()))
    with f3: loc_f = st.multiselect("📍 Lokasi", sorted(df['Lokasi'].unique()))
    with f4: ins_f = st.multiselect("🏢 Dinas", sorted(df['Instansi'].unique()))
    with f5: stat_f = st.multiselect("📌 Status", sorted(df['Status'].unique()))
    st.markdown('</div>', unsafe_allow_html=True)

    # APPLY FILTER
    df_show = df.copy()
    if len(date_range) == 2:
        df_show = df_show[(df_show['Tanggal'].dt.date >= date_range[0]) & (df_show['Tanggal'].dt.date <= date_range[1])]
    if cat_f: df_show = df_show[df_show['Kategori'].isin(cat_f)]
    if loc_f: df_show = df_show[df_show['Lokasi'].isin(loc_f)]
    if ins_f: df_show = df_show[df_show['Instansi'].isin(ins_f)]
    if stat_f: df_show = df_show[df_show['Status'].isin(stat_f)]

    if df_show.empty:
        st.warning("⚠️ Data tidak ditemukan.")
        st.stop()

    # KPI
    total = len(df_show)
    selesai = len(df_show[df_show['Status'].str.contains('Selesai|Tutup', case=False, na=False)])
    top_cat = df_show['Kategori'].mode()[0] if not df_show.empty else "-"
    top_dinas = df_show['Instansi'].mode()[0] if not df_show.empty else "-"
    
    k1, k2, k3 = st.columns(3)
    with k1: st.markdown(f"""<div class="kpi-container" style="border-left-color: #007BFF;"><div class="kpi-label">Total Aduan Masuk</div><div class="kpi-val">{total}</div></div>""", unsafe_allow_html=True)
    with k2: st.markdown(f"""<div class="kpi-container" style="border-left-color: #28A745;"><div class="kpi-label">Aduan Selesai</div><div class="kpi-val">{selesai}</div><div class="kpi-note">Rate: {((selesai/total)*100):.1f}%</div></div>""", unsafe_allow_html=True)
    with k3: st.markdown(f"""<div class="kpi-container" style="border-left-color: #DC3545;"><div class="kpi-label">Dinas Tersibuk</div><div class="kpi-val" style="font-size:20px;">{top_dinas}</div></div>""", unsafe_allow_html=True)

    with st.expander(f"🧐 Bedah Isu: Baca sampel laporan kategori '{top_cat}'"):
        sample_isu = df_show[df_show['Kategori'] == top_cat].head(3)
        for _, row in sample_isu.iterrows():
            st.info(f"📅 **{row['Tanggal'].date()}** | 📍 {row['Lokasi']}\n\n\"{row['Isi Laporan']}\"")
    st.markdown("---")

    # CHARTS
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    c_chart1, c_chart2 = st.columns([2, 1])
    
    with c_chart1:
        st.markdown("#### 📈 Tren Laporan Masuk")
        trend = df_show.groupby('Bulan').size().reset_index(name='Jumlah')
        fig_trend = px.line(trend, x='Bulan', y='Jumlah', markers=True, template='plotly_white')
        fig_trend.update_traces(line_color='#007BFF')
        fig_trend.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=350)
        st.plotly_chart(fig_trend, use_container_width=True)

    with c_chart2:
        st.markdown("#### 📊 Persentase Aduan per Kecamatan")
        kec_counts = df_show['Lokasi'].value_counts().reset_index()
        kec_counts.columns = ['Kecamatan', 'Jumlah']
        
        top_n = 7
        if len(kec_counts) > top_n:
            top_df = kec_counts.iloc[:top_n].copy()
            others_sum = kec_counts.iloc[top_n:]['Jumlah'].sum()
            others_df = pd.DataFrame([{'Kecamatan': 'Lainnya', 'Jumlah': others_sum}])
            pie_data = pd.concat([top_df, others_df])
        else:
            pie_data = kec_counts
            
        custom_colors = ['#007BFF', '#28A745', '#FFC107', '#DC3545', '#17a2b8', '#6610f2', '#6c757d', '#adb5bd']
        fig_pie = px.pie(pie_data, names='Kecamatan', values='Jumlah', hole=0.4, color_discrete_sequence=custom_colors, template='plotly_white')
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(showlegend=False, margin=dict(l=0,r=0,t=0,b=0), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- KANBAN BOARD (KARTU WARNA TEGAS + TOMBOL 'BACA SELENGKAPNYA') ---
    st.markdown("### 🎯 Prioritas Penanganan (Laporan Belum Selesai)")
    
    df_kanban = df_show[~df_show['Status'].str.contains('Selesai|Tutup', case=False, na=False)]

    if df_kanban.empty:
        st.success("🎉 Tidak ada laporan tertunda.")
    else:
        # Layout 3 Kolom
        kb1, kb2, kb3 = st.columns(3)
        priorities = [
            ("🔴 CRITICAL", "card-critical", kb1), 
            ("🟡 WARNING", "card-warning", kb2), 
            ("🟢 NORMAL", "card-normal", kb3)
        ]

        for label, css_class, col in priorities:
            with col:
                st.markdown(f"**{label}**")
                items = df_kanban[df_kanban['Label_Prioritas'] == label].sort_values('Final_Score', ascending=False).head(5)
                
                if items.empty:
                    st.caption("Tidak ada data.")
                
                for _, row in items.iterrows():
                    # --- CONTAINER KARTU ---
                    with st.container():
                        st.markdown(f"""
                        <div class="kanban-card {css_class}">
                            <div style="font-weight:bold; font-size:12px; margin-bottom:5px;">{row['ID']} <span style="font-weight:normal; opacity:0.7">| {row['Lokasi']}</span></div>
                            <div style="font-size:13px; margin-bottom:8px; color:#333;">"{str(row['Isi Laporan'])[:70]}..."</div>
                            <div style="font-size:11px; opacity:0.7; color:#555;">📅 {row['Tanggal'].date()} • Skor: {int(row['Final_Score'])}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # TOMBOL DI BAWAH KARTU
                        if st.button("Baca Selengkapnya", key=f"btn_{row['ID']}"):
                            show_detail_dialog(row)

    st.divider()

    # TABLES & MAPS
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.markdown("#### 📈 Analisis Kinerja Dinas")
    kinerja_df = df_show.groupby('Instansi').agg(
        Banyak_Aduan=('Instansi', 'count'),
        Aduan_Selesai=('Status', lambda x: x.str.contains('Selesai|Tutup', case=False).sum())
    ).reset_index().sort_values('Banyak_Aduan', ascending=False)
    kinerja_df['Rate'] = (kinerja_df['Aduan_Selesai'] / kinerja_df['Banyak_Aduan'] * 100).round(1).astype(str) + '%'
    st.dataframe(kinerja_df, use_container_width=True, hide_index=True, column_config={"Banyak_Aduan": st.column_config.ProgressColumn("Total Aduan", format="%d", max_value=int(kinerja_df['Banyak_Aduan'].max()))})
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.markdown("#### 🗺️ Peta Sebaran (Heatmap)")
    df_map = df_show.dropna(subset=['Lat', 'Lon'])
    map_agg = df_map.groupby(['Lokasi', 'Lat', 'Lon']).size().reset_index(name='Jumlah_Laporan')
    if not map_agg.empty:
        fig_map = px.scatter_mapbox(map_agg, lat="Lat", lon="Lon", size="Jumlah_Laporan", color="Jumlah_Laporan", color_continuous_scale=["#00ccff", "#ff0000"], size_max=40, zoom=9.5, center={"lat": DEFAULT_COORD[0], "lon": DEFAULT_COORD[1]}, height=500, template='plotly_white')
        fig_map.update_layout(mapbox_style="carto-positron", margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_map, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("📋 Tabel Detail Aduan Masyarakat"):
        cols_to_show = ['Tanggal', 'Kategori', 'Instansi', 'Isi Laporan', 'Final_Score', 'Label_Prioritas']
        st.dataframe(df_show[cols_to_show], use_container_width=True, hide_index=True, column_config={"Tanggal": st.column_config.DatetimeColumn("Tanggal Laporan", format="D MMM YYYY"),"Final_Score": st.column_config.NumberColumn("Skor Prioritas"),"Isi Laporan": st.column_config.TextColumn("Isi Aduan", width="medium"),"Label_Prioritas": "Status Prioritas"})

else:
    st.error("Gagal memuat data. Pastikan file 'sp4n-lapor_2021-2024.csv' tersedia di folder aplikasi.")