import io
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from fpdf import FPDF

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(
    page_title="DSS Analisis Beban Kerja Operator Lini",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    "<h2 style='text-align: center; color: #1E3A8A;'>Sistem Pendukung Keputusan"
    " Analisis Beban Kerja & Optimasi Tenaga Kerja</h2>",
    unsafe_allow_html=True,
)
st.caption(
    "<p style='text-align: center;'>Metode: Time Study & Workload Analysis (WLA)"
    " - Multi-Station Production</p>",
    unsafe_allow_html=True,
)

# ==========================================
# 2. FUNGSI GENERATOR LAPORAN PDF (FPDF)
# ==========================================
def generate_pdf_report(status_rek, staff_eksis, staff_opt, biaya_lembur, df_final):
    pdf = FPDF()
    pdf.add_page()

    # Header Laporan
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(190, 10, "LAPORAN REKOMENDASI DSS - ANALISIS BEBAN KERJA", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(190, 8, "Sistem Pendukung Keputusan Berbasis WLA & Time Study", ln=True, align="C")
    pdf.ln(5)

    # Ringkasan Keputusan
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(190, 8, "1. RINGKASAN REKOMENDASI STRATEGIS", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(190, 6, f"Status Rekomendasi : {status_rek}")
    pdf.cell(190, 6, f"Jumlah Operator Eksisting : {staff_eksis} Orang", ln=True)
    pdf.cell(190, 6, f"Kebutuhan Operator Optimal : {staff_opt} Orang", ln=True)
    pdf.cell(190, 6, f"Estimasi Biaya Lembur Lini : Rp {biaya_lembur:,.0f} / shift", ln=True)
    pdf.ln(6)

    # Tabel Ringkasan Operator
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(190, 8, "2. DETAIL BEBAN KERJA OPERATOR (PASCA SIMULASI)", ln=True)
    pdf.set_font("Helvetica", "B", 9)

    # Header Tabel (Total Lebar = 190)
    pdf.cell(35, 8, "Stasiun", 1)
    pdf.cell(40, 8, "Operator", 1)
    pdf.cell(35, 8, "Total Waktu (Min)", 1)
    pdf.cell(35, 8, "% WLA", 1)
    pdf.cell(45, 8, "Status WLA", 1)
    pdf.ln()

    # Isi Tabel
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
# 3. SIDEBAR - PARAMETER OPERASIONAL & BIAYA
# ==========================================
st.sidebar.header("⚙️ Parameter Operasional")

jam_kerja_shift = st.sidebar.number_input("Jam Kerja Per Shift (Jam)", min_value=1, max_value=12, value=8)
waktu_istirahat = st.sidebar.number_input("Waktu Istirahat (Menit)", min_value=0, max_value=120, value=60)

jam_kerja_efektif = (jam_kerja_shift * 60) - waktu_istirahat
st.sidebar.info(f"⏱️ **Jam Kerja Efektif:** {jam_kerja_efektif} menit/shift")

st.sidebar.subheader("🎯 Threshold WLA (%)")
threshold_underload = st.sidebar.number_input("Batas Maksimal Underload (%)", value=85.0)
threshold_overload = st.sidebar.number_input("Batas Minimal Overload (%)", value=110.0)

st.sidebar.subheader("💰 Parameter Finansial (Lembur)")
tarif_lembur_per_jam = st.sidebar.number_input("Tarif Lembur Operator per Jam (Rp)", min_value=0, value=25000, step=5000)

st.sidebar.subheader("📂 Sumber Data")
data_source = st.sidebar.radio(
    "Pilih Sumber Data:",
    ["Gunakan Data Dummy (Default)", "Unggah File CSV/Excel"],
)


# ==========================================
# 4. LOAD DATASET EKSISTING
# ==========================================
if data_source == "Gunakan Data Dummy (Default)":
    df_input = pd.DataFrame({
        "Stasiun": ["Perakitan", "Perakitan", "Perakitan", "Pemeriksaan", "Pemeriksaan", "Pengemasan"],
        "Operator": ["Andi", "Budi", "Citra", "Dani", "Eka", "Fajar"],
        "Waktu_Siklus_Menit": [3.5, 4.8, 2.9, 1.4, 1.2, 4.5],
        "Rating_Factor": [1.10, 1.05, 1.00, 0.95, 1.00, 1.10],
        "Allowance_Percent": [15.0, 12.0, 15.0, 10.0, 12.0, 15.0],
        "Target_Output_Unit": [150, 150, 150, 150, 150, 150],
    })
else:
    uploaded_file = st.sidebar.file_uploader("Unggah File (CSV atau XLSX)", type=["csv", "xlsx"])
    st.sidebar.caption(
        "💡 **Format Kolom Excel:** `Stasiun`, `Operator`, `Waktu_Siklus_Menit`,"
        " `Rating_Factor`, `Allowance_Percent`, `Target_Output_Unit`"
    )

    if uploaded_file is not None:
        if uploaded_file.name.endswith(".csv"):
            df_input = pd.read_csv(uploaded_file)
        else:
            df_input = pd.read_excel(uploaded_file)
    else:
        st.warning("Silakan unggah file dataset sesuai format kolom. Menampilkan data template sementara:")
        df_input = pd.DataFrame({
            "Stasiun": ["Stasiun 1"],
            "Operator": ["Operator A"],
            "Waktu_Siklus_Menit": [2.0],
            "Rating_Factor": [1.0],
            "Allowance_Percent": [10.0],
            "Target_Output_Unit": [100],
        })

# Cek pergantian sumber data untuk reset simulasi
if 'current_source' not in st.session_state or st.session_state.current_source != data_source:
    st.session_state.current_source = data_source
    if 'df_simulasi' in st.session_state:
        del st.session_state['df_simulasi']


# ==========================================
# 5. KALKULASI TIME STUDY, WLA & FATIGUE RISK
# ==========================================
df_input["Waktu_Normal_Menit"] = df_input["Waktu_Siklus_Menit"] * df_input["Rating_Factor"]
df_input["Waktu_Baku_Menit"] = df_input["Waktu_Normal_Menit"] * (1 + (df_input["Allowance_Percent"] / 100))
df_input["Total_Waktu_Kerja_Menit"] = df_input["Waktu_Baku_Menit"] * df_input["Target_Output_Unit"]
df_input["Percent_WLA"] = (df_input["Total_Waktu_Kerja_Menit"] / jam_kerja_efektif) * 100

def kategorisasi_wla(val):
    if val < threshold_underload:
        return "Underload"
    elif val > threshold_overload:
        return "Overload"
    else:
        return "Normal"

def indikator_fatigue(val):
    if val <= threshold_overload:
        return "🟢 Low Risk (Aman)"
    elif val <= 130.0:
        return "🟡 Moderate Risk (Kelelahan Sedang)"
    else:
        return "🔴 High Hazard Risk (Kelelahan Ekstrem)"

df_input["Kategori_WLA"] = df_input["Percent_WLA"].apply(kategorisasi_wla)
df_input["Fatigue_Risk"] = df_input["Percent_WLA"].apply(indikator_fatigue)


# ==========================================
# 6. TAMPILAN DASHBOARD (5 TAB STRATEGIS)
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Page 1: Data Time Study",
    "📊 Page 2: Visualisasi Beban Kerja",
    "🔄 Page 3: DSS Redistribusi Interaktif",
    "⚖️ Page 4: Analisis Kebutuhan Staff",
    "🎯 Page 5: Rekomendasi Akhir DSS",
])

# ------------------------------------------
# PAGE 1: DATA TIME STUDY & KALKULASI DASAR (REKAP PER STASIUN)
# ------------------------------------------
with tab1:
    st.subheader("📋 Rekapitulasi Time Study per Stasiun")
    
    # 1. Mengelompokkan (grouping) data berdasarkan stasiun
    df_rekap = df_input.groupby("Stasiun").agg(
        Jumlah_Operator=('Operator', 'count'), 
        Total_Waktu_Siklus_Menit=('Waktu_Siklus_Menit', 'sum'),
        Total_Waktu_Baku_Menit=('Waktu_Baku_Menit', 'sum'),
        Total_Waktu_Kerja_Menit=('Total_Waktu_Kerja_Menit', 'sum')
    ).reset_index()
    
    # 2. Menghitung rata-rata utilisasi WLA per stasiun
    df_rekap["Rata_rata_WLA (%)"] = (df_rekap["Total_Waktu_Kerja_Menit"] / (df_rekap["Jumlah_Operator"] * jam_kerja_efektif)) * 100

    # 3. Menampilkan tabel yang sudah diringkas
    st.dataframe(
        df_rekap.style.format({
            "Total_Waktu_Siklus_Menit": "{:.2f}",
            "Total_Waktu_Baku_Menit": "{:.2f}",
            "Total_Waktu_Kerja_Menit": "{:.2f}",
            "Rata_rata_WLA (%)": "{:.2f}%",
        }),
        use_container_width=True,
        hide_index=True 
    )

    # 4. Metrik Rangkuman
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Stasiun Kerja", f"{df_input['Stasiun'].nunique()} Stasiun")
    col_b.metric("Total Operator Lini", f"{len(df_input)} Orang")
    col_c.metric("Total Waktu Baku Diperlukan", f"{df_input['Total_Waktu_Kerja_Menit'].sum():.2f} Menit")


# ------------------------------------------
# PAGE 2: VISUALISASI BEBAN KERJA & ERGONOMIC RISK
# ------------------------------------------
with tab2:
    st.subheader("📊 Visualisasi Beban Kerja (Macro & Micro Level)")
    color_map = {"Underload": "#FBBF24", "Normal": "#10B981", "Overload": "#EF4444"}

    # Chart 1: MACRO VIEW (Level Stasiun)
    df_stasiun = df_input.groupby("Stasiun").agg(
        Total_Waktu=('Total_Waktu_Kerja_Menit', 'sum'),
        Jml_Operator=('Operator', 'count')
    ).reset_index()
    df_stasiun['Total_Kapasitas'] = df_stasiun['Jml_Operator'] * jam_kerja_efektif
    df_stasiun['Utilisasi_Stasiun'] = (df_stasiun['Total_Waktu'] / df_stasiun['Total_Kapasitas']) * 100

    fig_macro = px.bar(df_stasiun, x="Stasiun", y="Utilisasi_Stasiun", text=df_stasiun["Utilisasi_Stasiun"].apply(lambda x: f"{x:.1f}%"),
                       title="[MACRO] Utilisasi Keseluruhan per Stasiun", color="Utilisasi_Stasiun", color_continuous_scale="Blues")
    fig_macro.add_hline(y=100, line_dash="dash", line_color="red")
    st.plotly_chart(fig_macro, use_container_width=True)

    # Chart 2: MICRO VIEW (Level Operator)
    fig_bar = px.bar(
        df_input, x="Operator", y="Percent_WLA", color="Kategori_WLA", facet_col="Stasiun",
        color_discrete_map=color_map, text=df_input["Percent_WLA"].apply(lambda x: f"{x:.1f}%"),
        title="[MICRO] Persentase Beban Kerja (% WLA) per Operator",
    )
    fig_bar.add_hline(y=threshold_underload, line_dash="dash", line_color="orange", annotation_text="Underload")
    fig_bar.add_hline(y=threshold_overload, line_dash="dash", line_color="red", annotation_text="Overload")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("### 🫀 Indikator Risiko Kelelahan Kerja (Fatigue)")
    st.dataframe(
        df_input[["Stasiun", "Operator", "Percent_WLA", "Fatigue_Risk"]].style.format({"Percent_WLA": "{:.1f}%"}),
        use_container_width=True,
        hide_index=True
    )

# ------------------------------------------
# PAGE 3: DSS INTERAKTIF (REDISTRIBUSI DINAMIS)
# ------------------------------------------
with tab3:
    st.subheader("🔄 Interactive Decision Support System: Simulasi Redistribusi")
    st.write("Fitur interaktif ini digunakan untuk memindahkan elemen kerja antar operator **di dalam stasiun yang sama**.")

    if "df_simulasi" not in st.session_state or st.button("Reset Simulasi ke Kondisi Awal"):
        st.session_state.df_simulasi = df_input.copy()

    df_sim = st.session_state.df_simulasi

    # Filter Stasiun Dulu
    pilih_stasiun = st.selectbox("1. Pilih Stasiun Kerja:", df_sim['Stasiun'].unique())
    df_sim_stasiun = df_sim[df_sim['Stasiun'] == pilih_stasiun]

    col_s1, col_s2 = st.columns(2)
    list_over = df_sim_stasiun[df_sim_stasiun["Kategori_WLA"] == "Overload"]["Operator"].tolist()
    list_under = df_sim_stasiun[df_sim_stasiun["Kategori_WLA"] != "Overload"]["Operator"].tolist()

    if list_over and list_under:
        with col_s1:
            op_sumber = st.selectbox("2. Pilih Operator Sumber (Overload):", list_over)
        with col_s2:
            op_penerima = st.selectbox("3. Pilih Operator Penerima (Underload/Normal):", list_under)

        waktu_sumber = df_sim.loc[df_sim["Operator"] == op_sumber, "Total_Waktu_Kerja_Menit"].values[0]
        waktu_penerima = df_sim.loc[df_sim["Operator"] == op_penerima, "Total_Waktu_Kerja_Menit"].values[0]

        kapasitas_maks_penerima_menit = (threshold_overload / 100.0) * jam_kerja_efektif
        sisa_kapasitas_menit = max(0.0, kapasitas_maks_penerima_menit - waktu_penerima)

        st.markdown("---")
        st.caption(f"🛡️ **Guardrail Sistem:** Maksimal waktu yang dapat dipindahkan ke **{op_penerima}** adalah **{sisa_kapasitas_menit:.1f} menit**.")

        if sisa_kapasitas_menit > 0:
            menit_transfer = st.slider(
                f"Geser Waktu (Menit) dari {op_sumber} ➡️ {op_penerima}:",
                min_value=0.0, max_value=float(sisa_kapasitas_menit), value=0.0, step=1.0,
            )

            if st.button("Terapkan Redistribusi"):
                st.session_state.df_simulasi.loc[st.session_state.df_simulasi["Operator"] == op_sumber, "Total_Waktu_Kerja_Menit"] -= menit_transfer
                st.session_state.df_simulasi.loc[st.session_state.df_simulasi["Operator"] == op_penerima, "Total_Waktu_Kerja_Menit"] += menit_transfer
                
                # Hitung ulang persentase WLA
                st.session_state.df_simulasi["Percent_WLA"] = (st.session_state.df_simulasi["Total_Waktu_Kerja_Menit"] / jam_kerja_efektif) * 100
                st.session_state.df_simulasi["Kategori_WLA"] = st.session_state.df_simulasi["Percent_WLA"].apply(kategorisasi_wla)
                st.session_state.df_simulasi["Fatigue_Risk"] = st.session_state.df_simulasi["Percent_WLA"].apply(indikator_fatigue)
                
                st.success(f"Berhasil memindahkan {menit_transfer} menit kerja dari {op_sumber} ke {op_penerima} di {pilih_stasiun}!")
                st.rerun()
        else:
            st.warning(f"Operator {op_penerima} sudah di ambang batas maksimal. Pilih operator lain!")
    else:
        st.info(f"Kondisi stasiun **{pilih_stasiun}** saat ini: Tidak ada pasangan Overload & Underload yang bisa di-redistribusi.")

    st.markdown("### 📊 Perbandingan % WLA Eksisting vs Hasil Simulasi (Seluruh Lini)")
    df_compare = pd.DataFrame({
        "Stasiun": df_input["Stasiun"],
        "Operator": df_input["Operator"],
        "Eksisting": df_input["Percent_WLA"],
        "Hasil Redistribusi": st.session_state.df_simulasi["Percent_WLA"],
    }).melt(id_vars=["Stasiun", "Operator"], var_name="Kondisi", value_name="Percent_WLA")

    fig_sim = px.bar(
        df_compare, x="Operator", y="Percent_WLA", color="Kondisi", 
        barmode="group", facet_col="Stasiun", 
        text=df_compare["Percent_WLA"].apply(lambda x: f"{x:.1f}%")
    )
    fig_sim.add_hline(y=threshold_overload, line_dash="dash", line_color="red")
    st.plotly_chart(fig_sim, use_container_width=True)

# ------------------------------------------
# PAGE 4: ANALISIS KEBUTUHAN STAFF
# ------------------------------------------
with tab4:
    st.subheader("⚖️ Analisis Kebutuhan Tenaga Kerja Optimal per Stasiun")

    df_hasil_sim = st.session_state.df_simulasi
    df_kebutuhan = df_hasil_sim.groupby("Stasiun").agg(
        Total_Waktu=('Total_Waktu_Kerja_Menit', 'sum'), 
        Staff_Eksisting=('Operator', 'count')
    ).reset_index()
    
    df_kebutuhan['Staff_Teoritis'] = df_kebutuhan['Total_Waktu'] / jam_kerja_efektif
    df_kebutuhan['Staff_Optimal'] = np.ceil(df_kebutuhan['Staff_Teoritis']).astype(int)
    df_kebutuhan['Selisih (Rekrut/Kurangi)'] = df_kebutuhan['Staff_Optimal'] - df_kebutuhan['Staff_Eksisting']

    st.dataframe(df_kebutuhan, use_container_width=True, hide_index=True)

    sisa_overload = len(df_hasil_sim[df_hasil_sim["Kategori_WLA"] == "Overload"])
    col_e1, col_e2 = st.columns(2)
    col_e1.metric("Total Kebutuhan Operator (Seluruh Lini)", f"{df_kebutuhan['Staff_Optimal'].sum()} Orang")
    col_e2.metric("Sisa Operator Overload (Pasca Simulasi)", f"{sisa_overload} Orang")

# ------------------------------------------
# PAGE 5: REKOMENDASI DSS, BIAYA, & EXPORT
# ------------------------------------------
with tab5:
    st.subheader("🎯 Rekomendasi Strategis Pengambilan Keputusan (DSS)")

    df_final = st.session_state.df_simulasi.copy()
    sisa_over = len(df_final[df_final["Kategori_WLA"] == "Overload"])
    
    # Hitung makro
    total_waktu_butuh = df_final["Total_Waktu_Kerja_Menit"].sum()
    staff_optimal = int(np.ceil(total_waktu_butuh / jam_kerja_efektif))
    staff_eksisting = len(df_final)
    selisih_staff = staff_optimal - staff_eksisting

    status_rekomendasi = ""
    total_biaya_lembur = 0

    if sisa_over == 0:
        status_rekomendasi = "REKOMENDASI 1: CUKUP LAKUKAN REDISTRIBUSI TUGAS INTERNAL STASIUN"
        st.success("✅ **REKOMENDASI 1: CUKUP LAKUKAN REDISTRIBUSI (TANPA REKRUTMEN / LEMBUR)**")
        st.write("* Keputusan: Line Balancing berhasil. Terapkan alokasi tugas hasil simulasi secara resmi.")
    elif selisih_staff > 0:
        status_rekomendasi = f"REKOMENDASI 2: PENAMBAHAN {selisih_staff} STAFF ATAU SKEMA LEMBUR"
        st.error(f"⚠️ **REKOMENDASI 2: PERLU PENAMBAHAN TENAGA KERJA ({selisih_staff} ORANG) ATAU SKEMA LEMBUR**")
        st.write("* Keputusan: Terdapat stasiun kerja yang *bottleneck* (beban total stasiun > kapasitas).")
        
        # Hitung lembur
        df_lembur = df_final[df_final["Kategori_WLA"] == "Overload"].copy()
        df_lembur["Kebutuhan_Lembur_Jam"] = (df_lembur["Total_Waktu_Kerja_Menit"] - jam_kerja_efektif) / 60.0
        df_lembur["Estimasi_Biaya_Lembur_Rp"] = df_lembur["Kebutuhan_Lembur_Jam"] * tarif_lembur_per_jam
        st.dataframe(df_lembur[["Stasiun", "Operator", "Kebutuhan_Lembur_Jam", "Estimasi_Biaya_Lembur_Rp"]], use_container_width=True, hide_index=True)
        total_biaya_lembur = df_lembur["Estimasi_Biaya_Lembur_Rp"].sum()
    elif selisih_staff < 0:
        status_rekomendasi = f"REKOMENDASI 3: EFISIENSI OPERATOR ({abs(selisih_staff)} ORANG OVERSTAFFED)"
        st.warning(f"⚠️ **REKOMENDASI 3: EFISIENSI OPERATOR (OVERSTAFFED)**")
    else:
        status_rekomendasi = "REKOMENDASI 4: OPTIMALKAN KEMBALI REDISTRIBUSI ATOMIK"
        st.info("💡 **REKOMENDASI 4: OPTIMALKAN KEMBALI REDISTRIBUSI DI TAB 3**")

    # ==========================================
    # FITUR EXPORT LAPORAN
    # ==========================================
    st.markdown("---")
    st.markdown("### 📥 Export Laporan Hasil Rekomendasi DSS")
    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_final.to_excel(writer, sheet_name="Simulasi_WLA_Final", index=False)
            pd.DataFrame({"Parameter": ["Status Rekomendasi", "Biaya Lembur"], "Nilai": [status_rekomendasi, total_biaya_lembur]}).to_excel(writer, sheet_name="Ringkasan", index=False)
        st.download_button(
            "📥 Download Laporan (Excel .xlsx)", 
            data=buffer.getvalue(), 
            file_name="Laporan_DSS_WLA.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            use_container_width=True
        )

    with col_exp2:
        pdf_bytes = generate_pdf_report(status_rekomendasi, staff_eksisting, staff_optimal, total_biaya_lembur, df_final)
        st.download_button(
            "📄 Download Laporan Resmi (PDF .pdf)", 
            data=pdf_bytes, 
            file_name="Laporan_DSS_WLA.pdf", 
            mime="application/pdf", 
            use_container_width=True
        )
