FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py core.py storage.py timesheets.py timesheet_drafts.py stock.py stocktake_sessions.py office_files.py stock_import.py stock_reports.py stock_handoff.py stock_standard.py standard_soh_template.xlsx stock_take.py stock_take_template.xlsx vehicles.py leave.py quote_settings.py accounts.py reminders.py labour.py schedule.py schedule_routes.py schedule_links.py schedule_history.py staff_setup.py weekly_report.py recycle.py ./
CMD exec gunicorn --bind :${PORT:-8080} --workers 2 --threads 4 --timeout 120 app:app
