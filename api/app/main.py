import json
import os
import uuid

import psycopg
import redis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Cloud Job Queue API",
    version="1.0.0",
    description="API for submitting and monitoring asynchronous background jobs."
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/jobqueue"
)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379"
)


# ============================================================
# REDIS CLIENT
# ============================================================

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True
)


# ============================================================
# REQUEST MODELS
# ============================================================

class JobRequest(BaseModel):
    job_type: str
    payload: dict


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    return psycopg.connect(DATABASE_URL)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "service": "job-queue-api",
        "status": "healthy"
    }


# ============================================================
# CREATE JOB
# ============================================================

@app.post("/jobs")
def create_job(data: JobRequest):

    job_id = str(uuid.uuid4())

    try:

        # ----------------------------------------------------
        # Store job in PostgreSQL
        # ----------------------------------------------------

        with get_db_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    INSERT INTO jobs
                    (
                        id,
                        job_type,
                        payload,
                        status
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        job_id,
                        data.job_type,
                        json.dumps(data.payload),
                        "queued"
                    )
                )

                connection.commit()

        # ----------------------------------------------------
        # Add job to Redis queue
        # ----------------------------------------------------

        queue_message = {
            "job_id": job_id,
            "job_type": data.job_type,
            "payload": data.payload
        }

        redis_client.rpush(
            "job_queue",
            json.dumps(queue_message)
        )

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return {
            "job_id": job_id,
            "status": "queued",
            "message": "Job added to queue"
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to create job: {str(error)}"
        )


# ============================================================
# GET JOB STATUS
# ============================================================

@app.get("/jobs/{job_id}")
def get_job(job_id: str):

    try:

        with get_db_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT
                        id,
                        job_type,
                        payload,
                        status,
                        result,
                        error,
                        attempts,
                        created_at,
                        started_at,
                        completed_at
                    FROM jobs
                    WHERE id = %s
                    """,
                    (job_id,)
                )

                job = cursor.fetchone()

        # ----------------------------------------------------
        # Job not found
        # ----------------------------------------------------

        if not job:

            raise HTTPException(
                status_code=404,
                detail="Job not found"
            )

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return {
            "job_id": str(job[0]),
            "job_type": job[1],
            "payload": job[2],
            "status": job[3],
            "result": job[4],
            "error": job[5],
            "attempts": job[6],
            "created_at": job[7],
            "started_at": job[8],
            "completed_at": job[9]
        }

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve job: {str(error)}"
        )


# ============================================================
# LIST JOBS
# ============================================================

@app.get("/jobs")
def list_jobs():

    try:

        with get_db_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT
                        id,
                        job_type,
                        status,
                        attempts,
                        created_at,
                        started_at,
                        completed_at
                    FROM jobs
                    ORDER BY created_at DESC
                    LIMIT 100
                    """
                )

                jobs = cursor.fetchall()

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        return {
            "count": len(jobs),

            "jobs": [
                {
                    "job_id": str(job[0]),
                    "job_type": job[1],
                    "status": job[2],
                    "attempts": job[3],
                    "created_at": job[4],
                    "started_at": job[5],
                    "completed_at": job[6]
                }

                for job in jobs
            ]
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve jobs: {str(error)}"
        )