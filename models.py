# models.py

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Job(db.Model):
    __tablename__ = 'jobs'

    id = db.Column(db.Integer, primary_key=True)
    cron_expression = db.Column(db.String(120), nullable=False)
    command = db.Column(db.String(500), nullable=False)
    next_run_time = db.Column(db.DateTime)
    status = db.Column(db.String(10), default='Active')

    executions = db.relationship('JobExecution', backref='job', cascade='all, delete-orphan')

class JobExecution(db.Model):
    __tablename__ = 'job_executions'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    execution_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(10), nullable=False)  # 'Success' or 'Failed'
    stdout = db.Column(db.Text)
    stderr = db.Column(db.Text)
