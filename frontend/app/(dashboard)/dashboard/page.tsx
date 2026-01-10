import { requireAuth } from '@/lib/auth'
import { createClient } from '@/lib/supabase/server'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { UploadDialog } from '@/components/dashboard/upload-dialog'
import { Plus, BookOpen } from 'lucide-react'
import type { Course } from '@/types'

export default async function DashboardPage() {
  const session = await requireAuth()
  const supabase = await createClient()

  // Get user
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser()

  if (userError || !user) {
    return (
      <div className="container mx-auto p-6">
        <p className="text-red-600">Error loading user data</p>
      </div>
    )
  }

  // Fetch courses
  const { data: courses, error: coursesError } = await supabase
    .from('courses')
    .select('*')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })

  if (coursesError) {
    console.error('Error fetching courses:', coursesError)
  }

  const coursesList: Course[] = courses || []

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-slate-600 mt-2">
            Welcome back, {user.email}
          </p>
        </div>
        <UploadDialog courses={coursesList} />
      </div>

      {coursesList.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-slate-400 mb-4" />
            <h3 className="text-lg font-semibold mb-2">No courses yet</h3>
            <p className="text-slate-600 text-center mb-4">
              Get started by creating your first course and uploading lecture materials.
            </p>
            <UploadDialog courses={coursesList} />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {coursesList.map((course) => (
            <Card key={course.id} className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5" />
                  {course.title}
                </CardTitle>
                <CardDescription>
                  {course.description || 'No description'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {course.exam_date && (
                    <p className="text-sm text-slate-600">
                      Exam: {new Date(course.exam_date).toLocaleDateString()}
                    </p>
                  )}
                  <p className="text-xs text-slate-500">
                    Created: {new Date(course.created_at).toLocaleDateString()}
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
