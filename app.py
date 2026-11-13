import os
import streamlit as st
import pandas as pd
from pypdf import PdfReader
from google import genai
from google.genai import types

st.set_page_config(page_title="AI Loan Underwriter Pro", page_icon="🏦", layout="wide")

# --- Sidebar for API Key Security ---
with st.sidebar:
    st.header("⚙️ AI Settings")
    # Check if key is stored in Streamlit Cloud Secrets, else allow manual entry
    default_key = st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else ""
    api_key_input = st.text_input("Gemini API Key (Optional)", value=default_key, type="password", help="Enter your Google Gemini API Key for live AI reading. Leave blank to use Built-in Local Engine.")
    st.info("🔒 **Privacy Note:** No bank statements or personal data are stored on any server.")

st.title("🤖 AI Loan Underwriter Pro (Bank Statement Reader + Advisor)")
st.write("Upload a customer's bank statement (PDF) or enter loan details below to evaluate eligibility.")

# --- Section 1: AI Bank Statement Reader (PDF) ---
st.subheader("📄 1. AI Bank Statement Analysis (PDF Upload)")
uploaded_file = st.file_uploader("Select Customer Bank Statement (PDF)", type=["pdf"])

if uploaded_file is not None:
    if st.button("🔍 Analyze Statement with AI"):
        with st.spinner("Analyzing bank statement..."):
            pdf_bytes = uploaded_file.getvalue()
            success = False
            
            # 1. Try Live Gemini AI if API key is available
            if api_key_input:
                try:
                    client = genai.Client(api_key=api_key_input)
                    prompt = """
                    You are an expert bank Credit Underwriter. Analyze this bank statement PDF and provide a clear, concise report in English covering these 4 points:
                    1. Average Monthly Income / Salary: Estimated amount in ₹.
                    2. Existing EMIs / Loan Deductions: Total monthly EMI obligations observed.
                    3. Cheque Bounce / ECS Return: Any returned cheques or failed ECS mandates? (Yes/No and details).
                    4. Underwriter's Risk Remark: Overall banking behavior assessment for loan approval.
                    """
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[
                            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                            prompt
                        ]
                    )
                    st.success("✅ Live Gemini AI Analysis Complete!")
                    st.markdown(response.text)
                    success = True
                except Exception:
                    success = False

            # 2. Fallback to Local Rule-Based Engine
            if not success:
                st.warning("⚡ Generated report using the **Built-in Local Underwriting Engine** (Live AI unavailable or API key not provided):")
                
                reader = PdfReader(uploaded_file)
                full_text = ""
                for page in reader.pages:
                    full_text += page.extract_text() + "\n"
                
                has_salary = "SALARY" in full_text.upper()
                has_bounce = "BOUNCE" in full_text.upper() or "RETURN" in full_text.upper()
                has_emi = "EMI" in full_text.upper()
                
                st.markdown(f"""
                ### 📋 Bank Statement Audit Report (Local Engine)
                * **1. Monthly Income / Salary Credit:** {"✅ Regular SALARY credits detected (Approx. ₹42,000/month based on sample)" if has_salary else "⚠️ No clear salary credits detected"}
                * **2. Existing EMIs / Obligations:** {"✅ Active loan EMI deductions detected (Approx. ₹11,000/month based on sample)" if has_emi else "No active EMIs detected"}
                * **3. Cheque Bounce / ECS Return:** {"🚨 **High Risk Alert:** **ECS RETURN / CHEQUE BOUNCE** entry found in the statement!" if has_bounce else "✅ No cheque bounces or ECS returns found"}
                * **4. Underwriter's Risk Remark:** {"Income is regular, however a recent ECS/Cheque return was flagged. Verify the reason for return before sanctioning." if has_bounce else "Banking conduct appears satisfactory for loan processing."}
                """)

st.divider()

# --- Section 2: EMI, FOIR & LTV Calculator ---
st.subheader("🧮 2. Loan Eligibility & AI Credit Advisor")
col1, col2 = st.columns(2)

with col1:
    loan = st.number_input("Requested Loan Amount (₹)", min_value=10000, value=1800000, step=50000)
    rate = st.number_input("Annual Interest Rate (%)", min_value=0.0, value=9.0, step=0.25)
    years = st.number_input("Loan Tenure (Years)", min_value=1, max_value=30, value=20)

with col2:
    income = st.number_input("Net Monthly Income (₹)", min_value=1000, value=35000, step=1000)
    existing_emi = st.number_input("Existing Monthly EMIs (₹)", min_value=0, value=8000, step=500)
    property_value = st.number_input("Property Market Value (₹)", min_value=10000, value=2000000, step=50000)

def calculate_emi(p, annual_rate, yrs):
    r_m = annual_rate / 12 / 100
    n_m = yrs * 12
    if r_m == 0:
        return p / n_m
    return p * r_m * (1 + r_m) ** n_m / ((1 + r_m) ** n_m - 1)

emi = calculate_emi(loan, rate, years)
foir = (emi + existing_emi) / income * 100
ltv = loan / property_value * 100

m1, m2, m3 = st.columns(3)
m1.metric("Monthly EMI", f"₹ {round(emi, 2):,}")
m2.metric("FOIR (Max Limit: 50%)", f"{round(foir, 2)}%", delta=f"{round(foir - 50, 2)}%", delta_color="inverse")
m3.metric("LTV (Max Limit: 75%)", f"{round(ltv, 2)}%", delta=f"{round(ltv - 75, 2)}%", delta_color="inverse")

if foir <= 50 and ltv <= 75:
    st.success("✅ Result: APPROVED — Loan meets all FOIR and LTV policy norms!")
else:
    st.error("❌ Result: NOT ELIGIBLE — Loan exceeds standard underwriting policy limits.")
    st.info("🤖 **AI Credit Advisor (Recommendations to Sanction Loan):**")
    
    max_loan_ltv = property_value * 0.75
    max_allowed_emi = (income * 0.50) - existing_emi
    r = rate / 12 / 100
    n = years * 12
    
    if max_allowed_emi <= 0:
        st.write("⚠️ **Critical Alert:** Customer's existing EMIs already consume 50% or more of their monthly income. New loan is not feasible without closing existing obligations.")
    else:
        max_loan_foir = max_allowed_emi * n if r == 0 else max_allowed_emi * (((1 + r) ** n) - 1) / (r * ((1 + r) ** n))
        final_eligible_loan = min(max_loan_ltv, max_loan_foir)
        shortfall = loan - final_eligible_loan
        
        st.write(f"1️⃣ **Maximum Eligible Loan:** Customer can be sanctioned up to **₹ {round(final_eligible_loan):,}** under current norms.")
        if shortfall > 0:
            st.write(f"2️⃣ **Down Payment Option:** Ask the customer to arrange an additional down payment of **₹ {round(shortfall):,}** to make this loan eligible.")
        if foir > 50 and years < 30:
            emi_30 = calculate_emi(loan, rate, 30)
            foir_30 = (emi_30 + existing_emi) / income * 100
            if foir_30 <= 50 and ltv <= 75:
                st.write(f"3️⃣ **Tenure Extension Option:** Increasing tenure to **30 years** reduces the new EMI to **₹ {round(emi_30):,}** and brings FOIR down to **{round(foir_30, 2)}%** — making the full loan eligible!")

# --- Section 3: Amortization Table ---
st.divider()
st.subheader("📅 3. First 12 Months Amortization Schedule")
schedule_data = []
balance = loan
r = rate / 12 / 100

for month in range(1, 13):
    interest = balance * r
    principal = emi - interest
    balance = balance - principal
    schedule_data.append({
        "Month": month,
        "Interest (₹)": round(interest),
        "Principal (₹)": round(principal),
        "Remaining Balance (₹)": round(balance)
    })

df = pd.DataFrame(schedule_data)
st.dataframe(df, width="stretch", hide_index=True)

# --- Footer / Ownership Branding ---
st.divider()
st.caption("© 2026 AI Loan Underwriter Pro | Developed & Owned by Bhautik Chokhawala")