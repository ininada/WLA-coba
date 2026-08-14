import io
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from fpdf import FPDF

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(page_title="DSS Analisis Beban Kerja Operator Lini", page_icon="📊", layout="wide")

st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>Sistem Pendukung Keputusan Analisis Beban Kerja & Optimasi Tenaga Kerja</h2>", unsafe_allow_html=True)
st.caption("<p style='text-align: center;'>Metode: Time Study & Workload Analysis (WLA) - Multi-Station Production</p>", unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR & CACHING DATASET BESAR
# ==========================================
st.sidebar.header("⚙️ Parameter Operasional")

jam_kerja_shift = st.sidebar.number_input("Jam Kerja Per Shift (Jam)", min_value=1, max_value=12, value=8)
waktu_istirahat = st.sidebar.number_input("Waktu Istirahat (Menit)", min_value=0, max_value=120, value=60)
jam_kerja_efektif = (jam_kerja_shift * 60) - waktu_istirahat
st.sidebar.info(f"⏱️ **Jam Kerja Efektif:** {jam_kerja_efektif} menit/shift")

threshold_underload = st.sidebar.number_input("Batas Maksimal Underload (%)", value=85.0)
threshold_overload = st.sidebar.number_input("Batas Minimal Overload (%)", value=110.0)

st.sidebar.subheader("📂 Sumber Data")
data_source = st.sidebar.radio("Pilih Sumber Data:", ["Gunakan Data Dummy (20 Operator)", "Unggah File CSV/Excel"])

# FITUR CACHING: Menyimpan data di memori agar aplikasi tidak "loading ulang" setiap kali tombol di-klik (Wajib untuk data besar)
@st.cache_data
def load_uploaded_data(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    else:
        return pd.read_excel(file)

@st.cache_data
def get_dummy_data():
    # Menyiapkan data 20 Operator Anonim
    # Didesain secara khusus agar Stasiun Perakitan kekurangan orang (Overload) 
    # dan Stasiun Gudang kelebihan orang (Underload ekstrim)
    return pd.DataFrame({
        "Stasiun": ["Pemotongan"]*4 + ["Penghalusan"]*4 + ["Perakitan"]*6 + ["Pemeriksaan"]*3 + ["Gudang"]*3,
        "Operator": [f"Operator {i}" for i in range(1, 21)],
        "Waktu_Siklus_Menit": [
            3.2, 3.1, 3.3, 3.0, 
            2.5, 2.6, 2.4, 2.5, 
            5.8, 6.0, 5.7, 5.9, 5.8, 5.5, # Waktu sangat tinggi
            1.4, 1.5, 1.3, 
            0.9, 0.8, 1.0 # Waktu sangat rendah
        ],
        "Rating_Factor": [1.05]*20,
        "Allowance_Percent": [15.0]*20,
        "Target_Output_Unit": [150]*20,
    })

# ==========================================
# 3. LOAD DATASET 
# ==========================================
if data_source == "Gunakan Data Dummy (20 Operator)":
    df_input = get_dummy_data()
else:
    uploaded_file = st.sidebar.file_uploader("Unggah File (CSV atau XLSX)", type=["csv", "xlsx"])
    if uploaded_file is not None:
        df_input = load_uploaded_data(uploaded_file)
    else:
        st.warning("Silakan unggah file. Menampilkan data dummy sementara:")
        df_input = get_dummy_data()

# Cek pergantian sumber data untuk reset simulasi
if 'current_source' not in st.session_state or st.session_state.current_source != data_source:
    st.session_state.current_source = data_source
    if 'df_simulasi' in st.session_state:
        del st.session_state['df_simulasi']

# ==========================================
# 4. KALKULASI TIME STUDY & WLA
# ==========================================
df_input["Waktu_Normal_Menit"] = df_input["Waktu_Siklus_Menit"] * df_input["Rating_Factor"]
df_input["Waktu_Baku_Menit"] = df_input["Waktu_Normal_Menit"] * (1 + (df_input["Allowance_Percent"] / 100))
df_input["Total_Waktu_Kerja_Menit"] = df_input["Waktu_Baku_Menit"] * df_input["Target_Output_Unit"]
df_input["Percent_WLA"] = (df_input["Total_Waktu_Kerja_Menit"] / jam_kerja_efektif) * 100

def kategorisasi_wla(val):
    if val < threshold_underload: return "Underload"
    elif val > threshold_overload: return "Overload"
    return "Normal"

df_input["Kategori_WLA"] = df_input["Percent_WLA"].apply(kategorisasi_wla)

# ==========================================
# 5. TAMPILAN DASHBOARD TABS
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "📊 Page 1 & 2: Data dan Visualisasi", 
    "🔄 Page 3: Pindah Tugas (Internal Stasiun)", 
    "⚖️ Page 4: Rekomendasi Mutasi Lintas Stasiun"
])

# ------------------------------------------
# TAB 1: VISUALISASI
# ------------------------------------------
with tab1:
    st.subheader("📊 Visualisasi Beban Kerja Lini")
    color_map = {"Underload": "#FBBF24", "Normal": "#10B981", "Overload": "#EF4444"}

    fig_bar = px.bar(
        df_input, x="Operator", y="Percent_WLA", color="Kategori_WLA", facet_col="Stasiun",
        color_discrete_map=color_map, title="[MICRO] Persentase Beban Kerja (% WLA) per Operator",
    )
    fig_bar.add_hline(y=threshold_overload, line_dash="dash", line_color="red")
    st.plotly_chart(fig_bar, use_container_width=True)

# ------------------------------------------
# TAB 2: REDISTRIBUSI (INTERNAL)
# ------------------------------------------
with tab2:
    st.subheader("🔄 Redistribusi Tugas (Internal Stasiun)")
    st.write("Fitur ini digunakan untuk menyeimbangkan elemen kerja JIKA jumlah operator di stasiun tersebut sudah sesuai (Tidak kurang/lebih).")
    
    if "df_simulasi" not in st.session_state or st.button("Reset Simulasi Tugas"):
        st.session_state.df_simulasi = df_input.copy()
    
    df_sim = st.session_state.df_simulasi
    pilih_stasiun = st.selectbox("1. Pilih Stasiun:", df_sim['Stasiun'].unique())
    df_sim_stasiun = df_sim[df_sim['Stasiun'] == pilih_stasiun]
    
    list_over = df_sim_stasiun[df_sim_stasiun["Kategori_WLA"] == "Overload"]["Operator"].tolist()
    list_under = df_sim_stasiun[df_sim_stasiun["Kategori_WLA"] != "Overload"]["Operator"].tolist()

    if list_over and list_under:
        col_s1, col_s2 = st.columns(2)
        with col_s1: op_sumber = st.selectbox("2. Operator Sumber (Overload):", list_over)
        with col_s2: op_penerima = st.selectbox("3. Operator Penerima (Under/Normal):", list_under)
        
        w_penerima = df_sim.loc[df_sim["Operator"] == op_penerima, "Total_Waktu_Kerja_Menit"].values[0]
        kap_maks = (threshold_overload / 100.0) * jam_kerja_efektif
        sisa = max(0.0, kap_maks - w_penerima)
        
        if sisa > 0:
            menit_transfer = st.slider(f"Geser Waktu (Menit) ke {op_penerima}:", 0.0, float(sisa), 0.0, 1.0)
            if st.button("Terapkan Pindah Tugas"):
                st.session_state.df_simulasi.loc[st.session_state.df_simulasi["Operator"] == op_sumber, "Total_Waktu_Kerja_Menit"] -= menit_transfer
                st.session_state.df_simulasi.loc[st.session_state.df_simulasi["Operator"] == op_penerima, "Total_Waktu_Kerja_Menit"] += menit_transfer
                
                st.session_state.df_simulasi["Percent_WLA"] = (st.session_state.df_simulasi["Total_Waktu_Kerja_Menit"] / jam_kerja_efektif) * 100
                st.session_state.df_simulasi["Kategori_WLA"] = st.session_state.df_simulasi["Percent_WLA"].apply(kategorisasi_wla)
                st.success(f"Berhasil menggeser waktu dari {op_sumber} ke {op_penerima}!")
                st.rerun()

# ------------------------------------------
# TAB 3: MUTASI LINTAS STASIUN (FITUR BARU)
# ------------------------------------------
with tab3:
    st.subheader("⚖️ Analisis & Mutasi Headcount Antar Stasiun")
    st.write("Mendeteksi lini mana yang memiliki kelebihan tenaga kerja dan memindahkannya secara cerdas ke stasiun yang kekurangan kapasitas (*bottleneck*).")

    df_hasil_sim = st.session_state.df_simulasi
    df_kebutuhan = df_hasil_sim.groupby("Stasiun").agg(
        Total_Waktu=('Total_Waktu_Kerja_Menit', 'sum'), 
        Staff_Eksisting=('Operator', 'count')
    ).reset_index()
    
    df_kebutuhan['Staff_Teoritis'] = df_kebutuhan['Total_Waktu'] / jam_kerja_efektif
    df_kebutuhan['Staff_Optimal'] = np.ceil(df_kebutuhan['Staff_Teoritis']).astype(int)
    df_kebutuhan['Selisih (Rekrut/Kurangi)'] = df_kebutuhan['Staff_Optimal'] - df_kebutuhan['Staff_Eksisting']

    st.dataframe(df_kebutuhan, use_container_width=True, hide_index=True)

    st.markdown("### 🔄 Rekomendasi Cross-Training & Mutasi Operator")
    
    surplus_stations = df_kebutuhan[df_kebutuhan['Selisih (Rekrut/Kurangi)'] < 0].to_dict('records')
    deficit_stations = df_kebutuhan[df_kebutuhan['Selisih (Rekrut/Kurangi)'] > 0].to_dict('records')

    if surplus_stations and deficit_stations:
        st.write("Sistem mendeteksi adanya ketimpangan jumlah operator antar stasiun. Berikut adalah rekomendasi mutasi otomatis berdasarkan identifikasi *Workload* terendah di stasiun yang surplus:")
        
        for surp in surplus_stations:
            s_sumber = surp['Stasiun']
            jml_surp = abs(surp['Selisih (Rekrut/Kurangi)'])
            
            # URUTKAN operator berdasarkan % WLA terendah di stasiun yang overstaffed
            kandidat = df_hasil_sim[df_hasil_sim['Stasiun'] == s_sumber].sort_values('Percent_WLA').head(jml_surp)['Operator'].tolist()
            
            for deficit in deficit_stations:
                if deficit['Selisih (Rekrut/Kurangi)'] > 0 and len(kandidat) > 0:
                    s_tujuan = deficit['Stasiun']
                    jml_butuh = deficit['Selisih (Rekrut/Kurangi)']
                    
                    jml_mutasi = min(len(kandidat), jml_butuh)
                    ops_dimutasi = kandidat[:jml_mutasi]
                    
                    st.success(f"📌 **Sistem Merekomendasikan Pemindahan {jml_mutasi} Operator ({', '.join(ops_dimutasi)})** dari stasiun **{s_sumber}** ke stasiun **{s_tujuan}**.")
                    
                    # Hapus operator yang sudah dipindah dari daftar kandidat
                    kandidat = kandidat[jml_mutasi:]
                    deficit['Selisih (Rekrut/Kurangi)'] -= jml_mutasi
    else:
        st.info("Tidak ada stasiun yang memiliki kelebihan/kekurangan kapasitas ekstrem. Tidak diperlukan mutasi silang.")
