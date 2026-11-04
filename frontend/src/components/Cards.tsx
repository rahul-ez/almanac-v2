import { useState } from 'react';
import {
  BookmarkSimple,
  CalendarBlank,
  Clock,
  MapPin,
  Users,
  ArrowUpRight,
  CheckCircle,
  Chalkboard,
  GraduationCap,
} from '@phosphor-icons/react';
import { useWorkspace } from '../app/state';
import type { Card } from '../api/schemas';
import { dateLabel, intervalLabel, priceLabel, safeSource, timeLabel } from './format';
import { Dialog, ErrorNotice, Skeleton } from './ui';
import { api, apiMode } from '../api';
import { DEMO_NOW } from '../api/seed';

export function RecordCard({
  card,
  compact = false,
  snapshot = false,
}: {
  card: Card;
  compact?: boolean;
  snapshot?: boolean;
}) {
  const { savedOverrides, savedLoaded, toggleSaved, references } = useWorkspace();
  const zone = references?.campus_timezone;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<Card | null>(null);
  const [detailError, setDetailError] = useState<unknown>(null);
  const saved =
    savedOverrides[`${card.kind}:${card.record_id}`] ?? (savedLoaded ? false : card.saved);
  const source = safeSource(card.source_url);
  const now = apiMode === 'mock' ? new Date(DEMO_NOW).getTime() : Date.now();
  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      await toggleSaved(card.kind, card.record_id, saved);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const showDetails = async () => {
    setDetailOpen(true);
    setDetailError(null);
    setDetail(null);
    try {
      setDetail(await api.detail(card.kind, card.record_id));
    } catch (e) {
      setDetailError(e);
    }
  };
  return (
    <article
      className={`record-card ${card.kind} ${compact ? 'compact' : ''} ${['cancelled', 'archived'].includes(card.record_status) ? 'inactive' : ''}`}
    >
      {card.kind === 'event' && (
        <div
          className={`event-art art-${card.topics.some((t) => /intelligence|learning/i.test(t)) ? 'ai' : card.topics.includes('Design') ? 'design' : 'code'}`}
          aria-hidden="true"
        >
          <div className="art-grid" />
          <span className="art-symbol">
            {card.topics.some((t) => /intelligence|learning/i.test(t))
              ? 'ai'
              : card.topics.includes('Design')
                ? 'Aa'
                : '</>'}
          </span>
          <span className="art-date">{dateLabel(card.starts_at, zone)}</span>
        </div>
      )}
      <div className="card-body">
        <div className="card-top">
          <span className="card-type">
            {card.kind === 'event'
              ? card.event_type
              : card.kind === 'room'
                ? 'Campus room'
                : 'Published office hours'}
          </span>
          <button
            className={`icon-button save-button ${saved ? 'is-saved' : ''}`}
            onClick={toggle}
            disabled={busy}
            aria-label={`${saved ? 'Unsave' : 'Save'} ${card.title}`}
            aria-pressed={saved}
          >
            <BookmarkSimple size={20} weight={saved ? 'fill' : 'regular'} />
          </button>
        </div>
        <h3>
          {compact ? (
            <button
              className="card-title-button"
              onClick={() => void showDetails()}
              aria-label={`View details for ${card.title}`}
            >
              {card.title}
            </button>
          ) : (
            card.title
          )}
        </h3>
        {card.record_status === 'cancelled' || card.record_status === 'archived' ? (
          <span className="badge cancelled">
            {card.record_status === 'cancelled' ? 'Cancelled' : 'Archived'}
          </span>
        ) : null}
        {card.kind === 'event' ? (
          <>
            {!compact && <p className="card-description">{card.description}</p>}
            <div className="card-meta">
              <span>
                <CalendarBlank />
                {dateLabel(card.starts_at, zone)}
                {dateLabel(card.starts_at, zone) !== dateLabel(card.ends_at, zone)
                  ? ` – ${dateLabel(card.ends_at, zone)}`
                  : ''}
                <span className="meta-separator" />
                {timeLabel(card.starts_at, zone)}
              </span>
              <span>
                <MapPin />
                {card.venue}
              </span>
            </div>
            <div className="card-footer">
              <span className="price">{priceLabel(card.cost_minor, card.currency)}</span>
              <span className={`eligibility ${card.eligibility}`} title={card.eligibility_basis}>
                {card.eligibility === 'eligible' ? (
                  <>
                    <CheckCircle size={14} /> You’re eligible
                  </>
                ) : card.eligibility === 'ineligible' ? (
                  'Outside your eligibility'
                ) : (
                  'Eligibility unknown'
                )}
              </span>
            </div>
            {!compact && (
              <div className="card-extra">
                <p>{card.eligibility_basis}</p>
                <p>
                  Ends {timeLabel(card.ends_at, zone)}.{' '}
                  {card.registration_deadline
                    ? `${new Date(card.registration_deadline).getTime() < now ? 'Registration closed' : 'Register by'} ${dateLabel(card.registration_deadline, zone)}, ${timeLabel(card.registration_deadline, zone)}.`
                    : 'Registration deadline not published.'}
                </p>
              </div>
            )}
          </>
        ) : card.kind === 'room' ? (
          <>
            <div className="card-meta">
              <span>
                <MapPin />
                {card.building}
              </span>
              <span>
                <Users />
                {card.capacity} seats
              </span>
              <span>
                <Chalkboard />
                {card.facilities.join(', ') || 'Facilities not published'}
              </span>
              {card.requested_interval && (
                <span>
                  <Clock />
                  {intervalLabel(
                    card.requested_interval.starts_at,
                    card.requested_interval.ends_at,
                    zone,
                  )}
                </span>
              )}
            </div>
            <p className="card-limitation">
              {card.requested_interval
                ? 'No scheduled booking for this interval. Physical vacancy is not guaranteed.'
                : 'Saved room. Ask a new question to check scheduled availability.'}
            </p>
            <span className="badge">Timetable coverage: {card.schedule_coverage}</span>
          </>
        ) : (
          <>
            <div className="card-meta">
              <span>
                <GraduationCap />
                {card.department}
              </span>
              <span>
                <MapPin />
                {card.location || 'Location not published'}
              </span>
              {card.meeting_interval && (
                <span>
                  <Clock />
                  {intervalLabel(
                    card.meeting_interval.starts_at,
                    card.meeting_interval.ends_at,
                    zone,
                  )}
                </span>
              )}
            </div>
            <p className="card-limitation">
              {card.meeting_interval
                ? 'Published meeting hours. Contact the faculty member to confirm a meeting.'
                : 'Saved faculty record. Ask for current published office hours.'}
            </p>
            {card.exception_note && <p className="exception-note">{card.exception_note}</p>}
          </>
        )}
        {!compact && (
          <div className="card-source">
            <span>
              {snapshot ? 'Snapshot source: ' : ''}
              {card.source_label}
              <small>Record updated {dateLabel(card.record_updated_at, zone, true)}</small>
            </span>
            {source && (
              <a
                href={source}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`View source for ${card.title}`}
              >
                <ArrowUpRight size={18} />
              </a>
            )}
          </div>
        )}
        {!!error && <ErrorNotice error={error} />}
      </div>
      {compact && (
        <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} title="Event details">
          {detail ? (
            <RecordCard card={detail} />
          ) : detailError ? (
            <ErrorNotice error={detailError} retry={() => void showDetails()} />
          ) : (
            <Skeleton count={1} />
          )}
        </Dialog>
      )}
    </article>
  );
}
