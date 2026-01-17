import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
from datetime import datetime, timedelta
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import io

from ocr_pipeline import preprocess_image, extract_text,create_download_link, process_invoice_file
from pdf2image import convert_from_bytes
from database import (
    init_db,
    save_invoice,
    get_or_create_user,      # ← needed to get user_id from username
    get_user_invoices,       # ← to load history
    get_invoice_by_id,
    delete_invoices_by_ids   # ← for deletion
)

# Initialize database
init_db()


# User login
st.sidebar.title("🔐 Login")
username = st.sidebar.text_input("Username", value="demo_user").strip()
if not username:
    st.sidebar.warning("Please enter a username")
    st.stop()

# Get user_id from username
user_id = get_or_create_user(username)
st.sidebar.success(f"✅ {username}")



st.title('Receipt Invoice and Digitizer')


# Total pages
pages = {
    "🏠 Home": "home",
    "🔍 Analyzer": "analyzer",
    "📊 Dashboard": "dashboard",
    "📜 History": "history",
    "💬 Support": "support",
    "⚙️ Settings": "settings"
}

# Sidebar navigation
selection = st.sidebar.radio("Go to", list(pages.keys()))



#tab 1: Home
if selection == "🏠 Home":
    st.subheader("About the Project")
    left_col, right_col = st.columns([1, 1])

    with right_col:
        st.image("RID.jpg", width=500)

    with left_col:
        st.write("The Receipt and Invoice Digitizer is an AI-driven system that automates the digitization and processing of physical and digital receipts and invoices using Optical Character Recognition (OCR) and Natural Language Processing (NLP), reducing manual effort and improving accuracy in financial operations.")

    st.subheader("Features:")
    st.markdown("""
    * Automated OCR-based text extraction from scanned receipts and invoices
    * Field-level parsing for date, vendor, amount, tax, and line items.
    * A searchable database of receipts and invoices with metadata.
    * Web-based dashboard for uploading files, reviewing extracted data, and downloading CSV/Excel reports.
    * Error handling & validation (e.g., duplicate receipts, invalid totals).
    """)



# tab 2: Analyzer
elif selection == "🔍 Analyzer":
    st.subheader("Receipt Analyzer")
    st.write("Analyzes your Recipt!")

    # Widget for multiple file uploads
    uploaded_files = st.file_uploader(
        "Choose files(single/mutiples) ... ",
        type=["png", "jpg", "jpeg", "pdf"],
        accept_multiple_files=True
    )


    if uploaded_files:
        results= []

        for uploaded_file in uploaded_files:
            st.subheader(f"Processing: {uploaded_file.name}")

            # 1. Read file bytes ONCE
            file_bytes = uploaded_file.read()
            uploaded_file.seek(0)  # Reset pointer

            try:
                result = process_invoice_file(file_bytes, uploaded_file.name)

                # 3. Show preview (PDF or image)
                if uploaded_file.name.lower().endswith('.pdf'):
                    from pdf2image import convert_from_bytes
                    pages = convert_from_bytes(file_bytes, dpi=200)
                    col1, col2 = st.columns(2)
                    with col1:
                        st.image(pages[0], caption="First Page (Original)", use_column_width=True)
                    with col2:
                        processed_img = preprocess_image(pages[0])
                        st.image(processed_img, caption="Preprocessed", use_column_width=True)
                    full_text = result["raw_text"]

                else:
                    image = Image.open(io.BytesIO(file_bytes))
                    col1, col2 = st.columns(2)
                    with col1:
                        st.image(image, caption="Original", use_column_width=True)
                    with col2:
                        processed_img = preprocess_image(image)
                        st.image(processed_img, caption="Preprocessed", use_column_width=True)
                    full_text = result["raw_text"]


                # 4. Display extracted text
                st.text_area("Extracted Text", full_text, height=400)

                # 5. ✅ SAVE TO DATABASE
                save_invoice(user_id, uploaded_file.name, file_bytes, result)

                st.success("✅ Invoice saved to History Vault!")

            except Exception as e:
                st.error(f"Error processing {uploaded_file.name}: {str(e)}")



# tab 3:dashboard
elif selection == "📊 Dashboard":
    st.subheader("User's Dasboard")

    # Generate mock data
    data = {
        'date': [datetime.now() - timedelta(days=i) for i in range(100)],
        'vendor': ['Amazon', 'Walmart', 'Starbucks', 'Shell'] * 25,
        'category': ['Shopping', 'Groceries', 'Food', 'Transport'] * 25,
        'total': [25.99, 89.50, 4.75, 45.00] * 25,
        'payment_method': ['Card', 'Cash', 'Card', 'Digital'] * 25
    }
    df = pd.DataFrame(data)


    # 1. Spending by Category
    category_spending = df.groupby('category')['total'].sum().sort_values(ascending=False)

    plt.figure(figsize=(8, 6))
    plt.pie(
        category_spending.values,
        labels=category_spending.index,
        autopct='%1.1f%%',
        startangle=140,
        colors=plt.cm.Set3.colors
    )
    plt.title('Spending by Category', fontsize=14, fontweight='bold')
    plt.tight_layout()
    st.pyplot(plt)



    # 2. Monthly Spending Trend
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)

    # Resample to monthly total
    monthly_spending = df.resample('ME')['total'].sum()

    plt.figure(figsize=(10, 4))
    plt.plot(monthly_spending.index, monthly_spending.values, marker='o', linewidth=2, markersize=6)
    plt.title('Monthly Spending Trend', fontsize=14, fontweight='bold')
    plt.xlabel('Month')
    plt.ylabel('Total Spent ($)')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    st.pyplot(plt)





    # 3. Top 10 Vendors by Spend
    top_vendors = df.groupby('vendor')['total'].sum().nlargest(10)

    plt.figure(figsize=(10, 5))
    bars = plt.barh(top_vendors.index, top_vendors.values, color='#4CAF50')
    plt.title('Top 10 Vendors by Total Spend', fontsize=14, fontweight='bold')
    plt.xlabel('Total Spent ($)')
    plt.tight_layout()
    st.pyplot(plt)



    #4. Average Transaction Value Over Time

    df.reset_index(inplace=True)  # If 'date' was index
    df['month'] = df['date'].dt.to_period('M')
    avg_transaction = df.groupby('month')['total'].mean()

    plt.figure(figsize=(10, 4))
    plt.plot(avg_transaction.index.astype(str), avg_transaction.values, marker='s', color='#FF6B6B')
    plt.title('Average Transaction Value by Month', fontsize=14, fontweight='bold')
    plt.xlabel('Month')
    plt.ylabel('Avg. Spend per Receipt ($)')
    plt.xticks(rotation=45)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    st.pyplot(plt)


    #5. Payment Method Distribution
    payment_counts = df['payment_method'].value_counts()

    plt.figure(figsize=(7, 5))
    plt.bar(payment_counts.index, payment_counts.values, color='#2196F3')
    plt.title('Payment Method Usage', fontsize=14, fontweight='bold')
    plt.ylabel('Number of Transactions')
    plt.xticks(rotation=0)
    plt.tight_layout()
    st.pyplot(plt)





# tab 4: History
elif selection == "📜 History":
    st.subheader("User's History")

    # Fetch all invoices for user
    invoices = get_user_invoices(user_id)

    if not invoices:
        st.info("📭 No invoices saved yet.")
    else:
        #  Define all expected columns
        expected_cols = ['id', 'filename', 'vendor', 'invoice_id', 'date', 'total_amount', 'upload_time']

        #  Fill missing keys with empty strings
        normalized_invoices = []
        for inv in invoices:
            normalized = {}
            for col in expected_cols:
                # Extract from top-level or nested 'fields'
                if col in inv:
                    normalized[col] = inv[col]
                elif 'fields' in inv and col in inv['fields']:
                    normalized[col] = inv['fields'][col]
                else:
                    normalized[col] = ""  # ← fallback
            normalized_invoices.append(normalized)

        # Create DataFrame
        df = pd.DataFrame(normalized_invoices)

        # Format upload_time
        if 'upload_time' in df.columns:
            df['upload_time'] = pd.to_datetime(df['upload_time'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')

        # Now safe to select columns
        display_cols = ['id', 'filename', 'vendor', 'invoice_id', 'date', 'total_amount', 'upload_time']
        df_display = df[display_cols].copy()

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        selected_id = st.selectbox(
            "View details",
            options=[None] + df_display["id"].tolist(),  # Add None as first option
            format_func=lambda x: "Select an invoice..." if x is None else f"ID {x}: {df_display[df_display['id']==x]['filename'].iloc[0]}",
            index=0  # Default to first item (the "Select..." placeholder)
        )

        if selected_id:
            full_invoice = get_invoice_by_id(selected_id)
            if full_invoice:
                st.subheader(f"📄 {full_invoice['filename']}")

                # Try to show preview
                file_bytes = full_invoice["file_data"]
                filename = full_invoice["filename"]

                if filename.lower().endswith('.pdf'):
                    st.info("📄 This is a PDF document")
                    try:
                        # Convert first page to image for preview
                        from pdf2image import convert_from_bytes
                        first_page = convert_from_bytes(file_bytes, dpi=100, first_page=1, last_page=1)[0]
                        st.image(first_page, caption="First Page Preview", use_column_width=True)
                    except Exception as e:
                        st.error(f"❌ Could not generate preview: {str(e)}")
                else:
                    # It's an image
                    try:
                        img = Image.open(io.BytesIO(file_bytes))
                        st.image(img, caption="Original Image", use_column_width=True)
                    except Exception as e:
                        st.error(f"❌ Invalid image: {str(e)}")

                # Show fields and text
                st.json(full_invoice["fields"])
                st.text_area("Extracted Text", full_invoice["raw_text"], height=300)

        # Multi-select for deletion
        selected_ids = st.multiselect(
            "Select invoices to delete:",
            options=df_display['id'].tolist(),
            format_func=lambda x: f"ID {x}: {df_display[df_display['id']==x]['filename'].iloc[0]}"
            )

        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("🗑️ Delete Selected", type="primary"):
                if selected_ids:
                    delete_invoices_by_ids(user_id, selected_ids)
                    st.success(f"Deleted {len(selected_ids)} invoice(s).")
                    st.rerun()  # Refresh page to reflect deletion


# tab 5: Chat Support
elif selection == "💬 Support":
    st.subheader("Ask your Queries about bills")

    # Load API key (do this once at top of app.py ideally, but okay here too)
    load_dotenv()
    API_KEY = os.getenv("GEMINI_API_KEY")
    if not API_KEY:
        st.error("❌ GEMINI_API_KEY not found in .env file!")
        st.stop()
    genai.configure(api_key=API_KEY)

    # ✅ CORRECT: Create actual model object
    model = genai.GenerativeModel("gemini-2.5-flash")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Handle user input
    if prompt := st.chat_input("Ask about your bills..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Prepare history for Gemini (exclude current user message)
        history = []
        for msg in st.session_state.messages[:-1]:  # ← exclude the one we just added
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})

        # Stream response
        with st.chat_message("assistant"):
            try:
                # ✅ Now use the REAL model object
                chat = model.start_chat(history=history)
                response = chat.send_message(
                    prompt,
                    stream=True,
                    safety_settings={
                        'HATE': 'BLOCK_NONE',
                        'HARASSMENT': 'BLOCK_NONE',
                    }
                )

                full_response = ""
                placeholder = st.empty()
                for chunk in response:
                    if chunk.text:
                        full_response += chunk.text
                        placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)

                # ✅ Fix: append to "messages", not "support_chat_messages"
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            except Exception as e:
                st.error(f"An error occurred: {e}")


# tab 6: Environment Settings
elif selection == "⚙️ Settings":
    st.subheader("Environment Settings")
    google_api_key = st.text_input(
    "Enter the Google API key:",
    type="password"  # masking of password.
)
