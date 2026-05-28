import React, { useState, useEffect } from 'react';

/**
 * VideoTimelineSelector Component
 *
 * Modal component for selecting a time range from long videos (> 10 minutes).
 * Uses two overlapping native range inputs for start/end time selection.
 *
 * Props:
 *   - video: { id, filename, duration_seconds, storage_path }
 *   - onExtract: (startTime, endTime) => void
 *   - onExtractFull: () => void
 *   - onClose: () => void
 */
export default function VideoTimelineSelector({ video, onExtract, onExtractFull, onClose }) {
  const [startTime, setStartTime] = useState(0);
  const [endTime, setEndTime] = useState(Math.min(600, video.duration_seconds)); // Default 10min or max
  const [isDragging, setIsDragging] = useState(null); // 'start' or 'end'

  const duration = video.duration_seconds || 0;

  // Validation
  const segmentDuration = endTime - startTime;
  const isValid = segmentDuration >= 60 && startTime < endTime;

  // Format seconds to MM:SS
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Calculate percentage positions for visual indicators
  const startPercent = (startTime / duration) * 100;
  const endPercent = (endTime / duration) * 100;

  const handleExtractSegment = () => {
    if (isValid) {
      onExtract(startTime, endTime);
    }
  };

  const handleExtractFull = () => {
    onExtractFull();
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: 20
    }}>
      <div style={{
        background: '#1a1a2e',
        borderRadius: 16,
        padding: 32,
        maxWidth: 700,
        width: '100%',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)'
      }}>
        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <h2 style={{
            color: '#fff',
            fontSize: 24,
            fontWeight: 600,
            margin: '0 0 8px 0'
          }}>
            Selecionar trecho do vídeo
          </h2>
          <p style={{
            color: 'rgba(255, 255, 255, 0.6)',
            fontSize: 14,
            margin: 0
          }}>
            {video.filename} • Duração total: {formatTime(duration)}
          </p>
        </div>

        {/* Timeline Slider Container */}
        <div style={{ marginBottom: 32 }}>
          {/* Time Display */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: 16,
            fontSize: 18,
            fontWeight: 600,
            color: '#fff'
          }}>
            <div>
              <span style={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: 14, fontWeight: 400 }}>
                Início:
              </span>
              {' '}{formatTime(startTime)}
            </div>
            <div>
              <span style={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: 14, fontWeight: 400 }}>
                Duração:
              </span>
              {' '}{formatTime(segmentDuration)}
            </div>
            <div>
              <span style={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: 14, fontWeight: 400 }}>
                Fim:
              </span>
              {' '}{formatTime(endTime)}
            </div>
          </div>

          {/* Overlapping Range Inputs */}
          <div style={{ position: 'relative', height: 48 }}>
            {/* Track Background */}
            <div style={{
              position: 'absolute',
              top: '50%',
              left: 0,
              right: 0,
              height: 8,
              transform: 'translateY(-50%)',
              background: 'rgba(255, 255, 255, 0.1)',
              borderRadius: 4,
              pointerEvents: 'none'
            }} />

            {/* Selected Range Highlight */}
            <div style={{
              position: 'absolute',
              top: '50%',
              left: `${startPercent}%`,
              width: `${endPercent - startPercent}%`,
              height: 8,
              transform: 'translateY(-50%)',
              background: 'linear-gradient(90deg, #2563eb, #3b82f6)',
              borderRadius: 4,
              pointerEvents: 'none'
            }} />

            {/* Start Time Slider */}
            <input
              type="range"
              min="0"
              max={duration}
              step="1"
              value={startTime}
              onChange={(e) => {
                const newStart = parseInt(e.target.value);
                setStartTime(Math.min(newStart, endTime - 60));
              }}
              onMouseDown={() => setIsDragging('start')}
              onMouseUp={() => setIsDragging(null)}
              onTouchStart={() => setIsDragging('start')}
              onTouchEnd={() => setIsDragging(null)}
              style={{
                position: 'absolute',
                top: '50%',
                left: 0,
                width: '100%',
                height: 48,
                transform: 'translateY(-50%)',
                opacity: 0,
                cursor: 'pointer',
                zIndex: 2
              }}
            />

            {/* End Time Slider */}
            <input
              type="range"
              min="0"
              max={duration}
              step="1"
              value={endTime}
              onChange={(e) => {
                const newEnd = parseInt(e.target.value);
                setEndTime(Math.max(newEnd, startTime + 60));
              }}
              onMouseDown={() => setIsDragging('end')}
              onMouseUp={() => setIsDragging(null)}
              onTouchStart={() => setIsDragging('end')}
              onTouchEnd={() => setIsDragging(null)}
              style={{
                position: 'absolute',
                top: '50%',
                left: 0,
                width: '100%',
                height: 48,
                transform: 'translateY(-50%)',
                opacity: 0,
                cursor: 'pointer',
                zIndex: 1
              }}
            />

            {/* Thumb Indicators */}
            <div style={{
              position: 'absolute',
              top: '50%',
              left: `${startPercent}%`,
              width: 20,
              height: 20,
              transform: 'translate(-50%, -50%)',
              background: isDragging === 'start' ? '#2563eb' : '#fff',
              border: '3px solid #2563eb',
              borderRadius: '50%',
              pointerEvents: 'none',
              zIndex: 3,
              transition: 'all 0.15s ease',
              boxShadow: isDragging === 'start' ? '0 0 0 4px rgba(37, 99, 235, 0.3)' : 'none'
            }} />

            <div style={{
              position: 'absolute',
              top: '50%',
              left: `${endPercent}%`,
              width: 20,
              height: 20,
              transform: 'translate(-50%, -50%)',
              background: isDragging === 'end' ? '#2563eb' : '#fff',
              border: '3px solid #2563eb',
              borderRadius: '50%',
              pointerEvents: 'none',
              zIndex: 3,
              transition: 'all 0.15s ease',
              boxShadow: isDragging === 'end' ? '0 0 0 4px rgba(37, 99, 235, 0.3)' : 'none'
            }} />
          </div>

          {/* Validation Error */}
          {!isValid && (
            <div style={{
              marginTop: 12,
              padding: '10px 14px',
              background: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              borderRadius: 8,
              color: '#fca5a5',
              fontSize: 13,
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}>
              <span style={{ fontSize: 16 }}>⚠️</span>
              {segmentDuration < 60
                ? `Duração mínima: 60 segundos (atual: ${Math.round(segmentDuration)}s)`
                : 'Start deve ser menor que End'}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div style={{
          display: 'flex',
          gap: 12,
          justifyContent: 'flex-end'
        }}>
          <button
            onClick={onClose}
            style={{
              padding: '12px 24px',
              background: 'transparent',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              borderRadius: 8,
              color: '#fff',
              fontSize: 15,
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.1)'}
            onMouseLeave={(e) => e.target.style.background = 'transparent'}
          >
            Cancelar
          </button>

          <button
            onClick={handleExtractFull}
            style={{
              padding: '12px 24px',
              background: 'rgba(255, 255, 255, 0.1)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              borderRadius: 8,
              color: '#fff',
              fontSize: 15,
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.15)'}
            onMouseLeave={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.1)'}
          >
            Extrair Vídeo Inteiro
          </button>

          <button
            onClick={handleExtractSegment}
            disabled={!isValid}
            style={{
              padding: '12px 24px',
              background: isValid
                ? 'linear-gradient(135deg, #2563eb 0%, #3b82f6 100%)'
                : 'rgba(255, 255, 255, 0.05)',
              border: isValid ? '1px solid #2563eb' : '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 8,
              color: isValid ? '#fff' : 'rgba(255, 255, 255, 0.3)',
              fontSize: 15,
              fontWeight: 600,
              cursor: isValid ? 'pointer' : 'not-allowed',
              transition: 'all 0.2s',
              opacity: isValid ? 1 : 0.6
            }}
            onMouseEnter={(e) => {
              if (isValid) e.target.style.background = 'linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%)';
            }}
            onMouseLeave={(e) => {
              if (isValid) e.target.style.background = 'linear-gradient(135deg, #2563eb 0%, #3b82f6 100%)';
            }}
          >
            Extrair Trecho Selecionado
          </button>
        </div>

        {/* Info Text */}
        <div style={{
          marginTop: 20,
          padding: 12,
          background: 'rgba(37, 99, 235, 0.1)',
          border: '1px solid rgba(37, 99, 235, 0.2)',
          borderRadius: 8,
          color: 'rgba(255, 255, 255, 0.7)',
          fontSize: 13,
          textAlign: 'center'
        }}>
          💡 Arraste os marcadores para ajustar o início e fim do trecho
        </div>
      </div>
    </div>
  );
}
