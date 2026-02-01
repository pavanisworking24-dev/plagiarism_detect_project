import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
import re
import hashlib
import base64
import io

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="Plagiarism Detection System",
    page_icon="🎓",
    layout="wide"
)

# ========== PLAGIARISM DETECTION ==========
def clean_text(text):
    """Clean text for comparison"""
    if not isinstance(text, str) or not text.strip():
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters, numbers, and extra spaces
    text = re.sub(r'[^a-z\s]', ' ', text)
    text = ' '.join(text.split())
    
    return text

def calculate_similarity(text1, text2):
    """Calculate similarity between two texts"""
    if not text1 or not text2:
        return 0.0
    
    # Clean texts
    text1_clean = clean_text(text1)
    text2_clean = clean_text(text2)
    
    # Skip if too short
    if len(text1_clean) < 50 or len(text2_clean) < 50:
        return 0.0
    
    # Split into words
    words1 = set(text1_clean.split())
    words2 = set(text2_clean.split())
    
    # Calculate Jaccard Similarity
    common = words1.intersection(words2)
    all_words = words1.union(words2)
    
    if not all_words:
        return 0.0
    
    similarity = len(common) / len(all_words)
    return min(similarity * 100, 100.0)

def check_plagiarism(new_text, previous_texts):
    """Check plagiarism against multiple texts"""
    if not previous_texts:
        return 0.0
    
    max_score = 0.0
    
    for prev_text in previous_texts:
        if prev_text and isinstance(prev_text, str):
            score = calculate_similarity(new_text, prev_text)
            if score > max_score:
                max_score = score
    
    # Only show significant matches (>10%)
    return max_score if max_score >= 10 else 0.0

# ========== FILE EXTRACTION ==========
def extract_text_from_pdf(file_bytes):
    """Extract text from PDF using pure Python"""
    try:
        # Check if PyPDF2 is available
        try:
            import PyPDF2
            # Create PDF reader from bytes
            pdf_file = io.BytesIO(file_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            # Extract text from first 10 pages (to avoid large files)
            for i in range(min(10, len(pdf_reader.pages))):
                page = pdf_reader.pages[i]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            if text.strip():
                return text
            else:
                return "[PDF appears to be scanned/image-based. Text extraction limited.]"
                
        except ImportError:
            return "[PDF processing requires PyPDF2. Please install or use TXT files.]"
            
    except Exception as e:
        return f"[Error reading PDF: {str(e)[:100]}]"

def extract_text_from_docx(file_bytes):
    """Extract text from DOCX using pure Python"""
    try:
        # Check if python-docx is available
        try:
            import docx
            from docx import Document
            
            # Create document from bytes
            doc_file = io.BytesIO(file_bytes)
            doc = Document(doc_file)
            
            text = ""
            # Extract text from paragraphs
            for para in doc.paragraphs:
                if para.text.strip():
                    text += para.text + "\n"
            
            if text.strip():
                return text
            else:
                return "[Could not extract text from DOCX file]"
                
        except ImportError:
            return "[DOCX processing requires python-docx. Please install or use TXT files.]"
            
    except Exception as e:
        return f"[Error reading DOCX: {str(e)[:100]}]"

def extract_text_from_file(uploaded_file):
    """Extract text from any supported file type"""
    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name.lower()
    
    if file_name.endswith('.txt'):
        # For text files
        try:
            return uploaded_file.read().decode('utf-8', errors='ignore')
        except:
            return ""
    
    elif file_name.endswith('.pdf'):
        # For PDF files
        return extract_text_from_pdf(file_bytes)
    
    elif file_name.endswith(('.docx', '.doc')):
        # For Word documents
        return extract_text_from_docx(file_bytes)
    
    else:
        return f"[Unsupported file format: {uploaded_file.name}]"

# ========== DATABASE FUNCTIONS ==========
def init_database():
    """Initialize CSV database"""
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("database", exist_ok=True)
    
    # Users database
    if not os.path.exists("database/users.csv"):
        users_df = pd.DataFrame(columns=['username', 'password', 'name', 'role', 'email'])
        
        # Default accounts
        default_users = pd.DataFrame([
            {
                'username': 'teacher',
                'password': hash_password('teacher123'),
                'name': 'Admin Teacher',
                'role': 'teacher',
                'email': 'teacher@school.edu'
            },
            {
                'username': 'student1',
                'password': hash_password('student123'),
                'name': 'John Doe',
                'role': 'student',
                'email': 'john@student.edu'
            },
            {
                'username': 'student2',
                'password': hash_password('student123'),
                'name': 'Jane Smith',
                'role': 'student',
                'email': 'jane@student.edu'
            }
        ])
        
        users_df = pd.concat([users_df, default_users], ignore_index=True)
        users_df.to_csv("database/users.csv", index=False)
    
    # Submissions database
    if not os.path.exists("database/submissions.csv"):
        submissions_df = pd.DataFrame(columns=[
            'id', 'student_name', 'student_id', 'filename', 'file_type',
            'word_count', 'char_count', 'text_preview', 'submission_time', 
            'plagiarism_score', 'status'
        ])
        submissions_df.to_csv("database/submissions.csv", index=False)

def hash_password(password):
    """Simple password hashing"""
    return hashlib.md5(password.encode()).hexdigest()

def authenticate_user(username, password):
    """Check user credentials"""
    try:
        users_df = pd.read_csv("database/users.csv")
        hashed_pwd = hash_password(password)
        user = users_df[(users_df['username'] == username) & (users_df['password'] == hashed_pwd)]
        
        if len(user) > 0:
            return user.iloc[0].to_dict()
    except Exception as e:
        st.error(f"Auth error: {e}")
    
    return None

def register_user(username, password, name, email):
    """Register new user"""
    try:
        users_df = pd.read_csv("database/users.csv")
        
        # Check if username exists
        if username in users_df['username'].values:
            return False, "Username already exists"
        
        # Add new user
        new_user = pd.DataFrame([{
            'username': username,
            'password': hash_password(password),
            'name': name,
            'role': 'student',
            'email': email
        }])
        
        users_df = pd.concat([users_df, new_user], ignore_index=True)
        users_df.to_csv("database/users.csv", index=False)
        return True, "Registration successful"
        
    except Exception as e:
        return False, f"Error: {str(e)}"

def save_submission_to_db(student_name, student_id, filename, file_type, text_content, plagiarism_score):
    """Save submission to database"""
    try:
        df = pd.read_csv("database/submissions.csv")
        
        new_row = pd.DataFrame([{
            'id': len(df) + 1,
            'student_name': student_name,
            'student_id': student_id,
            'filename': filename,
            'file_type': file_type.upper(),
            'word_count': len(text_content.split()),
            'char_count': len(text_content),
            'text_preview': text_content[:300],  # Store preview
            'submission_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'plagiarism_score': plagiarism_score,
            'status': 'Submitted'
        }])
        
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv("database/submissions.csv", index=False)
        
        # Save original file
        filepath = f"uploads/{filename}"
        with open(filepath, 'wb') as f:
            f.write(io.BytesIO(st.session_state.uploaded_file_bytes).getvalue())
        
        return True
        
    except Exception as e:
        st.error(f"Database error: {e}")
        return False

def get_previous_submissions():
    """Get all previous submissions"""
    try:
        if os.path.exists("database/submissions.csv"):
            df = pd.read_csv("database/submissions.csv")
            if 'text_preview' in df.columns:
                return df['text_preview'].dropna().astype(str).tolist()
    except:
        pass
    return []

def get_all_submissions_data():
    """Get complete submissions data"""
    try:
        if os.path.exists("database/submissions.csv"):
            return pd.read_csv("database/submissions.csv")
    except:
        pass
    return pd.DataFrame()

# ========== UI COMPONENTS ==========
def show_login_page():
    """Login/Register page"""
    st.title("🎓 Plagiarism Detection System")
    st.markdown("### Submit assignments and check for plagiarism automatically")
    
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    
    with tab1:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
        
        with col2:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            if st.button("Login", type="primary", use_container_width=True):
                if username and password:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_info = user
                        st.success(f"Welcome {user['name']}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.warning("Please enter both username and password")
            
            st.markdown("---")
            st.caption("**Demo Accounts:**")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if st.button("👨‍🏫 Teacher", use_container_width=True):
                    st.session_state.logged_in = True
                    st.session_state.user_info = {
                        'username': 'teacher',
                        'name': 'Admin Teacher',
                        'role': 'teacher'
                    }
                    st.rerun()
            with col_b:
                if st.button("👨‍🎓 Student 1", use_container_width=True):
                    st.session_state.logged_in = True
                    st.session_state.user_info = {
                        'username': 'student1',
                        'name': 'John Doe',
                        'role': 'student'
                    }
                    st.rerun()
            with col_c:
                if st.button("👩‍🎓 Student 2", use_container_width=True):
                    st.session_state.logged_in = True
                    st.session_state.user_info = {
                        'username': 'student2',
                        'name': 'Jane Smith',
                        'role': 'student'
                    }
                    st.rerun()
    
    with tab2:
        st.subheader("Create Student Account")
        
        with st.form("register_form"):
            name = st.text_input("Full Name")
            email = st.text_input("Email Address")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            confirm = st.text_input("Confirm Password", type="password")
            
            submitted = st.form_submit_button("Create Account", type="primary")
            
            if submitted:
                if not all([name, email, username, password]):
                    st.error("Please fill all fields")
                elif password != confirm:
                    st.error("Passwords do not match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, message = register_user(username, password, name, email)
                    if success:
                        st.success("✅ Account created successfully!")
                        st.info("You can now login with your credentials")
                    else:
                        st.error(f"❌ {message}")

def show_student_dashboard():
    """Student dashboard"""
    user = st.session_state.user_info
    
    st.title(f"👨‍🎓 Welcome, {user['name']}")
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📤 Submit Assignment", "📋 My Submissions", "📊 My Stats"])
    
    with tab1:
        st.header("Submit New Assignment")
        
        # Student info
        student_id = st.text_input("Student ID", value=user.get('username', ''))
        
        # File upload section
        st.subheader("Upload Your Assignment")
        st.info("**Supported formats:** TXT, PDF, DOCX (Max: 10MB)")
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['txt', 'pdf', 'docx', 'doc'],
            help="Upload your assignment file"
        )
        
        if uploaded_file:
            # Store file bytes for later use
            st.session_state.uploaded_file_bytes = uploaded_file.getvalue()
            
            # Extract text
            with st.spinner("📖 Reading file content..."):
                extracted_text = extract_text_from_file(uploaded_file)
            
            if extracted_text and not extracted_text.startswith("["):
                # Show file info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("File", uploaded_file.name)
                with col2:
                    file_size = len(st.session_state.uploaded_file_bytes) / 1024
                    st.metric("Size", f"{file_size:.1f} KB")
                with col3:
                    file_type = uploaded_file.name.split('.')[-1].upper()
                    st.metric("Type", file_type)
                
                # Show text preview
                with st.expander("📄 Preview Extracted Text", expanded=True):
                    preview = extracted_text[:1500]
                    if len(extracted_text) > 1500:
                        preview += "...\n\n[Text truncated for preview]"
                    st.text_area("", preview, height=250, label_visibility="collapsed")
                
                # Text statistics
                word_count = len(extracted_text.split())
                char_count = len(extracted_text)
                
                st.caption(f"📊 Text extracted: {word_count} words, {char_count} characters")
                
                # Check plagiarism button
                if st.button("🔍 Check for Plagiarism", type="primary", use_container_width=True):
                    with st.spinner("🔬 Analyzing for plagiarism..."):
                        # Get previous submissions
                        previous_texts = get_previous_submissions()
                        
                        # Calculate plagiarism score
                        plagiarism_score = check_plagiarism(extracted_text, previous_texts)
                        
                        # Display results
                        st.markdown("---")
                        st.subheader("📊 Plagiarism Analysis Results")
                        
                        # Score with color coding
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if plagiarism_score == 0:
                                st.success("✅ **ORIGINAL**")
                                st.metric("Score", f"{plagiarism_score:.1f}%")
                            elif plagiarism_score < 30:
                                st.info("📊 **LOW SIMILARITY**")
                                st.metric("Score", f"{plagiarism_score:.1f}%")
                            elif plagiarism_score < 70:
                                st.warning("⚠️ **MODERATE SIMILARITY**")
                                st.metric("Score", f"{plagiarism_score:.1f}%")
                            else:
                                st.error("🚨 **HIGH SIMILARITY**")
                                st.metric("Score", f"{plagiarism_score:.1f}%")
                        
                        with col2:
                            st.metric("Compared With", f"{len(previous_texts)} submissions")
                        
                        with col3:
                            # Submit button
                            if st.button("✅ Submit Assignment", type="primary", use_container_width=True):
                                filename = f"{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
                                
                                success = save_submission_to_db(
                                    user['name'],
                                    student_id,
                                    filename,
                                    file_type,
                                    extracted_text,
                                    plagiarism_score
                                )
                                
                                if success:
                                    st.success("✅ Assignment submitted successfully!")
                                    st.balloons()
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error("Failed to save submission")
                        
                        # Interpretation
                        st.markdown("---")
                        if plagiarism_score == 0:
                            st.success("**Interpretation:** Excellent! This appears to be original work with no significant matches to previous submissions.")
                        elif plagiarism_score < 30:
                            st.info("**Interpretation:** Low similarity detected. Common phrases or coincidental matches.")
                        elif plagiarism_score < 70:
                            st.warning("**Interpretation:** Moderate similarity detected. Review recommended for potential paraphrasing.")
                        else:
                            st.error("**Interpretation:** High similarity detected. Possible plagiarism. Further investigation required.")
            else:
                st.error("❌ Could not extract text from file. Please try a different file or format.")
                if extracted_text:
                    st.warning(f"Extraction issue: {extracted_text}")
    
    with tab2:
        st.header("My Submission History")
        
        df = get_all_submissions_data()
        
        if not df.empty and 'student_name' in df.columns:
            # Filter student's submissions
            student_subs = df[df['student_name'] == user['name']]
            
            if not student_subs.empty:
                # Format for display
                display_cols = ['filename', 'file_type', 'word_count', 'submission_time', 'plagiarism_score']
                display_df = student_subs[display_cols].copy()
                display_df.columns = ['File', 'Type', 'Words', 'Time', 'Plagiarism %']
                display_df = display_df.sort_values('Time', ascending=False)
                
                # Color coding for plagiarism
                def color_score(val):
                    if val > 70:
                        return 'background-color: #ffcccc'
                    elif val > 40:
                        return 'background-color: #fff3cd'
                    else:
                        return 'background-color: #d4edda'
                
                styled_df = display_df.style.applymap(color_score, subset=['Plagiarism %'])
                st.dataframe(styled_df, use_container_width=True)
                
                # Download option
                csv = student_subs.to_csv(index=False)
                st.download_button(
                    "📥 Download My Submissions",
                    csv,
                    f"my_submissions_{user['name']}.csv",
                    "text/csv",
                    use_container_width=True
                )
            else:
                st.info("📭 No submissions yet. Submit your first assignment!")
        else:
            st.info("📭 No submission history available.")
    
    with tab3:
        st.header("My Statistics")
        
        df = get_all_submissions_data()
        
        if not df.empty and 'student_name' in df.columns:
            student_subs = df[df['student_name'] == user['name']]
            
            if not student_subs.empty:
                # Calculate statistics
                total_subs = len(student_subs)
                avg_score = student_subs['plagiarism_score'].mean()
                latest_score = student_subs.iloc[-1]['plagiarism_score'] if total_subs > 0 else 0
                high_risk = len(student_subs[student_subs['plagiarism_score'] > 50])
                
                # Display metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Submissions", total_subs)
                with col2:
                    st.metric("Average Score", f"{avg_score:.1f}%")
                with col3:
                    st.metric("Latest Score", f"{latest_score:.1f}%")
                with col4:
                    st.metric("High Risk", high_risk)
                
                # Progress bars
                st.subheader("Score Distribution")
                
                safe = len(student_subs[student_subs['plagiarism_score'] <= 30])
                moderate = len(student_subs[(student_subs['plagiarism_score'] > 30) & 
                                          (student_subs['plagiarism_score'] <= 70)])
                high = len(student_subs[student_subs['plagiarism_score'] > 70])
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.progress(safe/total_subs if total_subs > 0 else 0)
                    st.caption(f"Safe ({safe})")
                with col2:
                    st.progress(moderate/total_subs if total_subs > 0 else 0)
                    st.caption(f"Moderate ({moderate})")
                with col3:
                    st.progress(high/total_subs if total_subs > 0 else 0)
                    st.caption(f"High ({high})")
                
                # Score trend
                if total_subs > 1:
                    st.subheader("Score Trend Over Time")
                    trend_df = student_subs[['submission_time', 'plagiarism_score']].copy()
                    trend_df['submission_time'] = pd.to_datetime(trend_df['submission_time'])
                    trend_df = trend_df.sort_values('submission_time')
                    st.line_chart(trend_df.set_index('submission_time')['plagiarism_score'])
            else:
                st.info("Submit your first assignment to see statistics!")
        else:
            st.info("No statistics available yet.")

def show_teacher_dashboard():
    """Teacher dashboard"""
    st.title("👨‍🏫 Teacher Dashboard")
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📊 All Submissions", "🚨 High Risk Cases", "⚙️ Management"])
    
    with tab1:
        st.header("All Student Submissions")
        
        df = get_all_submissions_data()
        
        if not df.empty:
            # Summary statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total", len(df))
            with col2:
                avg_score = df['plagiarism_score'].mean()
                st.metric("Avg. Score", f"{avg_score:.1f}%")
            with col3:
                high_risk = len(df[df['plagiarism_score'] > 50])
                st.metric("High Risk", high_risk)
            with col4:
                students = df['student_name'].nunique()
                st.metric("Students", students)
            
            # Filters
            st.subheader("Filters")
            col1, col2 = st.columns(2)
            with col1:
                min_score = st.slider("Minimum Score %", 0, 100, 0)
            with col2:
                max_score = st.slider("Maximum Score %", 0, 100, 100)
            
            # Apply filters
            filtered_df = df[
                (df['plagiarism_score'] >= min_score) & 
                (df['plagiarism_score'] <= max_score)
            ]
            
            # Sort options
            sort_by = st.selectbox("Sort by", 
                ['Submission Time (Newest)', 'Plagiarism Score (Highest)', 'Student Name'])
            
            if sort_by == 'Submission Time (Newest)':
                filtered_df = filtered_df.sort_values('submission_time', ascending=False)
            elif sort_by == 'Plagiarism Score (Highest)':
                filtered_df = filtered_df.sort_values('plagiarism_score', ascending=False)
            else:
                filtered_df = filtered_df.sort_values('student_name')
            
            # Display table
            if not filtered_df.empty:
                display_cols = ['student_name', 'student_id', 'filename', 'file_type', 
                              'word_count', 'submission_time', 'plagiarism_score']
                
                # Color coding function
                def highlight_row(row):
                    if row['plagiarism_score'] > 70:
                        return ['background-color: #ffcccc'] * len(row)
                    elif row['plagiarism_score'] > 40:
                        return ['background-color: #fff3cd'] * len(row)
                    return ['background-color: #d4edda'] * len(row)
                
                styled_df = filtered_df[display_cols].style.apply(highlight_row, axis=1)
                st.dataframe(styled_df, use_container_width=True, height=400)
                
                # Download button
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    "📥 Download Full Report",
                    csv,
                    "plagiarism_report.csv",
                    "text/csv",
                    use_container_width=True
                )
                
                # Visualization
                st.subheader("📈 Score Distribution")
                st.bar_chart(filtered_df['plagiarism_score'].value_counts().sort_index())
            else:
                st.info("No submissions match the selected filters")
        else:
            st.info("No submissions in the system yet.")
    
    with tab2:
        st.header("🚨 High Plagiarism Cases")
        
        df = get_all_submissions_data()
        
        if not df.empty:
            # Get high risk cases
            high_risk = df[df['plagiarism_score'] > 50]
            
            if not high_risk.empty:
                st.warning(f"⚠️ Found {len(high_risk)} submissions with plagiarism > 50%")
                
                # Group by student
                student_stats = high_risk.groupby('student_name').agg({
                    'plagiarism_score': ['count', 'mean', 'max'],
                    'filename': lambda x: list(x)[:3]
                }).round(1)
                
                student_stats.columns = ['Count', 'Average %', 'Max %', 'Files']
                student_stats = student_stats.sort_values('Max %', ascending=False)
                
                st.dataframe(student_stats, use_container_width=True)
                
                # Action buttons
                st.subheader("Actions")
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📧 Send Warning", use_container_width=True):
                        st.success("Warning emails sent to selected students")
                with col2:
                    if st.button("📝 Request Explanation", use_container_width=True):
                        st.success("Explanation requests sent")
                with col3:
                    if st.button("🔍 Detailed Report", use_container_width=True):
                        st.success("Detailed report generated")
                
                # View suspicious submissions
                st.subheader("Suspicious Submissions")
                for idx, row in high_risk.iterrows():
                    with st.expander(f"{row['student_name']} - {row['filename']} ({row['plagiarism_score']}%)"):
                        st.write(f"**Student ID:** {row['student_id']}")
                        st.write(f"**File Type:** {row['file_type']}")
                        st.write(f"**Words:** {row['word_count']}")
                        st.write(f"**Time:** {row['submission_time']}")
                        st.write(f"**Text Preview:** {row.get('text_preview', 'N/A')[:200]}...")
            else:
                st.success("✅ No high plagiarism cases detected!")
        else:
            st.info("No data available")
    
    with tab3:
        st.header("System Management")
        
        # Create assignment
        st.subheader("Create New Assignment")
        
        with st.form("create_assignment"):
            title = st.text_input("Assignment Title")
            description = st.text_area("Description")
            deadline = st.date_input("Deadline")
            
            if st.form_submit_button("Create Assignment", type="primary"):
                st.success(f"Assignment '{title}' created with deadline {deadline}")
        
        # System info
        st.subheader("System Information")
        
        info_col1, info_col2 = st.columns(2)
        
        with info_col1:
            st.metric("Total Users", "Multiple")
            st.metric("Storage Used", "CSV Based")
            st.metric("File Support", "TXT/PDF/DOCX")
        
        with info_col2:
            st.metric("Algorithm", "Jaccard Similarity")
            st.metric("Detection", "Real-time")
            st.metric("Reports", "CSV Export")

# ========== MAIN APP ==========
def main():
    # Initialize database
    init_database()
    
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_info = {}
    
    # Sidebar
    with st.sidebar:
        st.title("🎓 Plagiarism System")
        
        if st.session_state.logged_in:
            user = st.session_state.user_info
            st.success(f"Logged in as:\n**{user['name']}**")
            st.caption(f"Role: {user['role'].title()}")
            
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user_info = {}
                st.rerun()
        else:
            st.info("Please login to continue")
        
        st.markdown("---")
        st.caption("""
        **Features:**
        - 📤 Upload TXT, PDF, DOCX
        - 🔍 Real-time plagiarism check
        - 📊 Student & Teacher dashboards
        - 📥 Export CSV reports
        - 🚨 High-risk detection
        
        **Quick Login:**
        - Teacher: teacher/teacher123
        - Student1: student1/student123
        - Student2: student2/student123
        """)
        
        st.markdown("---")
        st.caption("For issues: Use TXT files if PDF/DOCX don't work initially")

    # Main content
    if not st.session_state.logged_in:
        show_login_page()
    else:
        user = st.session_state.user_info
        if user['role'] == 'student':
            show_student_dashboard()
        else:
            show_teacher_dashboard()

# ========== RUN APP ==========
if __name__ == "__main__":
    main()
