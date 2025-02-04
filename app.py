from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Set a folder for file uploads
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'xls'}


# Database connection configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # Your MySQL password
    'database': 'attendance_db'
}

# Utility function to get a database connection
def get_db_connection():
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn

from flask import session

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    print("Login route accessed")  # Debugging log
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Query the Teachers table for the provided email
            cursor.execute("SELECT * FROM Teachers WHERE email = %s", (email,))
            teacher = cursor.fetchone()

            if not teacher:
                flash('Incorrect email. Please try again.', 'danger')
            elif teacher['password_hash'] != password:
                flash('Incorrect password. Please try again.', 'danger')
            else:
                # Store the email in the session on successful login
                session['user_email'] = email
                # Redirect to course selection page
                return redirect(url_for('select_course'))

            cursor.close()
            conn.close()

        except mysql.connector.Error as e:
            flash(f"Database error: {e}", 'danger')

    return render_template('login.html')


# Home route
@app.route('/')
def home():
    return redirect(url_for('login'))


# Dashboard route
@app.route('/dashboard')
def dashboard():
    return render_template('base.html')


@app.route('/select_week', methods=['GET', 'POST'])
def select_week():

    if request.method == 'POST':
        selected_week = request.form.get('week')
        if selected_week:
            session['week'] = selected_week
            return redirect(url_for('select_day'))  # Replace 'next_step' with the actual next route

    # Example of weeks (replace this with actual data if available in the database)
    weeks = [
        {'week_number': 'Week 1'},
        {'week_number': 'Week 2'},
        {'week_number': 'Week 3'},
        {'week_number': 'Week 4'},
        {'week_number': 'Week 5'},
        {'week_number': 'Week 6'},
        {'week_number': 'Week 7'},
        {'week_number': 'Week 8'},
        {'week_number': 'Week 9'},
        {'week_number': 'Week 10'},
        {'week_number': 'Week 11'},
        {'week_number': 'Week 12'},
        {'week_number': 'Week 13'},
        {'week_number': 'Week 14'},
        # Add more weeks as necessary
    ]

    return render_template('select_week.html', weeks=weeks)

@app.route('/process_week', methods=['POST'])
def process_week():
    selected_week = request.form.get('week')
    if not selected_week:
        flash("Please select a week.")
        return redirect(url_for('select_week'))

    # Store the selected week in the session
    session['week'] = selected_week

    # Redirect to the next step (e.g., course selection or attendance)
    return redirect(url_for('select_day'))  # Replace 'next_step' with the actual next route

@app.route('/select_day', methods=['GET', 'POST'])
def select_day():
    week = session.get('week')
    if not week:
        flash("Please select a week first.")
        return redirect(url_for('select_week'))

    if request.method == 'POST':
        selected_day = request.form.get('day')
        if selected_day:
            session['day'] = selected_day
            return redirect(url_for('select_p'))  # Replace 'next_step' with the actual next route

    # Example of days (you can replace this with actual data if available)
    days = [
        {'day_name': 'Monday'},
        {'day_name': 'Tuesday'},
        {'day_name': 'Wednesday'},
        {'day_name': 'Thursday'},
        {'day_name': 'Friday'},
        {'day_name': 'Saturday'},
        {'day_name': 'Sunday'},
    ]

    return render_template('select_day.html', days=days)

@app.route('/process_day', methods=['POST'])
def process_day():
    selected_day = request.form.get('day')
    if not selected_day:
        flash("Please select a day.")
        return redirect(url_for('select_day'))

    # Store the selected day in the session
    session['day'] = selected_day

    # Redirect to the next step (e.g., course selection or attendance)
    return redirect(url_for('select_p'))  # Replace 'next_step' with the actual next route

@app.route('/select_p', methods=['GET', 'POST'])
def select_p():
    # Ensure week and day are selected first
    week = session.get('week')
    day = session.get('day')

    if not week:
        flash("Please select a week first.")
        return redirect(url_for('select_week'))

    if not day:
        flash("Please select a day first.")
        return redirect(url_for('select_day'))

    if request.method == 'POST':
        selected_p = request.form.get('p')
        if selected_p:
            session['p'] = selected_p
            return redirect(url_for('mark_attendance'))  # Go to the mark attendance route

    # List of P values (p1, p2, ..., p5)
    p_values = [
        {'p_name': 'p1'},
        {'p_name': 'p2'},
        {'p_name': 'p3'},
        {'p_name': 'p4'},
        {'p_name': 'p5'},
    ]

    return render_template('select_p.html', p_values=p_values)


@app.route('/process_p', methods=['POST'])
def process_p():
    selected_p = request.form.get('p')
    if not selected_p:
        flash("Please select a P value.")
        return redirect(url_for('select_p'))

    # Store the selected P value in the session
    session['p'] = selected_p

    # Redirect to the mark attendance route
    return redirect(url_for('mark_attendance'))  # Go to the mark attendance route


@app.route('/select_course', methods=['GET', 'POST'])
def select_course():
    # Ensure the user is logged in
    if 'user_email' not in session:
        flash("Please log in to continue.")
        return redirect(url_for('login'))

    user_email = session['user_email']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch the teacher's ID using their email
        cursor.execute("SELECT id FROM Teachers WHERE email = %s", (user_email,))
        teacher = cursor.fetchone()

        if not teacher:
            flash("No teacher found with the provided email.")
            return redirect(url_for('login'))

        teacher_id = teacher['id']

        # Fetch courses taught by the teacher
        cursor.execute("""
            SELECT c.cours_code, c.intitulé_cours 
            FROM cours c
            JOIN Teachers_cours tc ON c.cours_code = tc.cours_cours_code
            WHERE tc.teacher_id = %s;
        """, (teacher_id,))
        courses = cursor.fetchall()

        cursor.close()
        conn.close()

        if request.method == 'POST':
            selected_course = request.form.get('course')
            if selected_course:
                session['selected_course'] = selected_course
                # Redirect to the next step (e.g., attendance management)
                return redirect(url_for('select_week'))  # Replace 'next_step' with the actual route

        return render_template('select_course.html', courses=courses)

    except mysql.connector.Error as e:
        flash(f"Database error: {e}")
        return "An error occurred while fetching courses.", 500


@app.route('/mark_attendance', methods=['GET', 'POST'])
def mark_attendance():
    global cursor, conn
    if 'user_email' not in session:
        flash("Please log in to continue.")
        return redirect(url_for('login'))

    # Get session data
    selected_course = session.get('selected_course')
    week = session.get('week')
    day = session.get('day')

    if not all([selected_course, week, day]):
        flash("Please complete all selections first.")
        return redirect(url_for('select_course'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get the teacher's ID
        user_email = session['user_email']
        cursor.execute("SELECT id FROM Teachers WHERE email = %s", (user_email,))
        teacher = cursor.fetchone()

        if not teacher:
            flash("Teacher not found.")
            return redirect(url_for('login'))

        teacher_id = teacher['id']

        # Verify teacher is assigned to this course
        cursor.execute("""
            SELECT 1 FROM Teachers_cours 
            WHERE teacher_id = %s AND cours_cours_code = %s
        """, (teacher_id, selected_course))

        if not cursor.fetchone():
            flash("You are not assigned to this course.")
            return redirect(url_for('select_course'))

        # Get the department of the selected course
        cursor.execute("""
            SELECT d.code_dep
            FROM cours c
            JOIN departement d ON c.code_dep = d.code_dep
            WHERE c.cours_code = %s
        """, (selected_course,))
        department = cursor.fetchone()

        if not department:
            flash("Course department not found.")
            return redirect(url_for('select_course'))

        department_code = department['code_dep']

        # Get students from the same department as the course
        cursor.execute("""
            SELECT DISTINCT e.matricule, SUBSTRING_INDEX(e.nom_prenom, ' ', 1) as nom,
                   SUBSTRING(e.nom_prenom, LENGTH(SUBSTRING_INDEX(e.nom_prenom, ' ', 1)) + 2) as prenom
            FROM etudiants e
            JOIN departement d ON e.code_dep = d.code_dep
            JOIN niveau n ON d.code_niv = n.code_niv
            JOIN semestre s ON n.code_niv = s.code_niv
            JOIN cours c ON s.code_sem = c.code_sem
            WHERE e.code_dep = %s AND c.cours_code = %s
        """, (department_code, selected_course))

        students = cursor.fetchall()

        if not students:
            flash("No students found for this course in the selected department.")
            return redirect(url_for('select_course'))

        # Handle attendance submission
        if request.method == 'POST':
            try:
                # Start transaction
                conn.start_transaction()

                # Check for existing attendance records
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM Attendance 
                    WHERE cours_cours_code = %s AND week = %s AND day = %s
                """, (selected_course, week, day))

                if cursor.fetchone()['count'] > 0:
                    conn.rollback()
                    flash("Attendance for this course, week, and day already exists!")
                    return redirect(url_for('dashboard'))

                # Insert attendance records
                for student in students:
                    is_present = request.form.get(f'attendance_{student["matricule"]}') == 'present'
                    cursor.execute("""
                        INSERT INTO Attendance 
                        (etudiants_matricule, cours_cours_code, date, week, day)
                        VALUES (%s, %s, CURDATE(), %s, %s)
                    """, (student['matricule'], selected_course, week, day))

                conn.commit()
                flash("Attendance marked successfully!")
                return redirect(url_for('dashboard'))

            except mysql.connector.Error as e:
                conn.rollback()
                print(f"Database error during attendance submission: {str(e)}")
                flash("Error marking attendance. Please try again.")
                return redirect(url_for('mark_attendance'))

        # For GET request, show the attendance form
        cursor.close()
        conn.close()

        return render_template('mark_attendance.html',
                               students=students,
                               week=week,
                               day=day,
                               course=selected_course)

    except mysql.connector.Error as e:
        print(f"Database error: {str(e)}")
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        flash(f"Database error: {str(e)}")
        return redirect(url_for('dashboard'))



if __name__ == '__main__':
    app.run(debug=True)
