import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  Activity,
  CheckCircle2,
  Clock3,
  RefreshCw,
  XCircle,
  Plus,
  X,
} from "lucide-react";
import "./App.css";

const API_URL = "http://localhost:8020";
const POLL_INTERVAL_MS = 3000;

const STATUS_ICONS = {
  completed: CheckCircle2,
  failed: XCircle,
  processing: Activity,
  queued: Clock3,
};

function getStatusIcon(status) {
  const Icon = STATUS_ICONS[status] ?? Clock3;
  return <Icon size={18} />;
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "-";
}

function countByStatus(jobs) {
  return jobs.reduce(
    (counts, job) => {
      counts[job.status] = (counts[job.status] ?? 0) + 1;
      return counts;
    },
    { queued: 0, processing: 0, completed: 0, failed: 0 }
  );
}

function App() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);

  const [jobType, setJobType] = useState("demo");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [selectedJob, setSelectedJob] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  const fetchJobs = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/jobs`);
      setJobs(response.data.jobs);
      setLoadError(null);
    } catch (error) {
      console.error("Failed to fetch jobs:", error);
      setLoadError("Couldn't reach the job queue. Retrying shortly...");
    } finally {
      setLoading(false);
    }
  }, []);

  const createJob = useCallback(async () => {
    if (!jobType.trim() || submitting) return;

    try {
      setSubmitting(true);
      await axios.post(`${API_URL}/jobs`, {
        job_type: jobType,
        payload: {
          message: message || "Dashboard test job",
          source: "react-dashboard",
        },
      });
      setMessage("");
      await fetchJobs();
    } catch (error) {
      console.error("Failed to create job:", error);
    } finally {
      setSubmitting(false);
    }
  }, [jobType, message, submitting, fetchJobs]);

  const openJobDetails = useCallback(async (jobId) => {
    try {
      setDetailsLoading(true);
      const response = await axios.get(`${API_URL}/jobs/${jobId}`);
      setSelectedJob(response.data);
    } catch (error) {
      console.error("Failed to fetch job details:", error);
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  const closeJobDetails = useCallback(() => setSelectedJob(null), []);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  // Close the modal on Escape as well as the overlay click it already supports.
  useEffect(() => {
    if (!selectedJob) return;

    const onKeyDown = (event) => {
      if (event.key === "Escape") closeJobDetails();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedJob, closeJobDetails]);

  const statusCounts = countByStatus(jobs);

  return (
    <div className="app">
      {/* =====================================================
          HEADER
      ===================================================== */}
      <header className="header">
        <div>
          <h1>Cloud Job Queue</h1>
          <p>Background processing and job monitoring platform</p>
        </div>

        <button
          className="refresh-button"
          onClick={fetchJobs}
          disabled={loading}
          aria-label="Refresh jobs"
        >
          <RefreshCw size={18} />
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {loadError && (
        <div className="banner banner-error" role="alert">
          {loadError}
        </div>
      )}

      {/* =====================================================
          STATISTICS
      ===================================================== */}
      <section className="stats">
        <div className="stat-card card">
          <span>Total Jobs</span>
          <strong>{jobs.length}</strong>
        </div>

        <div className="stat-card card">
          <span>Queued</span>
          <strong>{statusCounts.queued}</strong>
        </div>

        <div className="stat-card card">
          <span>Processing</span>
          <strong>{statusCounts.processing}</strong>
        </div>

        <div className="stat-card card">
          <span>Completed</span>
          <strong>{statusCounts.completed}</strong>
        </div>

        <div className="stat-card card">
          <span>Failed</span>
          <strong>{statusCounts.failed}</strong>
        </div>
      </section>

      {/* =====================================================
          CREATE JOB
      ===================================================== */}
      <section className="create-job card">
        <div>
          <h2>Create Job</h2>
          <p>Submit a background task to the Redis queue.</p>
        </div>

        <div className="form">
          <input
            value={jobType}
            onChange={(event) => setJobType(event.target.value)}
            placeholder="Job type"
            aria-label="Job type"
          />

          <input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Job message"
            aria-label="Job message"
            onKeyDown={(event) => {
              if (event.key === "Enter") createJob();
            }}
          />

          <button
            onClick={createJob}
            disabled={submitting || !jobType.trim()}
          >
            <Plus size={18} />
            {submitting ? "Submitting..." : "Submit Job"}
          </button>
        </div>
      </section>

      {/* =====================================================
          JOB TABLE
      ===================================================== */}
      <section className="jobs-section card">
        <div className="section-header">
          <div>
            <h2>Jobs</h2>
            <p>Live background job activity</p>
          </div>

          {loading && <span className="loading">Refreshing...</span>}
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Type</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Created</th>
              </tr>
            </thead>

            <tbody>
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan="5" className="empty">
                    No jobs found
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr
                    key={job.job_id}
                    className="job-row"
                    role="button"
                    tabIndex={0}
                    onClick={() => openJobDetails(job.job_id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openJobDetails(job.job_id);
                      }
                    }}
                  >
                    <td className="job-id">{job.job_id}</td>
                    <td>{job.job_type}</td>
                    <td>
                      <span className={`status ${job.status}`}>
                        {getStatusIcon(job.status)}
                        {job.status}
                      </span>
                    </td>
                    <td>{job.attempts}</td>
                    <td>{formatDate(job.created_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* =====================================================
          JOB DETAILS MODAL
      ===================================================== */}
      {selectedJob && (
        <div
          className="modal-overlay"
          onClick={closeJobDetails}
          role="presentation"
        >
          <div
            className="job-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Job details"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2>Job Details</h2>
                <p>Complete job execution information</p>
              </div>

              <button
                className="close-button"
                onClick={closeJobDetails}
                aria-label="Close job details"
              >
                <X size={20} />
              </button>
            </div>

            {detailsLoading ? (
              <div className="details-loading">Loading job details...</div>
            ) : (
              <div className="job-details">
                <div className="detail-row">
                  <span>Job ID</span>
                  <strong>{selectedJob.job_id}</strong>
                </div>

                <div className="detail-row">
                  <span>Job Type</span>
                  <strong>{selectedJob.job_type}</strong>
                </div>

                <div className="detail-row">
                  <span>Status</span>
                  <span className={`status ${selectedJob.status}`}>
                    {getStatusIcon(selectedJob.status)}
                    {selectedJob.status}
                  </span>
                </div>

                <div className="detail-row">
                  <span>Attempts</span>
                  <strong>{selectedJob.attempts}</strong>
                </div>

                <div className="detail-block">
                  <span>Payload</span>
                  <pre>{JSON.stringify(selectedJob.payload, null, 2)}</pre>
                </div>

                {selectedJob.result && (
                  <div className="detail-block">
                    <span>Result</span>
                    <pre>{JSON.stringify(selectedJob.result, null, 2)}</pre>
                  </div>
                )}

                {selectedJob.error && (
                  <div className="detail-block error-block">
                    <span>Error</span>
                    <pre>{selectedJob.error}</pre>
                  </div>
                )}

                <div className="timestamps">
                  <div>
                    <span>Created</span>
                    <strong>{formatDate(selectedJob.created_at)}</strong>
                  </div>

                  <div>
                    <span>Started</span>
                    <strong>{formatDate(selectedJob.started_at)}</strong>
                  </div>

                  <div>
                    <span>Completed</span>
                    <strong>{formatDate(selectedJob.completed_at)}</strong>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;