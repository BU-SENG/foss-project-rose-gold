from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from dotenv import load_dotenv
import os
import requests
from geopy.distance import geodesic
from collections import defaultdict

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads/resumes'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============================================================================
# DATABASE MODELS
# ============================================================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    
    # Contact Information
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    zip_code = db.Column(db.String(10))
    
    # Geographic coordinates
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # Role-specific fields
    company_name = db.Column(db.String(100))
    company_description = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    job_postings = db.relationship('JobPosting', backref='employer', lazy=True, cascade='all, delete-orphan')
    applications = db.relationship('Application', backref='applicant', lazy=True, cascade='all, delete-orphan')
    resumes = db.relationship('Resume', backref='user', lazy=True, cascade='all, delete-orphan')
    saved_jobs = db.relationship('SavedJob', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'


class JobPosting(db.Model):
    __tablename__ = 'job_postings'
    
    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Job Details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    employment_type = db.Column(db.String(50))
    salary_min = db.Column(db.Float)
    salary_max = db.Column(db.Float)
    
    # Location
    street_address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    
    # Status
    status = db.Column(db.String(20), default='active')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    applications = db.relationship('Application', backref='job', lazy=True, cascade='all, delete-orphan')
    saved_by = db.relationship('SavedJob', backref='job', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<JobPosting {self.title}>'


class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey('resumes.id'))
    
    # Application Details
    cover_letter = db.Column(db.Text)
    status = db.Column(db.String(50), default='applied')
    
    # Timestamps
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Application {self.id}>'


class Resume(db.Model):
    __tablename__ = 'resumes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Resume {self.original_filename}>'


class SavedJob(db.Model):
    __tablename__ = 'saved_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SavedJob {self.id}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def geocode_address(address, city, zip_code):
    """Convert address to latitude and longitude using Mapbox Geocoding API"""
    full_address = f"{address}, {city}, {zip_code}"
    api_key = os.getenv('MAPBOX_ACCESS_TOKEN')
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{full_address}.json"
    params = {
        'access_token': api_key,
        'limit': 1,
        'country': 'NG'
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data['features']:
            coordinates = data['features'][0]['geometry']['coordinates']
            longitude = coordinates[0]
            latitude = coordinates[1]
            return latitude, longitude
        else:
            return None, None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None, None


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers"""
    return geodesic((lat1, lon1), (lat2, lon2)).km


def is_within_service_area(lat, lng):
    """Check if location is within defined service area"""
    center_lat = float(os.getenv('SERVICE_AREA_CENTER_LAT', 0))
    center_lng = float(os.getenv('SERVICE_AREA_CENTER_LNG', 0))
    max_radius = float(os.getenv('SERVICE_AREA_RADIUS_KM', 50))
    
    distance = calculate_distance(center_lat, center_lng, lat, lng)
    return distance <= max_radius


# ============================================================================
# ROUTES - AUTHENTICATION
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    # Redirect if already logged in
    if current_user.is_authenticated:
        flash('You are already logged in. Logout first to create a new account.', 'warning')
        if current_user.role == 'employer':
            return redirect(url_for('employer_dashboard'))
        return redirect(url_for('job_seeker_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        city = request.form.get('city')
        zip_code = request.form.get('zip_code')
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('register'))
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long!', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'error')
            return redirect(url_for('register'))
        
        lat, lng = geocode_address(address, city, zip_code)
        
        if not lat or not lng:
            flash('Could not verify address. Please check and try again.', 'error')
            return redirect(url_for('register'))
        
        user = User(
            email=email,
            role=role,
            full_name=full_name,
            phone=phone,
            address=address,
            city=city,
            zip_code=zip_code,
            latitude=lat,
            longitude=lng
        )
        user.set_password(password)
        
        if role == 'employer':
            user.company_name = request.form.get('company_name')
            user.company_description = request.form.get('company_description')
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        if current_user.role == 'employer':
            return redirect(url_for('employer_dashboard'))
        return redirect(url_for('job_seeker_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            if user.role == 'employer':
                return redirect(url_for('employer_dashboard'))
            else:
                return redirect(url_for('job_seeker_dashboard'))
        else:
            flash('Invalid email or password!', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


# ============================================================================
# ROUTES - JOB SEEKER
# ============================================================================

@app.route('/job-seeker/dashboard')
@login_required
def job_seeker_dashboard():
    if current_user.role != 'job_seeker':
        flash('Access denied!', 'error')
        return redirect(url_for('index'))
    
    applications = Application.query.filter_by(applicant_id=current_user.id).order_by(Application.submitted_at.desc()).all()
    saved_jobs = SavedJob.query.filter_by(user_id=current_user.id).order_by(SavedJob.saved_at.desc()).all()
    now = datetime.now()
    
    return render_template('job_seeker_dashboard.html', applications=applications, saved_jobs=saved_jobs, now=now)


@app.route('/jobs/search')
@login_required
def search_jobs():
    if current_user.role != 'job_seeker':
        flash('Access denied!', 'error')
        return redirect(url_for('index'))
    
    keyword = request.args.get('keyword', '')
    category = request.args.get('category', '')
    radius = float(request.args.get('radius', 25))
    
    query = JobPosting.query.filter_by(status='active')
    
    if keyword:
        query = query.filter(
            db.or_(
                JobPosting.title.ilike(f'%{keyword}%'),
                JobPosting.description.ilike(f'%{keyword}%')
            )
        )
    
    if category:
        query = query.filter_by(category=category)
    
    jobs = query.all()
    
    jobs_with_distance = []
    for job in jobs:
        distance = calculate_distance(
            current_user.latitude,
            current_user.longitude,
            job.latitude,
            job.longitude
        )
        
        if distance <= radius:
            jobs_with_distance.append({
                'job': job,
                'distance': round(distance, 2)
            })
    
    jobs_with_distance.sort(key=lambda x: x['distance'])
    
    return render_template('search_jobs.html', jobs_with_distance=jobs_with_distance, keyword=keyword, category=category, radius=radius)


@app.route('/jobs/<int:job_id>')
@login_required
def view_job(job_id):
    job = JobPosting.query.get_or_404(job_id)
    
    distance = None
    if current_user.role == 'job_seeker':
        distance = round(calculate_distance(
            current_user.latitude,
            current_user.longitude,
            job.latitude,
            job.longitude
        ), 2)
    
    already_applied = Application.query.filter_by(
        job_id=job_id,
        applicant_id=current_user.id
    ).first() if current_user.role == 'job_seeker' else None
    
    is_saved = SavedJob.query.filter_by(
        job_id=job_id,
        user_id=current_user.id
    ).first() if current_user.role == 'job_seeker' else None
    
    return render_template('view_job.html', job=job, distance=distance, already_applied=already_applied, is_saved=is_saved)


@app.route('/jobs/<int:job_id>/apply', methods=['GET', 'POST'])
@login_required
def apply_job(job_id):
    if current_user.role != 'job_seeker':
        flash('Only job seekers can apply!', 'error')
        return redirect(url_for('index'))
    
    job = JobPosting.query.get_or_404(job_id)
    
    existing_application = Application.query.filter_by(
        job_id=job_id,
        applicant_id=current_user.id
    ).first()
    
    if existing_application:
        flash('You have already applied to this job!', 'warning')
        return redirect(url_for('view_job', job_id=job_id))
    
    if request.method == 'POST':
        resume_id = request.form.get('resume_id')
        cover_letter = request.form.get('cover_letter')
        
        application = Application(
            job_id=job_id,
            applicant_id=current_user.id,
            resume_id=resume_id if resume_id else None,
            cover_letter=cover_letter
        )
        
        db.session.add(application)
        db.session.commit()
        
        flash('Application submitted successfully!', 'success')
        return redirect(url_for('job_seeker_dashboard'))
    
    resumes = Resume.query.filter_by(user_id=current_user.id).all()
    return render_template('apply_job.html', job=job, resumes=resumes)


@app.route('/resumes/upload', methods=['POST'])
@login_required
def upload_resume():
    if current_user.role != 'job_seeker':
        flash('Only job seekers can upload resumes!', 'error')
        return redirect(url_for('index'))
    
    resume_count = Resume.query.filter_by(user_id=current_user.id).count()
    if resume_count >= 3:
        flash('You can only upload up to 3 resumes. Please delete one first.', 'warning')
        return redirect(url_for('job_seeker_dashboard'))
    
    if 'resume' not in request.files:
        flash('No file selected!', 'error')
        return redirect(url_for('job_seeker_dashboard'))
    
    file = request.files['resume']
    
    if file.filename == '':
        flash('No file selected!', 'error')
        return redirect(url_for('job_seeker_dashboard'))
    
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        filename = f"{current_user.id}_{datetime.utcnow().timestamp()}_{original_filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        resume = Resume(
            user_id=current_user.id,
            filename=filename,
            original_filename=original_filename
        )
        db.session.add(resume)
        db.session.commit()
        
        flash('Resume uploaded successfully!', 'success')
    else:
        flash('Only PDF files are allowed!', 'error')
    
    return redirect(url_for('job_seeker_dashboard'))


@app.route('/resumes/<int:resume_id>/delete', methods=['POST'])
@login_required
def delete_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    
    if resume.user_id != current_user.id:
        flash('Access denied!', 'error')
        return redirect(url_for('job_seeker_dashboard'))
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], resume.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    db.session.delete(resume)
    db.session.commit()
    
    flash('Resume deleted successfully!', 'success')
    return redirect(url_for('job_seeker_dashboard'))


@app.route('/jobs/<int:job_id>/save', methods=['POST'])
@login_required
def save_job(job_id):
    if current_user.role != 'job_seeker':
        flash('Only job seekers can save jobs!', 'error')
        return redirect(url_for('index'))
    
    existing = SavedJob.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    
    if existing:
        flash('Job already in your watch list!', 'warning')
    else:
        saved_job = SavedJob(user_id=current_user.id, job_id=job_id)
        db.session.add(saved_job)
        db.session.commit()
        flash('Job added to watch list!', 'success')
    
    return redirect(url_for('view_job', job_id=job_id))


@app.route('/jobs/<int:job_id>/unsave', methods=['POST'])
@login_required
def unsave_job(job_id):
    saved_job = SavedJob.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    
    if saved_job:
        db.session.delete(saved_job)
        db.session.commit()
        flash('Job removed from watch list!', 'success')
    
    return redirect(url_for('job_seeker_dashboard'))


# ============================================================================
# ROUTES - EMPLOYER
# ============================================================================

@app.route('/employer/dashboard')
@login_required
def employer_dashboard():
    if current_user.role != 'employer':
        flash('Access denied!', 'error')
        return redirect(url_for('index'))
    
    jobs = JobPosting.query.filter_by(employer_id=current_user.id).order_by(JobPosting.created_at.desc()).all()
    
    jobs_with_counts = []
    for job in jobs:
        application_count = Application.query.filter_by(job_id=job.id).count()
        jobs_with_counts.append({
            'job': job,
            'application_count': application_count
        })
    
    return render_template('employer_dashboard.html', jobs_with_counts=jobs_with_counts)


@app.route('/employer/jobs/create', methods=['GET', 'POST'])
@login_required
def create_job():
    if current_user.role != 'employer':
        flash('Access denied!', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        employment_type = request.form.get('employment_type')
        salary_min = request.form.get('salary_min')
        salary_max = request.form.get('salary_max')
        street_address = request.form.get('street_address')
        city = request.form.get('city')
        zip_code = request.form.get('zip_code')
        
        lat, lng = geocode_address(street_address, city, zip_code)
        
        if not lat or not lng:
            flash('Could not verify address. Please check and try again.', 'error')
            return redirect(url_for('create_job'))
        
        if not is_within_service_area(lat, lng):
            flash('This location is outside our service area!', 'error')
            return redirect(url_for('create_job'))
        
        job = JobPosting(
            employer_id=current_user.id,
            title=title,
            description=description,
            category=category,
            employment_type=employment_type,
            salary_min=float(salary_min) if salary_min else None,
            salary_max=float(salary_max) if salary_max else None,
            street_address=street_address,
            city=city,
            zip_code=zip_code,
            latitude=lat,
            longitude=lng
        )
        
        db.session.add(job)
        db.session.commit()
        
        flash('Job posted successfully!', 'success')
        return redirect(url_for('employer_dashboard'))
    
    return render_template('create_job.html')


@app.route('/employer/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_job(job_id):
    job = JobPosting.query.get_or_404(job_id)
    
    if job.employer_id != current_user.id:
        flash('Access denied!', 'error')
        return redirect(url_for('employer_dashboard'))
    
    if request.method == 'POST':
        job.title = request.form.get('title')
        job.description = request.form.get('description')
        job.category = request.form.get('category')
        job.employment_type = request.form.get('employment_type')
        job.salary_min = float(request.form.get('salary_min')) if request.form.get('salary_min') else None
        job.salary_max = float(request.form.get('salary_max')) if request.form.get('salary_max') else None
        
        db.session.commit()
        
        flash('Job updated successfully!', 'success')
        return redirect(url_for('employer_dashboard'))
    
    return render_template('edit_job.html', job=job)


@app.route('/employer/jobs/<int:job_id>/toggle-status', methods=['POST'])
@login_required
def toggle_job_status(job_id):
    job = JobPosting.query.get_or_404(job_id)
    
    if job.employer_id != current_user.id:
        flash('Access denied!', 'error')
        return redirect(url_for('employer_dashboard'))
    
    if job.status == 'active':
        job.status = 'paused'
        flash('Job paused successfully!', 'success')
    elif job.status == 'paused':
        job.status = 'active'
        flash('Job activated successfully!', 'success')
    
    db.session.commit()
    return redirect(url_for('employer_dashboard'))


@app.route('/employer/jobs/<int:job_id>/archive', methods=['POST'])
@login_required
def archive_job(job_id):
    job = JobPosting.query.get_or_404(job_id)
    
    if job.employer_id != current_user.id:
        flash('Access denied!', 'error')
        return redirect(url_for('employer_dashboard'))
    
    job.status = 'archived'
    db.session.commit()
    
    flash('Job archived successfully!', 'success')
    return redirect(url_for('employer_dashboard'))


@app.route('/employer/jobs/<int:job_id>/applications')
@login_required
def view_applications(job_id):
    job = JobPosting.query.get_or_404(job_id)
    
    if job.employer_id != current_user.id:
        flash('Access denied!', 'error')
        return redirect(url_for('employer_dashboard'))
    
    applications = Application.query.filter_by(job_id=job_id).order_by(Application.submitted_at.desc()).all()
    
    # Get all resumes for each applicant
    applications_with_resumes = []
    for application in applications:
        applicant_resumes = Resume.query.filter_by(user_id=application.applicant_id).all()
        applications_with_resumes.append({
            'application': application,
            'all_resumes': applicant_resumes
        })
    
    return render_template('view_applications.html', job=job, applications_with_resumes=applications_with_resumes)


@app.route('/employer/applications/<int:application_id>/update-status', methods=['POST'])
@login_required
def update_application_status(application_id):
    application = Application.query.get_or_404(application_id)
    
    if application.job.employer_id != current_user.id:
        flash('Access denied!', 'error')
        return redirect(url_for('employer_dashboard'))
    
    new_status = request.form.get('status')
    application.status = new_status
    db.session.commit()
    
    flash('Application status updated!', 'success')
    return redirect(url_for('view_applications', job_id=application.job_id))


@app.route('/uploads/resumes/<filename>')
@login_required
def download_resume(filename):
    if current_user.role != 'employer':
        flash('Access denied!', 'error')
        return redirect(url_for('index'))
    
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ============================================================================
# ROUTES - PROFILE MANAGEMENT
# ============================================================================

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.phone = request.form.get('phone')
        
        # Get new address fields
        new_address = request.form.get('address')
        new_city = request.form.get('city')
        new_zip = request.form.get('zip_code')
        
        # Check if address changed
        address_changed = (
            new_address != current_user.address or 
            new_city != current_user.city or 
            new_zip != current_user.zip_code
        )
        
        if address_changed:
            # Re-geocode the new address
            lat, lng = geocode_address(new_address, new_city, new_zip)
            
            if not lat or not lng:
                flash('Could not verify new address. Please check and try again.', 'error')
                return redirect(url_for('edit_profile'))
            
            # Update address and coordinates
            current_user.address = new_address
            current_user.city = new_city
            current_user.zip_code = new_zip
            current_user.latitude = lat
            current_user.longitude = lng
        
        if current_user.role == 'employer':
            current_user.company_name = request.form.get('company_name')
            current_user.company_description = request.form.get('company_description')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html')


# ============================================================================
# ROUTES - ANALYTICS
# ============================================================================

@app.route('/analytics')
@login_required
def analytics():
    if current_user.role != 'employer':
        flash('Access denied!', 'error')
        return redirect(url_for('index'))
    
    jobs = JobPosting.query.filter_by(employer_id=current_user.id).all()
    total_apps = Application.query.join(JobPosting).filter(JobPosting.employer_id == current_user.id).all()
    total_applications = len(total_apps)
    
    accepted = len([app for app in total_apps if app.status == 'accepted'])
    acceptance_rate = (accepted / total_applications * 100) if total_applications else 0
    
    interviews = len([app for app in total_apps if app.status == 'interview'])
    interview_rate = (interviews / total_applications * 100) if total_applications else 0
    
    rejected = len([app for app in total_apps if app.status == 'rejected'])
    rejection_rate = (rejected / total_applications * 100) if total_applications else 0
    
    responded = len([app for app in total_apps if app.status != 'applied'])
    response_rate = (responded / total_applications * 100) if total_applications else 0
    
    apps_by_month = defaultdict(int)
    apps_by_status = defaultdict(int)
    
    for app in total_apps:
        month = app.submitted_at.strftime('%B %Y')
        apps_by_month[month] += 1
        apps_by_status[app.status] += 1
    
    sorted_months = dict(sorted(apps_by_month.items(), key=lambda x: datetime.strptime(x[0], '%B %Y'), reverse=True)[:6])
    
    response_times = []
    for app in total_apps:
        if app.status != 'applied':
            time_diff = (app.updated_at - app.submitted_at).days
            response_times.append(time_diff)
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    job_popularity = {}
    for job in jobs:
        app_count = Application.query.filter_by(job_id=job.id).count()
        job_popularity[job.title] = app_count
    
    most_popular_job = max(job_popularity.items(), key=lambda x: x[1]) if job_popularity else ("None", 0)
    active_jobs = len([job for job in jobs if job.status == 'active'])
    paused_jobs = len([job for job in jobs if job.status == 'paused'])
    archived_jobs = len([job for job in jobs if job.status == 'archived'])
    
    return render_template('analytics.html', 
                         total_jobs=len(jobs),
                         total_applications=total_applications,
                         acceptance_rate=round(acceptance_rate, 1),
                         interview_rate=round(interview_rate, 1),
                         rejection_rate=round(rejection_rate, 1),
                         response_rate=round(response_rate, 1),
                         apps_by_month=sorted_months,
                         apps_by_status=dict(apps_by_status),
                         avg_response_time=round(avg_response_time, 1),
                         most_popular_job=most_popular_job,
                         active_jobs=active_jobs,
                         paused_jobs=paused_jobs,
                         archived_jobs=archived_jobs)


# ============================================================================
# INITIALIZE DATABASE AND RUN APP
# ============================================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
