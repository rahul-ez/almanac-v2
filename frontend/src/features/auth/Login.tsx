import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router';
import {
  ArrowRight,
  Eye,
  EyeSlash,
  GraduationCap,
  Buildings,
  CalendarBlank,
  MapPin,
} from '@phosphor-icons/react';
import { apiMode } from '../../api';
import { DEMO_PASSWORD } from '../../api/seed';
import { useAuth } from '../../app/state';
import { ErrorNotice, Notice, Skeleton } from '../../components/ui';

export function Login() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (auth.loading)
    return (
      <div className="boot-loading">
        <Skeleton count={2} />
      </div>
    );
  if (auth.user) return <Navigate to={auth.user.role === 'admin' ? '/admin' : '/app'} replace />;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await auth.login(email, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(
        from?.startsWith(u.role === 'admin' ? '/admin' : '/app')
          ? from
          : u.role === 'admin'
            ? '/admin'
            : '/app',
        { replace: true },
      );
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login-page">
      <section className="login-form-panel">
        <a className="brand login-brand" href="/login">
          <span className="brand-mark">
            <GraduationCap size={26} weight="duotone" />
          </span>
          <span>
            campus<span className="brand-second">companion</span>
          </span>
        </a>
        <div className="login-form-wrap">
          <span className="welcome-tag">A little less searching</span>
          <h1>
            Your campus.
            <br />
            All in one place.
          </h1>
          <p className="login-intro">
            Good things are happening around you.
            <br />
            Let’s help you find them.
          </p>
          {!!auth.error && <ErrorNotice error={auth.error} retry={() => void auth.restore()} />}
          {(location.state as { expired?: boolean } | null)?.expired && (
            <Notice tone="warning">
              Your session expired. Sign in to continue. Your unsent question is kept on this
              device.
            </Notice>
          )}
          <form onSubmit={submit}>
            <label htmlFor="email">Campus email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              placeholder="you@college.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={busy}
            />
            <label htmlFor="password">Password</label>
            <div className="password-input">
              <input
                id="password"
                name="password"
                type={visible ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="Your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={busy}
              />
              <button
                type="button"
                className="icon-button"
                aria-label={visible ? 'Hide password' : 'Show password'}
                onClick={() => setVisible((v) => !v)}
              >
                {visible ? <EyeSlash size={19} /> : <Eye size={19} />}
              </button>
            </div>
            {!!error && <ErrorNotice error={error} />}
            <button className="button primary login-submit" type="submit" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
              <ArrowRight size={18} />
            </button>
          </form>
          {apiMode === 'mock' && (
            <div className="demo-login">
              <strong>Explore the demo</strong>
              <p>Fictional campus records, saved in this browser.</p>
              <div className="demo-buttons">
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => {
                    setEmail('student@campus.demo');
                    setPassword(DEMO_PASSWORD);
                  }}
                >
                  <GraduationCap size={18} /> Use student demo
                </button>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => {
                    setEmail('admin@campus.demo');
                    setPassword(DEMO_PASSWORD);
                  }}
                >
                  <Buildings size={18} /> Use admin demo
                </button>
              </div>
              <small>Demo password: {DEMO_PASSWORD}</small>
            </div>
          )}
          <p className="login-help">Accounts are provided by your campus administrator.</p>
        </div>
        <span className="login-bottom">A clearer way to navigate campus life.</span>
      </section>
      <aside className="login-story">
        <div className="story-lines" aria-hidden="true" />
        <div className="story-title">
          Find your next
          <br />
          “glad I went.”
        </div>
        <div className="story-card">
          <span className="story-card-label">
            <CalendarBlank size={18} /> This Friday
          </span>
          <div className="story-card-art" aria-hidden="true">
            <span>
              ideas
              <br />
              into
              <br />
              anything.
            </span>
          </div>
          <h2>Build something with AI</h2>
          <p>
            <MapPin size={16} /> Innovation Lab, B Block
          </p>
          <div className="story-card-foot">
            <span>Free workshop</span>
            <span>2:00 PM</span>
          </div>
        </div>
        <div className="story-note">
          An event worth your time.
          <br />A room for your next idea.
          <br />A conversation that helps.
        </div>
        <span className="story-demo">Illustration with fictional demo event</span>
      </aside>
    </div>
  );
}
