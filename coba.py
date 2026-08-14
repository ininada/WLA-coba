import io
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from fpdf import FPDF

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(page_title="DSS Analisis Beban Kerja", page_icon="📊", layout="wide")

st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>Sistem Pendukung Keputusan Analisis Beban Kerja & Optimasi Lini</h2>", unsafe_allow_html=True)
st.caption("<p style='text-align: center;'>Metode: Time Study & Workload Analysis (WLA) - Multi-Station Production</p>", unsafe_allow_html=True)

# ==========================================
# 2. FUNGSI GENERATOR LAPORAN PDF (FPDF)
# ==========================================
def generate_pdf_report(status_rek, staff_eksis, staff_opt, biaya_lembur, df_final):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(190, 10, "LAPORAN REKOMENDASI DSS - ANALISIS BEBAN KERJA", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(190, 8, "Sistem Pendukung Keputusan Berbasis WLA & Time Study", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(190, 8, "1. RINGKASAN REKOMENDASI STRATEGIS", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(190, 6, f"Status Rekomendasi : {status_rek}")
    pdf.cell(190, 6, f"Jumlah Operator Eksisting : {staff_eksis} Orang", ln=True)
    pdf.cell(190, 6, f"Kebutuhan Operator Optimal : {staff_opt} Orang", ln=True)
    pdf.cell(190, 6, f"Estimasi Biaya Lembur Lini : Rp {biaya_lembur:,.0f} / shift", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(190, 8, "2. DETAIL BEBAN KERJA OPERATOR (PASCA SIMULASI)", ln=True)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(35, 8, "Stasiun", 1)
    pdf.cell(40, 8, "Operator", 1)
    pdf.cell(35, 8, "Total Waktu (Min)", 1)
    pdf.cell(35, 8, "% WLA", 1)
    pdf.cell(45, 8, "Status WLA", 1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for index, row in df_final.iterrows():
        pdf.cell(35, 8, str(row["Stasiun"]), 1)
        pdf.cell(40, 8, str(row["Operator"]), 1)
        pdf.cell(35, 8, f"{row['Total_Waktu_Kerja_Menit']:.1f}", 1)
        pdf.cell(35, 8, f"{row['Percent_WLA']:.1f}%", 1)
        pdf.cell(45, 8, str(row["Kategori_WLA"]), 1)
        pdf.ln()

    return bytes(pdf.output())

# ==========================================
# 3. SIDEBAR & CACHING DATASET BESAR
# ==========================================
st.sidebar.header("⚙️ Parameter Operasional")
jam_kerja_shift = st.sidebar.number_input("Jam Kerja Per Shift (Jam)", min_value=1, max_value=12, value=8)
waktu_istirahat = st.sidebar.number_input("Waktu Istirahat (Menit)", min_value=0, max_value=120, value=60)
jam_kerja_efektif = (jam_kerja_shift * 60) - waktu_istirahat
st.sidebar.info(f"⏱️ **Jam Kerja Efektif:** {jam_kerja_efektif} menit/shift")

threshold_underload = st.sidebar.number_input("Batas Maksimal Underload (%)", value=85.0)
threshold_overload = st.sidebar.number_input("Batas Minimal Overload (%)", value=110.0)
tarif_lembur_per_jam = st.sidebar.number_input("Tarif Lembur per Jam (Rp)", min_value=0, value=25000, step=5000)

st.sidebar.subheader("📂 Sumber Data")
data_source = st.sidebar.radio("Pilih Sumber Data:", ["Gunakan Data Dummy (20 Operator)", "Unggah File CSV/Excel"])

# FITUR CACHING: Menghindari loading ulang saat klik tombol (penting untuk dataset besar)
@st.cache_data
def load_uploaded_data(file):
    if file.name.endswith(".csv"): return pd.read_csv(file)
    else: return pd.read_excel(file)

@st.cache_data
def get_dummy_data():
    # 5 Stasiun Kerja, 20 Operator Anonim
    # Skenario: Perakitan Overload parah, Gudang & Pemeriksaan Underload parah
    return pd.DataFrame({
        "Stasiun": ["Pemotongan"]*4 + ["Penghalusan"]*4 + ["Perakitan"]*6 + ["Pemeriksaan"]*3 + ["Gudang"]*3,
        "Operator": [f"Operator {i}" for i in range(1, 21)],
        "Waktu_Siklus_Menit": [
            3.2, 3.1, 3.3, 3.0, 
            2.5, 2.6, 2.4, 2.5, 
            5.8, 6.0, 5.7, 5.9, 5.8, 5.5, # Perakitan sangat lambat
            1.4, 1.5, 1.3, 
            0.9, 0.8, 1.0 # Gudang sangat cepat
        ],
        "Rating_Factor": [1.05]*20,
        "Allowance_Percent": [15.0]*20,
        "Target_Output_Unit": [150]*20,
    })

if data_source == "Gunakan Data Dummy (20 Operator)":
    df_input = get_dummy_data()
else:
    uploaded_file = st.sidebar.file_uploader("Unggah File (CSV atau XLSX)", type=["csv", "xlsx"])
    if uploaded_file is not None:
        df_input = load_uploaded_data(uploaded_file)
    else:
        st.warning("Silakan unggah file. Menampilkan data dummy sementara:")
        df_input = get_dummy_data()

# Reset state jika sumber data diganti
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

def indikator_fatigue(val):
    if val <= threshold_overload: return "🟢 Low Risk"
    elif val <= 130.0: return "🟡 Moderate Risk"
    return "🔴 High Hazard Risk"

df_input["Kategori_WLA"] = df_input["Percent_WLA"].apply(kategorisasi_wla)
df_input["Fatigue_Risk"] = df_input["Percent_WLA"].apply(indikator_fatigue)

if "df_simulasi" not in st.session_state:
    st.session_state.df_simulasi = df_input.copy()

# ==========================================
# 5. TAMPILAN DASHBOARD (5 TAB)
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Page 1: Data Dasar", 
    "📊 Page 2: Visualisasi", 
    "🔄 Page 3: Pindah Tugas (Internal)", 
    "⚖️ Page 4: Mutasi Operator (Lintas Stasiun)",
    "🎯 Page 5: Laporan Akhir"
])

# ------------------------------------------
# TAB 1: DATA DASAR
# ------------------------------------------
with tab1:
    st.subheader("📋 Rekapitulasi Time Study per Stasiun")
    df_rekap = df_input.groupby("Stasiun").agg(
        Jumlah_Operator=('Operator', 'count'), 
        Total_Waktu_Siklus_Menit=('Waktu_Siklus_Menit', 'sum'),
        Total_Waktu_Kerja_Menit=('Total_Waktu_Kerja_Menit', 'sum')
    ).reset_index()
    df_rekap["Rata_rata_WLA (%)"] = (df_rekap["Total_Waktu_Kerja_Menit"] / (df_rekap["Jumlah_Operator"] * jam_kerja_efektif)) * 100
    st.dataframe(df_rekap.style.format({"Total_Waktu_Siklus_Menit": "{:.2f}", "Total_Waktu_Kerja_Menit": "{:.2f}", "Rata_rata_WLA (%)": "{:.2f}%"}), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📑 Detail Tabel Data Operator (Raw Data)")
    st.dataframe(df_input.style.format({"Waktu_Siklus_Menit": "{:.2f}", "Waktu_Baku_Menit": "{:.2f}", "Total_Waktu_Kerja_Menit": "{:.2f}", "Percent_WLA": "{:.2f}%"}), use_container_width=True, hide_index=True)

# ------------------------------------------
# TAB 2: VISUALISASI
# ------------------------------------------
with tab2:
    st.subheader("📊 Visualisasi Beban Kerja")
    color_map = {"Underload": "#FBBF24", "Normal": "#10B981", "Overload": "#EF4444"}

    df_stasiun = df_input.groupby("Stasiun").agg(Total_Waktu=('Total_Waktu_Kerja_Menit', 'sum'), Jml_Operator=('Operator', 'count')).reset_index()
    df_stasiun['Total_Kapasitas'] = df_stasiun['Jml_Operator'] * jam_kerja_efektif
    df_stasiun['Utilisasi_Stasiun'] = (df_stasiun['Total_Waktu'] / df_stasiun['Total_Kapasitas']) * 100

    fig_macro = px.bar(df_stasiun, x="Stasiun", y="Utilisasi_Stasiun", text=df_stasiun["Utilisasi_Stasiun"].apply(lambda x: f"{x:.1f}%"), title="[MACRO] Utilisasi Keseluruhan per Stasiun", color="Utilisasi_Stasiun", color_continuous_scale="Blues")
    fig_macro.add_hline(y=100, line_dash="dash", line_color="red")
    st.plotly_chart(fig_macro, use_container_width=True)

    fig_bar = px.bar(df_input, x="Operator", y="Percent_WLA", color="Kategori_WLA", facet_col="Stasiun", color_discrete_map=color_map, title="[MICRO] Persentase Beban Kerja (% WLA) per Operator")
    fig_bar.add_hline(y=threshold_overload, line_dash="dash", line_color="red")
    st.plotly_chart(fig_bar, use_container_width=True)

# ------------------------------------------
# TAB 3: REDISTRIBUSI (INTERNAL)
# ------------------------------------------
with tab3:
    st.subheader("🔄 Redistribusi Tugas (Internal Stasiun)")
    st.write("Fitur ini digunakan untuk memindahkan elemen kerja/waktu antar operator **di dalam stasiun yang sama**.")
    
    if st.button("Reset Simulasi"):
        st.session_state.df_simulasi = df_input.copy()
        st.rerun()
    
    df_sim = st.session_state.df_simulasi
    pilih_stasiun = st.selectbox("1. Pilih Stasiun Kerja:", df_sim['Stasiun'].unique())
    df_sim_stasiun = df_sim[df_sim['Stasiun'] == pilih_stasiun]
    
    list_over = df_sim_stasiun[df_sim_stasiun["Kategori_WLA"] == "Overload"]["Operator"].tolist()
    list_under = df_sim_stasiun[df_sim_stasiun["Kategori_WLA"] != "Overload"]["Operator"].tolist()

    if list_over and list_under:
        col_s1, col_s2 = st.columns(2)
        with col_s1: op_sumber = st.selectbox("2. Operator Sumber (Overload):", list_over)
        with col_s2: op_penerima = st.selectbox("3. Operator Penerima (Under/Normal):", list_under)
        
        w_penerima = df_sim.loc[df_sim["Operator"] == op_penerima, "Total_Waktu_Kerja_Menit"].values[0]
        sisa = max(0.0, ((threshold_overload / 100.0) * jam_kerja_efektif) - w_penerima)
        
        if sisa > 0:
            menit_transfer = st.slider(f"Geser Waktu (Menit) ke {op_penerima}:", 0.0, float(sisa), 0.0, 1.0)
            if st.button("Terapkan Pindah Tugas"):
                st.session_state.df_simulasi.loc[st.session_state.df_simulasi["Operator"] == op_sumber, "Total_Waktu_Kerja_Menit"] -= menit_transfer
                st.session_state.df_simulasi.loc[st.session_state.df_simulasi["Operator"] == op_penerima, "Total_Waktu_Kerja_Menit"] += menit_transfer
                st.session_state.df_simulasi["Percent_WLA"] = (st.session_state.df_simulasi["Total_Waktu_Kerja_Menit"] / jam_kerja_efektif) * 100
                st.session_state.df_simulasi["Kategori_WLA"] = st.session_state.df_simulasi["Percent_WLA"].apply(kategorisasi_wla)
                st.success("Tugas berhasil digeser!")
                st.rerun()
    else:
        st.info("Tidak ada pasangan Overload & Underload di stasiun ini.")

# ------------------------------------------
# TAB 4: MUTASI LINTAS STASIUN
# ------------------------------------------
with tab4:
    st.subheader("⚖️ Analisis Kebutuhan & Mutasi Headcount Antar Stasiun")
    st.write("Tabel ini membandingkan **Jumlah Operator Eksisting** dengan **Jumlah Operator Ideal/Optimal** berdasarkan kapasitas total di masing-masing stasiun.")

    df_hasil_sim = st.session_state.df_simulasi
    df_kebutuhan = df_hasil_sim.groupby("Stasiun").agg(Total_Waktu=('Total_Waktu_Kerja_Menit', 'sum'), Staff_Eksisting=('Operator', 'count')).reset_index()
    
    df_kebutuhan['Staff_Teoritis'] = df_kebutuhan['Total_Waktu'] / jam_kerja_efektif
    df_kebutuhan['Staff_Optimal'] = np.ceil(df_kebutuhan['Staff_Teoritis']).astype(int)
    df_kebutuhan['Selisih (Rekrut/Kurangi)'] = df_kebutuhan['Staff_Optimal'] - df_kebutuhan['Staff_Eksisting']

    st.dataframe(df_kebutuhan, use_container_width=True, hide_index=True)

    st.markdown("### 🔄 Rekomendasi Cross-Training & Mutasi Operator Lintas Stasiun")
    
    surplus_stations = df_kebutuhan[df_kebutuhan['Selisih (Rekrut/Kurangi)'] < 0].to_dict('records')
    deficit_stations = df_kebutuhan[df_kebutuhan['Selisih (Rekrut/Kurangi)'] > 0].to_dict('records')

    if surplus_stations and deficit_stations:
        st.info("Sistem mendeteksi adanya ketimpangan jumlah operator antar stasiun. Berikut adalah rekomendasi mutasi otomatis (Sistem otomatis memilih operator dengan beban kerja/WLA paling rendah di stasiun yang *Overstaffed* untuk dipindah ke stasiun *Understaffed*):")
        
        for surp in surplus_stations:
            s_sumber = surp['Stasiun']
            jml_surp = abs(surp['Selisih (Rekrut/Kurangi)'])
            
            # Urutkan WLA dari terkecil untuk dipilih mutasi
            kandidat = df_hasil_sim[df_hasil_sim['Stasiun'] == s_sumber].sort_values('Percent_WLA').head(jml_surp)['Operator'].tolist()
            
            for deficit in deficit_stations:
                if deficit['Selisih (Rekrut/Kurangi)'] > 0 and len(kandidat) > 0:
                    s_tujuan = deficit['Stasiun']
                    jml_butuh = deficit['Selisih (Rekrut/Kurangi)']
                    
                    jml_mutasi = min(len(kandidat), jml_butuh)
                    ops_dimutasi = kandidat[:jml_mutasi]
                    
                    st.success(f"📌 **Tindakan Disarankan:** Mutasi **{jml_mutasi} Orang ({', '.join(ops_dimutasi)})** dari Stasiun **{s_sumber}** ke Stasiun **{s_tujuan}**.")
                    
                    kandidat = kandidat[jml_mutasi:]
                    deficit['Selisih (Rekrut/Kurangi)'] -= jml_mutasi
    else:
        st.success("Kapasitas tenaga kerja antar stasiun sudah merata secara makro. Tidak diperlukan mutasi lintas stasiun.")

# ------------------------------------------
# TAB 5: LAPORAN AKHIR & EXPORT
# ------------------------------------------
with tab5:
    st.subheader("🎯 Rekomendasi Akhir Pengambilan Keputusan")

    df_final = st.session_state.df_simulasi.copy()
    total_waktu_butuh = df_final["Total_Waktu_Kerja_Menit"].sum()
    staff_optimal = int(np.ceil(total_waktu_butuh / jam_kerja_efektif))
    staff_eksisting = len(df_final)
    selisih_staff = staff_optimal - staff_eksisting

    status_rekomendasi = ""
    total_biaya_lembur = 0

    if selisih_staff == 0:
        status_rekomendasi = "KESEIMBANGAN LINI OPTIMAL. TERAPKAN MUTASI TAB 3 & 4."
        st.success("✅ Lini sudah seimbang secara kapasitas total.")
    elif selisih_staff > 0:
        status_rekomendasi = f"PENAMBAHAN {selisih_staff} STAFF ATAU SKEMA LEMBUR"
        st.error(f"⚠️ **Total Kapasitas Lini Kurang! Perlu +{selisih_staff} Orang atau Skema Lembur.**")
        
        df_lembur = df_final[df_final["Kategori_WLA"] == "Overload"].copy()
        df_lembur["Kebutuhan_Lembur_Jam"] = (df_lembur["Total_Waktu_Kerja_Menit"] - jam_kerja_efektif) / 60.0
        df_lembur["Estimasi_Biaya_Lembur_Rp"] = df_lembur["Kebutuhan_Lembur_Jam"] * tarif_lembur_per_jam
        st.write("Tabel Rincian Lembur (Untuk operator yang masih overload):")
        st.dataframe(df_lembur[["Stasiun", "Operator", "Kebutuhan_Lembur_Jam", "Estimasi_Biaya_Lembur_Rp"]], use_container_width=True, hide_index=True)
        total_biaya_lembur = df_lembur["Estimasi_Biaya_Lembur_Rp"].sum()
    else:
        status_rekomendasi = f"EFISIENSI OPERATOR ({abs(selisih_staff)} ORANG OVERSTAFFED)"
        st.warning(f"⚠️ **Lini Overstaffed! Kurangi {abs(selisih_staff)} Orang secara keseluruhan.**")

    st.markdown("---")
    st.markdown("### 📥 Export Laporan (Excel & PDF)")
    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_final.to_excel(writer, sheet_name="Simulasi_WLA_Final", index=False)
        st.download_button("📥 Download Excel (.xlsx)", data=buffer.getvalue(), file_name="Laporan_DSS_WLA.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    with col_exp2:
        pdf_bytes = generate_pdf_report(status_rekomendasi, staff_eksisting, staff_optimal, total_biaya_lembur, df_final)
        st.download_button("📄 Download PDF Resmi (.pdf)", data=pdf_bytes, file_name="Laporan_DSS_WLA.pdf", mime="application/pdf", use_container_width=True)
