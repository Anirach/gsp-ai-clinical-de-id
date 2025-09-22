import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

const AuditViewer = ({ user }) => {
  const [detectionTraces, setDetectionTraces] = useState([]);
  const [transformationTraces, setTransformationTraces] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('detections');

  const fetchDetectionTraces = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/v1/audit/detections?limit=50');
      setDetectionTraces(response.data.traces || []);
    } catch (error) {
      toast.error('Failed to load detection traces');
    } finally {
      setLoading(false);
    }
  };

  const fetchTransformationTraces = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/v1/audit/transformations?limit=50');
      setTransformationTraces(response.data.traces || []);
    } catch (error) {
      toast.error('Failed to load transformation traces');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user.permissions.includes('view_audit_logs')) {
      if (activeTab === 'detections') {
        fetchDetectionTraces();
      } else {
        fetchTransformationTraces();
      }
    }
  }, [activeTab, user.permissions]);

  return (
    <div className="container-fluid">
      <div className="row">
        <div className="col-12">
          <h1 className="h3 mb-4">Audit Viewer</h1>
          
          {user.permissions.includes('view_audit_logs') ? (
            <div>
              <div className="alert alert-info">
                <h6>Audit Trail</h6>
                <p className="mb-0">
                  Complete audit trail of all de-identification operations for compliance and quality assurance.
                  All operations are logged with full traceability for regulatory requirements.
                </p>
              </div>
              
              <div className="card">
                <div className="card-header">
                  <ul className="nav nav-tabs card-header-tabs">
                    <li className="nav-item">
                      <button 
                        className={`nav-link ${activeTab === 'detections' ? 'active' : ''}`}
                        onClick={() => setActiveTab('detections')}
                      >
                        Detection Traces
                      </button>
                    </li>
                    <li className="nav-item">
                      <button 
                        className={`nav-link ${activeTab === 'transformations' ? 'active' : ''}`}
                        onClick={() => setActiveTab('transformations')}
                      >
                        Transformation Traces
                      </button>
                    </li>
                  </ul>
                </div>
                
                <div className="card-body">
                  {loading ? (
                    <div className="text-center">
                      <div className="spinner-border" role="status">
                        <span className="visually-hidden">Loading...</span>
                      </div>
                    </div>
                  ) : (
                    <div>
                      {activeTab === 'detections' && (
                        <div>
                          <h6>Detection Traces ({detectionTraces.length})</h6>
                          {detectionTraces.length > 0 ? (
                            <div className="table-responsive">
                              <table className="table table-sm">
                                <thead>
                                  <tr>
                                    <th>Timestamp</th>
                                    <th>Job ID</th>
                                    <th>Entity Type</th>
                                    <th>Detector</th>
                                    <th>Confidence</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {detectionTraces.map((trace, index) => (
                                    <tr key={index}>
                                      <td className="small">{new Date(trace.timestamp).toLocaleString()}</td>
                                      <td className="small font-monospace">{trace.job_id.substring(0, 8)}...</td>
                                      <td>
                                        <span className="badge bg-light text-dark">{trace.entity_type}</span>
                                      </td>
                                      <td className="small">{trace.detector_type}</td>
                                      <td>
                                        <span className="badge bg-success">{(trace.confidence * 100).toFixed(0)}%</span>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="text-muted">No detection traces found.</p>
                          )}
                        </div>
                      )}
                      
                      {activeTab === 'transformations' && (
                        <div>
                          <h6>Transformation Traces ({transformationTraces.length})</h6>
                          {transformationTraces.length > 0 ? (
                            <div className="table-responsive">
                              <table className="table table-sm">
                                <thead>
                                  <tr>
                                    <th>Timestamp</th>
                                    <th>Job ID</th>
                                    <th>Entity Type</th>
                                    <th>Transformation</th>
                                    <th>Policy Rule</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {transformationTraces.map((trace, index) => (
                                    <tr key={index}>
                                      <td className="small">{new Date(trace.timestamp).toLocaleString()}</td>
                                      <td className="small font-monospace">{trace.job_id.substring(0, 8)}...</td>
                                      <td>
                                        <span className="badge bg-light text-dark">{trace.entity_type}</span>
                                      </td>
                                      <td>
                                        <span className="badge bg-primary">{trace.transformation_type}</span>
                                      </td>
                                      <td className="small">{trace.policy_rule_id}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="text-muted">No transformation traces found.</p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="alert alert-warning">
              <h6>Access Restricted</h6>
              <p className="mb-0">
                You do not have permission to view audit logs. Contact your administrator for access.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AuditViewer;