# Job Scheduler

A Python-based job scheduler that accepts cron-formatted schedules, executes specified files, and provides a web interface for scheduling tasks.

## Features

- Schedule tasks using cron expressions.
- Execute Python scripts or other executable files.
- Web interface for adding, editing, and deleting jobs.
- Stores job information in an SQLite database.
- Validates cron expressions and file paths.

## Requirements

- Python 3.x
- Flask
- APScheduler
- SQLAlchemy
- croniter

## Setup Instructions

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/job_scheduler.git
   cd job_scheduler
