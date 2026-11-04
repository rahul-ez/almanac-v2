import { useState } from 'react';
import { Link } from 'react-router';
import { ChatCircleText, ArrowRight, Plus, Trash, MagnifyingGlass } from '@phosphor-icons/react';
import { api } from '../../api';
import { usePages } from '../../app/hooks';
import {
  ConfirmDialog,
  EmptyState,
  ErrorNotice,
  PageHeading,
  Pagination,
  Skeleton,
} from '../../components/ui';
import { dateLabel, timeLabel } from '../../components/format';
import { useAuth, useWorkspace } from '../../app/state';

export function History() {
  const { user } = useAuth();
  const { references } = useWorkspace();
  const pages = usePages((cursor, signal) => api.conversations(cursor, signal));
  const [query, setQuery] = useState('');
  const [deleting, setDeleting] = useState<{ id: string; title: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const items = pages.items.filter((c) => c.title.toLowerCase().includes(query.toLowerCase()));
  const remove = async () => {
    if (!deleting) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteConversation(deleting.id);
      try {
        sessionStorage.removeItem(`campus.draft:${user!.id}:${deleting.id}`);
        sessionStorage.removeItem(`campus.pending:${user!.id}:${deleting.id}`);
      } catch {
        /* unavailable */
      }
      setDeleting(null);
      pages.reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="standard-page history-page">
      <PageHeading
        title="Pick up where you left off"
        description="Your questions, and the campus answers you found along the way."
        action={
          <Link className="button primary" to="/app">
            <Plus size={18} /> New conversation
          </Link>
        }
      />
      <div className="search-input">
        <MagnifyingGlass size={20} />
        <label className="sr-only" htmlFor="history-search">
          Search loaded conversations
        </label>
        <input
          id="history-search"
          placeholder="Search loaded conversations…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      {pages.loading && !pages.items.length ? (
        <Skeleton />
      ) : pages.items.length ? (
        <>
          <div className="history-list">
            {items.map((c) => (
              <article className="history-row" key={c.id}>
                <span className="history-icon">
                  <ChatCircleText size={23} />
                </span>
                <Link to={'/app/conversations/' + c.id}>
                  <h2>{c.title}</h2>
                  <p>
                    {dateLabel(c.updated_at, references?.campus_timezone, true)} at{' '}
                    {timeLabel(c.updated_at, references?.campus_timezone)}
                    <span className="meta-separator" />
                    {c.turn_count} {c.turn_count === 1 ? 'turn' : 'turns'}
                  </p>
                </Link>
                <Link
                  className="icon-button"
                  to={'/app/conversations/' + c.id}
                  aria-label={`Open ${c.title}`}
                >
                  <ArrowRight size={19} />
                </Link>
                <button
                  className="icon-button delete-button"
                  aria-label={`Delete ${c.title}`}
                  onClick={() => {
                    setDeleting(c);
                    setError(null);
                  }}
                >
                  <Trash size={19} />
                </button>
              </article>
            ))}
          </div>
          {!items.length && (
            <EmptyState title="No conversations match this search">
              Try a shorter phrase or load more conversations.
            </EmptyState>
          )}
        </>
      ) : (
        !pages.error && (
          <EmptyState icon={<ChatCircleText size={29} />} title="Your next question starts here">
            Ask about a workshop, an open room, or office hours. Your conversations will be kept
            here.
          </EmptyState>
        )
      )}
      {!!pages.error && <ErrorNotice error={pages.error} retry={pages.reload} />}
      <Pagination next={pages.next} busy={pages.loading} onNext={pages.loadMore} />
      <p className="privacy-note">
        Only you can view your conversations. Deleting one removes its stored questions, answers,
        and conversation context.
      </p>
      <ConfirmDialog
        open={!!deleting}
        title="Delete this conversation?"
        onClose={() => setDeleting(null)}
        onConfirm={() => void remove()}
        busy={busy}
        error={error}
      >
        “{deleting?.title}” and all its turns will be permanently removed.
      </ConfirmDialog>
    </div>
  );
}
