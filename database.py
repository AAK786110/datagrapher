import streamlit as st
import pandas as pd
import io
import hashlib

st.set_page_config(page_title="Excel Analyzer", layout="wide")

# --- Custom CSS for background image and styling ---
st.markdown("""
   <style>
/* === Background === */
.stApp {
    background-image: url("https://4kwallpapers.com/images/wallpapers/windows-11-dark-mode-abstract-background-black-background-3840x2160-8710.jpg");
    background-size: cover;
    background-attachment: fixed;
    background-position: center;
}

/* === Card styling === */
.stContainer, .stSidebar, .stMarkdown, .stDataFrame {
    background-color: rgba(0, 0, 0, 0.55) !important;
    color: white !important;
    backdrop-filter: blur(10px);
    border-radius: 10px;
    padding: 1rem;
}

/* === Inputs (text, dropdowns, etc.) === */
.stTextInput, .stSelectbox, .stMultiselect, .stCheckbox {
    background-color: rgba(255, 255, 255, 0.1) !important;
    color: white !important;
}

/* === Labels and dropdown options === */
label,
div[data-testid="stTextInput"] *,
div[data-testid="stCheckbox"] *,
div[data-testid="stMultiselect"] * {
    color: white !important;
    font-weight: bold !important;
}

}

/* === Checkbox labels === */
div[data-testid="stCheckbox"] label {
    color: white !important;
    font-weight: bold !important;
}

/* === File uploader === */
section[data-testid="stFileUploader"] * {
    color: white !important;
    font-weight: bold !important;
}

/* === Success messages (st.success) === */
div[data-testid="stAlert-success"] {
    background-color: rgba(0, 128, 0, 0.3) !important;
    color: white !important;
    font-weight: bold !important;
    border-radius: 0.5rem;
}
div[data-testid="stAlert-success"] * {
    color: white !important;
    font-weight: bold !important;
}

/* === Multiselect pills === */
div[data-baseweb="tag"] {
    background-color: rgba(0, 128, 255, 0.5) !important;
    border: 1px solid #00aaff !important;
    color: white !important;
    font-weight: bold;
    border-radius: 0.5rem;
}
div[data-baseweb="tag"] svg {
    fill: white !important;
}

/* === Headers === */
h1, h2, h3, h4 {
    color: white !important;
    font-weight: bold;
    text-shadow: 1px 1px 5px black;
}
/* Make dropdown captions / helper text black */
.stCaption {
    color: black !important;
}

/* Fix selected dropdown value (white text on white background) */
div[data-baseweb="select"] > div {
    color: black !important;
}
/* Make the selected text in dropdown visible */
div[data-baseweb="select"] div[role="button"] {
    color: black !important;
}

/* Make input text inside text_input fields black */
input[type="text"] {
    color: black !important;
}


</style>

""", unsafe_allow_html=True)

st.title("📊 Excel Data Analyzer (Filter → Calculate → Plot)")

# --- SESSION INIT ---
if "df_raw" not in st.session_state:
    st.session_state.df_raw = None
if "df_filtered" not in st.session_state:
    st.session_state.df_filtered = None
if "df_calculated" not in st.session_state:
    st.session_state.df_calculated = None
if "last_file_hash" not in st.session_state:
    st.session_state.last_file_hash = None

import os

# === Persistent File Upload with Disk Storage ===
UPLOAD_PATH = "uploaded.xlsx"

if "file_loaded" not in st.session_state:
    st.session_state.file_loaded = False

st.subheader("📁 Step 0: Upload Excel File")

# Remove File Button
if os.path.exists(UPLOAD_PATH):
    st.success(f"📄 Using saved file: {UPLOAD_PATH}")
    if st.button("❌ Remove File"):
        os.remove(UPLOAD_PATH)
        st.session_state.file_loaded = False
        st.session_state.df_raw = None
        st.session_state.df_filtered = None
        st.session_state.df_calculated = None
        st.rerun()

# Upload New File
if not os.path.exists(UPLOAD_PATH):
    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"], key="file_upload")
    if uploaded_file is not None:
        with open(UPLOAD_PATH, "wb") as f:
            f.write(uploaded_file.read())
        st.session_state.file_loaded = True
        st.rerun()

# Load from saved file
if os.path.exists(UPLOAD_PATH) and st.session_state.df_raw is None:
    xls = pd.ExcelFile(UPLOAD_PATH)
    sheet = st.selectbox("Select a sheet", xls.sheet_names, key="sheet_select")

    if sheet:
        df = pd.read_excel(xls, sheet_name=sheet)

        # Clean column names
        df.columns = df.columns.map(str).str.strip().str.replace(r"\W+", "_", regex=True)
        df = df.loc[:, ~df.columns.duplicated()]
        df = df.dropna(axis=1, how="all")
        df = df.dropna(axis=0, how="all")
        if "date" in df.columns:
            df = df[df["date"].notna()]
            df = df[~df["date"].astype(str).str.startswith("1900")]
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

        st.session_state.df_raw = df
        st.session_state.df_filtered = df.copy()
        st.session_state.df_calculated = df.copy()



# Drop fully empty rows (important!)
        df = df.dropna(axis=0, how="all")

# Drop rows where 'date' column is missing or invalid (optional but safer)
        if "date" in df.columns:
            df = df[df["date"].notna()]
            df = df[~df["date"].astype(str).str.startswith("1900")]

        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

        st.session_state.df_raw = df
        st.session_state.df_filtered = df.copy()
        st.session_state.df_calculated = df.copy()

# --- FILTERING ---
if st.session_state.df_raw is not None:
    st.subheader("🔎 Step 1: Filter the Data")
    df = st.session_state.df_raw.copy()

    for col in df.columns:
        if df[col].dtype == "object" or df[col].nunique() < 50:
            unique_vals = df[col].dropna().unique().tolist()
            if len(unique_vals) > 0:
                selected = st.multiselect(f"Filter by {col}", unique_vals, default=unique_vals, key=f"filter_{col}")
                df = df[df[col].isin(selected)]

    sort_col = st.selectbox("Sort by column", df.columns, key="sort_col")
    sort_asc = st.checkbox("Sort ascending", value=True, key="sort_order")
    df = df.sort_values(by=sort_col, ascending=sort_asc, ignore_index=True)

    if "df_calculated" in st.session_state:
        for col in st.session_state.df_calculated.columns:
            if col not in df.columns:
                df[col] = st.session_state.df_calculated[col]

    st.session_state.df_filtered = df.copy()
    st.session_state.df_calculated = df.copy()
    st.dataframe(st.session_state.df_calculated)

# --- CALCULATED COLUMN ---
if st.session_state.df_calculated is not None:
    st.subheader("➕ Step 2: Add a Calculated Column")
    st.code("Available columns:\n" + "\n".join(st.session_state.df_calculated.columns), language="python")

    with st.form("calc_form"):
        new_col = st.text_input("New column name", key="new_col")
        formula = st.text_input("Formula (e.g. (NAV_unit - NAV_unit.shift(1)) / NAV_unit.shift(1) * 100)", key="formula")
        submit = st.form_submit_button("Add Column")

    if submit:
        try:
            local_vars = {col: st.session_state.df_calculated[col] for col in st.session_state.df_calculated.columns}
            st.session_state.df_calculated[new_col] = eval(formula, {}, local_vars)
            st.success(f"✅ Column '{new_col}' added.")
        except Exception as e:
            st.error(f"❌ Calculation error: {e}")

    st.dataframe(st.session_state.df_calculated)

# --- PLOTTING ---
if st.session_state.df_calculated is not None and not st.session_state.df_calculated.empty:
    st.subheader("📈 Step 3: Plot a Line Chart")
    df_plot = st.session_state.df_calculated

    x_axis = st.selectbox("X-axis", df_plot.columns, key="x_axis")
    y_axis = st.selectbox("Y-axis", df_plot.select_dtypes(include=["number"]).columns.tolist(), key="y_axis")

    try:
        chart_df = df_plot[[x_axis, y_axis]].dropna()
        chart_df = chart_df.set_index(x_axis)
        st.line_chart(chart_df)
    except Exception as e:
        st.error(f"❌ Plotting error: {e}")
