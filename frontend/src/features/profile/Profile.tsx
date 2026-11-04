import { useEffect, useState, type FormEvent } from 'react';
import { CheckCircle, GraduationCap, Info } from '@phosphor-icons/react';
import { api } from '../../api';
import { ApiError } from '../../api/errors';
import { useAuth, useWorkspace } from '../../app/state';
import { useData } from '../../app/hooks';
import type { Profile as ProfileType } from '../../api/schemas';
import {
  ErrorNotice,
  FieldError,
  Notice,
  PageHeading,
  Skeleton,
  useUnsavedChanges,
} from '../../components/ui';

export function Profile() {
  const { user } = useAuth();
  const { references, refresh } = useWorkspace();
  const result = useData((signal) => api.profile(signal));
  const [form, setForm] = useState<ProfileType | null>(null);
  const [original, setOriginal] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [success, setSuccess] = useState(false);
  useEffect(() => {
    if (result.data) {
      setForm(result.data);
      setOriginal(JSON.stringify(result.data));
    }
  }, [result.data]);
  const dirty = !!form && JSON.stringify(form) !== original;
  const guard = useUnsavedChanges(dirty);
  const fieldErrors = error instanceof ApiError ? error.fieldErrors : {};
  const update = <K extends keyof ProfileType>(key: K, value: ProfileType[K]) => {
    setForm((f) => f && { ...f, [key]: value });
    setSuccess(false);
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await api.updateProfile({ ...form, section: form.section?.trim() || null });
      setForm(saved);
      setOriginal(JSON.stringify(saved));
      setSuccess(true);
      refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="standard-page profile-page">
      <PageHeading
        title="A little about you"
        description="Better campus answers start with a little context."
      />
      {result.loading && !form ? (
        <Skeleton />
      ) : result.error ? (
        <ErrorNotice error={result.error} retry={result.reload} />
      ) : (
        form && (
          <div className="profile-layout">
            <form className="form-panel" onSubmit={submit}>
              <div className="profile-identity">
                <span className="avatar avatar-large">
                  {user!.name
                    .split(' ')
                    .map((s) => s[0])
                    .slice(0, 2)
                    .join('')}
                </span>
                <div>
                  <h2>{user!.name}</h2>
                  <p>{user!.email}</p>
                </div>
                <span className="badge">{user!.role}</span>
              </div>
              <div className="form-section">
                <h2>Academic details</h2>
                <p>These help check event eligibility. Unknown fields stay unknown.</p>
                <div className="form-grid">
                  <div className="field">
                    <label htmlFor="department">Department</label>
                    <select
                      id="department"
                      aria-invalid={!!fieldErrors.department_id?.length}
                      aria-describedby={
                        fieldErrors.department_id?.length ? 'department-error' : undefined
                      }
                      value={form.department_id || ''}
                      disabled={busy || !references}
                      onChange={(e) => update('department_id', e.target.value || null)}
                    >
                      <option value="">Not specified</option>
                      {references?.departments.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.label}
                        </option>
                      ))}
                    </select>
                    <FieldError id="department-error" message={fieldErrors.department_id?.[0]} />
                  </div>
                  <div className="field">
                    <label htmlFor="year">Year of study</label>
                    <select
                      id="year"
                      aria-invalid={!!fieldErrors.year?.length}
                      aria-describedby={fieldErrors.year?.length ? 'year-error' : undefined}
                      value={form.year || ''}
                      disabled={busy || !references}
                      onChange={(e) =>
                        update('year', e.target.value ? Number(e.target.value) : null)
                      }
                    >
                      <option value="">Not specified</option>
                      {references?.supported_years.map((y) => (
                        <option key={y} value={y}>
                          Year {y}
                        </option>
                      ))}
                    </select>
                    <FieldError id="year-error" message={fieldErrors.year?.[0]} />
                  </div>
                  <div className="field">
                    <label htmlFor="section">
                      Section <span className="optional">Optional</span>
                    </label>
                    <input
                      id="section"
                      aria-invalid={!!fieldErrors.section?.length}
                      aria-describedby={fieldErrors.section?.length ? 'section-error' : undefined}
                      maxLength={20}
                      value={form.section || ''}
                      onChange={(e) => update('section', e.target.value || null)}
                      disabled={busy}
                      placeholder="For example, B"
                    />
                    <FieldError id="section-error" message={fieldErrors.section?.[0]} />
                  </div>
                </div>
              </div>
              <div className="form-section">
                <h2>What interests you?</h2>
                <p>Interests help order events. They don’t change who can attend.</p>
                <div className="interest-options">
                  {references?.topics.map((t) => (
                    <label
                      className={`interest-option ${form.interests.includes(t.id) ? 'selected' : ''}`}
                      key={t.id}
                    >
                      <input
                        type="checkbox"
                        checked={form.interests.includes(t.id)}
                        disabled={busy}
                        onChange={(e) =>
                          update(
                            'interests',
                            e.target.checked
                              ? [...form.interests, t.id]
                              : form.interests.filter((i) => i !== t.id),
                          )
                        }
                      />
                      <span>{t.label}</span>
                      {form.interests.includes(t.id) && <CheckCircle size={16} weight="fill" />}
                    </label>
                  ))}
                </div>
              </div>
              {!!error && <ErrorNotice error={error} />}
              {success && (
                <Notice tone="success">
                  Profile updated. New questions will use this context.
                </Notice>
              )}
              <div className="form-actions">
                <span>{dirty ? 'You have unsaved changes' : 'Your profile is up to date'}</span>
                <button
                  className="button primary"
                  type="submit"
                  disabled={busy || !dirty || !references}
                >
                  {busy ? 'Saving…' : 'Save profile'}
                </button>
              </div>
            </form>
            <aside className="profile-aside">
              <span className="aside-icon">
                <GraduationCap size={28} />
              </span>
              <h2>A starting point, always in your control.</h2>
              <p>
                Your question takes priority over your profile. You can ask for another year or
                department without changing these details.
              </p>
              <div className="aside-rule">
                <Info size={19} />
                <p>Effective filters and their sources appear with each answer.</p>
              </div>
              <p>Your conversations and saved items belong to your account.</p>
            </aside>
          </div>
        )
      )}
      {guard.dialog}
    </div>
  );
}
