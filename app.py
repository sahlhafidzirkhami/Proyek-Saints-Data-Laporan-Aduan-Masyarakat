import streamlit as st
import pandas as pd
import plotly.express as px
import re

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Analisis Laporan Publik", layout="wide")

# --- FUNGSI PEMBERSIHAN NAMA (Agar Rapi di Grafik) ---
def clean_category_name(text):
    if pd.isna(text): return "Lainnya"
    text = str(text)
    # Hapus kata-kata awalan yang tidak perlu agar grafik tidak penuh
    text = text.replace("Lainnya terkait ", "")
    text = text.replace("Permintaan Informasi ", "")
    text = text.replace("Pengaduan ", "")
    return text

def clean_agency_name(text):
    if pd.isna(text): return "Umum"
    text = str(text)
    
    # Mapping Manual (Jika ada ID/Nama Panjang diubah jadi Singkatan)
    # Ini berjaga-jaga jika data masih berupa ID atau nama sangat panjang
    text_lower = text.lower()
    
    if "pekerjaan umum" in text_lower or "pupr" in text_lower or "14637" in text: 
        return "Dinas PUTR"
    if "lingkungan hidup" in text_lower or "dlh" in text_lower or "14633" in text: 
        return "DLH (Lingkungan Hidup)"
    if "kependudukan" in text_lower or "pencatatan sipil" in text_lower or "14638" in text: 
        return "Disdukcapil"
    if "sosial" in text_lower or "dinsos" in text_lower or "14647" in text: 
        return "Dinas Sosial"
    if "kesehatan" in text_lower or "dinkes" in text_lower or "14639" in text: 
        return "Dinas Kesehatan"
    if "polisi pamong" in text_lower or "satpol" in text_lower or "14635" in text: 
        return "Satpol PP"
    if "pendidikan" in text_lower or "disdik" in text_lower or "16098" in text: 
        return "Dinas Pendidikan"
    if "perhubungan" in text_lower or "dishub" in text_lower or "14643" in text: 
        return "Dinas Perhubungan"
    if "kecamatan" in text_lower:
        return text # Biarkan nama kecamatan apa adanya
        
    return text # Kembalikan nama asli jika tidak ada di daftar

# --- FUNGSI LOAD DATA ---
@st.cache_data
def load_data():
    file_path = "Laporan Ringkas Lapor.xlsx" 
    
    try:
        # BACA EXCEL
        df = pd.read_excel(file_path, skiprows=10, engine='openpyxl')

        # --- VALIDASI HEADER & KOLOM ---
        if 'Tanggal Laporan Masuk' not in df.columns:
            st.warning("Header tidak pas di baris 10. Mencoba auto-detect...")
            df_raw = pd.read_excel(file_path, header=None, engine='openpyxl')
            idx = df_raw[df_raw.apply(lambda x: x.astype(str).str.contains('Tanggal Laporan Masuk').any(), axis=1)].index
            
            if not idx.empty:
                df = pd.read_excel(file_path, skiprows=idx[0]+1, engine='openpyxl')
                df.columns = df_raw.iloc[idx[0]]
            else:
                st.error("Gagal membaca kolom. Pastikan format Excel benar.")
                return pd.DataFrame()

        # --- BERSIHKAN TANGGAL ---
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

        # --- LOGIKA BARU: MEMILIH KOLOM NAMA (BUKAN ID) ---
        
        # 1. Cari kolom Kategori
        col_cat_candidates = [c for c in df.columns if 'Kategori' in str(c) and 'ID' not in str(c)]
        col_cat = col_cat_candidates[0] if col_cat_candidates else df.columns[4]

        # 2. Cari kolom Instansi (HINDARI KOLOM YANG ADA KATA 'ID')
        col_inst_candidates = [c for c in df.columns if 'Instansi' in str(c) and 'Terdisposisi' in str(c)]
        
        # Filter: Ambil yang TIDAK ada kata "ID" di nama kolomnya
        col_inst_final = [c for c in col_inst_candidates if 'ID' not in str(c).upper()]
        
        if col_inst_final:
            col_inst = col_inst_final[0] # Ambil yang bukan ID
        elif col_inst_candidates:
            col_inst = col_inst_candidates[0] # Terpaksa ambil yang ada (nanti dibersihkan di clean_agency_name)
        else:
            col_inst = df.columns[13] # Default tebakan posisi

        # 3. Cari Isi Laporan
        col_isi = [c for c in df.columns if 'Isi Laporan' in str(c)][0]

        # Terapkan Pembersihan
        df['Kategori_Clean'] = df[col_cat].apply(clean_category_name)
        df['Instansi_Clean'] = df[col_inst].apply(clean_agency_name) # Ini akan mengubah ID/Nama Panjang jadi Nama Pendek
        df['Isi_Laporan'] = df[col_isi]

        return df
    
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# --- MAIN APP ---
df = load_data()

if not df.empty:
    # Sidebar
    st.sidebar.title("Filter Data")
    available_years = ["Semua"] + sorted(df['Tahun'].dropna().astype(int).unique().tolist(), reverse=True)
    pilih_tahun = st.sidebar.selectbox("Pilih Tahun:", available_years)

    if pilih_tahun != "Semua":
        df_view = df[df['Tahun'] == pilih_tahun]
    else:
        df_view = df

    # --- JUDUL ---
    st.title("📊 Dashboard Analisis Pengaduan Publik")
    st.caption("Monitoring Kinerja Instansi & Tren Laporan Masyarakat")
    
    # --- KPI METRICS ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Laporan", len(df_view))
    
    # Mengambil modus (data terbanyak)
    top_kat = df_view['Kategori_Clean'].mode()[0] if not df_view.empty else "-"
    top_ins = df_view['Instansi_Clean'].mode()[0] if not df_view.empty else "-"
    
    col2.metric("Keluhan Terbanyak", top_kat)
    col3.metric("Instansi Tersibuk", top_ins) # Sekarang akan muncul Nama, bukan Angka
    
    st.divider()

    # --- GRAFIK 1: TREN WAKTU ---
    st.subheader("📈 Tren Laporan Masuk")
    if not df_view.empty:
        trend = df_view.groupby('Bulan').size().reset_index(name='Jumlah')
        fig_trend = px.line(trend, x='Bulan', y='Jumlah', markers=True, template="plotly_white")
        st.plotly_chart(fig_trend, use_container_width=True)

    # --- GRAFIK 2 & 3 (BAR & PIE) ---
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("🚧 Top 10 Kategori Masalah")
        top_cat = df_view['Kategori_Clean'].value_counts().head(10).reset_index()
        top_cat.columns = ['Kategori', 'Jumlah']
        # Pakai Horizontal Bar agar tulisan terbaca
        fig_cat = px.bar(top_cat, x='Jumlah', y='Kategori', orientation='h', color='Jumlah', text='Jumlah')
        fig_cat.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_cat, use_container_width=True)
        
    with c2:
        st.subheader("🏢 Top 5 Instansi Tujuan")
        top_inst = df_view['Instansi_Clean'].value_counts().head(5).reset_index()
        top_inst.columns = ['Instansi', 'Jumlah']
        fig_inst = px.pie(top_inst, values='Jumlah', names='Instansi', hole=0.4)
        st.plotly_chart(fig_inst, use_container_width=True)

    # --- TABEL DATA ---
    with st.expander("📂 Lihat Data Detail"):
        st.dataframe(df_view[['Tanggal Laporan Masuk', 'Kategori_Clean', 'Instansi_Clean', 'Isi_Laporan']])