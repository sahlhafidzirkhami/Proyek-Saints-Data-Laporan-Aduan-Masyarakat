import streamlit as st
import pandas as pd
import plotly.express as px
import os
import streamlit.components.v1 as components
from pathlib import Path
from datetime import datetime

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Public Insight Engine", layout="wide")

# --- FUNGSI PEMBERSIHAN ---
def clean_category_name(text):
    if pd.isna(text) or str(text).strip() in ["-", "", "nan"]: 
        return "Tidak Diketahui"
    text = str(text).strip()
    for prefix in ["Lainnya terkait ", "Permintaan Informasi ", "Pengaduan ", "Aspirasi "]:
        text = text.replace(prefix, "")
    return text

def clean_agency_name(text):
    if pd.isna(text): return "Umum"
    text = str(text)
    text_lower = text.lower()
    if "pekerjaan umum" in text_lower or "pupr" in text_lower: return "Dinas PUTR"
    if "lingkungan hidup" in text_lower or "dlh" in text_lower: return "DLH (Lingkungan Hidup)"
    if "kependudukan" in text_lower or "capil" in text_lower: return "Disdukcapil"
    if "sosial" in text_lower or "dinsos" in text_lower: return "Dinas Sosial"
    if "kesehatan" in text_lower or "dinkes" in text_lower: return "Dinas Kesehatan"
    if "polisi pamong" in text_lower or "satpol" in text_lower: return "Satpol PP"
    if "pendidikan" in text_lower or "disdik" in text_lower: return "Dinas Pendidikan"
    if "perhubungan" in text_lower or "dishub" in text_lower: return "Dinas Perhubungan"
    return text

# --- FUNGSI LOAD DATA ---
@st.cache_data
def load_data():
    # Auto-detect file
    possible_files = [
        "sp4n-lapor_2021-2024.xlsx", 
        "sp4n-lapor_2021-2024.csv",
        "sp4n-lapor_2021-2024.xlsx - Sheet1.csv"
    ]
    file_path = next((f for f in possible_files if os.path.exists(f)), None)

    if not file_path:
        st.error("❌ File data tidak ditemukan!")
        return pd.DataFrame()

    try:
        # Load File
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path, engine='openpyxl')
        else:
            df = pd.read_csv(file_path)

        # 1. NORMALISASI NAMA KOLOM
        col_map = {
            'tanggal_masuk': 'Tanggal Laporan Masuk',
            'kategori': 'Kategori',
            'dinas_tujuan': 'Instansi Terdisposisi',
            'isi_laporan_awal': 'Isi Laporan Awal',
            'tracking_id': 'Tracking ID',
            'status_final': 'Status Final' # Tambahan mapping status
        }
        df.rename(columns=col_map, inplace=True)
        
        # Validasi Kolom Utama
        if 'Tanggal Laporan Masuk' not in df.columns: 
            st.error("Kolom Tanggal tidak ditemukan.")
            return pd.DataFrame()

        # Fallback kolom jika tidak ada
        if 'Kategori' not in df.columns: df['Kategori'] = "Tidak Diketahui"
        if 'Instansi Terdisposisi' not in df.columns: df['Instansi Terdisposisi'] = "Umum"
        if 'Isi Laporan Awal' not in df.columns: df['Isi Laporan Awal'] = "-"
        if 'Tracking ID' not in df.columns: df['Tracking ID'] = "-"
        
        # Cek Kolom Status (Penting untuk filter Kanban)
        col_stat = 'Status Final' if 'Status Final' in df.columns else 'status'
        if col_stat in df.columns:
            # Ubah jadi Title Case ("diproses" -> "Diproses", "SELESAI" -> "Selesai") agar rapi
            df['Status_Clean'] = df[col_stat].astype(str).str.title().str.strip()
        else:
            df['Status_Clean'] = "Diproses" # Default jika tidak ada kolom status

        # 2. PROSES DATA
        df['Tanggal_Parsed'] = pd.to_datetime(df['Tanggal Laporan Masuk'], errors='coerce')
        df['Tahun'] = df['Tanggal_Parsed'].dt.year
        df['Bulan'] = df['Tanggal_Parsed'].dt.to_period('M').astype(str)

        df['Kategori_Clean'] = df['Kategori'].apply(clean_category_name)
        df['Instansi_Clean'] = df['Instansi Terdisposisi'].apply(clean_agency_name)
        df['Isi_Laporan'] = df['Isi Laporan Awal'].astype(str)

        # 3. ALGORITMA PRIORITAS
        keywords_critical = {'banjir':30, 'kebakaran':40, 'longsor':40, 'kecelakaan':35, 'meninggal':50, 'korban':40, 'darurat':30, 'tewas':50}
        keywords_complaint = {'parah':10, 'kecewa':10, 'lambat':5, 'rusak':10, 'bau':10, 'macet':10, 'sampah':10, 'pungli':20}

        def calculate_priority(row):
            text = str(row['Isi_Laporan']).lower()
            score = 0
            for w, v in keywords_critical.items():
                if w in text: score += v
            for w, v in keywords_complaint.items():
                if w in text: score += v
            
            if pd.notna(row['Tanggal_Parsed']):
                days = (pd.to_datetime('today') - row['Tanggal_Parsed']).days
                score += (days * 0.1)
            
            final = min(score, 100)
            label = "🔴 CRITICAL" if final >= 50 else "🟡 WARNING" if final >= 20 else "🟢 NORMAL"
            return pd.Series([final, label])

        df[['Final_Score', 'Label_Prioritas']] = df.apply(calculate_priority, axis=1)

        return df

    except Exception as e:
        st.error(f"Error membaca file: {e}")
        return pd.DataFrame()

# --- MAIN APP ---
df = load_data()

if not df.empty:
    # Sidebar
    st.sidebar.header("🔍 Filter Dashboard")
    years = sorted(df['Tahun'].dropna().astype(int).unique().tolist(), reverse=True)
    sel_year = st.sidebar.selectbox("Pilih Tahun:", ["Semua Tahun"] + years)
    
    df_view = df if sel_year == "Semua Tahun" else df[df['Tahun'] == sel_year]
    title_year = "2021-2024" if sel_year == "Semua Tahun" else str(sel_year)

    st.title(f"📊 Dashboard Analisis: {title_year}")
    
    # KPI LOGIC (Exclude "Tidak Diketahui")
    noise_list = ["Tidak Diketahui", "Lainnya", "Permintaan Informasi", "Topik Lainnya", ""]
    
    kategori_valid = df_view[~df_view['Kategori_Clean'].isin(noise_list)]
    top_cat = kategori_valid['Kategori_Clean'].mode()[0] if not kategori_valid.empty else "Belum Ada Data Valid"

    instansi_valid = df_view[~df_view['Instansi_Clean'].isin(["Umum", "Tidak Diketahui"])]
    top_inst = instansi_valid['Instansi_Clean'].mode()[0] if not instansi_valid.empty else "-"

    # KPI Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Laporan Masuk", f"{len(df_view):,}")
    c2.metric("Isu Utama (Real)", top_cat)
    c3.metric("Instansi Tersibuk", top_inst)

    # BEDAH ISU UTAMA
    if top_cat != "Belum Ada Data Valid":
        with st.expander(f"🧐 Bedah Isu: Apa sebenarnya isi laporan '{top_cat}'?"):
            df_isu = df_view[df_view['Kategori_Clean'] == top_cat]
            st.markdown(f"**Sampel 3 Laporan Terbaru tentang {top_cat}:**")
            for i, row in df_isu.head(3).iterrows():
                st.info(f"📅 **{str(row['Tanggal_Parsed'])[:10]}** | \"{row['Isi_Laporan'][:200]}...\"")

    st.divider()

    # Grafik Tren & Pie
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Tren Laporan")
        if not df_view.empty:
            trend = df_view.groupby('Bulan').size().reset_index(name='Jumlah')
            fig = px.line(trend, x='Bulan', y='Jumlah', markers=True, template='plotly_white', height=350)
            st.plotly_chart(fig, use_container_width=True)
            
    with c2:
        st.subheader("Instansi Top 5")
        if not df_view.empty:
            pie_data = df_view[~df_view['Instansi_Clean'].isin(["Umum", "Tidak Diketahui"])]
            pie_df = pie_data['Instansi_Clean'].value_counts().head(5).reset_index()
            pie_df.columns = ['Instansi', 'Jumlah']
            fig = px.pie(pie_df, values='Jumlah', names='Instansi', hole=0.4, height=350)
            fig.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)

    # --- KANBAN BOARD SECTION (FILTER: HANYA STATUS "DIPROSES") ---
    st.divider()
    
    # 1. Filter Data Khusus Kanban (Hanya Status 'Diproses')
    df_kanban = df_view[df_view['Status_Clean'] == 'Diproses']
    
    st.subheader(f"🎯 Prioritas Penanganan (Sedang Diproses: {len(df_kanban)})")
    st.caption("Menampilkan laporan yang **belum selesai** (Status: Diproses) berdasarkan tingkat urgensi.")
    
    if df_kanban.empty:
        st.success("🎉 Tidak ada laporan dengan status 'Diproses'. Semua pekerjaan selesai!")
    else:
        cols = st.columns(3)
        labels = [("🔴 CRITICAL", "#ffebeb", "#ff4b4b"), ("🟡 WARNING", "#fff8db", "#ffc107"), ("🟢 NORMAL", "#e6fffa", "#00cc96")]
        
        for col, (label, bg, border) in zip(cols, labels):
            with col:
                # Ambil data dari df_kanban (yang sudah difilter statusnya)
                items = df_kanban[df_kanban['Label_Prioritas'] == label].sort_values('Final_Score', ascending=False).head(5)
                
                st.markdown(f"**{label} ({len(df_kanban[df_kanban['Label_Prioritas'] == label])})**")
                
                if items.empty:
                    st.write("-")
                
                for _, row in items.iterrows():
                    # Kartu
                    st.markdown(f"""
                    <div style="background-color:{bg}; padding:10px; border:1px solid {border}; border-radius:5px; margin-bottom:5px; color:black;">
                        <div style="display:flex; justify-content:space-between;">
                            <b>Skor: {int(row['Final_Score'])}</b>
                            <span style="font-size:10px; background:white; padding:2px 5px; border-radius:3px;">{row['Status_Clean']}</span>
                        </div>
                        <small>{str(row['Tanggal_Parsed'])[:10]}</small><br>
                        <i style="font-size:12px">"{str(row['Isi_Laporan'])[:80]}..."</i>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.popover("📖 Baca", use_container_width=True):
                        st.markdown(f"**ID:** {row['Tracking ID']}")
                        st.markdown(f"**Status:** {row['Status_Clean']}")
                        st.info(row['Isi_Laporan'])

    # Grafik Kategori Horizontal
    st.divider()
    st.subheader("Top 10 Kategori Masalah (Valid)")
    cat_clean = df_view[~df_view['Kategori_Clean'].isin(noise_list)]
    if not cat_clean.empty:
        top_cat_df = cat_clean['Kategori_Clean'].value_counts().head(10).reset_index()
        top_cat_df.columns = ['Kategori', 'Jumlah']
        fig_bar = px.bar(top_cat_df, x='Jumlah', y='Kategori', orientation='h', text='Jumlah', color='Jumlah')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
        st.plotly_chart(fig_bar, use_container_width=True)

    # Tabel Data
    with st.expander("📂 Lihat Data Tabel Lengkap"):
        # Tampilkan kolom status juga agar jelas
        st.dataframe(df_view[['Tanggal Laporan Masuk', 'Status_Clean', 'Kategori_Clean', 'Instansi_Clean', 'Isi_Laporan', 'Final_Score', 'Label_Prioritas']])
        
    # GIS
    if st.sidebar.checkbox("Tampilkan Peta"):
        gis_file = "data_gis_kecamatan_improved.csv"
        if os.path.exists(gis_file):
            try:
                import folium
                gis_df = pd.read_csv(gis_file)
                valid = gis_df.dropna(subset=['lat', 'lon'])
                if not valid.empty:
                    m = folium.Map([valid['lat'].mean(), valid['lon'].mean()], zoom_start=10, tiles='CartoDB positron')
                    for _, r in valid.iterrows():
                        popup_txt = f"{r['kecamatan']}: {r['count']} Laporan"
                        folium.CircleMarker(
                            [r['lat'], r['lon']], 
                            radius=5 + (r['count']/valid['count'].max()*20), 
                            color='#2a9d8f', fill=True, 
                            popup=popup_txt
                        ).add_to(m)
                    components.html(m.get_root().render(), height=500)
            except: st.error("Install folium: pip install folium")
        else:
            st.warning("File peta tidak ditemukan. Jalankan script GIS dulu.")