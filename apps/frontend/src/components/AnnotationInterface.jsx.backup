'use client'

import { useState, useEffect, useRef } from 'react'

const DEFAULT_CLASSES = [
  { id: 1, name: 'Produto', color: '#22c55e' },
  { id: 2, name: 'Caminhão', color: '#f59e0b' },
  { id: 3, name: 'Placa', color: '#3b82f6' },
  { id: 4, name: 'Capacete', color: '#8b5cf6' },
  { id: 5, name: 'Colete', color: '#ec4899' },
  { id: 6, name: 'Sem EPI', color: '#ef4444' },
]

const CLASS_COLORS = [
  '#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#eab308',
  '#a855f7', '#6366f1'
]

export default function AnnotationInterface({ videoId, onBack }) {
  if (!videoId) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: 'calc(100vh - 100px)',
        background: '#0d1117',
        color: 'rgba(255, 255, 255, 0.5)',
        fontSize: '14px'
      }}>
        Nenhum vídeo selecionado
      </div>
    )
  }

  const [frames, setFrames] = useState([])
  const [selectedFrame, setSelectedFrame] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [annotations, setAnnotations] = useState([])
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)

  const [toolMode, setToolMode] = useState('draw')
  const [activeClass, setActiveClass] = useState(DEFAULT_CLASSES[0])
  const [classes, setClasses] = useState(DEFAULT_CLASSES)

  const [isDrawing, setIsDrawing] = useState(false)
  const [drawStart, setDrawStart] = useState(null)
  const [drawEnd, setDrawEnd] = useState(null)

  const [selectedBox, setSelectedBox] = useState(null)
  const [isDraggingBox, setIsDraggingBox] = useState(false)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })
  const [resizeHandle, setResizeHandle] = useState(null)

  const [showNewClassModal, setShowNewClassModal] = useState(false)
  const [newClassName, setNewClassName] = useState('')
  const [newClassColor, setNewClassColor] = useState(CLASS_COLORS[0])

  const imageContainerRef = useRef(null)
  const timelineRef = useRef(null)

  useEffect(() => {
    loadFrames()
    loadClasses()
  }, [videoId])

  useEffect(() => {
    if (!selectedFrame) return
    const timer = setTimeout(() => {
      loadAnnotations(selectedFrame.id)
    }, 300)
    return () => clearTimeout(timer)
  }, [selectedFrame])

  useEffect(() => {
    if (selectedFrame && timelineRef.current) {
      const element = timelineRef.current.querySelector(`[data-frame-id="${selectedFrame.id}"]`)
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
      }
    }
  }, [selectedFrame])

  const loadFrames = async () => {
    if (!videoId) return
    setLoading(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/training/videos/${videoId}/frames`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const result = await response.json()
      if (result.success && result.frames) {
        setFrames(result.frames || [])
        if (result.frames && result.frames.length > 0) {
          setSelectedFrame(result.frames[0])
        }
      } else {
        setFrames([])
      }
    } catch (error) {
      setFrames([])
    } finally {
      setLoading(false)
    }
  }

  const loadClasses = async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch('/api/classes', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const result = await response.json()
      if (result.success && result.classes && result.classes.length > 0) {
        setClasses(result.classes)
        setActiveClass(result.classes[0])
      }
    } catch (error) {
      // Use defaults
    }
  }

  const loadAnnotations = async (frameId) => {
    if (!frameId) return
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/training/frames/${frameId}/annotations`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!response.ok) {
        setAnnotations([])
        setHasUnsavedChanges(false)
        return
      }
      const result = await response.json()
      if (result.success && result.annotations) {
        setAnnotations(result.annotations)
        setHasUnsavedChanges(false)
      } else {
        setAnnotations([])
        setHasUnsavedChanges(false)
      }
    } catch (error) {
      setAnnotations([])
      setHasUnsavedChanges(false)
    }
  }

  const saveAnnotations = async (frameId, annotationsToSave) => {
    setSaving(true)
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/training/frames/${frameId}/annotations`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ annotations: annotationsToSave })
      })
      const result = await response.json()
      if (result.success) {
        setFrames(prev => prev.map(f =>
          f.id === frameId ? { ...f, is_annotated: true } : f
        ))
        setHasUnsavedChanges(false)
      }
    } catch (error) {
      // Silencioso
    } finally {
      setSaving(false)
    }
  }

  const handleFrameChange = async (newFrame) => {
    if (!selectedFrame || newFrame.id === selectedFrame.id) return

    if (hasUnsavedChanges) {
      await saveAnnotations(selectedFrame.id, annotations)
    }

    setSelectedFrame(newFrame)
  }

  const handlePrevFrame = async () => {
    if (!selectedFrame || !frames || frames.length === 0) return
    const currentIndex = frames.findIndex(f => f.id === selectedFrame.id)
    if (currentIndex > 0) {
      await handleFrameChange(frames[currentIndex - 1])
    }
  }

  const handleNextFrame = async () => {
    if (!selectedFrame || !frames || frames.length === 0) return
    const currentIndex = frames.findIndex(f => f.id === selectedFrame.id)
    if (currentIndex < frames.length - 1) {
      await handleFrameChange(frames[currentIndex + 1])
    }
  }

  const updateAnnotations = (newAnnotations) => {
    setAnnotations(newAnnotations)
    setHasUnsavedChanges(true)
  }

  const handleMouseDown = (e) => {
    if (!imageContainerRef.current) return

    const rect = imageContainerRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height

    if (toolMode === 'select' && selectedBox) {
      const handle = e.target.dataset.handle
      if (handle) {
        setResizeHandle(handle)
        return
      }

      const box = annotations.find(a => a.id === selectedBox)
      if (box) {
        const left = box.x_center - box.width / 2
        const top = box.y_center - box.height / 2
        const right = left + box.width
        const bottom = top + box.height

        if (x >= left && x <= right && y >= top && y <= bottom) {
          setIsDraggingBox(true)
          setDragOffset({ x: x - box.x_center, y: y - box.y_center })
          return
        }
      }

      setSelectedBox(null)
      return
    }

    if (toolMode === 'draw') {
      setIsDrawing(true)
      setDrawStart({ x, y })
      setDrawEnd({ x, y })
    }
  }

  const handleMouseMove = (e) => {
    if (!imageContainerRef.current) return

    const rect = imageContainerRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height

    if (toolMode === 'select' && resizeHandle && selectedBox) {
      updateAnnotations(prev => prev.map(box => {
        if (box.id !== selectedBox) return box

        let newBox = { ...box }

        const halfW = box.width / 2
        const halfH = box.height / 2
        let newX = box.x_center
        let newY = box.y_center
        let newW = box.width
        let newH = box.height

        switch (resizeHandle) {
          case 'nw':
            newW = (box.x_center + halfW) - x
            newH = (box.y_center + halfH) - y
            newX = x + newW / 2
            newY = y + newH / 2
            break
          case 'n':
            newH = (box.y_center + halfH) - y
            newY = y + newH / 2
            break
          case 'ne':
            newW = x - (box.x_center - halfW)
            newH = (box.y_center + halfH) - y
            newX = x - newW / 2
            newY = y + newH / 2
            break
          case 'e':
            newW = x - (box.x_center - halfW)
            newX = x - newW / 2
            break
          case 'se':
            newW = x - (box.x_center - halfW)
            newH = y - (box.y_center - halfH)
            newX = x - newW / 2
            newY = y - newH / 2
            break
          case 's':
            newH = y - (box.y_center - halfH)
            newY = y - newH / 2
            break
          case 'sw':
            newW = (box.x_center + halfW) - x
            newH = y - (box.y_center - halfH)
            newX = x + newW / 2
            newY = y - newH / 2
            break
          case 'w':
            newW = (box.x_center + halfW) - x
            newX = x + newW / 2
            break
        }

        if (newW >= 0.02 && newH >= 0.02) {
          newBox.x_center = Math.max(newW / 2, Math.min(1 - newW / 2, newX))
          newBox.y_center = Math.max(newH / 2, Math.min(1 - newH / 2, newY))
          newBox.width = newW
          newBox.height = newH
        }

        return newBox
      }))
      return
    }

    if (toolMode === 'select' && isDraggingBox && selectedBox) {
      updateAnnotations(prev => prev.map(box => {
        if (box.id !== selectedBox) return box

        const newX = x - dragOffset.x
        const newY = y - dragOffset.y
        const halfW = box.width / 2
        const halfH = box.height / 2

        return {
          ...box,
          x_center: Math.max(halfW, Math.min(1 - halfW, newX)),
          y_center: Math.max(halfH, Math.min(1 - halfH, newY)),
        }
      }))
      return
    }

    if (isDrawing) {
      setDrawEnd({ x, y })
    }
  }

  const handleMouseUp = () => {
    if (resizeHandle) {
      setResizeHandle(null)
      return
    }

    if (isDraggingBox) {
      setIsDraggingBox(false)
      return
    }

    if (!isDrawing || !drawStart || !drawEnd) return

    const x_center = (drawStart.x + drawEnd.x) / 2
    const y_center = (drawStart.y + drawEnd.y) / 2
    const width = Math.abs(drawEnd.x - drawStart.x)
    const height = Math.abs(drawEnd.y - drawStart.y)

    if (width > 0.05 && height > 0.05) {
      const newAnnotation = {
        id: `annotation-${Date.now()}`,
        class_id: activeClass.id,
        class_name: activeClass.name,
        x_center,
        y_center,
        width,
        height
      }
      updateAnnotations(prev => [...prev, newAnnotation])
    }

    setIsDrawing(false)
    setDrawStart(null)
    setDrawEnd(null)
  }

  const handleBoxClick = (boxId, e) => {
    e.stopPropagation()
    if (toolMode === 'delete') {
      updateAnnotations(prev => prev.filter(a => a.id !== boxId))
      if (selectedBox === boxId) setSelectedBox(null)
    } else if (toolMode === 'select') {
      setSelectedBox(boxId)
    }
  }

  const createNewClass = async () => {
    if (!newClassName.trim()) return

    try {
      const token = localStorage.getItem('token')
      const res = await fetch('/api/classes', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: newClassName.trim(),
          color: newClassColor
        })
      })

      if (res.ok) {
        const data = await res.json()
        const nova = data.class || { id: Date.now(), name: newClassName.trim(), color: newClassColor }
        setClasses(prev => [...prev, nova])
        setActiveClass(nova)
        setNewClassName('')
        setShowNewClassModal(false)
        setToolMode('draw')
      }
    } catch (e) {
      // Silencioso
    }
  }

  const renderBoundingBoxes = () => {
    const container = imageContainerRef.current
    if (!container) return null

    return annotations.map((box) => {
      const left = (box.x_center - box.width / 2) * 100
      const top = (box.y_center - box.height / 2) * 100
      const width = box.width * 100
      const height = box.height * 100
      const classColor = classes.find(c => c.id === box.class_id)?.color || '#ffffff'
      const isSelected = selectedBox === box.id

      return (
        <div key={box.id}>
          <div
            onClick={(e) => handleBoxClick(box.id, e)}
            style={{
              position: 'absolute',
              left: `${left}%`,
              top: `${top}%`,
              width: `${width}%`,
              height: `${height}%`,
              border: isSelected ? `3px solid ${classColor}` : `2px solid ${classColor}`,
              backgroundColor: isSelected ? `${classColor}30` : 'transparent',
              cursor: toolMode === 'select' ? 'move' : (toolMode === 'delete' ? 'not-allowed' : 'pointer'),
              zIndex: isSelected ? 100 : 1,
              pointerEvents: 'auto'
            }}
          >
            <div style={{
              position: 'absolute',
              top: '-16px',
              left: '-2px',
              backgroundColor: classColor,
              color: '#fff',
              fontSize: '10px',
              padding: '1px 4px',
              borderRadius: '2px',
              whiteSpace: 'nowrap',
              pointerEvents: 'none'
            }}>
              {box.class_name}
            </div>
          </div>

          {isSelected && toolMode === 'select' && (
            <>
              {['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'].map(handle => {
                const isVertical = handle === 'n' || handle === 's'
                return (
                  <div
                    key={handle}
                    data-handle={handle}
                    style={{
                      position: 'absolute',
                      width: isVertical ? '14px' : '8px',
                      height: isVertical ? '8px' : '14px',
                      backgroundColor: classColor,
                      border: '2px solid #fff',
                      borderRadius: '2px',
                      zIndex: 101,
                      pointerEvents: 'auto',
                      cursor: handle === 'nw' ? 'nw-resize' :
                             handle === 'n' ? 'n-resize' :
                             handle === 'ne' ? 'ne-resize' :
                             handle === 'e' ? 'e-resize' :
                             handle === 'se' ? 'se-resize' :
                             handle === 's' ? 's-resize' :
                             handle === 'sw' ? 'sw-resize' : 'w-resize',
                      ...(handle === 'nw' && { left: `${left}%`, top: `${top}%`, transform: 'translate(-50%, -50%)' }),
                      ...(handle === 'n' && { left: `${left + width / 2}%`, top: `${top}%`, transform: 'translate(-50%, -50%)' }),
                      ...(handle === 'ne' && { left: `${left + width}%`, top: `${top}%`, transform: 'translate(50%, -50%)' }),
                      ...(handle === 'e' && { left: `${left + width}%`, top: `${top + height / 2}%`, transform: 'translate(50%, -50%)' }),
                      ...(handle === 'se' && { left: `${left + width}%`, top: `${top + height}%`, transform: 'translate(50%, 50%)' }),
                      ...(handle === 's' && { left: `${left + width / 2}%`, top: `${top + height}%`, transform: 'translate(-50%, 50%)' }),
                      ...(handle === 'sw' && { left: `${left}%`, top: `${top + height}%`, transform: 'translate(-50%, 50%)' }),
                      ...(handle === 'w' && { left: `${left}%`, top: `${top + height / 2}%`, transform: 'translate(-50%, 50%)' }),
                    }}
                  />
                )
              })}
            </>
          )}
        </div>
      )
    })
  }

  const renderDrawingPreview = () => {
    if (!isDrawing || !drawStart || !drawEnd) return null

    const left = Math.min(drawStart.x, drawEnd.x) * 100
    const top = Math.min(drawStart.y, drawEnd.y) * 100
    const width = Math.abs(drawEnd.x - drawStart.x) * 100
    const height = Math.abs(drawEnd.y - drawStart.y) * 100

    return (
      <div style={{
        position: 'absolute',
        left: `${left}%`,
        top: `${top}%`,
        width: `${width}%`,
        height: `${height}%`,
        border: '2px dashed #2563eb',
        backgroundColor: 'rgba(37, 99, 235, 0.1)',
        pointerEvents: 'none',
        zIndex: 20
      }} />
    )
  }

  const formatTimestamp = (frameNumber) => {
    const seconds = Math.floor(frameNumber)
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const currentFrameIndex = selectedFrame && frames ? frames.findIndex(f => f.id === selectedFrame.id) : -1

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: 'calc(100vh - 100px)',
      background: '#0d1117'
    }}>
      {/* Header */}
      <div style={{
        background: '#161b22',
        borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
        padding: '12px 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <button
          onClick={onBack}
          style={{
            padding: '8px 16px',
            background: 'transparent',
            color: 'rgba(255, 255, 255, 0.7)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '6px',
            fontSize: '13px',
            cursor: 'pointer'
          }}
        >
          ← Voltar
        </button>

        <h2 style={{
          fontSize: '16px',
          fontWeight: '600',
          color: '#fff',
          margin: 0
        }}>
          Anotação — Vídeo {videoId ? videoId.slice(0, 8) : 'Unknown'}
        </h2>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {hasUnsavedChanges && (
            <span style={{
              padding: '4px 12px',
              background: 'rgba(245, 158, 11, 0.2)',
              color: '#f59e0b',
              borderRadius: '4px',
              fontSize: '12px'
            }}>
              Não salvo
            </span>
          )}
          {saving && (
            <span style={{
              padding: '4px 12px',
              background: 'rgba(34, 197, 94, 0.2)',
              color: '#22c55e',
              borderRadius: '4px',
              fontSize: '12px'
            }}>
              Salvando...
            </span>
          )}
        </div>
      </div>

      {/* Toolbar */}
      <div style={{
        background: '#161b22',
        borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
        padding: '8px 24px',
        display: 'flex',
        gap: '16px',
        alignItems: 'center'
      }}>
        {/* Tool buttons */}
        <div style={{ display: 'flex', gap: '8px' }}>
          {['draw', 'select', 'delete'].map(mode => (
            <button
              key={mode}
              onClick={() => {
                setToolMode(mode)
                setSelectedBox(null)
              }}
              style={{
                padding: '8px 16px',
                background: toolMode === mode ? 'rgba(37, 99, 235, 0.8)' : 'transparent',
                color: toolMode === mode ? '#fff' : 'rgba(255, 255, 255, 0.5)',
                border: toolMode === mode ? 'none' : '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '6px',
                fontSize: '13px',
                cursor: 'pointer'
              }}
            >
              {mode === 'draw' ? 'Desenhar' : mode === 'select' ? 'Selecionar' : 'Apagar'}
            </button>
          ))}
        </div>

        <div style={{
          width: '1px',
          height: '24px',
          background: 'rgba(255, 255, 255, 0.1)'
        }} />

        {/* Class dropdown */}
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: '13px' }}>Classe:</span>

          <button
            onClick={() => {
              if (showNewClassModal) {
                setShowNewClassModal(false)
              } else {
                setShowNewClassModal(true)
              }
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              background: `${activeClass.color}20`,
              border: `1px solid ${activeClass.color}`,
              borderRadius: '6px',
              fontSize: '13px',
              color: '#fff',
              cursor: 'pointer'
            }}
          >
            <span style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              background: activeClass.color
            }} />
            {activeClass.name}
            <span style={{ fontSize: '10px', opacity: 0.5 }}>▼</span>
          </button>

          {showNewClassModal && (
            <>
              <div
                onClick={() => setShowNewClassModal(false)}
                style={{
                  position: 'fixed',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  background: 'rgba(0, 0, 0, 0.5)',
                  zIndex: 999
                }}
              />
              <div style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                marginTop: '8px',
                background: '#161b22',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                padding: '8px',
                zIndex: 1000,
                minWidth: '280px',
                maxHeight: '400px',
                overflowY: 'auto'
              }}>
                {/* Existing classes */}
                <div style={{ marginBottom: '8px', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                  <div style={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: '11px', marginBottom: '4px', textTransform: 'uppercase' }}>
                    Classes existentes
                  </div>
                  {classes.map(cls => (
                    <button
                      key={cls.id}
                      onClick={() => {
                        setActiveClass(cls)
                        setToolMode('draw')
                        setShowNewClassModal(false)
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        width: '100%',
                        padding: '6px 8px',
                        background: activeClass.id === cls.id ? `${cls.color}30` : 'transparent',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '13px',
                        color: '#fff',
                        cursor: 'pointer',
                        textAlign: 'left'
                      }}
                    >
                      <span style={{
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        background: cls.color
                      }} />
                      {cls.name}
                    </button>
                  ))}
                </div>

                {/* New class */}
                <div>
                  <button
                    onClick={() => setNewClassName(' ')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      width: '100%',
                      padding: '6px 8px',
                      background: 'transparent',
                      border: '1px dashed rgba(255, 255, 255, 0.2)',
                      borderRadius: '4px',
                      fontSize: '13px',
                      color: 'rgba(255, 255, 255, 0.5)',
                      cursor: 'pointer'
                    }}
                  >
                    <span style={{ fontSize: '16px' }}>+</span>
                    Nova Classe...
                  </button>

                  {newClassName !== '' && (
                    <div style={{ marginTop: '8px' }}>
                      <input
                        type="text"
                        value={newClassName}
                        onChange={(e) => setNewClassName(e.target.value)}
                        placeholder="Nome da classe"
                        autoFocus
                        onFocus={(e) => e.currentTarget.select()}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            createNewClass()
                          } else if (e.key === 'Escape') {
                            setNewClassName('')
                          }
                        }}
                        style={{
                          width: '100%',
                          padding: '6px 8px',
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          borderRadius: '4px',
                          fontSize: '13px',
                          color: '#fff',
                          outline: 'none',
                          marginBottom: '8px'
                        }}
                      />

                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                        {CLASS_COLORS.map(color => (
                          <button
                            key={color}
                            onClick={() => setNewClassColor(color)}
                            style={{
                              width: '24px',
                              height: '24px',
                              borderRadius: '4px',
                              background: color,
                              border: newClassColor === color ? '2px solid #fff' : '2px solid transparent',
                              cursor: 'pointer'
                            }}
                          />
                        ))}
                      </div>

                      <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                        <button
                          onClick={createNewClass}
                          disabled={!newClassName.trim()}
                          style={{
                            flex: 1,
                            padding: '6px',
                            background: newClassName.trim() ? 'rgba(34, 197, 94, 0.8)' : 'rgba(255, 255, 255, 0.1)',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '4px',
                            fontSize: '12px',
                            cursor: newClassName.trim() ? 'pointer' : 'not-allowed',
                            opacity: newClassName.trim() ? 1 : 0.5
                          }}
                        >
                          Criar
                        </button>
                        <button
                          onClick={() => setNewClassName('')}
                          style={{
                            flex: 1,
                            padding: '6px',
                            background: 'transparent',
                            color: 'rgba(255, 255, 255, 0.5)',
                            border: '1px solid rgba(255, 255, 255, 0.1)',
                            borderRadius: '4px',
                            fontSize: '12px',
                            cursor: 'pointer'
                          }}
                        >
                          Cancelar
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Image area */}
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        background: '#0d1117'
      }}>
        {loading ? (
          <div style={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: '14px' }}>
            Carregando frames...
          </div>
        ) : selectedFrame ? (
          <div
            ref={imageContainerRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            style={{
              position: 'relative',
              maxWidth: '100%',
              maxHeight: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <img
              src={`/api/training/frames/${selectedFrame.id}/image`}
              alt={`Frame ${selectedFrame.frame_number}`}
              draggable={false}
              style={{
                maxWidth: '100%',
                maxHeight: 'calc(100vh - 350px)',
                display: 'block',
                userSelect: 'none',
                pointerEvents: 'none'
              }}
            />

            {renderBoundingBoxes()}
            {renderDrawingPreview()}

            {annotations.length === 0 && !isDrawing && (
              <div style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                background: 'rgba(0, 0, 0, 0.7)',
                color: '#fff',
                padding: '16px 24px',
                borderRadius: '8px',
                fontSize: '13px',
                textAlign: 'center',
                pointerEvents: 'none'
              }}>
                <div style={{ fontWeight: '600', marginBottom: '8px' }}>
                  Modo {toolMode === 'draw' ? 'Desenhar' : toolMode === 'select' ? 'Selecionar' : 'Apagar'}
                </div>
                <div style={{ fontSize: '12px', opacity: 0.8 }}>
                  {toolMode === 'draw' && 'Clique e arraste para desenhar caixas'}
                  {toolMode === 'select' && 'Clique em uma caixa para selecioná-la'}
                  {toolMode === 'delete' && 'Clique em uma caixa para removê-la'}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ color: 'rgba(255, 255, 255, 0.5)', fontSize: '14px' }}>
            Nenhum frame disponível
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div style={{
        background: '#161b22',
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
        padding: '8px 24px',
        fontSize: '12px',
        color: 'rgba(255, 255, 255, 0.6)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <button
          onClick={handlePrevFrame}
          disabled={!selectedFrame || currentFrameIndex === 0}
          style={{
            padding: '4px 12px',
            background: 'transparent',
            color: selectedFrame && currentFrameIndex > 0 ? 'rgba(255, 255, 255, 0.7)' : 'rgba(255, 255, 255, 0.2)',
            border: '1px solid transparent',
            borderRadius: '4px',
            fontSize: '12px',
            cursor: selectedFrame && currentFrameIndex > 0 ? 'pointer' : 'default'
          }}
        >
          ← {currentFrameIndex + 1}/{frames.length}
        </button>

        <div style={{ display: 'flex', gap: '16px' }}>
          <span>Boxes: {annotations.length}</span>
        </div>

        <button
          onClick={handleNextFrame}
          disabled={!selectedFrame || currentFrameIndex === frames.length - 1}
          style={{
            padding: '4px 12px',
            background: 'transparent',
            color: selectedFrame && currentFrameIndex < frames.length - 1 ? 'rgba(255, 255, 255, 0.7)' : 'rgba(255, 255, 255, 0.2)',
            border: '1px solid transparent',
            borderRadius: '4px',
            fontSize: '12px',
            cursor: selectedFrame && currentFrameIndex < frames.length - 1 ? 'pointer' : 'default'
          }}
        >
          Boxes: {annotations.length} →
        </button>
      </div>

      {/* Timeline */}
      <div style={{
        background: '#0d1117',
        height: '130px',
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        display: 'flex',
        flexDirection: 'column'
      }}>
        <div
          ref={timelineRef}
          style={{
            flex: 1,
            display: 'flex',
            gap: '4px',
            padding: '12px 24px',
            overflowX: 'auto',
            overflowY: 'hidden'
          }}
        >
          {(frames || []).map((frame) => (
            <div
              key={frame.id}
              data-frame-id={frame.id}
              onClick={() => handleFrameChange(frame)}
              style={{
                position: 'relative',
                flexShrink: 0,
                width: '80px',
                height: '50px',
                border: selectedFrame?.id === frame.id ? '2px solid #2563eb' : '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '4px',
                overflow: 'hidden',
                cursor: 'pointer',
                transform: selectedFrame?.id === frame.id ? 'scale(1.08)' : 'scale(1)',
                transition: 'all 0.15s',
                zIndex: selectedFrame?.id === frame.id ? 2 : 1,
                background: '#161b22'
              }}
            >
              <img
                src={`/api/training/frames/${frame.id}/image`}
                alt={`Frame ${frame.frame_number}`}
                loading="lazy"
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  display: 'block'
                }}
              />

              {frame.is_annotated && (
                <div style={{
                  position: 'absolute',
                  top: '4px',
                  right: '4px',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: '#2563eb',
                  boxShadow: '0 0 4px rgba(37, 99, 235, 0.5)'
                }} />
              )}
            </div>
          ))}
        </div>

        <div style={{
          padding: '0 24px 8px',
          display: 'flex',
          gap: '80px',
          overflowX: 'auto',
          fontSize: '9px',
          color: 'rgba(255, 255, 255, 0.25)'
        }}>
          {frames.filter((_, idx) => idx % 10 === 0).map((frame) => (
            <span key={frame.id} style={{ flexShrink: 0, minWidth: '80px', textAlign: 'center' }}>
              {formatTimestamp(frame.frame_number)}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
