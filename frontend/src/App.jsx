import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  UploadCloud, 
  CheckCircle2, 
  AlertTriangle, 
  Download, 
  RefreshCw, 
  Users, 
  MapPin, 
  Clock, 
  Play, 
  FileSpreadsheet, 
  Database, 
  Sparkles,
  Check
} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

// Axios Instance
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

export default function App() {
  // App States
  const [stats, setStats] = useState({
    volunteers_count: 0,
    volunteers_geocoded: 0,
    students_count: 0,
    students_geocoded: 0,
    coordinates_cache_count: 0,
    distance_cache_count: 0,
    assignments_count: 0,
    unassigned_students_count: 0,
    average_distance_km: 0,
    uploads: []
  });
  
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [backendStatus, setBackendStatus] = useState('checking'); // 'online', 'offline', 'checking'
  
  // Upload States
  const [uploadingVolunteers, setUploadingVolunteers] = useState(false);
  const [uploadingStudents, setUploadingStudents] = useState(false);
  const [volunteerResult, setVolunteerResult] = useState(null);
  const [studentResult, setStudentResult] = useState(null);
  
  // Pipeline Processing Steps
  const [processStep, setProcessStep] = useState(null); // 'geocoding', 'routing', 'matching', 'done'
  const [processProgress, setProcessProgress] = useState('');



  // Check Backend Connection
  const checkBackend = async () => {
    setBackendStatus('checking');
    try {
      await api.get('/stats');
      setBackendStatus('online');
      setErrorMsg('');
    } catch (err) {
      setBackendStatus('offline');
      setErrorMsg('Cannot connect to backend server. Make sure the FastAPI server is running on port 8000.');
    }
  };

  // Fetch Stats
  const fetchStats = async () => {
    try {
      const res = await api.get('/stats');
      setStats(res.data);
    } catch (err) {
      console.error('Failed to fetch stats', err);
    }
  };

  // Fetch Assignments
  const fetchAssignments = async () => {
    try {
      const res = await api.get('/assignments');
      setAssignments(res.data.assignments || []);
    } catch (err) {
      console.error('Failed to fetch assignments', err);
    }
  };

  useEffect(() => {
    checkBackend();
  }, []);

  useEffect(() => {
    if (backendStatus === 'online') {
      fetchStats();
      fetchAssignments();
    }
  }, [backendStatus]);

  // Handle File Upload automatically on selection
  const handleFileUpload = async (e, type) => {
    const file = e.target.files[0];
    if (!file) return;

    if (type === 'volunteers') {
      setUploadingVolunteers(true);
      setVolunteerResult(null);
    } else {
      setUploadingStudents(true);
      setStudentResult(null);
    }
    setErrorMsg('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post(`/upload/${type}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      if (type === 'volunteers') {
        setVolunteerResult(res.data);
      } else {
        setStudentResult(res.data);
      }
      await fetchStats();
    } catch (err) {
      console.error(err);
      setErrorMsg(err.response?.data?.detail || `Failed to upload ${type} sheet. Please check headers (must contain ID, Name, Address).`);
    } finally {
      if (type === 'volunteers') {
        setUploadingVolunteers(false);
      } else {
        setUploadingStudents(false);
      }
      // Reset input element
      e.target.value = '';
    }
  };

  // Sequential generation run
  const runGeneration = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      // Step 1: Geocoding (may be slow for large datasets — 10 min timeout)
      setProcessStep('geocoding');
      setProcessProgress('Translating addresses to latitude/longitude (Ola Maps API)...');
      await api.post('/geocode', null, { timeout: 600000 });
      await fetchStats();

      // Step 2: Routing/Distances (may be slow for large datasets — 10 min timeout)
      setProcessStep('routing');
      setProcessProgress('Calculating road distances between candidates (Ola Maps Matrix API)...');
      await api.post('/calculate-distances', null, { timeout: 600000 });
      await fetchStats();

      // Step 3: Assignment Generation
      setProcessStep('matching');
      setProcessProgress('Matching volunteers to nearest students...');
      await api.post('/generate-assignments', {
        max_students_per_volunteer: 4,
        prevent_duplicate_assignments: true
      }, { timeout: 120000 });

      // Complete
      setProcessStep('done');
      setProcessProgress('Mapping completed successfully!');
      await fetchStats();
      await fetchAssignments();
    } catch (err) {
      console.error(err);
      setErrorMsg(err.response?.data?.detail || 'Pipeline generation failed. Check connection or Ola Maps API limits.');
      setProcessStep(null);
    } finally {
      setLoading(false);
    }
  };

  // Download excel report
  const downloadReport = () => {
    window.open(`${API_BASE_URL}/download-report`, '_blank');
  };

  // Group assignments by volunteer for listing
  const groupedAssignments = assignments.reduce((acc, a) => {
    if (!acc[a.volunteer_id]) {
      acc[a.volunteer_id] = {
        name: a.volunteer_name,
        students: []
      };
    }
    acc[a.volunteer_id].students.push(a);
    return acc;
  }, {});

  // Has sheets uploaded?
  const hasVolunteers = stats.volunteers_count > 0;
  const hasStudents = stats.students_count > 0;
  const canGenerate = (hasVolunteers && hasStudents) && !loading;

  return (
    <div className="min-h-screen bg-slate-950 bg-gradient-glowing relative text-slate-100 flex flex-col items-center p-4 sm:p-8">
      {/* Background blur effects */}
      <div className="absolute top-10 left-1/4 w-96 h-96 bg-sky-500/10 rounded-full blur-3xl -z-10 animate-pulse-glow"></div>
      <div className="absolute bottom-10 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl -z-10 animate-pulse-glow" style={{ animationDelay: '2s' }}></div>

      {/* Header status bar */}
      <div className="w-full max-w-5xl flex items-center justify-between mb-8 z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <span className="text-xl">🗺️</span>
          </div>
          <div>
            <h1 className="font-bold text-xl tracking-tight text-white">NGO MapMapper</h1>
            <p className="text-[10px] text-slate-500">Address Matching Dashboard</p>
          </div>
        </div>

        {/* Backend Status Dot */}
        <div className="flex items-center gap-3 bg-slate-900/60 border border-slate-800 rounded-full px-4 py-1.5 glass-panel">
          <div className={`w-2 h-2 rounded-full ${
            backendStatus === 'online' ? 'bg-emerald-500 animate-pulse' : 
            backendStatus === 'offline' ? 'bg-rose-500' : 'bg-amber-500 animate-pulse'
          }`} />
          <span className="text-xs font-semibold text-slate-300">
            {backendStatus === 'online' ? 'Connected' : 
             backendStatus === 'offline' ? 'Offline' : 'Connecting...'}
          </span>
          <button 
            onClick={checkBackend} 
            className="text-slate-500 hover:text-sky-400 transition-smooth p-0.5"
            title="Refresh Connection"
          >
            <RefreshCw size={12} className={backendStatus === 'checking' ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Main Panel */}
      <main className="w-full max-w-5xl glass-panel rounded-3xl p-6 sm:p-10 shadow-2xl relative overflow-hidden space-y-8 z-10">
        
        {/* Intro */}
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <h2 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-sky-400 via-teal-400 to-indigo-400">
            Volunteer-Student Address Matching
          </h2>
          <p className="text-slate-400 text-sm">
            Upload your excel directories, match volunteers to their nearest students using road travel distances, and export formatted reports.
          </p>
        </div>

        {/* Error Notification */}
        {errorMsg && (
          <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-4 flex items-start gap-3 animate-fade-in">
            <AlertTriangle className="text-rose-400 shrink-0 mt-0.5" size={18} />
            <div className="flex-1">
              <h4 className="text-sm font-bold text-rose-300">Operation Alert</h4>
              <p className="text-xs text-rose-400/90 mt-0.5">{errorMsg}</p>
            </div>
          </div>
        )}

        {/* STEP 1: Upload Side-by-Side */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* Volunteer Upload Card */}
          <div className="bg-slate-900/30 border border-slate-900 rounded-2xl p-5 hover:border-slate-800 transition-smooth relative flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    <Users size={18} className="text-sky-400" />
                    Volunteer Directory
                  </h3>
                  <p className="text-xs text-slate-500">Only ID, Name, and Address required.</p>
                </div>
                {hasVolunteers && (
                  <span className="bg-emerald-500/10 text-emerald-400 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                    <Check size={10} /> Active Database
                  </span>
                )}
              </div>

              {/* Status information */}
              {hasVolunteers ? (
                <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-xl p-3.5 mb-4 text-xs flex justify-between items-center text-slate-300">
                  <span className="flex items-center gap-2">
                    <Database size={14} className="text-emerald-400" />
                    <span>Loaded records:</span>
                  </span>
                  <span className="font-bold text-white">{stats.volunteers_count} volunteers</span>
                </div>
              ) : (
                <div className="bg-slate-950/50 border border-slate-900 rounded-xl p-3.5 mb-4 text-xs text-slate-500 italic text-center">
                  No volunteers loaded. Please upload a sheet.
                </div>
              )}

              {/* Upload area */}
              <div className="border border-dashed border-slate-800 hover:border-sky-500/50 rounded-xl p-6 text-center bg-slate-950/20 hover:bg-slate-950/40 transition-smooth relative cursor-pointer">
                <input 
                  type="file" 
                  accept=".xlsx,.xls"
                  onChange={(e) => handleFileUpload(e, 'volunteers')}
                  disabled={uploadingVolunteers || loading}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:pointer-events-none"
                />
                <UploadCloud size={24} className="mx-auto text-slate-500 mb-2" />
                <span className="block text-xs font-semibold text-slate-300">
                  {uploadingVolunteers ? 'Uploading & validating...' : 'Upload Volunteer Sheet'}
                </span>
                <span className="block text-[10px] text-slate-600 mt-0.5">Supports Excel (.xlsx, .xls)</span>
              </div>
            </div>

            {/* Validation Feedback */}
            {volunteerResult && (
              <div className="mt-4 bg-slate-950/70 border border-slate-900 rounded-xl p-3 text-xs space-y-1.5 animate-fade-in">
                <div className="flex justify-between font-medium">
                  <span className="text-slate-400">Total processed:</span>
                  <span className="text-white">{volunteerResult.processed_count} rows</span>
                </div>
                <div className="flex justify-between font-medium">
                  <span className="text-slate-400">Valid saved:</span>
                  <span className="text-emerald-400">{volunteerResult.valid_count} rows</span>
                </div>
                {volunteerResult.errors.length > 0 && (
                  <div className="text-[10px] text-rose-400 border-t border-slate-900 pt-1.5 mt-1.5">
                    <strong>Errors skipped:</strong> {volunteerResult.errors.slice(0, 2).join(', ')}
                    {volunteerResult.errors.length > 2 && ` (+${volunteerResult.errors.length - 2} more)`}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Student Upload Card */}
          <div className="bg-slate-900/30 border border-slate-900 rounded-2xl p-5 hover:border-slate-800 transition-smooth relative flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="font-bold text-white text-base flex items-center gap-2">
                    <Users size={18} className="text-indigo-400" />
                    Student Directory
                  </h3>
                  <p className="text-xs text-slate-500">Only ID, Name, and Address required.</p>
                </div>
                {hasStudents && (
                  <span className="bg-emerald-500/10 text-emerald-400 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                    <Check size={10} /> Active Database
                  </span>
                )}
              </div>

              {/* Status information */}
              {hasStudents ? (
                <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-xl p-3.5 mb-4 text-xs flex justify-between items-center text-slate-300">
                  <span className="flex items-center gap-2">
                    <Database size={14} className="text-indigo-400" />
                    <span>Loaded records:</span>
                  </span>
                  <span className="font-bold text-white">{stats.students_count} students</span>
                </div>
              ) : (
                <div className="bg-slate-950/50 border border-slate-900 rounded-xl p-3.5 mb-4 text-xs text-slate-500 italic text-center">
                  No students loaded. Please upload a sheet.
                </div>
              )}

              {/* Upload area */}
              <div className="border border-dashed border-slate-800 hover:border-sky-500/50 rounded-xl p-6 text-center bg-slate-950/20 hover:bg-slate-950/40 transition-smooth relative cursor-pointer">
                <input 
                  type="file" 
                  accept=".xlsx,.xls"
                  onChange={(e) => handleFileUpload(e, 'students')}
                  disabled={uploadingStudents || loading}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:pointer-events-none"
                />
                <UploadCloud size={24} className="mx-auto text-slate-500 mb-2" />
                <span className="block text-xs font-semibold text-slate-300">
                  {uploadingStudents ? 'Uploading & validating...' : 'Upload Student Sheet'}
                </span>
                <span className="block text-[10px] text-slate-600 mt-0.5">Supports Excel (.xlsx, .xls)</span>
              </div>
            </div>

            {/* Validation Feedback */}
            {studentResult && (
              <div className="mt-4 bg-slate-950/70 border border-slate-900 rounded-xl p-3 text-xs space-y-1.5 animate-fade-in">
                <div className="flex justify-between font-medium">
                  <span className="text-slate-400">Total processed:</span>
                  <span className="text-white">{studentResult.processed_count} rows</span>
                </div>
                <div className="flex justify-between font-medium">
                  <span className="text-slate-400">Valid saved:</span>
                  <span className="text-emerald-400">{studentResult.valid_count} rows</span>
                </div>
                {studentResult.errors.length > 0 && (
                  <div className="text-[10px] text-rose-400 border-t border-slate-900 pt-1.5 mt-1.5">
                    <strong>Errors skipped:</strong> {studentResult.errors.slice(0, 2).join(', ')}
                    {studentResult.errors.length > 2 && ` (+${studentResult.errors.length - 2} more)`}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {/* STEP 2: Pipeline Action & Status */}
        <section className="flex flex-col items-center justify-center border-t border-slate-900 pt-8 space-y-5">



          {!processStep ? (
            <button
              onClick={runGeneration}
              disabled={!canGenerate}
              className={`w-full max-w-md py-4 px-6 rounded-2xl font-bold flex items-center justify-center gap-3 transition-smooth text-white shadow-xl ${
                canGenerate 
                  ? 'bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 shadow-sky-500/25 active:scale-95 cursor-pointer' 
                  : 'bg-slate-900 border border-slate-800 text-slate-500 opacity-50 cursor-not-allowed'
              }`}
            >
              <Play size={18} fill="currentColor" />
              Generate Assignments
            </button>
          ) : (
            <div className="w-full max-w-md bg-slate-900/50 border border-slate-900 rounded-2xl p-5 space-y-4">
              <div className="flex items-center gap-3">
                <RefreshCw className="text-sky-400 animate-spin" size={18} />
                <span className="text-sm font-semibold text-slate-200">Processing Assignment Pipeline</span>
              </div>
              
              {/* Stepper display */}
              <div className="space-y-2.5 text-xs">
                <div className="flex items-center gap-2.5">
                  <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold ${
                    processStep === 'geocoding' ? 'bg-sky-500 text-white animate-pulse' :
                    (processStep === 'routing' || processStep === 'matching' || processStep === 'done') ? 'bg-emerald-500 text-white' : 'bg-slate-800 text-slate-500'
                  }`}>
                    {(processStep === 'routing' || processStep === 'matching' || processStep === 'done') ? '✓' : '1'}
                  </div>
                  <span className={processStep === 'geocoding' ? 'text-white font-medium' : 'text-slate-400'}>
                    Geocoding addresses (cached: {stats.coordinates_cache_count})
                  </span>
                </div>

                <div className="flex items-center gap-2.5">
                  <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold ${
                    processStep === 'routing' ? 'bg-sky-500 text-white animate-pulse' :
                    (processStep === 'matching' || processStep === 'done') ? 'bg-emerald-500 text-white' : 'bg-slate-800 text-slate-500'
                  }`}>
                    {(processStep === 'matching' || processStep === 'done') ? '✓' : '2'}
                  </div>
                  <span className={processStep === 'routing' ? 'text-white font-medium' : 'text-slate-400'}>
                    Calculating road routing matrices
                  </span>
                </div>

                <div className="flex items-center gap-2.5">
                  <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold ${
                    processStep === 'matching' ? 'bg-sky-500 text-white animate-pulse' :
                    processStep === 'done' ? 'bg-emerald-500 text-white' : 'bg-slate-800 text-slate-500'
                  }`}>
                    {processStep === 'done' ? '✓' : '3'}
                  </div>
                  <span className={processStep === 'matching' ? 'text-white font-medium' : 'text-slate-400'}>
                    Assigning nearest students to volunteers
                  </span>
                </div>
              </div>

              <div className="text-[11px] text-sky-400 font-medium italic animate-pulse-glow">
                {processProgress}
              </div>
            </div>
          )}

          {!canGenerate && !processStep && (
            <p className="text-[11px] text-slate-500 text-center">
              * Upload both Volunteer and Student excel sheets to unlock mapping generation.
            </p>
          )}
        </section>

        {/* STEP 3: Results Display & Report Download */}
        {assignments.length > 0 && !loading && (
          <section className="border-t border-slate-900 pt-8 space-y-6 animate-fade-in">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/20 border border-slate-900 rounded-2xl p-5">
              <div>
                <h3 className="font-bold text-white text-base flex items-center gap-2">
                  <Sparkles size={18} className="text-yellow-400" />
                  Assignments Generated Successfully!
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Matched <strong>{assignments.length}</strong> pairings. Average travel distance is <strong>{stats.average_distance_km} km</strong>.
                  {stats.unassigned_students_count > 0 && (
                    <span className="text-amber-400 block sm:inline sm:ml-2">
                      ⚠️ {stats.unassigned_students_count} students remain unassigned.
                    </span>
                  )}
                </p>
              </div>

              <button 
                onClick={downloadReport}
                className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-6 py-3 rounded-xl transition-smooth shadow-lg shadow-emerald-500/10 flex items-center justify-center gap-2 active:scale-95"
              >
                <Download size={16} />
                Download Report (Excel)
              </button>
            </div>

            {/* Assignments Roster */}
            <div className="space-y-4">
              <h4 className="font-bold text-white text-sm flex items-center gap-2 uppercase tracking-wider text-slate-400">
                <FileSpreadsheet size={16} />
                Roster Preview
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {Object.entries(groupedAssignments).map(([vId, vData]) => (
                  <div key={vId} className="bg-slate-950/60 border border-slate-900 rounded-xl p-4 flex flex-col justify-between hover:border-slate-800 transition-smooth">
                    <div>
                      {/* Volunteer Header */}
                      <div className="flex justify-between items-start border-b border-slate-900 pb-2.5 mb-3">
                        <div>
                          <h5 className="font-bold text-white text-sm">{vData.name}</h5>
                          <span className="text-[9px] text-slate-500 font-mono">ID: {vId}</span>
                        </div>
                        <span className="bg-sky-500/10 text-sky-400 text-[10px] font-bold px-2 py-0.5 rounded">
                          {vData.students.length} mapped
                        </span>
                      </div>

                      {/* Mapped Students List */}
                      <div className="space-y-2.5">
                        {vData.students.map((s, idx) => (
                          <div key={idx} className="bg-slate-900/30 border border-slate-900/60 rounded-lg p-2.5 space-y-1">
                            <div className="flex justify-between items-start">
                              <div>
                                <h6 className="font-semibold text-xs text-slate-200">{s.student_name}</h6>
                                <span className="text-[9px] text-slate-500 font-mono">ID: {s.student_id}</span>
                              </div>
                              <span className="bg-indigo-500/10 text-indigo-400 text-[9px] font-bold px-1.5 py-0.5 rounded flex items-center gap-1 shrink-0">
                                <MapPin size={8} /> {s.distance_km} km
                              </span>
                            </div>
                            {/* Address details */}
                            <p className="text-[10px] text-slate-500 truncate" title={s.address}>
                              {s.address}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}
      </main>

      {/* Footer footer */}
      <footer className="mt-8 text-center text-xs text-slate-600 flex items-center gap-2">
        <Database size={12} />
        <span>Workbook database.xlsx storage active</span>
      </footer>
    </div>
  );
}
