import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

const DeIdentification = ({ user }) => {
  const [text, setText] = useState('');
  const [language, setLanguage] = useState('auto');
  const [policy, setPolicy] = useState('pdpa_v1.0');
  const [linkageDomain, setLinkageDomain] = useState('patient_id');
  const [policies, setPolicies] = useState({});
  const [previewResults, setPreviewResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState(null);

  useEffect(() => {
    fetchPolicies();
    loadSampleText();
  }, []);

  const loadSampleText = () => {
    const thaiSample = `คุณสมชาย ใจดี เลขประจำตัวประชาชน 1234567890123 มารับการรักษาที่โรงพยาบาลศิริราช
ที่อยู่: บ้านเลขที่ 123 หมู่ 4 ซอยลาดพร้าว 15 ถนนลาดพร้าว แขวงจันทรเกษม เขตจตุจักร กรุงเทพมหานคร 10900
เบอร์โทรศัพท์: 081-234-5678
อีเมล: somchai.jaidee@email.com
วันที่เข้ารับการรักษา: 15 มกราคม 2567
อายุ: 45 ปี`;

    setText(thaiSample);
  };

  const fetchPolicies = async () => {
    try {
      const response = await axios.get('/api/v1/policies');
      setPolicies(response.data.policies || {});
    } catch (error) {
      toast.error('Failed to load policies');
    }
  };

  const handlePreview = async () => {
    if (!text.trim()) {
      toast.error('Please enter text to analyze');
      return;
    }

    try {
      setLoading(true);
      
      const response = await axios.post('/api/v1/detect', {
        text: text,
        language_hint: language === 'auto' ? null : language
      });
      
      setPreviewResults(response.data);
      toast.success(`Found ${response.data.entities_found} entities`);
      
    } catch (error) {
      toast.error('Preview failed');
      console.error('Preview error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeIdentify = async () => {
    if (!text.trim()) {
      toast.error('Please enter text to de-identify');
      return;
    }

    try {
      setLoading(true);
      
      const request = {
        documents: [
          {
            content: text,
            document_id: `doc_${Date.now()}`,
            language_hint: language === 'auto' ? null : language
          }
        ],
        policy_version: policy,
        linkage_domain: linkageDomain,
        reviewer_sampling_rate: 0.1
      };
      
      const response = await axios.post('/api/v1/jobs', request);
      
      setJobId(response.data.job_id);
      toast.success('De-identification job created successfully!');
      
      // Poll for completion
      pollJobStatus(response.data.job_id);
      
    } catch (error) {
      const message = error.response?.data?.detail || 'De-identification failed';
      toast.error(message);
      console.error('De-identification error:', error);
    } finally {
      setLoading(false);
    }
  };

  const pollJobStatus = async (jobId) => {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;

    const poll = async () => {
      try {
        const response = await axios.get(`/api/v1/jobs/${jobId}/status`);
        const status = response.data;

        if (status.status === 'completed') {
          toast.success('De-identification completed!');
          // Redirect to job results
          window.location.href = `/jobs?highlight=${jobId}`;
          return;
        } else if (status.status === 'failed') {
          toast.error('De-identification failed');
          return;
        } else if (attempts < maxAttempts) {
          attempts++;
          setTimeout(poll, 5000); // Poll every 5 seconds
        } else {
          toast.warning('Job is taking longer than expected. Check the Jobs page for updates.');
        }
      } catch (error) {
        console.error('Job polling error:', error);
      }
    };

    poll();
  };

  return (
    <div className="container-fluid">
      <div className="row">
        <div className="col-12">
          <h1 className="h3 mb-4">De-Identification</h1>
          
          <div className="row">
            {/* Input Panel */}
            <div className="col-lg-8">
              <div className="card mb-4">
                <div className="card-header">
                  <h6 className="card-title mb-0">Input Text</h6>
                </div>
                <div className="card-body">
                  <div className="mb-3">
                    <textarea
                      className="form-control"
                      rows="12"
                      placeholder="Enter clinical text to de-identify..."
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      disabled={loading}
                    />
                  </div>
                  
                  <div className="row mb-3">
                    <div className="col-md-4">
                      <label className="form-label">Language</label>
                      <select
                        className="form-select"
                        value={language}
                        onChange={(e) => setLanguage(e.target.value)}
                        disabled={loading}
                      >
                        <option value="auto">Auto-detect</option>
                        <option value="th">Thai</option>
                        <option value="en">English</option>
                        <option value="mixed">Mixed</option>
                      </select>
                    </div>
                    
                    <div className="col-md-4">
                      <label className="form-label">Policy</label>
                      <select
                        className="form-select"
                        value={policy}
                        onChange={(e) => setPolicy(e.target.value)}
                        disabled={loading}
                      >
                        {Object.keys(policies).map(policyKey => (
                          <option key={policyKey} value={policyKey}>
                            {policyKey}
                          </option>
                        ))}
                      </select>
                    </div>
                    
                    <div className="col-md-4">
                      <label className="form-label">Linkage Domain</label>
                      <select
                        className="form-select"
                        value={linkageDomain}
                        onChange={(e) => setLinkageDomain(e.target.value)}
                        disabled={loading}
                      >
                        <option value="patient_id">Patient ID</option>
                        <option value="encounter_id">Encounter ID</option>
                        <option value="study_id">Study ID</option>
                      </select>
                    </div>
                  </div>
                  
                  <div className="d-flex gap-2">
                    <button
                      className="btn btn-outline-primary"
                      onClick={handlePreview}
                      disabled={loading || !text.trim()}
                    >
                      {loading ? (
                        <>
                          <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <i className="fas fa-search me-2"></i>
                          Preview Detection
                        </>
                      )}
                    </button>
                    
                    <button
                      className="btn btn-primary"
                      onClick={handleDeIdentify}
                      disabled={loading || !text.trim()}
                    >
                      {loading ? (
                        <>
                          <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                          Processing...
                        </>
                      ) : (
                        <>
                          <i className="fas fa-shield-alt me-2"></i>
                          De-Identify
                        </>
                      )}
                    </button>
                    
                    <button
                      className="btn btn-outline-secondary"
                      onClick={loadSampleText}
                      disabled={loading}
                    >
                      Load Sample
                    </button>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Configuration Panel */}
            <div className="col-lg-4">
              <div className="card mb-4">
                <div className="card-header">
                  <h6 className="card-title mb-0">Policy Configuration</h6>
                </div>
                <div className="card-body">
                  {policies[policy] ? (
                    <div>
                      <p className="text-muted mb-3">
                        {policies[policy].entity_count} transformation rules
                      </p>
                      
                      <div className="small">
                        {policies[policy].transformations.slice(0, 8).map((transform, index) => (
                          <div key={index} className="d-flex justify-content-between mb-2">
                            <span className="text-muted">{transform.entity_type}:</span>
                            <span className="badge bg-light text-dark">{transform.transformation}</span>
                          </div>
                        ))}
                        {policies[policy].transformations.length > 8 && (
                          <div className="text-muted">
                            ... and {policies[policy].transformations.length - 8} more
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className="text-muted">Loading policy information...</p>
                  )}
                </div>
              </div>
              
              {/* Preview Results */}
              {previewResults && (
                <div className="card">
                  <div className="card-header">
                    <h6 className="card-title mb-0">Detection Preview</h6>
                  </div>
                  <div className="card-body">
                    <div className="mb-3">
                      <div className="d-flex justify-content-between">
                        <span>Language:</span>
                        <span className="badge bg-info">{previewResults.detected_language}</span>
                      </div>
                      <div className="d-flex justify-content-between">
                        <span>Entities Found:</span>
                        <span className="badge bg-primary">{previewResults.entities_found}</span>
                      </div>
                    </div>
                    
                    {previewResults.detections.length > 0 && (
                      <div>
                        <h6 className="small mb-2">Detected Entities:</h6>
                        <div className="small">
                          {previewResults.detections.map((detection, index) => (
                            <div key={index} className="mb-2">
                              <div className="d-flex justify-content-between">
                                <span className="text-muted">{detection.entity_type}:</span>
                                <span className="badge bg-light text-dark">
                                  {(detection.confidence * 100).toFixed(0)}%
                                </span>
                              </div>
                              <div className="text-monospace small text-truncate">
                                "{detection.text}"
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
          
          {jobId && (
            <div className="alert alert-success">
              <h6>Job Created Successfully!</h6>
              <p className="mb-0">
                Job ID: <strong>{jobId}</strong><br />
                <a href={`/jobs?highlight=${jobId}`} className="alert-link">
                  View job status and results →
                </a>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DeIdentification;