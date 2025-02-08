import mysql.connector
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
import mysql.connector
import io
import csv

app = Flask(__name__)
app.secret_key = 'your_secret_key'



# Configuration de connexion à la base de données
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # Votre mot de passe MySQL
    'database': 'attendance_db'
}

# Fonction utilitaire pour obtenir une connexion à la base de données
def get_db_connection():
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM Teachers WHERE email = %s", (email,))
            teacher = cursor.fetchone()

            if not teacher:
                flash("Email incorrect. Veuillez réessayer.", 'danger')
            elif teacher['password_hash'] != password:  # Ideally, use a secure hash check
                flash("Mot de passe incorrect. Veuillez réessayer.", 'danger')
            else:
                # Store teacher information in session
                session['teacher_id'] = teacher['id']
                session['user_email'] = email
                session['username'] = teacher['name']

                if session['username'] == 'Mouhammed Lemin Oubeid':
                    return redirect(url_for('emploi_du_temps'))
                else:
                    return redirect(url_for('select_all'))  # Redirect to the dashboard

        except mysql.connector.Error as e:
            flash(f"Erreur de base de données : {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('login.html')

@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/logout', methods=['POST'])
def logout():
    # Effacer toutes les données de la session
    session.clear()

    flash("Vous êtes maintenant déconnecté.", 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    return render_template('base.html')


@app.route('/update_current_week', methods=['POST'])
def update_current_week():
    # Restrict access to admin users only
    if 'user_email' not in session or session.get('user_email') != 'mouhammed.leminoubeid@isms.esp.mr':
        flash("Accès refusé. Vous n'êtes pas autorisé à effectuer cette action.", 'danger')
        return redirect(url_for('login'))

    # Check if today is Monday
    if datetime.now().strftime("%A") != "Tuesday":
        flash("Ce n'est pas lundi. La semaine actuelle ne peut être mise à jour.", "warning")
        return redirect(url_for('emploi_du_temps'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Retrieve the current week from the database
        cursor.execute("SELECT current_week FROM CurrentWeek WHERE id = 1")
        result = cursor.fetchone()
        if not result:
            flash("Aucune entrée trouvée pour la semaine actuelle.", "danger")
            return redirect(url_for('emploi_du_temps'))

        current_week = int(result['current_week'])

        # Increment the week, wrapping to 1 if it exceeds 17
        new_week = current_week + 1
        if new_week > 17:
            new_week = 1

        # Update the CurrentWeek table
        cursor.execute("UPDATE CurrentWeek SET current_week = %s WHERE id = 1", (new_week,))
        conn.commit()

        flash(f"La semaine actuelle a été mise à jour de {current_week} à {new_week}.", "success")
    except mysql.connector.Error as e:
        flash(f"Erreur de base de données : {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return redirect(url_for('emploi_du_temps'))


# Route for managing the schedule (admin only)
@app.route('/emploi_du_temps', methods=['GET', 'POST'])
def emploi_du_temps():
    if 'user_email' not in session:
        flash("Veuillez vous connecter pour continuer.", 'warning')
        return redirect(url_for('login'))

    # Restrict access to the admin
    if session.get('user_email') != 'mouhammed.leminoubeid@isms.esp.mr':
        flash("Accès refusé. Vous n'êtes pas autorisé à accéder à cette page.", 'danger')
        return redirect(url_for('select_all'))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        # Use a buffered cursor so we can re-read the same connection
        cursor = conn.cursor(dictionary=True, buffered=True)

        # Get all departments for the dropdown
        cursor.execute("SELECT code_dep, intitulé_dep FROM departement")
        departments = cursor.fetchall()

        # Get selected week and department from URL parameters if provided.
        selected_week = request.args.get('week')
        selected_dep = request.args.get('dep')

        # If no week was passed via GET, use the current week stored in the database.
        if not selected_week:
            cursor.execute("SELECT current_week FROM CurrentWeek WHERE id = 1")
            current_week_data = cursor.fetchone()
            if current_week_data:
                selected_week = current_week_data['current_week']
            else:
                flash("Aucune semaine n'a été trouvée dans la base de données. Utilisation de la semaine 1 par défaut.", 'warning')
                selected_week = '1'
            # Debug: Print the retrieved week
            print(f"Retrieved week from database: {selected_week}")
        else:
            # Even if selected_week is passed via GET, fetch the current week for comparison.
            cursor.execute("SELECT current_week FROM CurrentWeek WHERE id = 1")
            current_week_data = cursor.fetchone()

        # Define a helper dictionary for day order (French day names)
        day_order = {"Lundi": 1, "Mardi": 2, "Mercredi": 3, "Jeudi": 4, "Vendredi": 5, "Samedi": 6, "Dimanche": 7}
        # And a mapping from English to French day names.
        en_to_fr_day = {
            "Monday": "Lundi",
            "Tuesday": "Mardi",
            "Wednesday": "Mercredi",
            "Thursday": "Jeudi",
            "Friday": "Vendredi",
            "Saturday": "Samedi",
            "Sunday": "Dimanche"
        }
        # Get the current day (in French) from the server's current time.
        now = datetime.now()
        current_day_fr = en_to_fr_day[now.strftime("%A")]

        # --- POST handling ---
        if request.method == 'POST':
            action = request.form.get('action')
            course_code = request.form.get('course')
            day = request.form.get('day')   # e.g. "Lundi", "Mardi", etc.
            period = request.form.get('period')

            # In the POST form, the week is passed as a hidden field.
            selected_week = request.form.get('week', selected_week)
            selected_dep = request.form.get('dep', selected_dep)

            # Convert the week values to integer for comparison.
            try:
                selected_week_int = int(selected_week)
            except ValueError:
                flash("Semaine invalide.", "danger")
                return redirect(url_for('emploi_du_temps'))
            try:
                current_week_int = int(current_week_data['current_week']) if current_week_data else 1
            except (ValueError, KeyError):
                current_week_int = 1

            # Prevent modifications to past weeks
            if selected_week_int < current_week_int:
                flash("Vous ne pouvez pas modifier l'emploi du temps d'une semaine passée.", 'danger')
                return redirect(url_for('emploi_du_temps'))

            # If it is the current week, prevent modifications to days that are already past.
            # Compare the numeric order of the days.
            if selected_week_int == current_week_int:
                selected_day_index = day_order.get(day)
                if selected_day_index is None:
                    flash("Jour invalide.", "danger")
                    return redirect(url_for('emploi_du_temps'))
                # Only allow modifications if the selected day is today or in the future.
                if selected_day_index < day_order[current_day_fr]:
                    flash("Vous ne pouvez pas modifier l'emploi du temps d'un jour passé.", 'danger')
                    return redirect(url_for('emploi_du_temps'))

            # Now perform the requested action (delete or add/modify)
            if action == 'delete':
                # Delete the course from the schedule
                cursor.execute("""
                    DELETE FROM emploi
                    WHERE course_code = %s AND day = %s AND P_ID = %s AND week = %s
                """, (course_code, day, period, selected_week))
                conn.commit()
                flash("Cours supprimé avec succès!", 'success')
            else:
                # Get the department of the new course
                cursor.execute("SELECT code_dep FROM cours WHERE cours_code = %s", (course_code,))
                department_data = cursor.fetchone()
                if not department_data:
                    flash("Cours non trouvé dans la base de données.", 'danger')
                    return redirect(url_for('emploi_du_temps'))

                department_code = department_data['code_dep']

                # Check if another course from the same department is already scheduled for the same week, day, and period
                cursor.execute("""
                    SELECT e.emploi_id
                    FROM emploi e
                    JOIN cours c ON e.course_code = c.cours_code
                    WHERE e.week = %s 
                    AND e.day = %s 
                    AND e.P_ID = %s
                    AND c.code_dep = %s
                """, (selected_week, day, period, department_code))
                conflicting_course = cursor.fetchone()

                if conflicting_course:
                    # Update the existing course with the new course details
                    cursor.execute("""
                        UPDATE emploi
                        SET course_code = %s, teacher_id = %s
                        WHERE emploi_id = %s
                    """, (course_code, 1, conflicting_course['emploi_id']))  # Replace 1 with the actual teacher_id if needed
                    conn.commit()
                    flash("Cours mis à jour avec succès!", 'success')
                else:
                    # Insert the new course
                    cursor.execute("""
                        INSERT INTO emploi (teacher_id, course_code, day, week, P_ID)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (1, course_code, day, selected_week, period))  # Replace 1 with the actual teacher_id if needed
                    conn.commit()
                    flash("Cours ajouté avec succès!", 'success')

            # Update the current week and department in the database if needed.
            cursor.execute("""
                UPDATE CurrentWeek
                SET current_week = %s
                WHERE id = 1
            """, (selected_week,))
            conn.commit()

        # --- End POST handling ---

        # Get courses for the selected department
        cursor.execute("""
            SELECT cours_code, intitulé_cours 
            FROM cours 
            WHERE code_dep = %s
        """, (selected_dep,))
        courses = cursor.fetchall()

        # Get the schedule data for the selected week and department
        cursor.execute("""
            SELECT 
                e.emploi_id,
                e.course_code,
                c.intitulé_cours,
                e.day,
                e.week,
                e.P_ID
            FROM emploi e
            JOIN cours c ON e.course_code = c.cours_code
            WHERE e.week = %s AND c.code_dep = %s
            ORDER BY 
                CASE 
                    WHEN e.day = 'Lundi' THEN 1
                    WHEN e.day = 'Mardi' THEN 2
                    WHEN e.day = 'Mercredi' THEN 3
                    WHEN e.day = 'Jeudi' THEN 4
                    WHEN e.day = 'Vendredi' THEN 5
                    WHEN e.day = 'Samedi' THEN 6
                    WHEN e.day = 'Dimanche' THEN 7
                END,
                e.P_ID
        """, (selected_week, selected_dep))
        schedule_data = cursor.fetchall()

        # Create schedule grid
        days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        periods = [f'Période {i}' for i in range(1, 6)]
        schedule_grid = {day: {period: None for period in periods} for day in days}

        # Fill the grid
        for entry in schedule_data:
            day_name = entry['day']
            period_name = f"Période {entry['P_ID']}"
            schedule_grid[day_name][period_name] = {
                'course_code': entry['course_code'],
                'course_name': entry['intitulé_cours'],
                'week': entry['week']
            }

    except mysql.connector.Error as e:
        flash(f"Erreur de base de données : {e}", 'danger')
        return redirect(url_for('login'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # Prepare the weeks list for the dropdown (here weeks 1 to 17)
    weeks = [{'week_number': str(i)} for i in range(1, 18)]

    return render_template('emploi_du_temps.html',
                           schedule_grid=schedule_grid,
                           days=days,
                           periods=periods,
                           weeks=weeks,
                           courses=courses,
                           departments=departments,
                           selected_week=selected_week,
                           selected_dep=selected_dep)

# Route for teachers to check their current schedule
@app.route('/select_all', methods=['GET', 'POST'])
def select_all():
    if 'user_email' not in session:
        flash("Veuillez vous connecter pour continuer.", 'warning')
        return redirect(url_for('login'))

    user_email = session['user_email']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get teacher ID
        cursor.execute("SELECT id FROM Teachers WHERE email = %s", (user_email,))
        teacher = cursor.fetchone()
        if not teacher:
            flash("Aucun enseignant trouvé avec cet email.", 'danger')
            return redirect(url_for('login'))

        teacher_id = teacher['id']

        # Get the current week from the CurrentWeek table
        cursor.execute("SELECT current_week FROM CurrentWeek WHERE id = 1")
        current_week_data = cursor.fetchone()
        if current_week_data:
            selected_week = current_week_data['current_week']
        else:
            flash("Aucune semaine n'a été trouvée dans la base de données. Utilisation de la semaine 1 par défaut.", 'warning')
            selected_week = '1'  # Default to week 1 if no data is found

        # Get current day and period
        current_day = datetime.now().strftime('%A')
        day_conversion = {
            'Monday': 'Lundi',
            'Tuesday': 'Mardi',
            'Wednesday': 'Mercredi',
            'Thursday': 'Jeudi',
            'Friday': 'Vendredi',
            'Saturday': 'Samedi',
            'Sunday': 'Dimanche'
        }
        current_day = day_conversion.get(current_day, 'Lundi')

        current_hour = datetime.now().hour
        current_period = 1
        if 8 <= current_hour < 9.30:
            current_period = 1
        elif 9.45 <= current_hour < 11.15:
            current_period = 2
        elif 11.30 <= current_hour < 13:
            current_period = 3
        elif 15.30 <= current_hour < 16.40:
            current_period = 4
        elif 17 <= current_hour < 18.30:
            current_period = 5

            # Debug: Print query parameters
        print(
            f"Query Parameters - Week: {selected_week}, Day: {current_day}, Period: {current_period}, Teacher ID: {teacher_id}")

        # Check if the teacher has a subject scheduled for the current week, day, and period

        cursor.execute("""
            SELECT e.*, c.intitulé_cours, d.intitulé_dep 
            FROM emploi e
            JOIN cours c ON e.course_code = c.cours_code
            JOIN departement d ON c.code_dep = d.code_dep
            JOIN Teachers_cours tc ON c.cours_code = tc.cours_cours_code
            WHERE e.week = %s 
            AND e.day = %s 
            AND e.P_ID = %s
            AND tc.teacher_id = %s
        """, (selected_week, current_day, str(current_period), teacher_id))
        scheduled_course = cursor.fetchone()

        # Debug: Print the scheduled course
        print(f"Scheduled Course: {scheduled_course}")
        # Handle POST request for manual selection
        if request.method == 'POST':
            if scheduled_course:
                # Use the scheduled course
                session['selected_course'] = scheduled_course['course_code']
                session['week'] = f"{scheduled_course['week']}"
                session['day'] = scheduled_course['day']
                session['p'] = f"{scheduled_course['P_ID']}"
                return redirect(url_for('mark_attendance'))
            else:
                # Handle manual selection
                manual_course = request.form.get('manual_course')
                manual_week = request.form.get('manual_week', selected_week)
                manual_day = request.form.get('manual_day', current_day)
                manual_period = request.form.get('manual_period', f"{current_period}")

                if manual_course and manual_week and manual_day and manual_period:
                    # Validate if the selected course, week, day, and period exist in the Emploi du Temps
                    cursor.execute("""
                        SELECT 1 
                        FROM emploi 
                        WHERE course_code = %s 
                        AND week = %s 
                        AND day = %s 
                        AND P_ID = %s
                    """, (manual_course, manual_week, manual_day, manual_period))
                    exists = cursor.fetchone()

                    if not exists:
                        flash("Cette combinaison de cours, semaine, jour et période n'existe pas dans l'emploi du temps.", 'danger')
                        return redirect(url_for('select_all'))

                    # Store manual selection in session
                    session['selected_course'] = manual_course
                    session['week'] = manual_week
                    session['day'] = manual_day
                    session['p'] = manual_period
                    return redirect(url_for('mark_attendance'))
                else:
                    flash("Veuillez remplir tous les champs pour la sélection manuelle.", 'warning')

        # Get all courses for manual selection (filtered by teacher)
        cursor.execute("""
            SELECT c.cours_code, c.intitulé_cours 
            FROM cours c 
            JOIN Teachers_cours tc ON c.cours_code = tc.cours_cours_code 
            WHERE tc.teacher_id = %s
        """, (teacher_id,))
        courses = cursor.fetchall()

    except mysql.connector.Error as e:
        flash(f"Erreur de base de données : {e}", 'danger')
        return "Une erreur est survenue lors de la récupération des données.", 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    weeks = [{'week_number': f'{i}'} for i in range(1, 18)]
    days = [{'day_name': day} for day in ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']]
    p_values = [{'p_name': f'{i}'} for i in range(1, 6)]



    # Debug: Print current day and period
    print(f"Current Day: {current_day}")
    print(f"Current Period: {current_period}")
    return render_template('select_all.html',
                           courses=courses,
                           weeks=weeks,
                           days=days,
                           p_values=p_values,
                           scheduled_course=scheduled_course,
                           selected_week=selected_week,
                           current_day=current_day,
                           current_period=current_period,
                           show_manual_selection=not scheduled_course)

@app.route('/mark_attendance', methods=['GET', 'POST'])
def mark_attendance():
    # Check if user is logged in
    if 'user_email' not in session:
        flash("Veuillez vous connecter pour continuer.", 'warning')
        return redirect(url_for('login'))

    # Retrieve session data
    selected_course = session.get('selected_course')
    week = session.get('week')
    day = session.get('day')
    period = session.get('p')

    # Debug: Print session data
    print(f"Session Data - Course: {selected_course}, Week: {week}, Day: {day}, Period: {period}")

    # Validate session data
    if not all([selected_course, week, day, period]):
        flash("Veuillez compléter toutes les sélections d'abord.", 'danger')
        return redirect(url_for('select_all'))

    try:
        # Establish database connection
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Retrieve course name (intitulé_cours)
        cursor.execute("SELECT intitulé_cours FROM cours WHERE cours_code = %s", (selected_course,))
        course_info = cursor.fetchone()
        selected_course_name = course_info['intitulé_cours'] if course_info else selected_course

        # Retrieve teacher ID
        user_email = session['user_email']
        cursor.execute("SELECT id FROM Teachers WHERE email = %s", (user_email,))
        teacher = cursor.fetchone()
        if not teacher:
            flash("Enseignant non trouvé.", 'danger')
            return redirect(url_for('login'))
        teacher_id = teacher['id']
        print(teacher_id)
        # Retrieve students for the selected course
        cursor.execute("""
            SELECT e.matricule, e.nom_prenom
            FROM etudiants e
            JOIN departement ON e.code_dep = departement.code_dep
            JOIN semestre ON departement.code_niv = semestre.code_niv
            JOIN cours ON semestre.code_sem = cours.code_sem
            WHERE cours.cours_code = %s
              AND (
                  (departement.intitulé_dep LIKE 'SEA%' AND cours.cours_code NOT LIKE 'SDID%')
                  OR
                  (departement.intitulé_dep LIKE 'SDID%' AND cours.cours_code NOT LIKE 'SEA%')
                  OR
                  (departement.intitulé_dep NOT LIKE 'SEA%' AND departement.intitulé_dep NOT LIKE 'SDID%')
              )
        """, (selected_course,))
        students = cursor.fetchall()



        # Retrieve existing attendance records
        cursor.execute("""
            SELECT student_id, status
            FROM Attendance
            WHERE course_code = %s AND week = %s AND day = %s AND P_ID = %s
        """, (selected_course, week, day, period))
        attendance_records = cursor.fetchall()



        # Create a dictionary of attendance records for quick lookup
        attendance_dict = {record['student_id']: record['status'] for record in attendance_records}

        # Handle form submission
        if request.method == 'POST':
            # Debug: Print form data
            print(f"Form Data: {request.form}")

            existing_absence = False  # Track if any record already exists
            for student in students:
                status = request.form.get(f'attendance_{student["matricule"]}')
                if status == "1":  # Absent
                    # Check if the record already exists
                    cursor.execute("""
                        SELECT 1 FROM Attendance
                        WHERE student_id = %s AND course_code = %s AND week = %s AND day = %s AND P_ID = %s
                    """, (student['matricule'], selected_course, week, day, period))
                    if cursor.fetchone():
                        existing_absence = True
                        flash(
                            f"L'absence de l'étudiant {student['nom_prenom']} (Matricule: {student['matricule']}) "
                            f"pour le cours {selected_course_name} (Période {period}) existe déjà.",
                            'warning'
                        )
                    else:
                        # Insert new absence record
                        cursor.execute("""
                            INSERT INTO Attendance 
                            (student_id, teacher_id, course_code, day, week, status, P_ID)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            student['matricule'], teacher_id, selected_course, day, week, 1, period
                        ))
                        conn.commit()  # Commit the transaction
                        flash("Absences enregistrées avec succès !", 'success')
            if existing_absence:
                flash("Certaines absences existent déjà. Veuillez vérifier.", 'info')

            return redirect(url_for('select_all'))

    except mysql.connector.Error as e:
        # Rollback in case of error
        conn.rollback()
        flash(f"Erreur lors de l'enregistrement des absences : {e}", 'danger')
        # Log the error for debugging
        app.logger.error(f"Database error: {e}")
    finally:
        # Close database connections
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # Render the template with all necessary data
    return render_template(
        'mark_attendance.html',
        students=students,
        selected_course=selected_course,
        selected_course_name=selected_course_name,  # Pass course name to template
        week=week,
        day=day,
        period=period,
        attendance_dict=attendance_dict
    )

@app.route('/profile')
def profile():
    if 'user_email' not in session:
        flash("Veuillez vous connecter pour continuer.")
        return redirect(url_for('login'))

    user_email = session['user_email']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM Teachers WHERE email = %s", (user_email,))
        teacher = cursor.fetchone()

        if not teacher:
            flash("Profil non trouvé.")
            return redirect(url_for('dashboard'))

        cursor.execute("""
            SELECT c.cours_code, c.intitulé_cours
            FROM cours c
            JOIN Teachers_cours tc ON c.cours_code = tc.cours_cours_code
            WHERE tc.teacher_id = %s
        """, (teacher['id'],))
        teacher_courses = cursor.fetchall()

    except mysql.connector.Error as e:
        flash(f"Erreur de base de données : {e}", 'danger')
        return redirect(url_for('dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template('profile.html', teacher=teacher, teacher_courses=teacher_courses)

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_email' not in session:
        flash("Veuillez vous connecter pour continuer.", 'danger')
        return redirect(url_for('login'))

    # Cette logique doit seulement s'appliquer après la soumission du formulaire
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Vérifier si les nouveaux mots de passe correspondent
        if new_password != confirm_password:
            flash("Les nouveaux mots de passe ne correspondent pas.", 'danger')
            return redirect(url_for('change_password'))

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Vérifier le mot de passe actuel uniquement si l'utilisateur soumet un formulaire
            cursor.execute("SELECT * FROM Teachers WHERE email = %s", (session['user_email'],))
            teacher = cursor.fetchone()

            if teacher and teacher['password_hash'] != old_password:
                flash("Le mot de passe actuel est incorrect.", 'danger')
                return redirect(url_for('change_password'))
            if len(new_password) < 4 :
                flash("le mots de passe doit avoir 4 charactère au moins.", 'danger')
                return redirect(url_for('change_password'))

            # Mettre à jour le mot de passe
            cursor.execute("""
                UPDATE Teachers
                SET password_hash = %s
                WHERE email = %s
            """, (new_password, session['user_email']))

            conn.commit()
            flash("Mot de passe mis à jour avec succès.", 'success')
            return redirect(url_for('profile'))

        except mysql.connector.Error as e:
            flash(f"Erreur de base de données : {e}", 'danger')
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('change_password.html')

@app.route('/statistique', methods=['GET'])
def statistique():
    try:
        teacher_id = session.get('teacher_id')
        if not teacher_id:
            flash("Vous devez être connecté en tant qu'enseignant.", 'danger')
            return redirect(url_for('login'))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get total absences across all courses for this teacher
        cursor.execute("""
            SELECT COUNT(a.student_id) AS total_teacher_absences
            FROM Attendance a
            JOIN Teachers_cours tc ON a.course_code = tc.cours_cours_code
            WHERE a.status = 1 AND tc.teacher_id = %s
        """, (teacher_id,))
        total_teacher_absences = cursor.fetchone()['total_teacher_absences'] or 1  # Avoid division by zero

        # Get total absences per course
        cursor.execute("""
            SELECT 
                c.cours_code, 
                c.intitulé_cours AS course_name,
                COUNT(a.student_id) AS total_absences
            FROM Attendance a
            JOIN cours c ON a.course_code = c.cours_code
            JOIN Teachers_cours tc ON c.cours_code = tc.cours_cours_code
            WHERE a.status = 1 AND tc.teacher_id = %s
            GROUP BY c.cours_code, c.intitulé_cours
            ORDER BY c.intitulé_cours
        """, (teacher_id,))
        course_absence_totals = cursor.fetchall() or []

        # Get total absences per day
        cursor.execute("""
            SELECT 
                a.day,
                COUNT(a.student_id) AS total_absences
            FROM Attendance a
            JOIN Teachers_cours tc ON a.course_code = tc.cours_cours_code
            WHERE a.status = 1 AND tc.teacher_id = %s
            GROUP BY a.day
            ORDER BY FIELD(a.day, 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche')
        """, (teacher_id,))
        daily_absences = cursor.fetchall() or []

        # Get total absences per period (aggregated across all days)
        cursor.execute("""
            SELECT 
                P_ID,
                COUNT(*) AS total_absences
            FROM Attendance
            WHERE status = 1
            GROUP BY P_ID
            ORDER BY P_ID;
        """)
        period_absences = cursor.fetchall() or []

        # Calculate percentage of absences for each period
        total_period_absences = sum(period['total_absences'] for period in period_absences) or 1
        for period in period_absences:
            period['absence_percentage'] = round((period['total_absences'] / total_period_absences) * 100, 2)
        print("Period Absences:", period_absences)

        # Get total absences per week
        cursor.execute("""
            SELECT 
                a.week,
                COUNT(a.student_id) AS total_absences
            FROM Attendance a
            JOIN Teachers_cours tc ON a.course_code = tc.cours_cours_code
            WHERE a.status = 1 AND tc.teacher_id = %s
            GROUP BY a.week
            ORDER BY a.week
        """, (teacher_id,))
        weekly_absences = cursor.fetchall() or []

        # Sort weeks numerically
        weekly_absences.sort(key=lambda x: int(x['week']))

        # Get most absent course, day, and period
        most_absent_course = max(course_absence_totals, key=lambda x: x['total_absences'], default={'course_name': 'N/A', 'total_absences': 0})
        most_absent_day = max(daily_absences, key=lambda x: x['total_absences'], default={'day': 'N/A', 'total_absences': 0})
        most_absent_period = max(period_absences, key=lambda x: x['total_absences'], default={'P_ID': 'N/A', 'total_absences': 0})

        # Get most absent week
        most_absent_week = max(weekly_absences, key=lambda x: x['total_absences'], default={'week': 'N/A', 'total_absences': 0})

        # -----------------------------
        # NEW: Get justification statistics
        # -----------------------------
        cursor.execute("""
            SELECT COUNT(j.justification_id) AS total_justified
            FROM Justification j
            JOIN Attendance a ON j.attend_id = a.attendance_id
            JOIN Teachers_cours tc ON a.course_code = tc.cours_cours_code
            WHERE a.status = 1 AND tc.teacher_id = %s AND j.status = '1'
        """, (teacher_id,))
        total_justified = cursor.fetchone()['total_justified'] or 0

        # Calculate the percentage of justified absences
        justification_percentage = round((total_justified / total_teacher_absences) * 100, 2)

    except mysql.connector.Error as e:
        flash(f"Erreur de base de données : {e}", 'danger')
        return redirect(url_for('select_all'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template('statistique.html',
                           course_absence_totals=course_absence_totals,
                           daily_absences=daily_absences,
                           period_absences=period_absences,
                           weekly_absences=weekly_absences,
                           most_absent_course=most_absent_course,
                           most_absent_day=most_absent_day,
                           most_absent_period=most_absent_period,
                           most_absent_week=most_absent_week,
                           total_teacher_absences=total_teacher_absences,
                           total_justified=total_justified,
                           justification_percentage=justification_percentage)


@app.route('/tables', methods=['GET', 'POST'])
def tables():
    if 'user_email' not in session:
        flash("Veuillez vous connecter pour continuer.", 'warning')
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get the teacher's ID
        cursor.execute("SELECT id FROM Teachers WHERE email = %s", (session['user_email'],))
        teacher = cursor.fetchone()
        if not teacher:
            flash("Aucun enseignant trouvé avec cet email.", 'danger')
            return redirect(url_for('login'))

        teacher_id = teacher['id']

        # Get the selected week (default to entire semester)
        selected_week = request.args.get('week', 'all')

        # Get the search query (Matricule)
        search_matricule = request.args.get('search_matricule', '')

        # Get all subjects taught by the teacher
        cursor.execute("""
            SELECT c.cours_code, c.intitulé_cours 
            FROM cours c
            JOIN Teachers_cours tc ON c.cours_code = tc.cours_cours_code
            WHERE tc.teacher_id = %s
        """, (teacher_id,))
        subjects = cursor.fetchall()

        # Get absence data for each subject
        absence_data = {}
        for subject in subjects:
            course_code = subject['cours_code']

            # Get total classes held for the course
            cursor.execute("""
                SELECT COUNT(DISTINCT CONCAT(day, P_ID, week)) AS total_classes
                FROM emploi
                WHERE course_code = %s
            """, (course_code,))
            total_classes = cursor.fetchone()['total_classes']

            # Get student absences
            if selected_week == 'all':
                query = """
                    SELECT 
                        e.matricule, 
                        e.nom_prenom, 
                        COUNT(a.attendance_id) AS total_absences
                    FROM Attendance a
                    JOIN etudiants e ON a.student_id = e.matricule
                    WHERE a.course_code = %s AND a.teacher_id = %s AND a.status = 1
                    AND (%s = '' OR e.matricule = %s)
                    GROUP BY e.matricule, e.nom_prenom
                """
                params = (course_code, teacher_id, search_matricule, search_matricule)
            else:
                query = """
                    SELECT 
                        e.matricule, 
                        e.nom_prenom, 
                        COUNT(a.attendance_id) AS total_absences
                    FROM Attendance a
                    JOIN etudiants e ON a.student_id = e.matricule
                    WHERE a.course_code = %s AND a.teacher_id = %s AND a.status = 1 AND a.week = %s
                    AND (%s = '' OR e.matricule = %s)
                    GROUP BY e.matricule, e.nom_prenom
                """
                params = (course_code, teacher_id, selected_week, search_matricule, search_matricule)

            cursor.execute(query, params)
            results = cursor.fetchall()
            absence_data[course_code] = results

    except mysql.connector.Error as e:
        flash(f"Erreur de base de données : {e}", 'danger')
        return redirect(url_for('login'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # Get list of weeks for the dropdown
    weeks = [{'week_number': str(i)} for i in range(1, 18)]
    weeks.append({'week_number': 'all'})  # Add option for entire semester

    return render_template('tables.html',
                           subjects=subjects,
                           absence_data=absence_data,
                           selected_week=selected_week,
                           weeks=weeks,
                           search_matricule=search_matricule)
@app.route('/export_absences')
def export_absences():
    if 'user_email' not in session:
        flash("Veuillez vous connecter pour continuer.", 'warning')
        return redirect(url_for('login'))

    course_code = request.args.get('course_code')
    selected_week = request.args.get('week', 'all')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get the teacher's ID
        cursor.execute("SELECT id FROM Teachers WHERE email = %s", (session['user_email'],))
        teacher = cursor.fetchone()
        if not teacher:
            flash("Aucun enseignant trouvé avec cet email.", 'danger')
            return redirect(url_for('login'))

        teacher_id = teacher['id']

        # Get total classes held for the course
        cursor.execute("""
            SELECT COUNT(DISTINCT CONCAT(day, P_ID, week)) AS total_classes
            FROM emploi
            WHERE course_code = %s
        """, (course_code,))
        total_classes = cursor.fetchone()['total_classes']

        # Get student absences with percentages
        if selected_week == 'all':
            query = """
                SELECT 
                    e.matricule, 
                    e.nom_prenom, 
                    COUNT(a.attendance_id) AS total_absences,
                    ROUND((COUNT(a.attendance_id) / %s) * 100, 2) AS absence_percentage
                FROM Attendance a
                JOIN etudiants e ON a.student_id = e.matricule
                WHERE a.course_code = %s AND a.teacher_id = %s AND a.status = 1
                GROUP BY e.matricule, e.nom_prenom
            """
            params = (total_classes, course_code, teacher_id)
        else:
            query = """
                SELECT 
                    e.matricule, 
                    e.nom_prenom, 
                    COUNT(a.attendance_id) AS total_absences,
                    ROUND((COUNT(a.attendance_id) / %s) * 100, 2) AS absence_percentage
                FROM Attendance a
                JOIN etudiants e ON a.student_id = e.matricule
                WHERE a.course_code = %s AND a.teacher_id = %s AND a.status = 1 AND a.week = %s
                GROUP BY e.matricule, e.nom_prenom
            """
            params = (total_classes, course_code, teacher_id, selected_week)

        cursor.execute(query, params)
        absence_data = cursor.fetchall()

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student Name', 'Matricule', 'Total Absences', 'Absence Percentage'])
        for student in absence_data:
            writer.writerow([student['nom_prenom'], student['matricule'], student['total_absences'], student['absence_percentage']])

        # Return CSV as a downloadable file
        output.seek(0)
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=absences_{course_code}_week_{selected_week}.csv"}
        )

    except mysql.connector.Error as e:
        flash(f"Erreur de base de données : {e}", 'danger')
        return redirect(url_for('tables'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/justifications')
def view_justifications():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Query to get all justified absences with related information
        query = """
        SELECT 
            j.justification_id,
            a.attendance_id,
            a.day,
            a.week,
            e.nom_prenom AS student_name,
            e.matricule AS matricule,
            d.intitulé_dep AS department_name,
            c.intitulé_cours AS course_name,
            t.name AS teacher_name,
            j.justification_image_link,
            j.submitted_at AS justification_date
        FROM Justification j
        INNER JOIN Attendance a ON j.attend_id = a.attendance_id
        INNER JOIN etudiants e ON a.student_id = e.matricule
        INNER JOIN departement d ON e.code_dep = d.code_dep
        INNER JOIN cours c ON a.course_code = c.cours_code
        INNER JOIN Teachers t ON a.teacher_id = t.id
        WHERE j.status = '0'  -- Only show pending justifications
        ORDER BY j.submitted_at DESC;
        """

        cursor.execute(query)
        justifications = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('justifications.html', justifications=justifications)

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        flash('An error occurred while fetching the justifications.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/update_justification_status', methods=['POST'])
def update_justification_status():
    justification_id = request.form.get('justification_id')
    status = request.form.get('status')  # '1' = validated, '0' = ignored

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if status == '1':
            # Update the justification to validated
            cursor.execute("""
                UPDATE Justification
                SET status = '1'
                WHERE justification_id = %s
            """, (justification_id,))
            flash('Justification validée avec succès!', 'success')
        elif status == '0':
            # Delete the justification if ignored
            cursor.execute("""
                DELETE FROM Justification
                WHERE justification_id = %s
            """, (justification_id,))
            flash('Justification ignorée et supprimée avec succès!', 'success')

        conn.commit()
        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        flash(f"Erreur de base de données: {err}", 'error')

    return redirect(url_for('view_justifications'))



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


