import { Component, lazy, Suspense, type ErrorInfo, type ReactNode } from 'react';
import {
  createBrowserRouter,
  Navigate,
  Outlet,
  RouterProvider,
  useLocation,
  useRouteError,
  Link,
} from 'react-router';
import { AuthProvider } from './context';
import { useAuth } from './state';
import { Shell } from './Shell';
import { Login } from '../features/auth/Login';
import { Assistant } from '../features/assistant/Assistant';
import { History } from '../features/history/History';
import { Saved } from '../features/saved/Saved';
import { Profile } from '../features/profile/Profile';
import { EmptyState, ErrorNotice, Skeleton } from '../components/ui';
const AdminHome = lazy(() =>
  import('../features/admin/Admin').then((m) => ({ default: m.AdminHome })),
);
const AdminList = lazy(() =>
  import('../features/admin/Admin').then((m) => ({ default: m.AdminList })),
);
const AdminEditor = lazy(() =>
  import('../features/admin/Admin').then((m) => ({ default: m.AdminEditor })),
);
function Protected({ admin = false }: { admin?: boolean }) {
  const auth = useAuth();
  const location = useLocation();
  if (auth.loading)
    return (
      <div className="boot-loading">
        <Skeleton count={2} />
      </div>
    );
  if (auth.error)
    return (
      <div className="boot-loading">
        <ErrorNotice error={auth.error} retry={() => void auth.restore()} />
        <Link to="/login">Go to sign in</Link>
      </div>
    );
  if (!auth.user)
    return <Navigate to="/login" replace state={{ from: location.pathname, expired: true }} />;
  if (admin && auth.user.role !== 'admin') return <Navigate to="/app" replace />;
  return <Outlet />;
}
function RootRedirect() {
  const { user, loading } = useAuth();
  return loading ? (
    <div className="boot-loading">
      <Skeleton />
    </div>
  ) : (
    <Navigate to={!user ? '/login' : user.role === 'admin' ? '/admin' : '/app'} replace />
  );
}
function RouteError() {
  const error = useRouteError();
  return (
    <div className="standard-page">
      <ErrorNotice error={error} />
      <Link className="button secondary" to="/">
        Return home
      </Link>
    </div>
  );
}
const router = createBrowserRouter([
  { path: '/', element: <RootRedirect />, errorElement: <RouteError /> },
  { path: '/login', element: <Login />, errorElement: <RouteError /> },
  {
    element: <Protected />,
    errorElement: <RouteError />,
    children: [
      {
        element: <Shell />,
        children: [
          { path: '/app', element: <Assistant /> },
          { path: '/app/conversations/:id', element: <Assistant /> },
          { path: '/app/history', element: <History /> },
          { path: '/app/saved', element: <Saved /> },
          { path: '/app/profile', element: <Profile /> },
        ],
      },
    ],
  },
  {
    element: <Protected admin />,
    errorElement: <RouteError />,
    children: [
      {
        element: <Shell />,
        children: [
          {
            path: '/admin',
            element: (
              <Suspense fallback={<Skeleton />}>
                <AdminHome />
              </Suspense>
            ),
          },
          {
            path: '/admin/:resource',
            element: (
              <Suspense fallback={<Skeleton />}>
                <AdminList />
              </Suspense>
            ),
          },
          {
            path: '/admin/:resource/new',
            element: (
              <Suspense fallback={<Skeleton />}>
                <AdminEditor />
              </Suspense>
            ),
          },
          {
            path: '/admin/:resource/:id/edit',
            element: (
              <Suspense fallback={<Skeleton />}>
                <AdminEditor />
              </Suspense>
            ),
          },
        ],
      },
    ],
  },
  {
    path: '*',
    element: (
      <EmptyState
        title="This page is off the map"
        action={
          <Link className="button primary" to="/">
            Return home
          </Link>
        }
      >
        The page may have moved. Your campus workspace is still here.
      </EmptyState>
    ),
  },
]);
class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(_error: Error, _info: ErrorInfo) {
    /* Error text stays out of ordinary operational logs. */
  }
  render() {
    return this.state.error ? (
      <div className="boot-loading">
        <h1>Something interrupted your workspace</h1>
        <p>Reload to return to your campus companion.</p>
        <button className="button primary" onClick={() => window.location.reload()}>
          Reload page
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
export function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ErrorBoundary>
  );
}
