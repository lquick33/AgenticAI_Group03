/**
 * API Client Functions for Course Materials
 * 
 * Handles communication with the backend API for:
 * - Material updates (filename, etc.)
 * - Material deletion
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Update course material filename
 */
export async function updateMaterialFilename(
  materialId: string,
  filename: string,
  userId: string
): Promise<void> {
  const url = `${API_URL}/api/materials/${encodeURIComponent(materialId)}?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      file_name: filename,
    }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }
}

/**
 * Delete a course material
 */
export async function deleteMaterial(
  materialId: string,
  userId: string
): Promise<void> {
  const url = `${API_URL}/api/materials/${encodeURIComponent(materialId)}?user_id=${encodeURIComponent(userId)}`
  
  const response = await fetch(url, {
    method: 'DELETE',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }
}
