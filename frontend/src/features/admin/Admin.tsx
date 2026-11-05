import { useEffect, useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router';
import {
  ArrowUpRight,
  CalendarBlank,
  ChalkboardTeacher,
  DoorOpen,
  MagnifyingGlass,
  PencilSimple,
  Plus,
  Trash,
  ArrowLeft,
} from '@phosphor-icons/react';
import { api } from '../../api';
import { ApiError } from '../../api/errors';
import {
  resourceNames,
  resourceSchemas,
  type DomainRecord,
  type ReferenceData,
  type Resource,
} from '../../api/schemas';
import { useWorkspace } from '../../app/state';
import { useData, usePages } from '../../app/hooks';
import {
  ConfirmDialog,
  EmptyState,
  ErrorNotice,
  FieldError,
  Notice,
  PageHeading,
  Pagination,
  Skeleton,
  useUnsavedChanges,
} from '../../components/ui';
import { dateLabel, inputInstant, localInput, safeSource } from '../../components/format';
import { adminConfig, commonFields, newRecord, recordTitle, type Field } from './config';

export function AdminHome() {
  return (
    <div className="standard-page admin-home">
      <PageHeading
        title="A campus that stays in the know"
        description="Maintain the records that make every answer dependable."
      />
      <div className="admin-intro">
        <div>
          <span className="aside-icon">
            <CalendarBlank size={26} />
          </span>
          <h2>Good answers start here.</h2>
          <p>
            Publish an event, keep a timetable current, or update a faculty member’s office hours.
            Students find what you maintain through their companion.
          </p>
          <Link className="button primary" to="/admin/events/new">
            <Plus size={18} /> Create an event
          </Link>
        </div>
        <div className="admin-principles">
          <p>
            <strong>Keep the source visible</strong>
            <span>Give every record a source label and update it when details change.</span>
          </p>
          <p>
            <strong>Unknown means unknown</strong>
            <span>
              Missing schedules and eligibility rules should never imply availability or access.
            </span>
          </p>
          <p>
            <strong>Changes reach new answers</strong>
            <span>
              Saved records show current details. Conversation snapshots keep their original
              answers.
            </span>
          </p>
        </div>
      </div>
      <div className="section-heading">
        <h2>Manage campus records</h2>
      </div>
      <div className="admin-resource-grid">
        {resourceNames.map((r) => (
          <Link className="admin-resource" to={'/admin/' + r} key={r}>
            <span>
              {r === 'events' ? (
                <CalendarBlank size={23} />
              ) : r.includes('faculty') || r.includes('office') ? (
                <ChalkboardTeacher size={23} />
              ) : (
                <DoorOpen size={23} />
              )}
            </span>
            <h3>{adminConfig[r].title}</h3>
            <p>{adminConfig[r].description}</p>
            <ArrowUpRight size={19} />
          </Link>
        ))}
      </div>
    </div>
  );
}
export function AdminList() {
  const { resource: raw } = useParams();
  const location = useLocation();
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const resource = raw as Resource;
  const config = adminConfig[resource];
  useEffect(() => {
    const t = setTimeout(() => setQuery(search), 250);
    return () => clearTimeout(t);
  }, [search]);
  const pages = usePages(
    (cursor, signal) =>
      config
        ? api.adminList(resource, query, cursor, signal)
        : Promise.resolve({ items: [], next_cursor: null }),
    [resource, query],
  );
  const [archive, setArchive] = useState<DomainRecord | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const { references, refresh } = useWorkspace();
  useEffect(() => {
    setSearch('');
    setQuery('');
    setArchive(null);
  }, [resource]);
  if (!config) return <Navigate to="/admin" replace />;
  const remove = async () => {
    if (!archive) return;
    setBusy(true);
    setError(null);
    try {
      await api.adminArchive(resource, archive.id, archive.version);
      setArchive(null);
      refresh();
      pages.reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="standard-page">
      <PageHeading
        title={config.title}
        description={config.description}
        action={
          <Link className="button primary" to={`/admin/${resource}/new`}>
            <Plus size={18} /> Add {config.singular}
          </Link>
        }
      />
      {(location.state as { saved?: boolean } | null)?.saved && (
        <Notice tone="success">
          Record saved. New student answers will use the updated details.
        </Notice>
      )}
      <div className="admin-toolbar">
        <div className="search-input">
          <MagnifyingGlass size={20} />
          <label className="sr-only" htmlFor="admin-search">
            Search {config.title.toLowerCase()}
          </label>
          <input
            id="admin-search"
            placeholder={`Search ${config.title.toLowerCase()}…`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span>Campus time: {references?.campus_timezone || 'Loading…'}</span>
      </div>
      {pages.loading && !pages.items.length ? (
        <Skeleton />
      ) : pages.items.length ? (
        <div className="table-scroll">
          <table className="admin-table">
            <thead>
              <tr>
                <th scope="col">Record</th>
                <th scope="col">Status</th>
                <th scope="col">Updated</th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {pages.items.map((record) => (
                <tr key={record.id}>
                  <td>
                    <Link to={`/admin/${resource}/${record.id}/edit`}>
                      {recordTitle(record as unknown as Record<string, unknown>)}
                    </Link>
                    <small>
                      {record.source_label} · v{record.version}
                    </small>
                  </td>
                  <td>
                    <span className={`badge ${record.status}`}>{record.status}</span>
                  </td>
                  <td>{dateLabel(record.updated_at, references?.campus_timezone)}</td>
                  <td>
                    <div className="table-actions">
                      <Link
                        className="icon-button"
                        to={`/admin/${resource}/${record.id}/edit`}
                        aria-label={`Edit ${recordTitle(record as unknown as Record<string, unknown>)}`}
                      >
                        <PencilSimple size={19} />
                      </Link>
                      <button
                        className="icon-button delete-button"
                        disabled={record.status === 'archived'}
                        aria-label={`Archive ${recordTitle(record as unknown as Record<string, unknown>)}`}
                        onClick={() => {
                          setArchive(record);
                          setError(null);
                        }}
                      >
                        <Trash size={19} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !pages.error && (
          <EmptyState
            title={query ? 'No records match your search' : `Add your first ${config.singular}`}
            icon={<CalendarBlank size={27} />}
          >
            {query
              ? 'Try another word or clear the search.'
              : 'Published campus records make the student companion useful.'}
          </EmptyState>
        )
      )}
      {!!pages.error && <ErrorNotice error={pages.error} retry={pages.reload} />}
      <Pagination next={pages.next} busy={pages.loading} onNext={pages.loadMore} />
      <ConfirmDialog
        open={!!archive}
        title={`Archive this ${config.singular}?`}
        onClose={() => setArchive(null)}
        onConfirm={() => void remove()}
        label="Archive record"
        busy={busy}
        error={error}
      >
        Students will see that this record is archived in saved items. New queries will use its
        updated status. Previous answers remain historical snapshots.
      </ConfirmDialog>
    </div>
  );
}
type Lookup = Record<string, { id: string; label: string }[]>;
async function loadLookups(signal: AbortSignal): Promise<Lookup> {
  const resources: Resource[] = ['rooms', 'faculty', 'bookings', 'office-hours'];
  const result = await Promise.all(
    resources.map(async (r) => {
      const rows: DomainRecord[] = [];
      let cursor: string | null = null;
      do {
        const p = await api.adminList(r, '', cursor, signal);
        rows.push(...p.items);
        cursor = p.next_cursor;
      } while (cursor);
      return [
        r,
        rows
          .filter((r) => r.status !== 'archived')
          .map((x) => ({ id: x.id, label: recordTitle(x as unknown as Record<string, unknown>) })),
      ] as const;
    }),
  );
  return Object.fromEntries(result);
}
export function AdminEditor() {
  const { resource, id } = useParams();
  return <AdminEditorForm key={`${resource}:${id || 'new'}`} />;
}
function AdminEditorForm() {
  const { resource: raw, id } = useParams();
  const resource = raw as Resource;
  const config = adminConfig[resource];
  const { references, refresh } = useWorkspace();
  const navigate = useNavigate();
  const result = useData(
    (signal) => (id && config ? api.adminGet(resource, id, signal) : Promise.resolve(null)),
    [resource, id],
  );
  const lookups = useData(loadLookups, [resource]);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [original, setOriginal] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [fields, setFields] = useState<Record<string, string[]>>({});
  const [confirm, setConfirm] = useState(false);
  useEffect(() => {
    if (!config || !references || (id && !result.data)) return;
    const data = id
      ? (result.data as unknown as Record<string, unknown>)
      : newRecord(resource, references.campus_timezone);
    setForm({ ...data });
    setOriginal(JSON.stringify(data));
    setError(null);
    setFields({});
  }, [resource, id, result.data, references]);
  const guard = useUnsavedChanges(!!original && original !== JSON.stringify(form));
  if (!config) return <Navigate to="/admin" replace />;
  const update = (key: string, value: unknown) => {
    setForm((f) => ({
      ...f,
      [key]: value,
      ...(key === 'entity_type' ? { canonical_id: '' } : {}),
    }));
    setFields((e) => ({ ...e, [key]: [] }));
  };
  const allFields: Field[] = [
    ...config.fields,
    ...commonFields,
    {
      key: 'status',
      label: 'Publication status',
      type: 'select',
      options:
        resource === 'events'
          ? ['draft', 'published', 'cancelled', 'archived']
          : ['active', 'cancelled', 'archived'],
    },
  ];
  async function save() {
    setConfirm(false);
    setError(null);
    const errors: Record<string, string[]> = {};
    for (const field of allFields) {
      const value = form[field.key];
      if (field.required && (value === null || value === undefined || value === ''))
        errors[field.key] = ['This field is required.'];
    }
    const payload = {
      ...form,
      ...(Array.isArray(form.aliases)
        ? {
            aliases: form.aliases
              .map(String)
              .map((name) => name.trim())
              .filter(Boolean),
          }
        : {}),
    };
    const candidate = {
      ...payload,
      id: id || 'new-record',
      version: Number(form.version || 1),
      updated_at: new Date().toISOString(),
    };
    const parsed = resourceSchemas[resource].safeParse(candidate);
    if (!parsed.success)
      for (const issue of parsed.error.issues)
        (errors[String(issue.path[0])] ||= []).push(issue.message);
    if (form.source_url && !safeSource(String(form.source_url)))
      errors.source_url = ['Use a complete http or https URL.'];
    for (const [start, end] of [
      ['starts_at', 'ends_at'],
      ['replacement_start', 'replacement_end'],
      ['coverage_start', 'coverage_end'],
    ] as const)
      if (
        form[start] &&
        form[end] &&
        new Date(String(form[end])).getTime() <= new Date(String(form[start])).getTime()
      )
        errors[end] = ['End must be after start.'];
    if (form.action === 'replace' && (!form.replacement_start || !form.replacement_end))
      errors.replacement_end = ['A replacement needs both a start and an end.'];
    if (form.recurrence === 'weekly' && !form.recurrence_until)
      errors.recurrence_until = ['Set a bounded recurrence end date.'];
    if (form.start_time && form.end_time && String(form.end_time) <= String(form.start_time))
      errors.end_time = ['End time must be after start time.'];
    if (
      form.effective_from &&
      form.effective_until &&
      String(form.effective_until) < String(form.effective_from)
    )
      errors.effective_until = ['End date must be on or after start.'];
    if (resource === 'rooms') {
      const hours = form.opening_hours as { weekday: number; start: string; end: string }[];
      if (hours?.some((h) => h.end <= h.start))
        errors.opening_hours = ['Every opening interval must end after it starts.'];
      if (form.coverage_complete && (!form.coverage_start || !form.coverage_end))
        errors.coverage_complete = ['Complete coverage needs a start and an end.'];
    }
    if (Object.keys(errors).length) {
      setFields(errors);
      setError(new Error('Check the highlighted fields before saving.'));
      requestAnimationFrame(() =>
        document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(),
      );
      return;
    }
    setBusy(true);
    try {
      await api.adminSave(resource, payload, id);
      guard.allow.current = true;
      refresh();
      navigate('/admin/' + resource, { state: { saved: true } });
    } catch (e) {
      setError(e);
      if (e instanceof ApiError) setFields(e.fieldErrors);
    } finally {
      setBusy(false);
    }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    if (
      ['cancelled', 'archived'].includes(String(form.status)) &&
      (!id || form.status !== result.data?.status)
    )
      setConfirm(true);
    else void save();
  }
  const stale = error instanceof ApiError && error.code === 'stale_version';
  return (
    <div className="standard-page editor-page">
      <Link className="back-link" to={'/admin/' + resource}>
        <ArrowLeft size={16} />
        {config.title}
      </Link>
      <PageHeading
        title={`${id ? 'Edit' : 'Add'} ${config.singular}`}
        description={`Dates and times use ${references?.campus_timezone || 'campus time'}.`}
      />
      {(id && result.loading && !result.data) || !original ? (
        result.error ? (
          <ErrorNotice error={result.error} retry={result.reload} />
        ) : (
          <Skeleton />
        )
      ) : (
        <form className="form-panel admin-form" onSubmit={submit}>
          <div className="form-section">
            <h2>Record details</h2>
            <div className="form-grid">
              {config.fields.map((field) => (
                <AdminField
                  key={field.key}
                  field={field}
                  form={form}
                  references={references!}
                  lookups={lookups.data || {}}
                  disabled={busy}
                  errors={fields[field.key]}
                  onChange={(value) => update(field.key, value)}
                />
              ))}
            </div>
            {form.recurrence === 'weekly' && (
              <Notice>
                Repeats weekly on the first booking’s weekday through{' '}
                {String(form.recurrence_until || 'the end date you choose')}. Dated exceptions are
                maintained separately.
              </Notice>
            )}
            {resource === 'office-hours' && (
              <Notice>
                This weekly rule applies from {String(form.effective_from || 'the start date')}{' '}
                through {String(form.effective_until || 'the end date')}. Dated exceptions override
                the rule.
              </Notice>
            )}
            {!!lookups.error && <ErrorNotice error={lookups.error} retry={lookups.reload} />}
          </div>
          <div className="form-section">
            <h2>Source & publication</h2>
            <div className="form-grid">
              {allFields.slice(config.fields.length).map((field) => (
                <AdminField
                  key={field.key}
                  field={field}
                  form={form}
                  references={references!}
                  lookups={lookups.data || {}}
                  disabled={busy}
                  errors={fields[field.key]}
                  onChange={(value) => update(field.key, value)}
                />
              ))}
            </div>
          </div>
          {resource === 'room-closures' && (
            <Notice tone="warning">
              A closure can overlap existing bookings. It takes priority when calculating scheduled
              availability.
            </Notice>
          )}
          {!!error && <ErrorNotice error={error} />}
          {stale && (
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                result.reload();
                setError(null);
              }}
            >
              Reload latest record
            </button>
          )}
          <div className="form-actions">
            <span>{id ? `Editing version ${form.version}` : 'New campus record'}</span>
            <Link className="button secondary" to={'/admin/' + resource}>
              Cancel
            </Link>
            <button
              className="button primary"
              type="submit"
              disabled={busy || !!lookups.error || stale || lookups.loading}
            >
              {busy ? 'Saving…' : id ? 'Save changes' : 'Create record'}
            </button>
          </div>
        </form>
      )}
      <ConfirmDialog
        open={confirm}
        title={`${form.status === 'archived' ? 'Archive' : 'Cancel'} this record?`}
        onClose={() => setConfirm(false)}
        onConfirm={() => void save()}
        label="Confirm status change"
      >
        Saved items and future answers will show this status. Existing conversation snapshots keep
        their original details.
      </ConfirmDialog>
      {guard.dialog}
    </div>
  );
}
function AdminField({
  field,
  form,
  references,
  lookups,
  disabled,
  errors,
  onChange,
}: {
  field: Field;
  form: Record<string, unknown>;
  references: ReferenceData;
  lookups: Lookup;
  disabled: boolean;
  errors?: string[];
  onChange: (value: unknown) => void;
}) {
  const value = form[field.key];
  const fieldId = 'field-' + field.key;
  const attrs = {
    id: fieldId,
    disabled,
    'aria-invalid': !!errors?.length,
    'aria-describedby': errors?.length
      ? fieldId + '-error'
      : field.hint
        ? fieldId + '-hint'
        : undefined,
  };
  let source: string = field.source || '';
  if (source === 'canonical')
    source = (
      {
        department: 'departments',
        building: 'buildings',
        topic: 'topics',
        room: 'rooms',
        faculty: 'faculty',
      } as Record<string, string>
    )[String(form.entity_type)];
  const options =
    source === 'years'
      ? references.supported_years.map((y) => ({ id: String(y), label: 'Year ' + y }))
      : field.source
        ? (references as unknown as Lookup)[source] || lookups[source] || []
        : (field.options || []).map((v, i) => ({
            id: field.key === 'weekday' ? String(i) : v,
            label: v.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase()),
          }));
  return (
    <div
      className={`field ${['textarea', 'multi', 'opening', 'boolean'].includes(field.type) ? 'field-wide' : ''}`}
    >
      <label htmlFor={fieldId}>
        {field.label}
        {field.required && <span className="required"> *</span>}
      </label>
      {field.type === 'textarea' ? (
        <textarea
          {...attrs}
          value={String(value || '')}
          onChange={(e) => onChange(e.target.value)}
          maxLength={4000}
          rows={3}
          required={field.required}
        />
      ) : field.type === 'select' ? (
        <select
          {...attrs}
          value={String(value ?? '')}
          onChange={(e) =>
            onChange(field.key === 'weekday' ? Number(e.target.value) : e.target.value)
          }
          required={field.required}
        >
          <option value="" disabled>
            Choose {field.label.toLowerCase()}
          </option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
      ) : field.type === 'multi' ? (
        <div className="checkbox-group" id={fieldId} role="group" aria-label={field.label}>
          {options.map((o) => (
            <label key={o.id}>
              <input
                type="checkbox"
                disabled={disabled}
                checked={((value || []) as (string | number)[]).map(String).includes(o.id)}
                onChange={(e) => {
                  const v = field.source === 'years' ? Number(o.id) : o.id;
                  const values = (value || []) as (string | number)[];
                  onChange(e.target.checked ? [...values, v] : values.filter((x) => x !== v));
                }}
              />
              {o.label}
            </label>
          ))}
        </div>
      ) : field.type === 'boolean' ? (
        <label className="checkbox-label">
          <input
            {...attrs}
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
          />
          Yes, confirmed from maintained records
        </label>
      ) : field.type === 'opening' ? (
        <OpeningHours
          value={(value as { weekday: number; start: string; end: string }[]) || []}
          onChange={onChange}
          disabled={disabled}
        />
      ) : field.type === 'datetime' ? (
        <input
          {...attrs}
          type="datetime-local"
          required={field.required}
          value={value ? localInput(String(value), references.campus_timezone) : ''}
          onChange={(e) => onChange(inputInstant(e.target.value, references.campus_timezone))}
        />
      ) : (
        <input
          {...attrs}
          type={
            field.type === 'number'
              ? 'number'
              : field.type === 'date'
                ? 'date'
                : field.type === 'time'
                  ? 'time'
                  : field.type === 'email'
                    ? 'email'
                    : 'text'
          }
          min={field.min}
          max={field.max && field.type === 'number' ? field.max : undefined}
          maxLength={
            field.max && field.type !== 'number'
              ? field.max
              : field.type === 'text'
                ? 300
                : undefined
          }
          step={field.type === 'number' ? 1 : undefined}
          required={field.required}
          value={
            field.type === 'list'
              ? ((value as string[]) || []).join(', ')
              : value === null || value === undefined
                ? ''
                : String(value)
          }
          onChange={(e) => {
            const s = e.target.value;
            onChange(
              field.type === 'number'
                ? s === ''
                  ? field.nullable
                    ? null
                    : ''
                  : Number(s)
                : field.type === 'list'
                  ? s.split(',').map((s) => s.trim())
                  : field.nullable && !s
                    ? null
                    : s,
            );
          }}
        />
      )}
      {field.hint && (
        <small id={fieldId + '-hint'} className="field-hint">
          {field.hint}
        </small>
      )}
      <FieldError id={fieldId + '-error'} message={errors?.[0]} />
    </div>
  );
}
function OpeningHours({
  value,
  onChange,
  disabled,
}: {
  value: { weekday: number; start: string; end: string }[];
  onChange: (value: unknown) => void;
  disabled: boolean;
}) {
  return (
    <div className="opening-hours">
      {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map(
        (name, weekday) => {
          const h = value.find((x) => x.weekday === weekday);
          return (
            <div className="opening-row" key={weekday}>
              <label>
                <input
                  type="checkbox"
                  disabled={disabled}
                  checked={!!h}
                  onChange={(e) =>
                    onChange(
                      e.target.checked
                        ? [...value, { weekday, start: '08:00', end: '18:00' }]
                        : value.filter((x) => x.weekday !== weekday),
                    )
                  }
                />
                {name}
              </label>
              {h ? (
                <>
                  <input
                    type="time"
                    aria-label={`${name} opening time`}
                    disabled={disabled}
                    value={h.start}
                    onChange={(e) =>
                      onChange(
                        value.map((x) =>
                          x.weekday === weekday ? { ...x, start: e.target.value } : x,
                        ),
                      )
                    }
                  />
                  <span>to</span>
                  <input
                    type="time"
                    aria-label={`${name} closing time`}
                    disabled={disabled}
                    value={h.end}
                    onChange={(e) =>
                      onChange(
                        value.map((x) =>
                          x.weekday === weekday ? { ...x, end: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </>
              ) : (
                <span className="closed-label">Closed</span>
              )}
            </div>
          );
        },
      )}
    </div>
  );
}
