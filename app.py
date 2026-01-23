import streamlit as st
import pandas as pd
import plotly.express as px
import os
import time
import streamlit.components.v1 as components
from pathlib import Path
from datetime import datetime, timedelta

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Public Insight Engine", layout="wide")

# --- KONSTANTA ---
SLA_HARI = 5
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASS = "admin123"

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
            'status_final': 'Status Final'
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
        df['Isi_Laporan'] = df['Isi Laporan Awal'].astype(str)

        keywords_critical = {'banjir':30, 'kebakaran':40, 'longsor':40, 'kecelakaan':35, 'meninggal':50, 'korban':40}
        keywords_complaint = {'parah':10, 'lambat':5, 'rusak':10, 'bau':10, 'macet':10, 'sampah':10, 'pungli':20}

        def calculate_priority(row):
            text = str(row['Isi_Laporan']).lower()
            score = 0
            for w, v in keywords_critical.items(): 
                if w in text: score += v
            for w, v in keywords_complaint.items(): 
                if w in text: score += v
            
            if row['Sisa_Hari'] < 0 and row['Status_Clean'] != 'Selesai':
                score += 50 
            
            final = min(score, 100)
            label = "🔴 CRITICAL" if final >= 50 else "🟡 WARNING" if final >= 20 else "🟢 NORMAL"
            return pd.Series([final, label])

        df[['Final_Score', 'Label_Prioritas']] = df.apply(calculate_priority, axis=1)
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

# --- MAIN APP ---
df = load_data()

if df.empty:
    st.warning("Data tidak ditemukan.")
    st.stop()

# --- SESSION STATE UNTUK LOGIN ---
if 'is_admin' not in st.session_state:
    st.session_state['is_admin'] = False

# Sidebar Filter
st.sidebar.title("🎛️ Panel Kontrol")
years = sorted(df['Tahun'].dropna().astype(int).unique().tolist(), reverse=True)
sel_year = st.sidebar.selectbox("Tahun:", ["Semua Tahun"] + years)
df_view = df if sel_year == "Semua Tahun" else df[df['Tahun'] == sel_year]

# --- TABS UTAMA ---
tab1, tab2, tab3 = st.tabs(["📊 Dashboard & Reminder", "⚡ Action Center (Admin)", "🗺️ Peta Sebaran"])

# ================= TAB 1: DASHBOARD =================
with tab1:
    st.title(f"Monitoring Laporan ({sel_year})")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Laporan", len(df_view))
    
    overdue = len(df_view[(df_view['Sisa_Hari'] < 0) & (df_view['Status_Clean'] != 'Selesai')])
    c2.metric("🔥 Overdue (Terlambat)", overdue, delta_color="inverse")
    
    selesai = len(df_view[df_view['Status_Clean'] == 'Selesai'])
    persen = (selesai/len(df_view)*100) if len(df_view) > 0 else 0
    c3.metric("Tingkat Penyelesaian", f"{persen:.1f}%")
    
    noise = ["Tidak Diketahui", "Lainnya"]
    valid_cat = df_view[~df_view['Kategori_Clean'].isin(noise)]
    top_isu = valid_cat['Kategori_Clean'].mode()[0] if not valid_cat.empty else "-"
    c4.metric("Isu Terbanyak", top_isu)
    
    if top_isu != "-":
        with st.expander(f"🧐 Bedah Isu: Apa isi laporan '{top_isu}'?"):
            df_isu = df_view[df_view['Kategori_Clean'] == top_isu]
            for i, row in df_isu.head(3).iterrows():
                st.info(f"📅 **{str(row['Tanggal_Parsed'])[:10]}** | \"{row['Isi_Laporan'][:200]}...\"")
    
    st.divider()

    col_g1, col_g2 = st.columns([2, 1])
    with col_g1:
        st.subheader("Tren Laporan")
        if not df_view.empty:
            trend = df_view.groupby('Bulan').size().reset_index(name='Jumlah')
            fig = px.line(trend, x='Bulan', y='Jumlah', markers=True, template='plotly_white', height=350)
            st.plotly_chart(fig, use_container_width=True)
            
    with col_g2:
        st.subheader("Instansi Top 5")
        if not df_view.empty:
            pie_data = df_view[~df_view['Instansi_Clean'].isin(["Umum", "Tidak Diketahui"])]
            pie_df = pie_data['Instansi_Clean'].value_counts().head(5).reset_index()
            pie_df.columns = ['Instansi', 'Jumlah']
            fig = px.pie(pie_df, values='Jumlah', names='Instansi', hole=0.4, height=350)
            fig.update_layout(showlegend=False, margin=dict(t=0,b=0,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    st.subheader("📋 Papan Kontrol: Laporan Dalam Proses")
    df_kanban = df_view[df_view['Status_Clean'] != 'Selesai'].copy()
    
    if df_kanban.empty:
        st.success("Semua laporan sudah selesai! 🎉")
    else:
        col_crit, col_warn, col_norm = st.columns(3)
        
        def card(row, color):
            border = "5px solid red" if row['Sisa_Hari'] < 0 else f"1px solid {color}"
            msg_waktu = f"🔥 Telat {abs(row['Sisa_Hari'])} hari" if row['Sisa_Hari'] < 0 else f"⏳ Sisa {row['Sisa_Hari']} hari"
            st.markdown(f"""
            <div style="background:{color}; padding:10px; border-radius:5px; border-left:{border}; margin-bottom:10px; color:black;">
                <div style="display:flex; justify-content:space-between; font-weight:bold;">
                    <span>ID: {row['Tracking ID']}</span>
                    <span style="color:{'red' if row['Sisa_Hari'] < 0 else 'black'}">{msg_waktu}</span>
                </div>
                <small>📅 {str(row['Tanggal_Parsed'])[:10]}</small><br>
                <i>"{str(row['Isi_Laporan'])[:50]}..."</i>
            </div>
            """, unsafe_allow_html=True)
            with st.popover("Detail"):
                st.write(row['Isi_Laporan'])

        with col_crit:
            st.error("🔴 KRITIS / TERLAMBAT")
            items = df_kanban[(df_kanban['Label_Prioritas'] == '🔴 CRITICAL') | (df_kanban['Sisa_Hari'] < 0)]
            for _, r in items.head(5).iterrows(): card(r, "#ffebeb")
            
        with col_warn:
            st.warning("🟡 WARNING")
            items = df_kanban[(df_kanban['Label_Prioritas'] == '🟡 WARNING') & (df_kanban['Sisa_Hari'] >= 0)]
            for _, r in items.head(5).iterrows(): card(r, "#fff8db")
            
        with col_norm:
            st.success("🟢 NORMAL")
            items = df_kanban[(df_kanban['Label_Prioritas'] == '🟢 NORMAL') & (df_kanban['Sisa_Hari'] >= 0)]
            for _, r in items.head(5).iterrows(): card(r, "#e6fffa")
            
    st.divider()
    st.subheader("Top 10 Kategori Masalah (Valid)")
    cat_clean = df_view[~df_view['Kategori_Clean'].isin(noise)]
    if not cat_clean.empty:
        top_cat_df = cat_clean['Kategori_Clean'].value_counts().head(10).reset_index()
        top_cat_df.columns = ['Kategori', 'Jumlah']
        fig_bar = px.bar(top_cat_df, x='Jumlah', y='Kategori', orientation='h', text='Jumlah', color='Jumlah')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
        st.plotly_chart(fig_bar, use_container_width=True)

# ================= TAB 2: ACTION CENTER (DENGAN LOGIN) =================
with tab2:
    # Cek apakah sudah login?
    if not st.session_state['is_admin']:
        # TAMPILAN LOGIN FORM
        st.header("🔒 Login Admin")
        st.info("Fitur ini khusus untuk Admin yang berwenang mengubah data.")
        
        with st.form("login_form"):
            email_input = st.text_input("Email")
            pass_input = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if email_input == ADMIN_EMAIL and pass_input == ADMIN_PASS:
                    st.session_state['is_admin'] = True
                    st.success("Login Berhasil!")
                    st.rerun()
                else:
                    st.error("Email atau Password salah.")
    else:
        # TAMPILAN ACTION CENTER (JIKA SUDAH LOGIN)
        col_header, col_btn = st.columns([4, 1])
        with col_header:
            st.header("⚡ Action Center: Update Status & Bukti")
        with col_btn:
            if st.button("Logout"):
                st.session_state['is_admin'] = False
                st.rerun()
        
        st.success(f"👋 Halo, Admin ({ADMIN_EMAIL})")
        
        # Dropdown pilih ID (Hanya yang belum selesai)
        df_open = df[df['Status_Clean'] != 'Selesai'].sort_values('Sisa_Hari')
        
        if df_open.empty:
            st.success("Tidak ada laporan yang perlu diproses.")
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
                    if row_sel['Sisa_Hari'] < 0:
                        st.error(f"⚠️ OVERDUE {abs(row_sel['Sisa_Hari'])} HARI")
                    else:
                        st.success(f"Sisa Waktu: {row_sel['Sisa_Hari']} Hari")
                    st.caption("Isi Laporan:")
                    st.text_area("", value=row_sel['Isi_Laporan'], height=150, disabled=True)
                else:
                    st.error("Data ID tidak ditemukan.")
                    st.stop()

            with c_input:
                st.markdown("### 2. Input Penyelesaian")
                with st.form("form_update"):
                    st.write(f"Menindaklanjuti Laporan ID: **{pilihan}**")
                    bukti_input = st.text_area("📝 Bukti Penyelesaian (Wajib Diisi):", 
                                               placeholder="Jelaskan tindakan yang diambil...")
                    konfirmasi = st.checkbox("Saya menyatakan laporan ini selesai ditangani.")
                    tombol = st.form_submit_button("💾 Simpan & Tandai Selesai", type="primary")
                    
                    if tombol:
                        if not bukti_input:
                            st.error("Harap isi bukti penyelesaian!")
                        elif not konfirmasi:
                            st.error("Harap centang konfirmasi!")
                        else:
                            with st.spinner("Menyimpan ke database..."):
                                sukses, pesan = update_laporan(pilihan, bukti_input)
                                if sukses:
                                    st.success(pesan)
                                    time.sleep(1.5)
                                    st.cache_data.clear()
                                    st.rerun()
                                else:
                                    st.error(pesan)

# ================= TAB 3: PETA =================
with tab3:
    st.header("🗺️ Peta Sebaran")
    gis_csv = "data_gis_kecamatan_improved.csv"
    gis_png = "peta_sebaran_laporan_kecamatan_improved.png"
    
    if os.path.exists(gis_csv):
        df_gis = pd.read_csv(gis_csv)
        col_a, col_b = st.columns([2, 1])
        with col_a:
            if os.path.exists(gis_png):
                st.image(gis_png, caption="Heatmap Sebaran", use_container_width=True)
            else:
                st.info("Peta visual (PNG) tidak tersedia.")
        with col_b:
            st.dataframe(df_gis[['kecamatan', 'count']].head(10), use_container_width=True)
        
        if st.checkbox("Tampilkan Peta Interaktif (Folium)"):
            try:
                import folium
                valid = df_gis.dropna(subset=['lat', 'lon'])
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
        st.warning("Data GIS tidak ditemukan.")

    st.divider()
    with st.expander("📂 Database Lengkap (Tabel)"):
        st.dataframe(df_view)