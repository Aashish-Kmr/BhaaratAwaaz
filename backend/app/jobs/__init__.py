from app import config
from app.jobs.store import JobStore
from app.jobs.worker import Worker

job_store = JobStore(config.JOBS_DIR)
worker = Worker(job_store)
