import { useState } from 'react';
import { BookmarkSimple } from '@phosphor-icons/react';
import { api } from '../../api';
import type { Kind, SavedItem } from '../../api/schemas';
import { usePages } from '../../app/hooks';
import { useWorkspace } from '../../app/state';
import { RecordCard } from '../../components/Cards';
import { EmptyState, ErrorNotice, PageHeading, Pagination, Skeleton } from '../../components/ui';

export function Saved() {
  const { revision } = useWorkspace();
  const pages = usePages((cursor, signal) => api.saved(cursor, signal), [revision]);
  const [filter, setFilter] = useState<Kind | 'all'>('all');
  const items = pages.items.filter((i) => filter === 'all' || i.kind === filter);
  return (
    <div className="standard-page">
      <PageHeading
        title="Keep the good things close"
        description="Saved records show their current details, including cancellations and changes."
      />
      <div className="filter-tabs" aria-label="Filter saved items">
        {(['all', 'event', 'room', 'faculty'] as const).map((k) => (
          <button
            key={k}
            className={filter === k ? 'active' : ''}
            onClick={() => setFilter(k)}
            aria-pressed={filter === k}
          >
            {k === 'all'
              ? 'Everything'
              : k === 'event'
                ? 'Events'
                : k === 'room'
                  ? 'Rooms'
                  : 'Faculty'}
          </button>
        ))}
      </div>
      {pages.loading && !pages.items.length ? (
        <Skeleton />
      ) : items.length ? (
        <div className="saved-grid">
          {items.map((item) =>
            item.record ? (
              <RecordCard key={item.kind + item.record_id} card={item.record} />
            ) : (
              <UnavailableRecord key={item.kind + item.record_id} item={item} />
            ),
          )}
        </div>
      ) : (
        !pages.error && (
          <EmptyState
            title={
              filter === 'all'
                ? 'A place for your campus finds'
                : `No saved ${filter === 'faculty' ? 'faculty records' : filter + 's'} yet`
            }
            icon={<BookmarkSimple size={28} />}
          >
            Tap the bookmark on an answer or event to keep it here. Saving a room keeps its details;
            availability needs a fresh query.
          </EmptyState>
        )
      )}
      {!!pages.error && <ErrorNotice error={pages.error} retry={pages.reload} />}
      <Pagination next={pages.next} busy={pages.loading} onNext={pages.loadMore} />
    </div>
  );
}

function UnavailableRecord({ item }: { item: SavedItem }) {
  const { toggleSaved } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <article className="unavailable-record">
      <h2>Record unavailable</h2>
      <p>This saved {item.kind} is no longer available. Its source may have been removed.</p>
      <button
        className="text-button"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await toggleSaved(item.kind, item.record_id, true);
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? 'Removing…' : 'Remove saved item'}
      </button>
      {!!error && <ErrorNotice error={error} />}
    </article>
  );
}
