import React, { useState, useEffect } from 'react';
import {
  cloneVoice,
  listVoices,
  deleteVoice,
  synthesizeClonedVoice,
  type VoiceInfo,
} from '../services/api';
import '../assets/app-styles.css';

const MAX_TEST_TEXT_LENGTH = 300;

const VoiceManager: React.FC = () => {
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Clone voice form state
  const [showCloneForm, setShowCloneForm] = useState(false);
  const [voiceName, setVoiceName] = useState('');
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [language, setLanguage] = useState('en');
  const [uploading, setUploading] = useState(false);

  // Test synthesized audio state
  const [selectedVoice, setSelectedVoice] = useState<string>('');
  const [testText, setTestText] = useState<string>('');
  const [generating, setGenerating] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [downloadFileName, setDownloadFileName] = useState<string>('cloned_voice_sample.wav');

  useEffect(() => {
    loadVoices();
  }, []);

  const loadVoices = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listVoices();
      setVoices(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load voices');
    } finally {
      setLoading(false);
    }
  };

  const handleCloneVoice = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!audioFile) {
      setError('Please select an audio file');
      return;
    }

    if (!voiceName.trim()) {
      setError('Please enter a voice name');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccess(null);

    try {
      await cloneVoice(audioFile, voiceName.trim(), language);
      setSuccess(`Voice '${voiceName}' cloned successfully!`);
      setVoiceName('');
      setAudioFile(null);
      setShowCloneForm(false);
      await loadVoices(); // Reload voices list
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to clone voice');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteVoice = async (voiceName: string) => {
    if (!window.confirm(`Are you sure you want to delete voice '${voiceName}'?`)) {
      return;
    }

    setError(null);
    setSuccess(null);

    try {
      await deleteVoice(voiceName);
      setSuccess(`Voice '${voiceName}' deleted successfully`);
      await loadVoices(); // Reload voices list
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete voice');
    }
  };

  const handleGenerateSample = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedVoice) {
      setError('Please select a cloned voice to test.');
      return;
    }

    if (!testText.trim()) {
      setError('Please enter text to synthesize.');
      return;
    }

    if (testText.trim().length > MAX_TEST_TEXT_LENGTH) {
      setError(`Text is too long. Maximum is ${MAX_TEST_TEXT_LENGTH} characters.`);
      return;
    }

    setGenerating(true);
    setError(null);
    setSuccess(null);

    try {
      const voice = voices.find((v) => v.name === selectedVoice);
      const lang = voice?.language || language || 'en';

      const response = await synthesizeClonedVoice(selectedVoice, testText.trim(), lang);

      // Revoke previous URL if any
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }

      const blob = new Blob([response.data], { type: 'audio/wav' });
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
      setDownloadFileName(`${selectedVoice}_sample.wav`);
      setSuccess(`Generated audio sample for '${selectedVoice}'.`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate voice sample');
    } finally {
      setGenerating(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      const validTypes = ['audio/wav', 'audio/mpeg', 'audio/mp3', 'audio/x-wav'];
      if (!validTypes.includes(file.type) && !file.name.match(/\.(wav|mp3|mpeg)$/i)) {
        setError('Please select a valid audio file (WAV or MP3)');
        return;
      }
      
      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        setError('Audio file must be less than 10MB');
        return;
      }
      
      setAudioFile(file);
      setError(null);
    }
  };

  const formatCreatedAt = (voice: VoiceInfo): string => {
    const raw = voice.created_at;
    if (!raw) return '—';
    const d = new Date(raw);
    return isNaN(d.getTime()) ? raw : d.toLocaleDateString();
  };

  return (
    <div className="section">
      <h2>Voice Management</h2>
      <p>
        Clone voices from audio samples using <strong>ElevenLabs</strong> and manage them for telemarketing calls.
      </p>

      {/* Status Messages */}
      {error && (
        <div className="status-area status-error">
          <strong>Error:</strong> {error}
        </div>
      )}
      {success && (
        <div className="status-area status-success">
          <strong>Success:</strong> {success}
        </div>
      )}

      {/* Clone Voice Button */}
      <div style={{ marginBottom: '1rem', marginTop: '1rem'}}>
        <button
          onClick={() => setShowCloneForm(!showCloneForm)}
          style={{ marginBottom: '1rem' }}
        >
          {showCloneForm ? 'Cancel' : '+ Clone New Voice'}
        </button>
      </div>

      {/* Clone Voice Form */}
      {showCloneForm && (
        <div className="section" style={{ marginBottom: '1rem', backgroundColor: 'var(--color-background-soft)' }}>
          <h3>Clone Voice from Audio Sample</h3>
          <form onSubmit={handleCloneVoice}>
            <div style={{ marginBottom: '1rem' }}>
              <label htmlFor="voice-name">Voice Name:</label>
              <input
                type="text"
                id="voice-name"
                value={voiceName}
                onChange={(e) => setVoiceName(e.target.value)}
                placeholder="e.g., company_voice"
                required
                style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
              />
              <small>Choose a unique name for this voice</small>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label htmlFor="audio-file">Audio File:</label>
              <input
                type="file"
                id="audio-file"
                accept="audio/wav,audio/mpeg,audio/mp3"
                onChange={handleFileChange}
                required
                style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
              />
              <small>
                Upload 3-10 seconds of clear speech (WAV or MP3, max 10MB)
              </small>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label htmlFor="language">Language:</label>
              <select
                id="language"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
              >
                <option value="en">English</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
                <option value="de">German</option>
                <option value="it">Italian</option>
                <option value="pt">Portuguese</option>
                <option value="pl">Polish</option>
                <option value="tr">Turkish</option>
                <option value="ru">Russian</option>
                <option value="nl">Dutch</option>
                <option value="cs">Czech</option>
                <option value="ar">Arabic</option>
                <option value="zh-cn">Chinese (Simplified)</option>
                <option value="ja">Japanese</option>
                <option value="hu">Hungarian</option>
                <option value="ko">Korean</option>
              </select>
            </div>

            <button type="submit" disabled={uploading || !audioFile || !voiceName.trim()}>
              {uploading ? 'Cloning...' : 'Clone Voice'}
            </button>
          </form>
        </div>
      )}

      {/* Voices List */}
      <div>
        <h3>Available Voices ({voices.length})</h3>
        
        {loading ? (
          <p>Loading voices...</p>
        ) : voices.length === 0 ? (
          <p>No cloned voices available. Clone a voice to get started.</p>
        ) : (
          <div style={{ display: 'grid', gap: '1rem' }}>
            {voices.map((voice) => (
              <div
                key={voice.name}
                className="section"
                style={{
                  backgroundColor: 'var(--color-background-soft)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '1rem',
                }}
              >
                <div>
                  <strong>{voice.name}</strong>
                  <div style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
                    Language: {voice.language} | Created: {formatCreatedAt(voice)}
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteVoice(voice.name)}
                  style={{
                    backgroundColor: 'var(--color-error)',
                    color: 'white',
                    padding: '0.5rem 1rem',
                  }}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Test Cloned Voice */}
      <div className="section" style={{ marginTop: '2rem', backgroundColor: 'var(--color-background-soft)' }}>
        <h3>Test Cloned Voice</h3>
        <p>Select a cloned voice, enter some text, and generate a sample you can play or download.</p>

        {voices.length === 0 ? (
          <p>No cloned voices available yet. Clone a voice above to begin testing.</p>
        ) : (
          <form onSubmit={handleGenerateSample}>
            <div style={{ marginBottom: '1rem' }}>
              <label htmlFor="test-voice-select">Select Voice:</label>
              <select
                id="test-voice-select"
                value={selectedVoice}
                onChange={(e) => setSelectedVoice(e.target.value)}
                style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
              >
                <option value="">-- Choose a cloned voice --</option>
                {voices.map((voice) => (
                  <option key={voice.name} value={voice.name}>
                    {voice.name} ({voice.language})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label htmlFor="test-text">Text to Synthesize:</label>
              <textarea
                id="test-text"
                value={testText}
                onChange={(e) => {
                  const value = e.target.value;
                  if (value.length <= MAX_TEST_TEXT_LENGTH) {
                    setTestText(value);
                  }
                }}
                maxLength={MAX_TEST_TEXT_LENGTH}
                placeholder="Type the text you want to hear in the selected cloned voice..."
                rows={4}
                style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem', resize: 'vertical' }}
              />
              <small>
                {testText.length}/{MAX_TEST_TEXT_LENGTH} characters
              </small>
            </div>

            <button type="submit" disabled={generating || !selectedVoice || !testText.trim()}>
              {generating ? 'Generating...' : 'Generate Sample'}
            </button>
          </form>
        )}

        {audioUrl && (
          <div style={{ marginTop: '1.5rem' }}>
            <h4>Preview & Download</h4>
            <audio controls src={audioUrl} style={{ width: '100%' }}>
              Your browser does not support the audio element.
            </audio>
            <div style={{ marginTop: '0.75rem' }}>
              <a href={audioUrl} download={downloadFileName}>
                Download generated audio
              </a>
            </div>
          </div>
        )}
      </div>

      {/* Instructions */}
      <div className="section" style={{ marginTop: '2rem', backgroundColor: 'var(--color-info-bg)' }}>
        <h3>Instructions</h3>
        <p style={{ marginBottom: '0.5rem' }}>
          Voice cloning is powered by <strong>ElevenLabs</strong>. Ensure <code>ELEVENLABS_API_KEY</code> is set in the backend.
        </p>
        <ul style={{ marginLeft: '1.5rem' }}>
          <li>Upload 3–10 seconds of clear speech audio (WAV or MP3 format)</li>
          <li>Ensure the audio has minimal background noise</li>
          <li>Use a unique name for each voice</li>
          <li>After cloning, the voice can be used in telemarketing calls</li>
          <li>Cloned voices are stored in the backend <code>data/voices/</code> directory and linked to ElevenLabs</li>
        </ul>
      </div>
    </div>
  );
};

export default VoiceManager;
