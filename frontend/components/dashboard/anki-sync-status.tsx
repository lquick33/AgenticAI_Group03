'use client'

import { useState, useEffect } from 'react'
import { AlertCircle, CheckCircle2, Cloud, CloudOff, Settings, RefreshCw, Upload, Download } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useSettings } from '@/components/settings'

interface SyncStatus {
  status: 'ok' | 'full_sync_required' | 'not_logged_in' | 'not_connected' | 'error'
  message: string
  can_sync: boolean
  action_required?: 'resolve_conflict' | 'login_ankiweb' | 'start_anki' | null
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function AnkiSyncStatus() {
  const { openSettings } = useSettings()
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [showConflictDialog, setShowConflictDialog] = useState(false)
  const [forceSyncDirection, setForceSyncDirection] = useState<'upload' | 'download' | null>(null)

  const checkSyncStatus = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_URL}/api/anki/sync-status`)
      if (response.ok) {
        const data = await response.json()
        setStatus(data)
      } else {
        setStatus({
          status: 'error',
          message: 'Failed to check sync status',
          can_sync: false,
        })
      }
    } catch (error) {
      setStatus({
        status: 'not_connected',
        message: 'Cannot connect to backend',
        can_sync: false,
        action_required: 'start_anki',
      })
    } finally {
      setLoading(false)
    }
  }

  const triggerSync = async () => {
    try {
      setSyncing(true)
      const response = await fetch(`${API_URL}/api/anki/sync`, {
        method: 'POST',
      })
      
      if (response.ok) {
        await checkSyncStatus()
      } else if (response.status === 409) {
        // Conflict - need force sync
        setShowConflictDialog(true)
      } else {
        const data = await response.json()
        setStatus({
          status: 'error',
          message: data.detail || 'Sync failed',
          can_sync: false,
        })
      }
    } catch (error) {
      setStatus({
        status: 'error',
        message: 'Sync request failed',
        can_sync: false,
      })
    } finally {
      setSyncing(false)
    }
  }

  const handleForceSync = async (direction: 'upload' | 'download') => {
    try {
      setForceSyncDirection(direction)
      const response = await fetch(`${API_URL}/api/anki/force-sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: direction }),
      })
      
      if (response.ok) {
        setShowConflictDialog(false)
        await checkSyncStatus()
      } else if (response.status === 501) {
        // Force sync not available - need VNC
        setShowConflictDialog(false)
        setStatus({
          status: 'full_sync_required',
          message: 'Please resolve the sync conflict manually via VNC',
          can_sync: false,
          action_required: 'resolve_conflict',
        })
      } else {
        const data = await response.json()
        throw new Error(data.detail || 'Force sync failed')
      }
    } catch (error) {
      console.error('Force sync failed:', error)
    } finally {
      setForceSyncDirection(null)
    }
  }

  useEffect(() => {
    checkSyncStatus()
  }, [])

  // Adaptive polling: faster when there's a problem, slower when OK
  useEffect(() => {
    // Poll every 5 seconds when not connected, every 2 minutes when OK
    const pollInterval = status?.status === 'ok' ? 120000 : 5000
    const interval = setInterval(checkSyncStatus, pollInterval)
    return () => clearInterval(interval)
  }, [status?.status])

  if (loading && !status) {
    return null
  }

  // Don't show anything if everything is OK
  if (status?.status === 'ok') {
    return null
  }

  // Render based on status
  const renderContent = () => {
    if (!status) return null

    switch (status.status) {
      case 'full_sync_required':
        return (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>AnkiWeb Sync Conflict</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>
                Your local Anki and AnkiWeb have diverged. Choose which data to keep.
              </span>
              <div className="flex gap-2 ml-4">
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => setShowConflictDialog(true)}
                >
                  Resolve
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )

      case 'not_logged_in':
        return (
          <div className="rounded-lg border bg-card p-6 mb-4">
            <div className="flex flex-col items-center text-center sm:flex-row sm:text-left sm:items-start gap-4">
              <div className="rounded-full bg-blue-100 p-3 shrink-0">
                <Cloud className="h-6 w-6 text-blue-600" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg">Mit AnkiWeb verbinden</h3>
                <p className="text-muted-foreground mt-1">
                  Verbinde dein AnkiWeb-Konto, um deine Karteikarten automatisch auf alle Geräte zu synchronisieren.
                </p>
                <div className="flex flex-wrap gap-2 mt-4">
                  <Button onClick={openSettings}>
                    <Settings className="h-4 w-4 mr-2" />
                    Jetzt verbinden
                  </Button>
                  <Button variant="ghost" asChild>
                    <a href="https://ankiweb.net/account/signup" target="_blank" rel="noopener noreferrer">
                      Konto erstellen
                    </a>
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )

      case 'not_connected':
        return (
          <div className="rounded-lg border bg-card p-6 mb-4">
            <div className="flex flex-col items-center text-center sm:flex-row sm:text-left sm:items-start gap-4">
              <div className="rounded-full bg-orange-100 p-3 shrink-0">
                <CloudOff className="h-6 w-6 text-orange-600" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg">Anki nicht verbunden</h3>
                <p className="text-muted-foreground mt-1">
                  Der Anki Docker Container läuft nicht. Karteikarten werden zwischengespeichert.
                </p>
                <details className="mt-3 text-sm">
                  <summary className="cursor-pointer font-medium text-muted-foreground hover:text-foreground">
                    Wie starte ich Anki?
                  </summary>
                  <ol className="mt-2 ml-4 list-decimal space-y-1 text-muted-foreground">
                    <li>Docker Desktop starten</li>
                    <li>Terminal im Projektordner öffnen</li>
                    <li>Ausführen: <code className="bg-muted px-1.5 py-0.5 rounded text-xs">./start_anki.sh</code></li>
                    <li>Warten bis &quot;Anki is ready!&quot; erscheint</li>
                  </ol>
                </details>
              </div>
            </div>
          </div>
        )

      case 'error':
        return (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Sync Error</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>{status.message}</span>
              <Button 
                variant="outline" 
                size="sm"
                onClick={checkSyncStatus}
              >
                <RefreshCw className="h-3 w-3 mr-1" />
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )

      default:
        return null
    }
  }

  return (
    <>
      {renderContent()}

      {/* Conflict Resolution Dialog */}
      <Dialog open={showConflictDialog} onOpenChange={setShowConflictDialog}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Resolve Sync Conflict</DialogTitle>
            <DialogDescription>
              Your local Anki data and AnkiWeb have diverged. Choose which data to keep:
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid gap-4 py-4">
            <div className="rounded-lg border p-4 hover:border-primary cursor-pointer" 
                 onClick={() => handleForceSync('upload')}>
              <div className="flex items-center gap-3">
                <Upload className="h-8 w-8 text-blue-500" />
                <div>
                  <h4 className="font-semibold">Upload (Keep Local)</h4>
                  <p className="text-sm text-muted-foreground">
                    Overwrite AnkiWeb with your generated flashcards. 
                    <strong className="text-destructive"> This will replace data on your phone/other devices.</strong>
                  </p>
                </div>
              </div>
              {forceSyncDirection === 'upload' && (
                <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Uploading...
                </div>
              )}
            </div>

            <div className="rounded-lg border p-4 hover:border-primary cursor-pointer"
                 onClick={() => handleForceSync('download')}>
              <div className="flex items-center gap-3">
                <Download className="h-8 w-8 text-green-500" />
                <div>
                  <h4 className="font-semibold">Download (Keep Cloud)</h4>
                  <p className="text-sm text-muted-foreground">
                    Overwrite local with AnkiWeb data.
                    <strong className="text-destructive"> This will discard any unsent generated flashcards.</strong>
                  </p>
                </div>
              </div>
              {forceSyncDirection === 'download' && (
                <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Downloading...
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConflictDialog(false)}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
