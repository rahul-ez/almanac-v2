import { useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router';
import {
  BookmarkSimple,
  ChatCircleText,
  ClockCounterClockwise,
  GraduationCap,
  SignOut,
  UserCircle,
  List,
  ArrowUpRight,
  CalendarBlank,
  DoorOpen,
  ChalkboardTeacher,
  Tag,
  Clock,
} from '@phosphor-icons/react';
import { apiMode } from '../api';
import { WorkspaceProvider } from './context';
import { useAuth, useWorkspace } from './state';
import { Dialog, ErrorNotice } from '../components/ui';

const adminLinks = [
  ['events', 'Events', CalendarBlank],
  ['rooms', 'Rooms', DoorOpen],
  ['bookings', 'Bookings', CalendarBlank],
  ['booking-exceptions', 'Booking exceptions', Clock],
  ['room-closures', 'Room closures', DoorOpen],
  ['faculty', 'Faculty', ChalkboardTeacher],
  ['office-hours', 'Office hours', Clock],
  ['office-hour-exceptions', 'Office-hour exceptions', Clock],
  ['aliases', 'Aliases', Tag],
] as const;
export function Shell() {
  const { user } = useAuth();
  return (
    <WorkspaceProvider key={user!.id}>
      <ShellContent />
    </WorkspaceProvider>
  );
}
function ShellContent() {
  const { user, logout } = useAuth();
  const { references, referenceError, reloadReferences } = useWorkspace();
  const location = useLocation();
  const navigate = useNavigate();
  const [navOpen, setNavOpen] = useState(false);
  const [logoutError, setLogoutError] = useState<unknown>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const admin = location.pathname.startsWith('/admin');
  const close = () => setNavOpen(false);
  const links = (
    <>
      <NavLink to={admin ? '/admin' : '/app'} end className="nav-item" onClick={close}>
        <ChatCircleText size={21} />
        {admin ? 'Overview' : 'Ask companion'}
      </NavLink>
      {admin ? (
        adminLinks.map(([path, label, Icon]) => (
          <NavLink className="nav-item" key={path} to={'/admin/' + path} onClick={close}>
            <Icon size={20} />
            {label}
          </NavLink>
        ))
      ) : (
        <>
          <NavLink to="/app/history" className="nav-item" onClick={close}>
            <ClockCounterClockwise size={21} />
            Conversations
          </NavLink>
          <NavLink to="/app/saved" className="nav-item" onClick={close}>
            <BookmarkSimple size={21} />
            Saved items
          </NavLink>
          <NavLink to="/app/profile" className="nav-item" onClick={close}>
            <UserCircle size={21} />
            My profile
          </NavLink>
        </>
      )}
    </>
  );
  const navContent = (
    <>
      <NavLink to={admin ? '/admin' : '/app'} className="brand" onClick={close}>
        <span className="brand-mark">
          <GraduationCap size={25} weight="duotone" />
        </span>
        <span>
          campus<span className="brand-second">companion</span>
        </span>
      </NavLink>
      <div className="campus-name">
        <span className="campus-dot" />
        {apiMode === 'mock' ? 'Northfield Institute' : 'Campus workspace'}
        <small>{apiMode === 'mock' ? 'Fictional demo campus' : 'Published campus records'}</small>
      </div>
      <nav aria-label={admin ? 'Administration' : 'Main navigation'}>{links}</nav>
      <div className="sidebar-bottom">
        {user!.role === 'admin' && (
          <NavLink className="workspace-switch" to={admin ? '/app' : '/admin'} onClick={close}>
            {admin ? 'View student workspace' : 'Open administration'}
            <ArrowUpRight size={17} />
          </NavLink>
        )}
        <div className="sidebar-note">
          <span className="small-orbit" aria-hidden="true">
            <GraduationCap size={21} />
          </span>
          <strong>Your campus, closer.</strong>
          <p>
            Events, spaces, and people.
            <br />A good place to start.
          </p>
        </div>
        <div className="user-row">
          <span className="avatar">
            {user!.name
              .split(' ')
              .map((s) => s[0])
              .slice(0, 2)
              .join('')}
          </span>
          <div>
            <strong>{user!.name}</strong>
            <small>{user!.role === 'admin' ? 'Campus administrator' : 'Student workspace'}</small>
          </div>
          <button
            className="icon-button"
            disabled={loggingOut}
            aria-label="Sign out"
            onClick={async () => {
              setLoggingOut(true);
              try {
                await logout();
                navigate('/login');
              } catch (e) {
                setLogoutError(e);
              } finally {
                setLoggingOut(false);
              }
            }}
          >
            <SignOut size={20} />
          </button>
        </div>
        {!!logoutError && <ErrorNotice error={logoutError} />}
      </div>
    </>
  );
  const section = admin
    ? 'Campus administration'
    : location.pathname.includes('profile')
      ? 'My profile'
      : location.pathname.includes('saved')
        ? 'Saved items'
        : location.pathname.includes('history')
          ? 'Conversations'
          : 'Your campus companion';
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">{navContent}</aside>
      <Dialog open={navOpen} onClose={close} title="Navigation" className="mobile-nav">
        {navContent}
      </Dialog>
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              onClick={() => setNavOpen(true)}
              aria-label="Open navigation"
            >
              <List size={23} />
            </button>
            <span>{section}</span>
          </div>
          <div className="topbar-right">
            <span className={`mode-badge ${apiMode}`}>
              {apiMode === 'mock' ? 'Demo mode' : 'Live campus data'}
            </span>
            <span className="zone-label">{references?.campus_timezone || 'Campus local time'}</span>
            <NavLink to="/app/profile" aria-label="Open profile" className="avatar avatar-small">
              {user!.name
                .split(' ')
                .map((s) => s[0])
                .slice(0, 2)
                .join('')}
            </NavLink>
          </div>
        </header>
        {apiMode === 'mock' && (
          <div className="demo-strip">
            Demo data · Campus clock fixed at 4 Nov 2026, 10:00 AM IST. Changes stay in this
            browser.
          </div>
        )}
        <main id="main-content" tabIndex={-1}>
          {!!referenceError && <ErrorNotice error={referenceError} retry={reloadReferences} />}
          <Outlet />
        </main>
        <footer className="workspace-footer">
          <span>Campus Companion</span>
          <span>Answers grounded in campus records.</span>
        </footer>
      </div>
    </div>
  );
}
