import { requireAuth } from '@/lib/auth'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default async function DashboardPage() {
  const session = await requireAuth()

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-slate-600 mt-2">Welcome back to Lernkompanien</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Welcome</CardTitle>
            <CardDescription>Your learning journey starts here</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600">
              Logged in as: <strong>{session.user.email}</strong>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Your Courses</CardTitle>
            <CardDescription>Manage your courses and materials</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600">
              Course management coming soon...
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Study Sessions</CardTitle>
            <CardDescription>Track your learning progress</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600">
              Study session tracking coming soon...
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
