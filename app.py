import streamlit as st
import pandas as pd
import plotly.express as px
import re
from pathlib import Path
import streamlit.components.v1 as components

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Public Insight Engine", layout="wide")

# --- FUNGSI PEMBERSIHAN NAMA ---
def clean_category_name(text):
    if pd.isna(text): return "Lainnya"
    text = str(text)
    # Hapus awalan yang mengganggu
    for prefix in ["Lainnya terkait ", "Permintaan Informasi ", "Pengaduan ", "Aspirasi "]:
        text = text.replace(prefix, "")
    return text

def clean_agency_name(text):
    if pd.isna(text): return "Umum"
    text = str(text)
    text_lower = text.lower()
    
    # Mapping Nama Dinas agar Pendek & Rapi
    if "pekerjaan umum" in text_lower or "pupr" in text_lower or "14637" in text: return "Dinas PUTR"
    if "lingkungan hidup" in text_lower or "dlh" in text_lower or "14633" in text: return "DLH (Lingkungan Hidup)"
    if "kependudukan" in text_lower or "capil" in text_lower or "14638" in text: return "Disdukcapil"
    if "sosial" in text_lower or "dinsos" in text_lower or "14647" in text: return "Dinas Sosial"
    if "kesehatan" in text_lower or "dinkes" in text_lower or "14639" in text: return "Dinas Kesehatan"
    if "polisi pamong" in text_lower or "satpol" in text_lower: return "Satpol PP"
    if "pendidikan" in text_lower or "disdik" in text_lower: return "Dinas Pendidikan"
    if "perhubungan" in text_lower or "dishub" in text_lower: return "Dinas Perhubungan"
    if "kecamatan" in text_lower: return text # Biarkan nama kecamatan
    
    return text

# --- FUNGSI LOAD DATA ---
@st.cache_data
def load_data():
    file_path = "./laporan21-24.xlsx" 
    
    try:
        # Baca Excel dengan engine openpyxl
        # Kita gunakan skiprows=10 sesuai format file Anda
        df = pd.read_excel(file_path, skiprows=10, engine='openpyxl')

        # Validasi Header: Cari lokasi kolom Tanggal jika meleset
        if 'Tanggal Laporan Masuk' not in df.columns:
            df_raw = pd.read_excel(file_path, header=None, engine='openpyxl')
            idx = df_raw[df_raw.apply(lambda x: x.astype(str).str.contains('Tanggal Laporan Masuk').any(), axis=1)].index
            if not idx.empty:
                df = pd.read_excel(file_path, skiprows=idx[0]+1, engine='openpyxl')
                df.columns = df_raw.iloc[idx[0]]
            else:
                st.error("Gagal membaca file. Pastikan format Excel benar.")
                return pd.DataFrame()

        # Parsing Tanggal (Indonesia -> DateTime)
        month_map = {'Jan': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Apr', 'Mei': 'May', 'Jun': 'Jun',
                     'Jul': 'Jul', 'Agt': 'Aug', 'Sep': 'Sep', 'Okt': 'Oct', 'Nov': 'Nov', 'Des': 'Dec'}
        
        def parse_date(d):
            if pd.isna(d): return None
            d = str(d)
            for indo, eng in month_map.items():
                if indo in d: d = d.replace(indo, eng)
            return pd.to_datetime(d, errors='coerce')

        df['Tanggal_Parsed'] = df['Tanggal Laporan Masuk'].apply(parse_date)
        df['Tahun'] = df['Tanggal_Parsed'].dt.year
        df['Bulan'] = df['Tanggal_Parsed'].dt.to_period('M').astype(str)

        # Bersihkan Kolom Kategori & Instansi
        # Logika: Cari kolom yang BUKAN ID
        col_cat = [c for c in df.columns if 'Kategori' in str(c) and 'ID' not in str(c)][0]
        
        # Cari kolom instansi yang BUKAN ID
        inst_candidates = [c for c in df.columns if 'Instansi' in str(c) and 'Terdisposisi' in str(c)]
        col_inst = [c for c in inst_candidates if 'ID' not in str(c).upper()]
        col_inst = col_inst[0] if col_inst else df.columns[12] # Fallback

        col_isi = [c for c in df.columns if 'Isi Laporan' in str(c)][0]

        df['Kategori_Clean'] = df[col_cat].apply(clean_category_name)
        df['Instansi_Clean'] = df[col_inst].apply(clean_agency_name)
        df['Isi_Laporan'] = df[col_isi]

        return df
    
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# --- MAIN APP ---
df = load_data()

if not df.empty:
    # --- SIDEBAR FILTER (BAGIAN PENTING) ---
    st.sidebar.header("🔍 Filter Dashboard")
    
    # 1. Ambil list tahun yang ada di data
    list_tahun = sorted(df['Tahun'].dropna().astype(int).unique().tolist(), reverse=True)
    
    # 2. Buat Pilihan "Semua Tahun" atau Tahun Spesifik
    pilihan_tahun = st.sidebar.selectbox("Pilih Tahun Laporan:", ["Semua Tahun"] + list_tahun)
    
    # 3. Filter Dataframe (df -> df_view)
    if pilihan_tahun == "Semua Tahun":
        df_view = df
        judul_tahun = "2021 - 2024"
    else:
        df_view = df[df['Tahun'] == pilihan_tahun]
        judul_tahun = str(pilihan_tahun)

    # --- KONTEN DASHBOARD ---
    st.title(f"📊 Dashboard Analisis: {judul_tahun}")
    st.markdown("Memantau kinerja pelayanan publik berdasarkan data laporan masuk.")

    # KPI Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Laporan", f"{len(df_view):,}")
    
    top_cat = df_view['Kategori_Clean'].mode()[0] if not df_view.empty else "-"
    c2.metric("Isu Utama", top_cat)
    
    top_inst = df_view['Instansi_Clean'].mode()[0] if not df_view.empty else "-"
    c3.metric("Instansi Tersibuk", top_inst)

    st.divider()

    # Layout Grafik
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader(f"Tren Laporan di Tahun {judul_tahun}")
        if not df_view.empty:
            # Group by Bulan
            trend = df_view.groupby('Bulan').size().reset_index(name='Jumlah')
            fig_trend = px.line(trend, x='Bulan', y='Jumlah', markers=True, 
                                template='plotly_white', height=350)
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("Tidak ada data untuk periode ini.")

    with col_right:
        st.subheader("Top 5 Instansi")
        if not df_view.empty:
            top_inst_df = df_view['Instansi_Clean'].value_counts().head(5).reset_index()
            top_inst_df.columns = ['Instansi', 'Jumlah']
            fig_pie = px.pie(top_inst_df, values='Jumlah', names='Instansi', hole=0.4, height=350)
            fig_pie.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)

    # Grafik Batang Horizontal (Kategori)
    st.subheader("Top 10 Kategori Masalah")
    if not df_view.empty:
        top_cat_df = df_view['Kategori_Clean'].value_counts().head(10).reset_index()
        top_cat_df.columns = ['Kategori', 'Jumlah']
        fig_bar = px.bar(top_cat_df, x='Jumlah', y='Kategori', orientation='h', text='Jumlah', color='Jumlah')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
        st.plotly_chart(fig_bar, use_container_width=True)

    # Tabel Data
    with st.expander(f"📂 Lihat Data Detail Tahun {judul_tahun}"):
        st.dataframe(df_view[['Tanggal Laporan Masuk', 'Kategori_Clean', 'Instansi_Clean', 'Isi_Laporan']])

else:
    st.warning("Data kosong. Silakan cek file Excel Anda.")

# --- GIS / PETA INTERAKTIF ---
try:
    # Sidebar control to show map (loads CSV produced by GIS_improved.py)
    st.sidebar.header("🗺️ Peta")
    show_map = st.sidebar.checkbox("Tampilkan Peta Interaktif (Folium)")

    if show_map:
        
        script_dir = Path(__file__).resolve().parent
        csv_path = script_dir / 'data_gis_kecamatan_improved.csv'

        if not csv_path.exists():
            st.info("File peta agregat tidak ditemukan: run `GIS_improved.py` terlebih dahulu atau upload CSV.")
            uploaded = st.file_uploader("Upload file `data_gis_kecamatan_improved.csv` jika tersedia", type=['csv'])
            if uploaded is None:
                st.stop()
            else:
                df_map = pd.read_csv(uploaded)
        else:
            df_map = pd.read_csv(csv_path)

        if df_map.empty:
            st.warning("Data peta kosong.")
        else:
            # Try to import folium lazily
            try:
                import folium
            except Exception:
                st.error("Paket `folium` tidak terpasang. Pasang dengan: pip install folium")
                st.stop()

            valid = df_map.dropna(subset=['lat', 'lon'])
            if valid.empty:
                st.warning("Tidak ada koordinat valid pada CSV peta.")
            else:
                m = folium.Map(location=[valid['lat'].mean(), valid['lon'].mean()], zoom_start=11, tiles='CartoDB positron')
                for _, r in valid.iterrows():
                    popup = folium.Popup(f"<b>{r.get('kecamatan','')}</b><br/>Laporan: {r.get('count', '')}", max_width=300)
                    folium.CircleMarker(location=(r['lat'], r['lon']), radius=6 + (int(r.get('count',0)) / max(1, valid['count'].max())) * 12,
                                         color='#2a9d8f', fill=True, fill_color='#2a9d8f', fill_opacity=0.7, popup=popup, weight=0.8).add_to(m)

                # Render Folium map to HTML string and embed
                map_html = m.get_root().render()
                components.html(map_html, height=600)

except Exception as e:
    st.error(f"Terjadi error pada bagian peta: {e}")