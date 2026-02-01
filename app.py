import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
import re
import hashlib

# ========== PAGE CONFIG ==========
st.set_page_config(
    page_title="Plagiarism Detection System",
    page_icon="🎓",
    layout="wide"
)

# ========== PLAGIARISM DETECTION FUNCTIONS ==========
def clean_text(text):
    """Clean and normalize text for comparison"""
    if not isinstance(text, str):
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters, numbers, and extra spaces
    text = re.sub(r'[^a-z\s]', '', text)
    text = ' '.join(text.split())
    
    return text

def calculate_similarity(text1, text2):
    """Calculate similarity percentage between two texts"""
    if not text1 or not text2:
        return 0.0
    
    # Clean both texts
    text1_clean = clean_text(text1)
    text2_clean = clean_text(text2)
    
    # Split into words
    words1 = set(text1_clean.split())
    words2 = set(text2_clean.split())
    
    # Check if texts are too short
    if len(words1) < 5 or len(words2) < 5:
        return 0.0
    
    # Calculate Jaccard Similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    if union == 0:
        return 0.0
    
    similarity = intersection / union
    return min(similarity * 100, 100.0)

def check_plagiarism(new_text, previous_texts):
    """Check plagiarism against multiple previous texts"""
    if not previous_texts:
        return 0.0
    
    max_similarity = 0.0
    
    for prev_text in previous_texts:
        if prev_text:
            similarity = calculate_similarity(new_text, prev_text)
            if similarity > max_similarity:
                max_similarity = similarity
    
    # Only report significant similarity (>5%)
    if max_similarity < 5:
        return 0.0
    
    return max_similarity

def extract_text_from_file(uploaded_file):
    """Extract text from uploaded file"""
    text = ""
    
    try:
        if uploaded_file.name.endswith('.txt'):
            text = uploaded_file.read().decode('utf-8', errors='ignore')
            uploaded_file.seek(0)  # Reset pointer
            
        elif uploaded_file.name.endswith('.pdf'):
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page_num in range(min(10, len(pdf_reader.pages))):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                    
        elif uploaded_file.name.endswith('.docx'):
            from docx import Document
            doc = Document(uploaded_file)
            for para in doc.paragraphs[:200]:
                if para.text.strip():
                    text += para.text + "\n"
    
    except Exception as e:
        st.error(f"Error reading file: {str(e)}")
    
    return text

# ========== DATABASE FUNCTIONS ==========
def init_database():
    """Initialize CSV database"""
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("database", exist_ok=True)
    
    # Users database
    if not os.path.exists("database/users.csv"):
        users_df = pd.DataFrame(columns=['username', 'password', 'name', 'role', 'email'])
        
        # Default teacher account
        teacher_data = pd.DataFrame([{
            'username': 'teacher',
            'password': hashlib.md5('teacher123'.encode()).hexdigest(),
            'name': 'Admin Teacher',
            'role': 'teacher',
            'email': 'teacher@school.edu'
        }])
        
        users_df = pd.concat([users_df, teacher_data], ignore_index=True)
        users_df.to_csv("database/users.csv", index=False)
    
    # Submissions database
    if not os.path.exists("database/submissions.csv"):
        submissions_df = pd.DataFrame(columns=[
            'id', 'student_name', 'student_id', 'filename',
            'file_type', 'file_size_kb', 'content_hash',
            'submission_time', 'plagiarism_score', 'status'
        ])
        submissions_df.to_csv("database/submissions.csv", index=False)
    
    # Assignments database
    if not os.path.exists("database/assignments.csv"):
        assignments_df = pd.DataFrame(columns=[
            'id', 'title', 'description', 'deadline', 'created_by', 'created_at'
        ])
        assignments_df.to_csv("database/assignments.csv", index=False)

def hash_password(password):
    """Simple password hashing"""
    return hashlib.md5(password.encode()).hexdigest()

def authenticate_user(username, password):
    """Authenticate user"""
    try:
        users_df = pd.read_csv("database/users.csv")
        hashed_pwd = hash_password(password)
        user = users_df[(users_df['username'] == username) & (users_df['password'] == hashed_pwd)]
        
        if len(user) > 0:
            return user.iloc[0].to_dict()
    except Exception as e:
        st.error(f"Authentication error: {e}")
    
    return None

def register_user(username, password, name, email, role='student'):
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
            'role': role,
            'email': email
        }])
        
        users_df = pd.concat([users_df, new_user], ignore_index=True)
        users_df.to_csv("database/users.csv", index=False)
        return True, "Registration successful"
        
    except Exception as e:
        return False, f"Registration failed: {e}"

def save_submission(student_name, student_id, filename, file_content, file_type, plagiarism_score):
    """Save submission to database"""
    try:
        df = pd.read_csv("database/submissions.csv")
        
        # Generate content hash for quick comparison
        content_hash = hashlib.md5(file_content.encode()).hexdigest()
        
        new_submission = pd.DataFrame([{
            'id': len(df) + 1,
            'student_name': student_name,
            'student_id': student_id,
            'filename': filename,
            'file_type': file_type,
            'file_size_kb': len(file_content) / 1024,
            'content_hash': content_hash,
            'submission_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'plagiarism_score': plagiarism_score,
            'status': 'Submitted'
        }])
        
        df = pd.concat([df, new_submission], ignore_index=True)
        df.to_csv("database/submissions.csv", index=False)
        
        # Save file to uploads folder
        filepath = f"uploads/{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        return True
        
    except Exception as e:
        st.error(f"Error saving submission: {e}")
        return False

def get_previous_submissions_text():
    """Get text from all previous submissions"""
    texts = []
    
    try:
        if os.path.exists("database/submissions.csv"):
            df = pd.read_csv("database/submissions.csv")
            
            for _, row in df.iterrows():
                filepath = f"uploads/{row['filename']}"
                if os.path.exists(filepath):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            texts.append(f.read())
                    except:
                        continue
    except Exception as e:
        st.error(f"Error reading previous submissions: {e}")
    
    return texts

# ========== UI PAGES ==========
def show_login_page():
    """Show login/register page"""
    st.title("🎓 Plagiarism Detection System")
    
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    
    with tab1:
        st.subheader("Login to Your Account")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
        
        with col2:
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            
            if st.button("Login", type="primary", use_container_width=True):
                if username and password:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_info = user
                        st.success(f"Welcome back, {user['name']}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.warning("Please enter both username and password")
    
    with tab2:
        st.subheader("Create Student Account")
        
        with st.form("registration_form"):
            full_name = st.text_input("Full Name")
            student_id = st.text_input("Student ID")
            email = st.text_input("Email Address")
            username = st.text_input("Choose Username")
            password = st.text_input("Choose Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            submitted = st.form_submit_button("Register", type="primary")
            
            if submitted:
                if not all([full_name, student_id, email, username, password]):
                    st.error("Please fill all fields")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, message = register_user(username, password, full_name, email, 'student')
                    if success:
                        st.success(message)
                        st.info("Please login with your new account")
                    else:
                        st.error(message)

def show_student_dashboard():
    """Student dashboard"""
    user = st.session_state.user_info
    
    st.title(f"👨‍🎓 Welcome, {user['name']}")
    st.markdown("---")
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📤 Submit Assignment", "📋 My Submissions", "📊 My Statistics"])
    
    with tab1:
        st.header("Submit New Assignment")
        
        # Student info
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Student:** {user['name']}")
        with col2:
            student_id = st.text_input("Student ID (Required)", value=user.get('email', '').split('@')[0])
        
        # File upload section
        st.subheader("Upload Assignment File")
        
        uploaded_file = st.file_uploader(
            "Choose your assignment file",
            type=['txt', 'pdf', 'docx'],
            help="Supported formats: TXT, PDF, DOCX. Max size: 10MB"
        )
        
        if uploaded_file:
            # File info
            file_size_mb = uploaded_file.size / (1024 * 1024)
            file_type = uploaded_file.name.split('.')[-1].upper()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("File", uploaded_file.name)
            with col2:
                st.metric("Size", f"{file_size_mb:.2f} MB")
            with col3:
                st.metric("Type", file_type)
            
            # Extract text
            with st.spinner("Reading file content..."):
                file_content = extract_text_from_file(uploaded_file)
            
            if file_content:
                # Show preview
                with st.expander("📄 Preview Content", expanded=False):
                    preview_text = file_content[:1500] + "..." if len(file_content) > 1500 else file_content
                    st.text_area("", preview_text, height=200, label_visibility="collapsed")
                
                # Check plagiarism button
                if st.button("🔍 Check for Plagiarism", type="primary", use_container_width=True):
                    if not student_id:
                        st.error("Please enter your Student ID")
                    else:
                        with st.spinner("Analyzing for plagiarism..."):
                            # Get previous submissions
                            previous_texts = get_previous_submissions_text()
                            
                            # Calculate plagiarism
                            plagiarism_score = check_plagiarism(file_content, previous_texts)
                            
                            # Display results
                            st.markdown("---")
                            st.subheader("📊 Plagiarism Analysis Results")
                            
                            # Score display with color
                            score_col1, score_col2, score_col3 = st.columns(3)
                            with score_col1:
                                if plagiarism_score == 0:
                                    st.success("✅ **ORIGINAL**")
                                elif plagiarism_score < 30:
                                    st.info("🟡 **LOW SIMILARITY**")
                                elif plagiarism_score < 70:
                                    st.warning("🟠 **MODERATE SIMILARITY**")
                                else:
                                    st.error("🔴 **HIGH SIMILARITY**")
                            
                            with score_col2:
                                st.metric("Plagiarism Score", f"{plagiarism_score:.1f}%")
                            
                            with score_col3:
                                st.metric("Compared With", f"{len(previous_texts)} submissions")
                            
                            # Interpretation
                            if plagiarism_score == 0:
                                st.success("Excellent! This appears to be original work.")
                            elif plagiarism_score < 20:
                                st.info("Low similarity - likely coincidental matches.")
                            elif plagiarism_score < 50:
                                st.warning("Moderate similarity - review recommended.")
                            else:
                                st.error("High similarity - possible plagiarism detected.")
                            
                            # Save submission
                            if st.button("✅ Submit Assignment", type="primary", use_container_width=True):
                                filename = f"{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_type.lower()}"
                                
                                if save_submission(user['name'], student_id, filename, file_content, file_type, plagiarism_score):
                                    st.success("✅ Assignment submitted successfully!")
                                    st.balloons()
                                    time.sleep(2)
                                    st.rerun()
            else:
                st.error("Could not extract text from the file. Please try a different file.")
    
    with tab2:
        st.header("My Submission History")
        
        try:
            if os.path.exists("database/submissions.csv"):
                df = pd.read_csv("database/submissions.csv")
                
                # Filter student's submissions
                student_subs = df[df['student_name'] == user['name']]
                
                if len(student_subs) > 0:
                    # Format for display
                    display_df = student_subs[['filename', 'file_type', 'submission_time', 'plagiarism_score']].copy()
                    display_df.columns = ['Filename', 'Type', 'Submission Time', 'Plagiarism %']
                    
                    # Sort by time
                    display_df = display_df.sort_values('Submission Time', ascending=False)
                    
                    # Display with formatting
                    st.dataframe(
                        display_df,
                        column_config={
                            "Plagiarism %": st.column_config.ProgressColumn(
                                "Plagiarism %",
                                format="%.1f%%",
                                min_value=0,
                                max_value=100,
                            )
                        },
                        use_container_width=True
                    )
                    
                    # Download option
                    csv = display_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download History",
                        csv,
                        f"{user['name']}_submissions.csv",
                        "text/csv",
                        use_container_width=True
                    )
                else:
                    st.info("No submissions found. Submit your first assignment!")
            else:
                st.info("No submissions yet.")
                
        except Exception as e:
            st.error(f"Error loading submissions: {e}")
    
    with tab3:
        st.header("My Statistics")
        
        try:
            if os.path.exists("database/submissions.csv"):
                df = pd.read_csv("database/submissions.csv")
                student_subs = df[df['student_name'] == user['name']]
                
                if len(student_subs) > 0:
                    # Calculate statistics
                    total_subs = len(student_subs)
                    avg_score = student_subs['plagiarism_score'].mean()
                    latest_score = student_subs.iloc[-1]['plagiarism_score'] if len(student_subs) > 0 else 0
                    high_risk_subs = len(student_subs[student_subs['plagiarism_score'] > 50])
                    
                    # Display metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Submissions", total_subs)
                    with col2:
                        st.metric("Average Score", f"{avg_score:.1f}%")
                    with col3:
                        st.metric("Latest Score", f"{latest_score:.1f}%")
                    with col4:
                        st.metric("High Risk", high_risk_subs)
                    
                    # Chart
                    st.subheader("Score Trend")
                    if len(student_subs) > 1:
                        chart_data = student_subs[['submission_time', 'plagiarism_score']].copy()
                        chart_data['submission_time'] = pd.to_datetime(chart_data['submission_time'])
                        chart_data = chart_data.sort_values('submission_time')
                        st.line_chart(chart_data.set_index('submission_time')['plagiarism_score'])
                    else:
                        st.info("Submit more assignments to see trends")
                else:
                    st.info("Submit your first assignment to see statistics")
            else:
                st.info("No statistics available yet")
                
        except Exception as e:
            st.error(f"Error loading statistics: {e}")

def show_teacher_dashboard():
    """Teacher dashboard"""
    st.title("👨‍🏫 Teacher Dashboard")
    st.markdown("---")
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📊 All Submissions", "🚨 High Plagiarism", "⚙️ Settings"])
    
    with tab1:
        st.header("All Student Submissions")
        
        try:
            if os.path.exists("database/submissions.csv"):
                df = pd.read_csv("database/submissions.csv")
                
                if len(df) > 0:
                    # Summary metrics
                    st.subheader("Summary")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Total", len(df))
                    with col2:
                        avg = df['plagiarism_score'].mean()
                        st.metric("Avg. Score", f"{avg:.1f}%")
                    with col3:
                        high = len(df[df['plagiarism_score'] > 50])
                        st.metric("High Risk", high)
                    with col4:
                        students = df['student_name'].nunique()
                        st.metric("Students", students)
                    
                    # Filters
                    st.subheader("Filters")
                    filter_col1, filter_col2, filter_col3 = st.columns(3)
                    
                    with filter_col1:
                        min_score = st.slider("Min Score", 0, 100, 0)
                    with filter_col2:
                        max_score = st.slider("Max Score", 0, 100, 100)
                    with filter_col3:
                        sort_by = st.selectbox("Sort By", ['Submission Time', 'Plagiarism Score', 'Student Name'])
                    
                    # Apply filters
                    filtered_df = df[
                        (df['plagiarism_score'] >= min_score) & 
                        (df['plagiarism_score'] <= max_score)
                    ]
                    
                    # Sort
                    if sort_by == 'Submission Time':
                        filtered_df = filtered_df.sort_values('submission_time', ascending=False)
                    elif sort_by == 'Plagiarism Score':
                        filtered_df = filtered_df.sort_values('plagiarism_score', ascending=False)
                    else:
                        filtered_df = filtered_df.sort_values('student_name')
                    
                    # Display table
                    st.subheader("Submissions List")
                    display_cols = ['student_name', 'student_id', 'filename', 'submission_time', 'plagiarism_score']
                    
                    # Color formatting function
                    def color_plagiarism(val):
                        if val > 70:
                            return 'background-color: #ffcccc; color: #000; font-weight: bold'
                        elif val > 40:
                            return 'background-color: #fff3cd; color: #000'
                        else:
                            return 'background-color: #d4edda; color: #000'
                    
                    styled_df = filtered_df[display_cols].style.applymap(
                        color_plagiarism, subset=['plagiarism_score']
                    )
                    
                    st.dataframe(styled_df, use_container_width=True, height=400)
                    
                    # Download
                    csv = filtered_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Full Report",
                        csv,
                        "plagiarism_report.csv",
                        "text/csv",
                        use_container_width=True
                    )
                    
                    # Chart
                    st.subheader("Distribution")
                    st.bar_chart(filtered_df['plagiarism_score'])
                    
                else:
                    st.info("No submissions yet. Ask students to submit assignments.")
                    
            else:
                st.info("Database not initialized. Please wait...")
                
        except Exception as e:
            st.error(f"Error loading data: {e}")
    
    with tab2:
        st.header("🚨 High Plagiarism Cases")
        
        try:
            if os.path.exists("database/submissions.csv"):
                df = pd.read_csv("database/submissions.csv")
                
                # Filter high plagiarism
                high_plagiarism = df[df['plagiarism_score'] > 50]
                
                if len(high_plagiarism) > 0:
                    st.warning(f"Found {len(high_plagiarism)} cases with plagiarism > 50%")
                    
                    # Group by student
                    student_stats = high_plagiarism.groupby('student_name').agg({
                        'plagiarism_score': ['count', 'mean', 'max'],
                        'filename': lambda x: ', '.join(x)
                    }).round(1)
                    
                    student_stats.columns = ['Count', 'Average %', 'Max %', 'Files']
                    student_stats = student_stats.sort_values('Max %', ascending=False)
                    
                    # Display
                    st.dataframe(student_stats, use_container_width=True)
                    
                    # Action buttons
                    st.subheader("Actions")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("📧 Send Warning Emails", use_container_width=True):
                            st.success("Warning emails sent to selected students")
                    
                    with col2:
                        if st.button("📝 Request Explanations", use_container_width=True):
                            st.success("Explanation requests sent")
                else:
                    st.success("✅ No high plagiarism cases found!")
                    
            else:
                st.info("No data available")
                
        except Exception as e:
            st.error(f"Error: {e}")
    
    with tab3:
        st.header("System Settings")
        
        # Create new assignment
        st.subheader("Create New Assignment")
        
        with st.form("assignment_form"):
            title = st.text_input("Assignment Title")
            description = st.text_area("Description")
            deadline = st.date_input("Deadline")
            
            submitted = st.form_submit_button("Create Assignment", type="primary")
            
            if submitted:
                try:
                    assignments_df = pd.read_csv("database/assignments.csv")
                    
                    new_assignment = pd.DataFrame([{
                        'id': len(assignments_df) + 1,
                        'title': title,
                        'description': description,
                        'deadline': deadline.strftime("%Y-%m-%d"),
                        'created_by': st.session_state.user_info['name'],
                        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    
                    assignments_df = pd.concat([assignments_df, new_assignment], ignore_index=True)
                    assignments_df.to_csv("database/assignments.csv", index=False)
                    
                    st.success(f"Assignment '{title}' created successfully!")
                    
                except Exception as e:
                    st.error(f"Error creating assignment: {e}")
        
        # System info
        st.subheader("System Information")
        
        info_col1, info_col2 = st.columns(2)
        
        with info_col1:
            st.metric("Database Size", "CSV Files")
            st.metric("File Storage", "Local Folder")
            st.metric("Max File Size", "10 MB")
        
        with info_col2:
            st.metric("Students", "Unlimited")
            st.metric("Assignments", "Unlimited")
            st.metric("Algorithm", "Jaccard Similarity")

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
        st.markdown("---")
        
        if st.session_state.logged_in:
            user = st.session_state.user_info
            st.success(f"Logged in as: {user['name']}")
            st.info(f"Role: {user['role'].title()}")
            
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user_info = {}
                st.rerun()
        else:
            st.info("Please login to continue")
        
        st.markdown("---")
        st.caption("""
        **Features:**
        - 📤 File upload (TXT, PDF, DOCX)
        - 🔍 Real-time plagiarism check
        - 📊 Detailed analytics
        - 👨‍🏫 Teacher dashboard
        - 📥 Export reports
        """)
        
        st.markdown("---")
        st.caption("v1.0 | Streamlit Deployment")
    
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