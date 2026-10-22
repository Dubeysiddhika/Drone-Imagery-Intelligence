import { useEffect, useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Database,
  MapPin,
  RefreshCw,
  Search,
  X,
} from "lucide-react";

import {
  getApiErrorMessage,
  getUAVVisLocRecord,
  getUAVVisLocStats,
  listUAVVisLocRecords,
  type UAVVisLocRecord,
  type UAVVisLocRecordsResponse,
  type UAVVisLocStats,
} from "../services/api";

const PAGE_SIZE = 25;

function formatValue(
  value: number | null,
  decimals = 2,
): string {
  return value === null || value === undefined
    ? "—"
    : value.toFixed(decimals);
}

export default function UAVVisLocPage() {
  const [stats, setStats] = useState<UAVVisLocStats | null>(null);
  const [recordPage, setRecordPage] =
    useState<UAVVisLocRecordsResponse | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedRecord, setSelectedRecord] =
    useState<UAVVisLocRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadData() {
      setLoading(true);
      setError("");

      try {
        const [nextStats, nextRecords] = await Promise.all([
          getUAVVisLocStats(),
          listUAVVisLocRecords((page - 1) * PAGE_SIZE, PAGE_SIZE),
        ]);

        if (active) {
          setStats(nextStats);
          setRecordPage(nextRecords);
        }
      } catch (err) {
        if (active) {
          setError(getApiErrorMessage(err));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadData();

    return () => {
      active = false;
    };
  }, [page]);

  const displayedRecords = useMemo(() => {
    const records = recordPage?.records ?? [];
    const term = search.trim().toLowerCase();

    if (!term) {
      return records;
    }

    // Search the records currently loaded on this page.
    return records.filter((record) =>
      [
        record.filename,
        record.relative_path,
        record.capture_time_raw ?? "",
        record.metadata_csv,
        String(record.latitude),
        String(record.longitude),
      ]
        .join(" ")
        .toLowerCase()
        .includes(term),
    );
  }, [recordPage, search]);

  const totalRecords = recordPage?.total ?? stats?.total_records ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalRecords / PAGE_SIZE));
  const firstRecord =
    totalRecords === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastRecord = Math.min(page * PAGE_SIZE, totalRecords);

  async function openRecord(recordId: number) {
    setDetailLoading(true);
    setDetailError("");

    try {
      const record = await getUAVVisLocRecord(recordId);
      setSelectedRecord(record);
    } catch (err) {
      setDetailError(getApiErrorMessage(err));
    } finally {
      setDetailLoading(false);
    }
  }

  function refreshPage() {
    setPage((current) => current);
    setLoading(true);
    setError("");

    Promise.all([
      getUAVVisLocStats(),
      listUAVVisLocRecords((page - 1) * PAGE_SIZE, PAGE_SIZE),
    ])
      .then(([nextStats, nextRecords]) => {
        setStats(nextStats);
        setRecordPage(nextRecords);
      })
      .catch((err: unknown) => {
        setError(getApiErrorMessage(err));
      })
      .finally(() => {
        setLoading(false);
      });
  }

  return (
    <div className="uav-page">
      <header className="uav-page-header">
        <div>
          <p className="dashboard-eyebrow">
            GEOSPATIAL INTELLIGENCE / RESEARCH DATA
          </p>
          <h1>UAV-VisLoc Dataset</h1>
          <p className="page-description">
            Browse image capture coordinates, recorded heights, capture
            times, and available camera-orientation metadata.
          </p>
        </div>

        <button
          type="button"
          className="uav-refresh-button"
          onClick={refreshPage}
          disabled={loading}
        >
          <RefreshCw size={16} aria-hidden="true" />
          Refresh data
        </button>
      </header>

      {error && (
        <div className="uav-error" role="alert">
          <strong>Unable to load the dataset</strong>
          <p>{error}</p>
          <p>
            Check that FastAPI is running and that the frontend is
            configured to use the correct API address.
          </p>
        </div>
      )}

      <section className="uav-stats-grid" aria-label="Dataset statistics">
        <article className="uav-stat-card">
          <span className="uav-stat-icon">
            <Database size={19} />
          </span>
          <div>
            <span className="uav-stat-label">Total records</span>
            <strong>
              {stats ? stats.total_records.toLocaleString() : "—"}
            </strong>
            <small>Imported metadata records</small>
          </div>
        </article>

        <article className="uav-stat-card">
          <span className="uav-stat-icon uav-icon-green">
            <MapPin size={19} />
          </span>
          <div>
            <span className="uav-stat-label">GPS coordinates</span>
            <strong>
              {stats ? stats.total_records.toLocaleString() : "—"}
            </strong>
            <small>Records with coordinates</small>
          </div>
        </article>

        <article className="uav-stat-card">
          <span className="uav-stat-icon uav-icon-purple">
            <Database size={19} />
          </span>
          <div>
            <span className="uav-stat-label">
              Complete orientation
            </span>
            <strong>
              {stats
                ? stats.records_with_complete_orientation.toLocaleString()
                : "—"}
            </strong>
            <small>All four fields available</small>
          </div>
        </article>

        <article className="uav-stat-card">
          <span className="uav-stat-icon uav-icon-orange">
            <Database size={19} />
          </span>
          <div>
            <span className="uav-stat-label">
              Incomplete orientation
            </span>
            <strong>
              {stats
                ? stats.records_without_complete_orientation.toLocaleString()
                : "—"}
            </strong>
            <small>One or more fields unavailable</small>
          </div>
        </article>
      </section>

      <section className="uav-data-panel">
        <div className="uav-table-header">
          <div>
            <h2>Image metadata</h2>
            <p>
              Showing up to {PAGE_SIZE} records per page. GPS values
              represent recorded image capture locations.
            </p>
          </div>

          <label className="uav-search">
            <Search size={17} aria-hidden="true" />
            <input
              type="search"
              placeholder="Filter displayed records..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Filter records on this page"
            />
          </label>
        </div>

        {loading ? (
          <div className="uav-table-state" role="status">
            Loading UAV-VisLoc metadata...
          </div>
        ) : !error && displayedRecords.length === 0 ? (
          <div className="uav-table-state">
            {recordPage?.records.length
              ? "No displayed records match your filter."
              : "No records were returned by the API."}
          </div>
        ) : !error ? (
          <div className="uav-table-scroll">
            <table className="uav-table">
              <thead>
                <tr>
                  <th>Image</th>
                  <th>Capture time</th>
                  <th>Latitude</th>
                  <th>Longitude</th>
                  <th>Height</th>
                  <th>Orientation</th>
                  <th>Details</th>
                </tr>
              </thead>

              <tbody>
                {displayedRecords.map((record) => {
                  const completeOrientation = [
                    record.omega,
                    record.kappa,
                    record.phi1,
                    record.phi2,
                  ].every((value) => value !== null);

                  return (
                    <tr key={record.id}>
                      <td>
                        <div className="uav-filename">
                          {record.filename}
                        </div>
                        <div className="uav-subpath">
                          {record.relative_path}
                        </div>
                      </td>

                      <td>{record.capture_time_raw || "—"}</td>

                      <td className="uav-number">
                        {formatValue(record.latitude, 6)}
                      </td>

                      <td className="uav-number">
                        {formatValue(record.longitude, 6)}
                      </td>

                      <td>{formatValue(record.height)}</td>

                      <td>
                        <span
                          className={
                            completeOrientation
                              ? "uav-status uav-status-complete"
                              : "uav-status uav-status-partial"
                          }
                        >
                          {completeOrientation
                            ? "Complete"
                            : "Partial"}
                        </span>
                      </td>

                      <td>
                        <button
                          type="button"
                          className="uav-view-button"
                          onClick={() => void openRecord(record.id)}
                          disabled={detailLoading}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}

        {detailError && (
          <div className="uav-inline-error" role="alert">
            {detailError}
          </div>
        )}

        <footer className="uav-pagination">
          <span>
            {totalRecords
              ? `Showing ${firstRecord}–${lastRecord} of ${totalRecords.toLocaleString()} records`
              : "No records"}
          </span>

          <div className="uav-pagination-controls">
            <button
              type="button"
              onClick={() => setPage((current) => current - 1)}
              disabled={loading || page <= 1}
              aria-label="Previous page"
            >
              <ChevronLeft size={16} />
              Previous
            </button>

            <span>
              Page {page} of {totalPages}
            </span>

            <button
              type="button"
              onClick={() => setPage((current) => current + 1)}
              disabled={loading || page >= totalPages}
              aria-label="Next page"
            >
              Next
              <ChevronRight size={16} />
            </button>
          </div>
        </footer>
      </section>

      {selectedRecord && (
        <section className="uav-detail-panel">
          <header className="uav-detail-header">
            <div>
              <h2>Record details</h2>
              <p>{selectedRecord.relative_path}</p>
            </div>

            <button
              type="button"
              className="uav-close-button"
              onClick={() => setSelectedRecord(null)}
              aria-label="Close record details"
            >
              <X size={18} />
            </button>
          </header>

          <dl className="uav-detail-grid">
            <div>
              <dt>Filename</dt>
              <dd>{selectedRecord.filename}</dd>
            </div>
            <div>
              <dt>Capture time (source)</dt>
              <dd>{selectedRecord.capture_time_raw || "—"}</dd>
            </div>
            <div>
              <dt>Latitude</dt>
              <dd>{formatValue(selectedRecord.latitude, 6)}</dd>
            </div>
            <div>
              <dt>Longitude</dt>
              <dd>{formatValue(selectedRecord.longitude, 6)}</dd>
            </div>
            <div>
              <dt>Recorded height</dt>
              <dd>{formatValue(selectedRecord.height)}</dd>
            </div>
            <div>
              <dt>Metadata CSV</dt>
              <dd>{selectedRecord.metadata_csv}</dd>
            </div>
            <div>
              <dt>Omega</dt>
              <dd>{formatValue(selectedRecord.omega, 6)}</dd>
            </div>
            <div>
              <dt>Kappa</dt>
              <dd>{formatValue(selectedRecord.kappa, 6)}</dd>
            </div>
            <div>
              <dt>Phi1</dt>
              <dd>{formatValue(selectedRecord.phi1, 6)}</dd>
            </div>
            <div>
              <dt>Phi2</dt>
              <dd>{formatValue(selectedRecord.phi2, 6)}</dd>
            </div>
          </dl>
        </section>
      )}
    </div>
  );
}