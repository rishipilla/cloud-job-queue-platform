import json
import os
import time
from datetime import datetime, timezone

import psycopg
import redis


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/jobqueue"
)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379"
)

QUEUE_NAME = "job_queue"

MAX_ATTEMPTS = 3


redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=None
)


def get_db_connection():

    return psycopg.connect(
        DATABASE_URL
    )


def process_job(job):

    job_id = job["job_id"]
    job_type = job["job_type"]
    payload = job["payload"]

    print(
        f"[WORKER] Processing job: {job_id}",
        flush=True
    )

    print(
        f"[WORKER] Job type: {job_type}",
        flush=True
    )

    print(
        f"[WORKER] Payload: {payload}",
        flush=True
    )

    time.sleep(5)

    # Used later to test retry behavior.
    # A job with job_type="failure-test" intentionally fails.

    if job_type == "failure-test":

        raise RuntimeError(
            "Intentional failure for retry testing"
        )

    result = {
        "message": "Job processed successfully",
        "job_id": job_id,
        "job_type": job_type,
        "processed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "output": {
            "processed": True,
            "input": payload
        }
    }

    return result


def mark_processing(job_id):

    with get_db_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE jobs
                SET
                    status = 'processing',
                    attempts = attempts + 1,
                    started_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (job_id,)
            )

            connection.commit()


def get_attempts(job_id):

    with get_db_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT attempts
                FROM jobs
                WHERE id = %s
                """,
                (job_id,)
            )

            row = cursor.fetchone()

            if not row:
                return 0

            return row[0]


def mark_completed(
    job_id,
    result
):

    with get_db_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE jobs
                SET
                    status = 'completed',
                    result = %s,
                    error = NULL,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    json.dumps(result),
                    job_id
                )
            )

            connection.commit()


def mark_failed(
    job_id,
    error_message
):

    with get_db_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE jobs
                SET
                    status = 'failed',
                    error = %s
                WHERE id = %s
                """,
                (
                    error_message,
                    job_id
                )
            )

            connection.commit()


def requeue_job(job):

    redis_client.rpush(
        QUEUE_NAME,
        json.dumps(job)
    )

    print(
        f"[WORKER] Job requeued: {job['job_id']}",
        flush=True
    )


def start_worker():

    print(
        "[WORKER] Starting job worker...",
        flush=True
    )

    print(
        f"[WORKER] Listening on queue: {QUEUE_NAME}",
        flush=True
    )

    while True:

        try:

            result = redis_client.brpop(
                QUEUE_NAME,
                timeout=0
            )

            if result is None:
                continue

            _, raw_job = result

            job = json.loads(
                raw_job
            )

            job_id = job["job_id"]

            print(
                f"[WORKER] Received job: {job_id}",
                flush=True
            )

            try:

                mark_processing(
                    job_id
                )

                attempts = get_attempts(
                    job_id
                )

                print(
                    f"[WORKER] Attempt {attempts}/{MAX_ATTEMPTS}",
                    flush=True
                )

                result = process_job(
                    job
                )

                mark_completed(
                    job_id,
                    result
                )

                print(
                    f"[WORKER] Job completed: {job_id}",
                    flush=True
                )

            except Exception as error:

                print(
                    f"[WORKER] Job failed: {job_id}",
                    flush=True
                )

                print(
                    f"[WORKER] Error: {error}",
                    flush=True
                )

                attempts = get_attempts(
                    job_id
                )

                if attempts < MAX_ATTEMPTS:

                    print(
                        f"[WORKER] Retrying job {job_id}",
                        flush=True
                    )

                    mark_failed(
                        job_id,
                        str(error)
                    )

                    requeue_job(
                        job
                    )

                else:

                    print(
                        f"[WORKER] Maximum attempts reached: {job_id}",
                        flush=True
                    )

                    mark_failed(
                        job_id,
                        f"Maximum attempts reached: {error}"
                    )

        except Exception as error:

            print(
                f"[WORKER] Worker error: {error}",
                flush=True
            )

            time.sleep(2)


if __name__ == "__main__":

    start_worker()