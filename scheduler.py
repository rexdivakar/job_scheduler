# scheduler.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import subprocess
from models import db, JobExecution

scheduler = BackgroundScheduler()

def execute_command(job_id, command):
    execution_time = datetime.now()
    status = 'Success'
    stdout = ''
    stderr = ''

    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.CalledProcessError as e:
        status = 'Failed'
        stdout = e.stdout
        stderr = e.stderr

    # Store execution details in the database
    execution = JobExecution(
        job_id=job_id,
        execution_time=execution_time,
        status=status,
        stdout=stdout,
        stderr=stderr
    )
    db.session.add(execution)
    db.session.commit()

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
