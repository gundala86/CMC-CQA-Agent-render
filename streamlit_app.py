import streamlit as st
import pandas as pd
import pdfplumber
import yaml
import os
from fpdf import FPDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import tempfile

# Load users
USERS_FILE = "users.yaml"
with open(USERS_FILE) as f:
    users = yaml.safe_load(f)["users"]

def login(username, password):
    if username in users and users[username]["password"] == password:
        return True, users[username]["name"], users[username].get("role", "user")
    return False, None, None

KB_PATH = "output/CQA_KnowledgeBase_Master.csv"
if not os.path.exists(KB_PATH):
    os.makedirs("output", exist_ok=True)
    pd.DataFrame(columns=["Modality", "Phase", "CQA", "Test Methods", "Justification", "Regulatory Source", "Control Action"]).to_csv(KB_PATH, index=False)

def load_kb():
    return pd.read_csv(KB_PATH).fillna("")

def save_kb(df):
    df.to_csv(KB_PATH, index=False)

def ingest_pdf(pdf_path, modality, phase):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
    results = []
    for chunk in chunks:
        lower = chunk.lower()
        if modality.lower() in ["mab", "car-t", "fusion protein", "aav gene therapy", "adc"]:
            if "purity" in lower:
                results.append(("Purity", "HPLC, SEC"))
            if "potency" in lower:
                results.append(("Potency", "Bioassay, Cell-based Assay"))
            if "identity" in lower:
                results.append(("Identity", "Peptide Mapping"))
            if "glycosylation" in lower:
                results.append(("Glycosylation", "UPLC-MS"))
            if "charge variant" in lower or "icief" in lower:
                results.append(("Charge Variants", "iCIEF"))
            if "aggregation" in lower or "aggregate" in lower:
                results.append(("Aggregates", "SEC-HPLC"))
            if "oxidation" in lower:
                results.append(("Oxidation", "Peptide Mapping"))
        else:
            if "identity" in lower:
                results.append(("Identity", "HPLC RT, Mass Spec"))
            if "purity" in lower:
                results.append(("Purity", "HPLC, CE"))
            if "potency" in lower:
                results.append(("Potency", "Bioassay"))
            if "residual solvent" in lower:
                results.append(("Residual Solvents", "GC"))
            if "heavy metal" in lower:
                results.append(("Heavy Metals", "ICP-MS"))
            if "degradation" in lower:
                results.append(("Degradation Products", "Stability HPLC"))
            if "moisture" in lower:
                results.append(("Moisture Content", "Karl Fischer"))
            if "content uniformity" in lower:
                results.append(("Content Uniformity", "HPLC Assay"))
            if "polymorph" in lower:
                results.append(("Polymorphic Forms", "XRPD"))
    return results

def query_reasoning(modality, phase, kb):
    df_filtered = kb[
        (kb['Modality'].str.lower() == modality.lower()) &
        (kb['Phase'].str.lower() == phase.lower())
    ]
    if df_filtered.empty:
        return pd.DataFrame([{
            "CQA": "No data found",
            "Test Methods": "",
            "Control Action": "",
            "Justification": "",
            "Reference": ""
        }])
    grouped = df_filtered.groupby("CQA")
    rows = []
    for cqa, group in grouped:
        tests = ", ".join(group["Test Methods"].unique())
        control_action = ", ".join(group["Control Action"].unique())
        justifications = ", ".join(group["Justification"].unique())
        references = ", ".join(group["Regulatory Source"].unique())
        rows.append({
            "CQA": cqa,
            "Test Methods": tests,
            "Control Action": control_action,
            "Justification": justifications,
            "Reference": references
        })
    return pd.DataFrame(rows)

def dataframe_to_pdf(df, title="Reasoning Results"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=title, ln=True, align="C")
    pdf.ln(5)

    # Calculate column widths
    col_widths = []
    for col in df.columns:
        max_content = max([len(str(x)) for x in df[col]] + [len(str(col))])
        col_widths.append(min(max(30, max_content * 2.2), 55))

    # Table headers (bold, single line)
    pdf.set_font("Arial", "B", 12)
    for i, col in enumerate(df.columns):
        pdf.cell(col_widths[i], 10, str(col), border=1, align='C')
    pdf.ln()

    # Table rows (wrap text)
    pdf.set_font("Arial", size=11)
    for _, row in df.iterrows():
        y_start = pdf.get_y()
        x_start = pdf.get_x()
        cell_heights = []
        # Calculate required height for each cell
        for i, item in enumerate(row):
            text = str(item)
            n_lines = len(pdf.multi_cell(col_widths[i], 8, text, border=0, align='L', split_only=True))
            cell_heights.append(n_lines * 8)
        max_height = max(cell_heights)
        pdf.set_y(y_start)
        pdf.set_x(x_start)
        # Draw each cell with wrapping
        for i, item in enumerate(row):
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.multi_cell(col_widths[i], 8, str(item), border=1, align='L')
            pdf.set_xy(x + col_widths[i], y)
        pdf.ln(max_height)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
        pdf.output(tmpfile.name)
        tmpfile.seek(0)
        pdf_bytes = tmpfile.read()
    return pdf_bytes

def dataframe_to_pdf_reportlab(df, title="Reasoning Results"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
        doc = SimpleDocTemplate(tmpfile.name, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        # Title
        elements.append(Paragraph(f"<b>{title}</b>", styles['Title']))
        # Prepare data for table (headers + rows)
        data = [list(df.columns)]
        for _, row in df.iterrows():
            data.append([Paragraph(str(cell), styles['BodyText']) for cell in row])
        # Create table
        table = Table(data, repeatRows=1)
        # Style the table
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        elements.append(table)
        doc.build(elements)
        tmpfile.seek(0)
        pdf_bytes = tmpfile.read()
    return pdf_bytes

st.set_page_config(page_title="CMC Unified SaaS (Phase 11.6)", page_icon="🔐", layout="wide")
st.title("🔐 CMC Unified SaaS Platform (Phase 11.6 Docker Build)")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.subheader("User Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        success, name, role = login(username, password)
        if success:
            st.session_state.logged_in = True
            st.session_state.user = name
            st.session_state.role = role
            st.experimental_rerun()
        else:
            st.error("Invalid username or password")
else:
    st.success(f"Welcome, {st.session_state.user}!")
    # Only show admin options to admin users
    if st.session_state.role == "admin":
        menu = st.sidebar.radio(
            "Navigate",
            ["🔎 Query Reasoning Agent", "📄 Ingest PDF", "📊 View KnowledgeBase", "🚪 Logout"]
        )
    else:
        menu = st.sidebar.radio(
            "Navigate",
            ["🔎 Query Reasoning Agent", "🚪 Logout"]
        )
    kb = load_kb()

    if menu == "📄 Ingest PDF" and st.session_state.role == "admin":
        st.header("📄 Ingest New Regulatory PDF")
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
        modality = st.text_input("Modality (e.g., mAb, ADC, CAR-T, AAV Gene Therapy, Small Molecule)")
        phase = st.text_input("Phase (e.g., Phase 1, Phase 2, Phase 3)")
        if st.button("Ingest"):
            if uploaded_file and modality and phase:
                with open("uploaded.pdf", "wb") as f:
                    f.write(uploaded_file.read())
                new_results = ingest_pdf("uploaded.pdf", modality, phase)
                if new_results:
                    new_records = []
                    for cqa, test in new_results:
                        new_records.append({
                            "Modality": modality, "Phase": phase, "CQA": cqa,
                            "Test Methods": test, "Justification": "AI Extracted",
                            "Regulatory Source": "PDF-LLM", "Control Action": "Specification"
                        })
                    new_df = pd.DataFrame(new_records)
                    kb = pd.concat([kb, new_df], ignore_index=True)
                    save_kb(kb)
                    st.success(f"Ingestion complete. {len(new_df)} new records added!")
                else:
                    st.warning("No extractable data found in PDF.")
            else:
                st.warning("Please upload a PDF and fill modality and phase.")

    elif menu == "🔎 Query Reasoning Agent":
        st.header("🔎 Reasoning Agent")
        modality = st.selectbox("Select Modality", sorted(kb["Modality"].unique()))
        phase = st.selectbox("Select Phase", sorted(kb["Phase"].unique()))
        if st.button("Run Reasoning Query"):
            result_df = query_reasoning(modality, phase, kb)
            st.dataframe(result_df, use_container_width=True)
            pdf_bytes = dataframe_to_pdf_reportlab(result_df)
            st.download_button(
                label="Download Results as PDF",
                data=pdf_bytes,
                file_name="reasoning_results.pdf",
                mime="application/pdf"
            )

    elif menu == "📊 View KnowledgeBase":
        st.header("📊 Current KnowledgeBase")
        st.dataframe(kb, use_container_width=True)
        st.download_button("Download KnowledgeBase CSV", kb.to_csv(index=False), file_name="CQA_KnowledgeBase_Master.csv")

    elif menu == "🚪 Logout":
        st.session_state.logged_in = False
        st.experimental_rerun()
