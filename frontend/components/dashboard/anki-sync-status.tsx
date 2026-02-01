'use client'

import { useState, useEffect } from 'react'
import { AlertCircle, CheckCircle2, CloudOff, Settings, RefreshCw, Upload, Download } from 'lucide-react'
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
    // Check every 2 minutes
    const interval = setInterval(checkSyncStatus, 120000)
    return () => clearInterval(interval)
  }, [])

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
          <Alert className="mb-4">
            <CloudOff className="h-4 w-4" />
            <AlertTitle>AnkiWeb Not Connected</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>
                Log in to AnkiWeb to sync your flashcards across devices.
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={openSettings}
                className="flex items-center gap-1"
              >
                <Settings className="h-3 w-3" />
                Open Settings to Login
              </Button>
            </AlertDescription>
          </Alert>
        )

      case 'not_connected':
        return (
          <Alert className="mb-4">
            <CloudOff className="h-4 w-4" />
            <AlertTitle>Anki Not Running</AlertTitle>
            <AlertDescription>
              The Anki service is not running. Flashcards will be queued until it&apos;s available.
            </AlertDescription>
          </Alert>
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
