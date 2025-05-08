from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
import pandas as pd
import os
import re
from io import BytesIO
from translations import translations
from sqlalchemy import func, or_
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import math

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True  # Force template reloading
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize CSRF protection
csrf = CSRFProtect(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    roll_number = db.Column(db.String(20), unique=True, nullable=False)
    # Replace class_name with class_id
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    phone = db.Column(db.String(15), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    attendance = db.relationship('Attendance', backref='student', lazy=True)
    class_relation = db.relationship('Class', backref='students', lazy=True)  # Define the relationship

class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<Class {self.name}>"

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False)  # Present or Absent
    reason = db.Column(db.String(200), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_class_number(class_name):
    """Extract numeric class number from class name (e.g., 'Class 1' -> 1)"""
    match = re.search(r'(\d+)', class_name)
    if match:
        return int(match.group(1))
    return 0

def generate_roll_number(class_name):
    """Generate next available roll number for a class (e.g., Class 1 -> 101, 102, etc.)"""
    class_num = get_class_number(class_name)
    if class_num <= 0:
        # Default to class 1 if class number can't be determined
        class_num = 1
    
    # Roll number prefix: Class 1 -> 100, Class 2 -> 200, etc.
    prefix = class_num * 100
    
    # Find the highest roll number for this class
    # Replace class_name with class_relation.name
    students = Student.query.join(Class).filter(Class.name == class_name).all()
    max_roll = prefix
    
    for student in students:
        try:
            roll_num = int(student.roll_number)
            if roll_num >= prefix and roll_num < prefix + 100:
                max_roll = max(max_roll, roll_num)
        except ValueError:
            # Skip roll numbers that aren't numeric
            continue
    
    # Return the next available roll number
    return str(max_roll + 1)

def get_class_statistics(selected_date):
    """Get attendance statistics for each class"""
    class_stats = []
    
    # Get unique class names
    # Replace Student.class_name with Class.name
    classes = db.session.query(Class.name).distinct().all()
    classes = [c[0] for c in classes]
    
    for class_name in classes:
        # Join Student and Class tables
        students = Student.query.join(Class).filter(Class.name == class_name).order_by(Student.roll_number.asc()).all()
        attendance_today = {a.student_id: a for a in Attendance.query.filter_by(date=selected_date).all()}
        
        present = [s for s in students if attendance_today.get(s.id, None) and attendance_today[s.id].status == 'Present']
        absent = [s for s in students if attendance_today.get(s.id, None) and attendance_today[s.id].status == 'Absent']
        
        class_stats.append({
            'class_name': class_name,
            'total': len(students),
            'present': len(present),
            'absent': len(absent),
            'attendance_rate': round(len(present) / len(students) * 100, 1) if students else 0
        })
    
    # Sort by class number
    class_stats.sort(key=lambda x: get_class_number(x['class_name']))
    
    return class_stats

def init_db():
    """
    Initialize the database if needed.
    - Creates tables only if they don't exist
    - Only adds admin user if no users exist
    - Only adds example students if no students exist
    This ensures existing data is preserved between application restarts.
    """
    # Create tables if they don't exist
    db.create_all()
    
    # Add admin user if no users exist
    if User.query.count() == 0:
        print("Creating admin user")
        admin = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

    # Add example students if none exist
    if Student.query.count() == 0:
        print("Adding example students")
        # Create classes first
        class1 = Class(name='Class 1')
        class2 = Class(name='Class 2')
        class3 = Class(name='Class 3')
        class4 = Class(name='Class 4')
        class5 = Class(name='Class 5')
        db.session.add_all([class1, class2, class3, class4, class5])
        db.session.commit()
        
        example_students = [
            {
                'name': 'Ahmed Khan',
                'class_name': 'Class 1',
                'phone': '03001234567',
                'email': 'ahmed.khan@example.com'
            },
            {
                'name': 'Fatima Noor',
                'class_name': 'Class 1',
                'phone': '03001234568',
                'email': 'fatima.noor@example.com'
            },
            {
                'name': 'Ali Raza',
                'class_name': 'Class 2',
                'phone': '03001234569',
                'email': 'ali.raza@example.com'
            },
            {
                'name': 'Ayesha Siddiqui',
                'class_name': 'Class 2',
                'phone': '03001234570',
                'email': 'ayesha.siddiqui@example.com'
            },
            {
                'name': 'Bilal Ahmed',
                'class_name': 'Class 3',
                'phone': '03001234571',
                'email': 'bilal.ahmed@example.com'
            },
            {
                'name': 'Zainab Bano',
                'class_name': 'Class 3',
                'phone': '03001234572',
                'email': 'zainab.bano@example.com'
            },
            {
                'name': 'Hassan Ali',
                'class_name': 'Class 4',
                'phone': '03001234573',
                'email': 'maryam.javed@example.com'
            },
            {
                'name': 'Maryam Javed',
                'class_name': 'Class 4',
                'phone': '03001234574',
                'email': 'hassan.ali@example.com'
            },
            {
                'name': 'Usman Tariq',
                'class_name': 'Class 5',
                'phone': '03001234575',
                'email': 'sara.imran@example.com'
            },
            {
                'name': 'Sara Imran',
                'class_name': 'Class 5',
                'phone': '03001234576',
                'email': 'usman.tariq@example.com'
            }
        ]
        
        for student_data in example_students:
            # Get the class object
            class_obj = Class.query.filter_by(name=student_data['class_name']).first()
            if class_obj:
                # Generate roll number based on class
                roll_number = generate_roll_number(student_data['class_name'])
                student_data['roll_number'] = roll_number
                # Replace class_name with class_id
                student_data['class_id'] = class_obj.id
                # Remove class_name only if it exists
                if 'class_name' in student_data:
                    del student_data['class_name']
                
                student = Student(**student_data)
                db.session.add(student)
        db.session.commit()

def copy_previous_attendance(current_date):
    """
    Copy attendance records from the previous day to the current day if not already present.
    
    This function implements the persistent attendance feature:
    1. It finds the most recent date before the current date that has attendance records
    2. For each student who doesn't have an attendance record for the current day,
       it copies their status (present/absent) and reason from the previous day
    3. This ensures attendance persists automatically unless explicitly changed
    
    Args:
        current_date: The date for which to copy attendance (usually today)
    """
    # Find the most recent date before the current date that has attendance records
    prev_date_record = db.session.query(Attendance.date).filter(Attendance.date < current_date).order_by(Attendance.date.desc()).first()
    
    if not prev_date_record:
        return  # No previous records, nothing to copy
    
    prev_date = prev_date_record[0]
    
    # Get all students
    students = Student.query.all()
    
    # Get previous day's attendance records
    prev_attendance = {a.student_id: a for a in Attendance.query.filter_by(date=prev_date).all()}
    
    # Get current day's attendance records (if any)
    current_attendance = {a.student_id: a for a in Attendance.query.filter_by(date=current_date).all()}
    
    # For each student, if they don't have an attendance record for the current day,
    # copy their status from the previous day
    copied_count = 0
    for student in students:
        if student.id not in current_attendance and student.id in prev_attendance:
            prev_record = prev_attendance[student.id]
            new_record = Attendance(
                student_id=student.id,
                date=current_date,
                status=prev_record.status,
                reason=prev_record.reason
            )
            db.session.add(new_record)
            copied_count += 1
    
    # Only commit if we actually copied records
    if copied_count > 0:
        db.session.commit()
        print(f"Copied {copied_count} attendance records from {prev_date} to {current_date}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    selected_date = request.args.get('date', str(date.today()))
    
    print(f"\n--- Dashboard for date: {selected_date} ---")
    # Copy attendance from previous day if needed
    copy_previous_attendance(selected_date)
    
    # Overall statistics
    students = Student.query.order_by(Student.roll_number.asc()).all()
    attendance_today = {a.student_id: a for a in Attendance.query.filter_by(date=selected_date).all()}
    present = [s for s in students if attendance_today.get(s.id, None) and attendance_today[s.id].status == 'Present']
    absent = [s for s in students if attendance_today.get(s.id, None) and attendance_today[s.id].status == 'Absent']
    missing = len(students) - len(present) - len(absent)
    
    print(f"Total students: {len(students)}, Present: {len(present)}, Absent: {len(absent)}, Missing records: {missing}")
    
    # Class-wise statistics
    class_stats = get_class_statistics(selected_date)
    
    return render_template('dashboard.html', 
                         total=len(students), 
                         present=len(present), 
                         absent=len(absent),
                         selected_date=selected_date,
                         date=datetime.strptime(selected_date, '%Y-%m-%d'),
                         class_stats=class_stats)

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        name = request.form['name']
        class_id = request.form['class_name']  # Get class_id from form
        phone = request.form.get('phone')
        email = request.form.get('email')
        
        # Check if roll number was provided or auto-generate
        roll_number = request.form.get('roll_number')
        if not roll_number:
            # Fetch the class to get the class name
            class_obj = Class.query.get(class_id)
            if class_obj:
                roll_number = generate_roll_number(class_obj.name)
            else:
                flash('Invalid Class selected.', 'danger')
                return redirect(url_for('register'))
        
        # Check if roll number already exists
        if Student.query.filter_by(roll_number=roll_number).first():
            flash('Roll number already exists', 'danger')
            return redirect(url_for('register'))
        
        # Check if student with same name and class already exists
        existing_student = Student.query.filter_by(name=name, class_id=class_id).first()
        if existing_student:
            flash('Warning: A student with the same name and class already exists. Please check before adding.', 'warning')
            
        student = Student(
            name=name,
            roll_number=roll_number,
            class_id=class_id,
            phone=phone,
            email=email
        )
        db.session.add(student)
        db.session.commit()
        flash('Student registered successfully', 'success')
        return redirect(url_for('register'))
    
    # For GET request, handle filter parameters
    filter_class = request.args.get('filter_class', '')
    filter_name = request.args.get('filter_name', '')
    filter_roll = request.args.get('filter_roll', '')
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Show 20 students per page
    
    # Build query with filters
    query = Student.query
    
    if filter_class:
        # Filter by class_id instead of class_name
        query = query.filter(Student.class_id == filter_class)
    if filter_name:
        query = query.filter(Student.name.ilike(f'%{filter_name}%'))
    if filter_roll:
        query = query.filter(Student.roll_number.ilike(f'%{filter_roll}%'))
    
    # Sort by roll_number in ascending order
    query = query.order_by(Student.roll_number.asc())
    
    # Paginate results
    total_students = query.count()
    students = query.paginate(page=page, per_page=per_page, error_out=False)
    total_pages = math.ceil(total_students / per_page)
    
    # Get classes for dropdown
    classes = Class.query.all()
    
    return render_template('register.html', 
                          students=students.items, 
                          classes=classes,  # Pass classes to template
                          filter_class=filter_class,
                          filter_name=filter_name,
                          filter_roll=filter_roll,
                          page=page,
                          total_pages=total_pages,
                          per_page=per_page,
                          total_students=total_students)

@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    selected_date = request.args.get('date', str(date.today()))
    
    print(f"\n--- Attendance for date: {selected_date} ---")
    # Copy attendance from previous day if needed
    copy_previous_attendance(selected_date)
    
    # Filter by class
    filter_class = request.args.get('filter_class', '')
    query = Student.query
    if filter_class:
        query = query.filter(Student.class_id == filter_class)
    
    # Sort students by roll number
    query = query.order_by(Student.roll_number.asc())
    
    # Get classes for dropdown
    classes = Class.query.all()
    
    students = query.all()
    
    if request.method == 'POST':
        print(f"Saving attendance data for {len(students)} students on {selected_date}")
        updated_count = 0
        for student in students:
            status = request.form.get(f'status_{student.id}', 'Absent')
            reason = request.form.get(f'reason_{student.id}', '')
            existing = Attendance.query.filter_by(student_id=student.id, date=selected_date).first()
            if existing:
                if existing.status != status or existing.reason != reason:
                    existing.status = status
                    existing.reason = reason
                    updated_count += 1
            else:
                db.session.add(Attendance(student_id=student.id, date=selected_date, status=status, reason=reason))
                updated_count += 1
        
        db.session.commit()
        print(f"Updated {updated_count} attendance records")
        flash('Attendance recorded successfully', 'success')
        return redirect(url_for('attendance', date=selected_date, filter_class=filter_class))
    
    attendance_today = {a.student_id: a for a in Attendance.query.filter_by(date=selected_date).all()}
    missing = len(students) - len([s for s in students if s.id in attendance_today])
    print(f"Students in view: {len(students)}, With attendance records: {len(students) - missing}, Missing records: {missing}")
    
    return render_template('attendance.html', 
                         students=students, 
                         attendance_today=attendance_today,
                         selected_date=selected_date,
                         classes=classes,
                         filter_class=filter_class)

@app.route('/absent')
@login_required
def absent_list():
    selected_date = request.args.get('date', str(date.today()))
    absents = Attendance.query.filter_by(date=selected_date, status='Absent').join(Student).order_by(Student.roll_number.asc()).all()
    return render_template('absent_list.html', absents=absents, selected_date=selected_date)

@app.route('/reports')
@login_required
def reports():
    start_date = request.args.get('start_date', str(date.today()))
    end_date = request.args.get('end_date', str(date.today()))
    class_name = request.args.get('class_name', '')
    
    query = Attendance.query.join(Student).join(Class)
    if class_name:
        query = query.filter(Class.name == class_name)
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    
    # Sort by roll number first, then by date
    query = query.order_by(Student.roll_number.asc(), Attendance.date.asc())
    
    attendance_records = query.all()
    
    # Get unique class names for filter dropdown
    class_names = [c[0] for c in db.session.query(Class.name).distinct().all()]
    class_names.sort(key=get_class_number)
    
    return render_template('reports.html', 
                         attendance_records=attendance_records,
                         start_date=start_date,
                         end_date=end_date,
                         class_name=class_name,
                         class_names=class_names)

@app.route('/export')
@login_required
def export_data():
    start_date = request.args.get('start_date', str(date.today()))
    end_date = request.args.get('end_date', str(date.today()))
    class_name = request.args.get('class_name', '')
    
    query = Attendance.query.join(Student)
    if class_name:
        query = query.filter(Student.class_name == class_name)
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    
    # Sort by roll number first, then by date
    query = query.order_by(Student.roll_number.asc(), Attendance.date.asc())
    
    attendance_records = query.all()
    
    data = []
    for record in attendance_records:
        data.append({
            'Date': record.date,
            'Student Name': record.student.name,
            'Roll Number': record.student.roll_number,
            'Class': record.student.class_name,
            'Status': record.status,
            'Reason': record.reason
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance')
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'attendance_report_{start_date}_to_{end_date}.xlsx'
    )

@app.route('/export_absent_list')
@login_required
def export_absent_list():
    selected_date = request.args.get('date', str(date.today()))
    
    absents = Attendance.query.filter_by(date=selected_date, status='Absent').join(Student).all()
    
    data = []
    for absent in absents:
        data.append({
            'Date': selected_date,
            'Roll Number': absent.student.roll_number,
            'Student Name': absent.student.name,
            'Class': absent.student.class_relation.name,
            'Reason': absent.reason or '-',
            'Phone': absent.student.phone or '-'
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Absent Students')
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'absent_students_{selected_date}.xlsx'
    )

@app.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    # Get all classes for the dropdown
    classes = Class.query.all()
    
    if request.method == 'POST':
        student.name = request.form['name']
        
        # Check if roll number has changed
        new_roll_number = request.form['roll_number']
        if new_roll_number != student.roll_number:
            # Check if the new roll number already exists
            if Student.query.filter_by(roll_number=new_roll_number).first():
                flash('Roll number already exists', 'danger')
                return render_template('edit_student.html', student=student, classes=classes)
            student.roll_number = new_roll_number
        
        student.class_id = request.form['class_id']
        student.phone = request.form.get('phone')
        student.email = request.form.get('email')
        db.session.commit()
        flash('Student information updated successfully', 'success')
        return redirect(url_for('register'))
    
    return render_template('edit_student.html', student=student, classes=classes)

@app.route('/student/<int:student_id>')
@login_required
def student_details(student_id):
    student = Student.query.get_or_404(student_id)
    
    # Get date range for attendance history (last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    # Get attendance records for the student
    attendance_records = Attendance.query.filter_by(student_id=student.id).filter(
        Attendance.date.between(str(start_date), str(end_date))
    ).order_by(Attendance.date.desc()).all()
    
    # Calculate attendance statistics
    total_days = len(attendance_records)
    days_present = sum(1 for record in attendance_records if record.status == 'Present')
    days_absent = total_days - days_present
    attendance_percentage = round(days_present / total_days * 100, 1) if total_days > 0 else 0
    
    return render_template('student_details.html', 
                         student=student, 
                         attendance_records=attendance_records,
                         days_present=days_present,
                         days_absent=days_absent,
                         attendance_percentage=attendance_percentage,
                         total_days=total_days)

@app.context_processor
def inject_translations():
    lang = session.get('lang', 'en')
    return {'_': translations[lang]}

@app.route('/switch_language/<lang>')
def switch_language(lang):
    if lang in ['en', 'bn']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/db_status')
@login_required
def db_status():
    """Display database status information for debugging"""
    # Count students
    student_count = Student.query.count()
    students_by_class = {}
    # Replace Student.class_name with Class.name
    class_names = [c[0] for c in db.session.query(Class.name).distinct().all()]
    for class_name in class_names:
        # Join Student and Class to filter by Class.name
        students_by_class[class_name] = Student.query.join(Class).filter(Class.name == class_name).count()
    
    # Count attendance records
    attendance_count = Attendance.query.count()
    
    # Get unique dates with attendance records
    dates = [d[0] for d in db.session.query(Attendance.date).distinct().order_by(Attendance.date.desc()).all()]
    attendance_by_date = {}
    for d in dates:
        attendance_by_date[d] = Attendance.query.filter_by(date=d).count()
    
    return render_template('db_status.html', 
                          student_count=student_count,
                          students_by_class=students_by_class,
                          attendance_count=attendance_count,
                          attendance_by_date=attendance_by_date,
                          dates=dates)

# Class Management Routes
@app.route('/classes')
@login_required
def classes():
    classes = Class.query.all()
    return render_template('classes.html', classes=classes)

@app.route('/classes/add', methods=['GET', 'POST'])
@login_required
def add_class():
    if request.method == 'POST':
        name = request.form['name']
        if Class.query.filter_by(name=name).first():
            flash('Class name already exists', 'danger')
            return redirect(url_for('classes'))
        new_class = Class(name=name)
        db.session.add(new_class)
        db.session.commit()
        flash('Class added successfully', 'success')
        return redirect(url_for('classes'))
    return render_template('add_class.html')

@app.route('/classes/edit/<int:class_id>', methods=['GET', 'POST'])
@login_required
def edit_class(class_id):
    class_to_edit = Class.query.get_or_404(class_id)
    if request.method == 'POST':
        name = request.form['name']
        if Class.query.filter_by(name=name).first() and name != class_to_edit.name:
            flash('Class name already exists', 'danger')
            return redirect(url_for('classes'))
        class_to_edit.name = name
        db.session.commit()
        flash('Class updated successfully', 'success')
        return redirect(url_for('classes'))
    return render_template('edit_class.html', class_to_edit=class_to_edit)

@app.route('/classes/delete/<int:class_id>')
@login_required
def delete_class(class_id):
    class_to_delete = Class.query.get_or_404(class_id)
    db.session.delete(class_to_delete)
    db.session.commit()
    flash('Class deleted successfully', 'success')
    return redirect(url_for('classes'))

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(debug=debug, use_reloader=debug) 