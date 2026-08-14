import streamlit as st
import pandas as pd
import plotly.express as px

# Konfigurasi Halaman
st.set_page_config(page_title="Workload Analysis Dashboard", layout="wide")
st.title("🏭 Dashboard Workload Analysis & Line Balancing")

# Kapasitas standar 1 operator (misal: 7 jam efektif = 420 menit)
KAPASITAS_STANDAR = 420 

# 1. Dummy Data Terintegrasi (Tugas -> Operator -> Stasiun)
if 'df_master' not in st.session_state:
    st.session_state.df_master = pd.DataFrame({
        'Stasiun': ['Perakitan', 'Perakitan', 'Perakitan', 'Perakitan', 'Pemeriksaan', 'Pemeriksaan', 'Pemeriksaan'],
        'Tugas': ['Rakit Rangka', 'Pasang Komponen', 'Kencangkan Baut', 'Finishing', 'Cek Visual', 'Uji Dimensi', 'Uji Fungsi'],
        'Waktu_Menit': [200, 150, 100, 50, 100, 80, 50],
        'Operator': ['Andi', 'Andi', 'Budi', 'Budi', 'Citra', 'Citra', 'Citra']
    })

# Membuat 2 Tab untuk Macro dan Micro
tab_macro, tab_micro = st.tabs(["🌐 Macro View (Antar Stasiun)", "🔬 Micro View (Internal Stasiun)"])

# ==========================================
# TAB 1: MACRO VIEW (Analisis Antar Stasiun)
# ==========================================
with tab_macro:
    st.header("Analisis Keseimbangan Lini (Antar Stasiun)")
    st.write("Melihat apakah ada stasiun yang kekurangan atau kelebihan orang secara keseluruhan.")
    
    # Agregasi data per stasiun
    df_macro = st.session_state.df_master.groupby('Stasiun').agg(
        Total_Beban=('Waktu_Menit', 'sum'),
        Jumlah_Operator=('Operator', 'nunique')
    ).reset_index()
    
    df_macro['Total_Kapasitas'] = df_macro['Jumlah_Operator'] * KAPASITAS_STANDAR
    df_macro['Utilisasi_Stasiun (%)'] = (df_macro['Total_Beban'] / df_macro['Total_Kapasitas']) * 100
    
    # Tampilkan Matrix dan Status
    cols = st.columns(len(df_macro))
    for i, row in df_macro.iterrows():
        status_stasiun = "Optimal ✅"
        if row['Utilisasi_Stasiun (%)'] > 100:
            status_stasiun = "Understaffed 🚨 (Butuh +Orang)"
        elif row['Utilisasi_Stasiun (%)'] < 70:
            status_stasiun = "Overstaffed ⚠️ (Kelebihan Orang)"
            
        cols[i].metric(label=f"Stasiun {row['Stasiun']}", 
                       value=f"{row['Utilisasi_Stasiun (%)']:.1f}%", 
                       delta=status_stasiun, delta_color="off")

    # Visualisasi
    fig_macro = px.bar(df_macro, x='Stasiun', y='Utilisasi_Stasiun (%)', 
                       color='Utilisasi_Stasiun (%)', color_continuous_scale='RdYlGn_r',
                       title="Perbandingan Utilisasi Antar Stasiun")
    fig_macro.add_hline(y=100, line_dash="dash", line_color="red")
    st.plotly_chart(fig_macro, use_container_width=True)


# ==========================================
# TAB 2: MICRO VIEW (Simulasi Internal)
# ==========================================
with tab_micro:
    st.header("Simulasi Re-routing Tugas (Internal Stasiun)")
    
    # Filter Stasiun
    stasiun_pilihan = st.selectbox("Pilih Stasiun untuk Simulasi:", st.session_state.df_master['Stasiun'].unique())
    
    # Ambil data HANYA untuk stasiun terpilih
    df_stasiun = st.session_state.df_master[st.session_state.df_master['Stasiun'] == stasiun_pilihan].reset_index(drop=True)
    
    # Daftar operator HANYA di stasiun tersebut (jadi gak bisa lempar tugas ke stasiun lain)
    daftar_operator_valid = df_stasiun['Operator'].unique().tolist()
    
    st.write(f"Tabel Interaktif: Ubah nama di kolom **Operator** untuk memindahkan tugas di dalam **Stasiun {stasiun_pilihan}**.")
    
    # Data Editor
    edited_df = st.data_editor(
        df_stasiun,
        column_config={
            "Operator": st.column_config.SelectboxColumn(
                "Assigned Operator",
                help="Pilih operator di stasiun ini",
                options=daftar_operator_valid,
                required=True,
            )
        },
        hide_index=True,
        use_container_width=True
    )
    
    # Kalkulasi ulang khusus stasiun ini
    df_summary = edited_df.groupby('Operator')['Waktu_Menit'].sum().reset_index()
    df_summary = df_summary.set_index('Operator').reindex(daftar_operator_valid).fillna(0).reset_index()
    df_summary['Utilisasi (%)'] = (df_summary['Waktu_Menit'] / KAPASITAS_STANDAR) * 100
    
    st.write(f"### Utilisasi Operator di Stasiun {stasiun_pilihan}")
    fig_micro = px.bar(df_summary, x='Operator', y='Utilisasi (%)', 
                       color='Utilisasi (%)', color_continuous_scale='RdYlGn_r', range_y=[0, 150])
    fig_micro.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="Batas 100%")
    st.plotly_chart(fig_micro, use_container_width=True)