from apscheduler.schedulers.blocking import BlockingScheduler
from jobs import sync_oracle_candidates

def run_scheduler():
    scheduler = BlockingScheduler()

    scheduler.add_job(sync_oracle_candidates, "interval", hours=1)

    print("Scheduler started")

    scheduler.start()