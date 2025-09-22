import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

const Dashboard = ({ user }) => {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      
      const [healthResponse, statsResponse] = await Promise.all([
        axios.get('/health'),
        user.permissions.includes('view_metrics') ? 
          axios.get('/api/v1/statistics') : 
          Promise.resolve({ data: null })
      ]);
      
      setHealth(healthResponse.data);
      setStats(statsResponse.data);
      
    } catch (error) {
      toast.error('Failed to load dashboard data');
      console.error('Dashboard data fetch error:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid">
      <div className="row">
        <div className="col-12">
          <h1 className="h3 mb-4">Dashboard</h1>
          
          {/* Welcome Card */}
          <div className="card mb-4">
            <div className="card-body">
              <h5 className="card-title">Welcome, {user.username}!</h5>
              <p className="card-text">
                You are logged in as <strong>{user.role}</strong> with access to the Clinical Text De-Identification System.
              </p>
              <p className="text-muted">
                This system provides bilingual (Thai/English) de-identification with policy-driven transformations 
                and comprehensive audit trails for PDPA, HIPAA, and GDPR compliance.
              </p>
            </div>
          </div>
          
          {/* System Health */}
          <div className="row mb-4">
            <div className="col-md-6">
              <div className="card">
                <div className="card-header">
                  <h6 className="card-title mb-0">System Health</h6>
                </div>
                <div className="card-body">
                  {health ? (
                    <>
                      <div className="d-flex align-items-center mb-3">
                        <span className={`badge ${health.status === 'healthy' ? 'bg-success' : 'bg-danger'} me-2`}>
                          {health.status}
                        </span>
                        <span>Version {health.version}</span>
                      </div>
                      
                      <div className="row">
                        {Object.entries(health.services || {}).map(([service, status]) => (
                          <div key={service} className="col-6 mb-2">
                            <div className="d-flex justify-content-between">
                              <small className="text-muted">{service}:</small>
                              <span className={`badge badge-sm ${status === 'healthy' ? 'bg-success' : 'bg-warning'}`}>
                                {status}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="text-muted">Health information unavailable</p>
                  )}
                </div>
              </div>
            </div>
            
            <div className="col-md-6">
              <div className="card">
                <div className="card-header">
                  <h6 className="card-title mb-0">Your Permissions</h6>
                </div>
                <div className="card-body">
                  <div className="row">
                    {user.permissions && user.permissions.map((permission, index) => (
                      <div key={index} className="col-12 mb-1">
                        <span className="badge bg-light text-dark">{permission}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          {/* System Statistics */}
          {stats && (
            <div className="row mb-4">
              <div className="col-12">
                <div className="card">
                  <div className="card-header">
                    <h6 className="card-title mb-0">System Statistics</h6>
                  </div>
                  <div className="card-body">
                    <div className="row">
                      {/* Orchestrator Stats */}
                      {stats.orchestrator && (
                        <div className="col-md-3 mb-3">
                          <div className="text-center">
                            <h4 className="text-primary">{stats.orchestrator.active_jobs || 0}</h4>
                            <p className="text-muted mb-0">Active Jobs</p>
                          </div>
                        </div>
                      )}
                      
                      {/* Detection Stats */}
                      {stats.detection_service && (
                        <div className="col-md-3 mb-3">
                          <div className="text-center">
                            <h4 className="text-success">{stats.detection_service.supported_entities || 0}</h4>
                            <p className="text-muted mb-0">Entity Types</p>
                          </div>
                        </div>
                      )}
                      
                      {/* Policy Stats */}
                      {stats.policy_engine && (
                        <div className="col-md-3 mb-3">
                          <div className="text-center">
                            <h4 className="text-info">{stats.policy_engine.available_policies || 0}</h4>
                            <p className="text-muted mb-0">Policies</p>
                          </div>
                        </div>
                      )}
                      
                      {/* Pseudonym Stats */}
                      {stats.pseudonym_service && (
                        <div className="col-md-3 mb-3">
                          <div className="text-center">
                            <h4 className="text-warning">{stats.pseudonym_service.pseudonyms_generated || 0}</h4>
                            <p className="text-muted mb-0">Pseudonyms Generated</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {/* Quick Actions */}
          <div className="row">
            <div className="col-12">
              <div className="card">
                <div className="card-header">
                  <h6 className="card-title mb-0">Quick Actions</h6>
                </div>
                <div className="card-body">
                  <div className="row">
                    {user.permissions.includes('create_job') && (
                      <div className="col-md-4 mb-3">
                        <div className="d-grid">
                          <a href="/deidentify" className="btn btn-primary">
                            <i className="fas fa-shield-alt me-2"></i>
                            Start De-Identification
                          </a>
                        </div>
                      </div>
                    )}
                    
                    <div className="col-md-4 mb-3">
                      <div className="d-grid">
                        <a href="/jobs" className="btn btn-outline-primary">
                          <i className="fas fa-tasks me-2"></i>
                          View Jobs
                        </a>
                      </div>
                    </div>
                    
                    {user.permissions.includes('view_audit_logs') && (
                      <div className="col-md-4 mb-3">
                        <div className="d-grid">
                          <a href="/audit" className="btn btn-outline-info">
                            <i className="fas fa-search me-2"></i>
                            View Audit Logs
                          </a>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;