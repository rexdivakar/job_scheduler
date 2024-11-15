# app.py

from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from croniter import croniter
from datetime import datetime
import io
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Job(db.Model):
    __tablename__ = 'jobs'

    id = db.Column(db.Integer, primary_key=True)
    cron_expression = db.Column(db.String(120), nullable=False)
    command = db.Column(db.String(500), nullable=False)
    next_run_time = db.Column(db.DateTime)
    status = db.Column(db.String(10), default='Active')  # 'Active' or 'Inactive'

    executions = db.relationship('JobExecution', backref='job', cascade='all, delete-orphan')

class JobExecution(db.Model):
    __tablename__ = 'job_executions'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    execution_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(10), nullable=False)  # 'Success' or 'Failed'
    stdout = db.Column(db.Text)
    stderr = db.Column(db.Text)

# Configure the scheduler with a larger thread pool
executors = {
    'default': ThreadPoolExecutor(max_workers=20),  # Adjust max_workers based on your needs
}

scheduler = BackgroundScheduler(executors=executors)

def execute_command(job_id, command):
    with app.app_context():
        execution_time = datetime.now()
        status = 'Success'
        stdout = ''
        stderr = ''

        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.CalledProcessError as e:
            status = 'Failed'
            stdout = e.stdout
            stderr = e.stderr
        except Exception as e:
            status = 'Failed'
            stderr = f"An unexpected error occurred: {e}"
            print(f"Error executing job {job_id}: {e}")

        # Store execution details in the database
        try:
            execution = JobExecution(
                job_id=job_id,
                execution_time=execution_time,
                status=status,
                stdout=stdout,
                stderr=stderr
            )
            db.session.add(execution)
            db.session.commit()
        except Exception as e:
            print(f"Error saving execution log for job {job_id}: {e}")
            db.session.rollback()

def schedule_job(job):
    trigger = CronTrigger.from_crontab(job.cron_expression)
    scheduler.add_job(
        func=execute_command,
        trigger=trigger,
        args=[job.id, job.command],
        id=str(job.id),
        replace_existing=True
    )

def remove_job(job_id):
    try:
        scheduler.remove_job(str(job_id))
    except Exception as e:
        print(f"Error removing job {job_id}: {e}")

scheduler.start()

with app.app_context():
    db.create_all()

    # Load existing jobs into the scheduler
    jobs = Job.query.filter_by(status='Active').all()
    for job in jobs:
        schedule_job(job)

def is_valid_cron(cron_expression):
    return croniter.is_valid(cron_expression)

@app.route('/')
def index():
    jobs = Job.query.all()
    job_statuses = []

    for job in jobs:
        last_execution = JobExecution.query.filter_by(job_id=job.id).order_by(JobExecution.execution_time.desc()).first()
        if last_execution:
            last_status = last_execution.status
        else:
            last_status = 'Never Executed'
        job_statuses.append({
            'job': job,
            'last_status': last_status
        })

    return render_template('index.html', job_statuses=job_statuses)


@app.route('/add', methods=['GET', 'POST'])
def add_job():
    if request.method == 'POST':
        cron_expression = request.form['cron_expression']
        command = request.form['command']

        if not is_valid_cron(cron_expression):
            flash('Invalid cron expression', 'danger')
            return redirect(url_for('add_job'))

        if not command.strip():
            flash('Command cannot be empty', 'danger')
            return redirect(url_for('add_job'))

        new_job = Job(
            cron_expression=cron_expression,
            command=command,
            next_run_time=croniter(cron_expression, datetime.now()).get_next(datetime),
            status='Active'
        )
        db.session.add(new_job)
        db.session.commit()

        schedule_job(new_job)
        flash('Job added successfully', 'success')
        return redirect(url_for('index'))

    return render_template('add_job.html')

@app.route('/edit/<int:job_id>', methods=['GET', 'POST'])
def edit_job(job_id):
    job = Job.query.get_or_404(job_id)
    if request.method == 'POST':
        cron_expression = request.form['cron_expression']
        command = request.form['command']

        if not is_valid_cron(cron_expression):
            flash('Invalid cron expression', 'danger')
            return redirect(url_for('edit_job', job_id=job_id))

        if not command.strip():
            flash('Command cannot be empty', 'danger')
            return redirect(url_for('edit_job', job_id=job_id))

        job.cron_expression = cron_expression
        job.command = command
        job.next_run_time = croniter(cron_expression, datetime.now()).get_next(datetime)
        db.session.commit()

        # Update the scheduled job if active
        if job.status == 'Active':
            remove_job(job.id)
            schedule_job(job)

        flash('Job updated successfully', 'success')
        return redirect(url_for('index'))

    return render_template('edit_job.html', job=job)

@app.route('/delete/<int:job_id>', methods=['POST'])
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)
    remove_job(job.id)
    db.session.delete(job)
    db.session.commit()
    flash('Job deleted successfully', 'success')
    return redirect(url_for('index'))

@app.route('/executions/<int:job_id>')
def job_executions(job_id):
    job = Job.query.get_or_404(job_id)
    executions = JobExecution.query.filter_by(job_id=job_id).order_by(JobExecution.execution_time.desc()).all()
    return render_template('job_executions.html', job=job, executions=executions)

@app.route('/view_log/<int:execution_id>')
def view_log(execution_id):
    execution = JobExecution.query.get_or_404(execution_id)
    return render_template('view_log.html', execution=execution)

@app.route('/download_log/<int:execution_id>')
def download_log(execution_id):
    execution = JobExecution.query.get_or_404(execution_id)
    log_content = f"""Command: {execution.job.command}
Execution Time: {execution.execution_time}
Status: {execution.status}

Standard Output:
{execution.stdout}

Standard Error:
{execution.stderr}
"""

    buffer = io.BytesIO()
    buffer.write(log_content.encode('utf-8'))
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'job_{execution.job_id}_execution_{execution.id}.txt',
        mimetype='text/plain'
    )

@app.route('/execute/<int:job_id>', methods=['POST'])
def execute_now(job_id):
    job = Job.query.get_or_404(job_id)

    # Execute the command immediately
    execute_command(job.id, job.command)

    flash('Job executed successfully', 'success')
    return redirect(url_for('index'))

@app.route('/toggle_status/<int:job_id>', methods=['POST'])
def toggle_status(job_id):
    job = Job.query.get_or_404(job_id)
    if job.status == 'Active':
        job.status = 'Inactive'
        remove_job(job.id)
        flash('Job disabled successfully', 'success')
    else:
        job.status = 'Active'
        schedule_job(job)
        flash('Job enabled successfully', 'success')
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
