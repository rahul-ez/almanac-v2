import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import {
  ArrowUp,
  ArrowUpRight,
  CalendarBlank,
  DoorOpen,
  ChalkboardTeacher,
  Plus,
  FunnelSimple,
  X,
  Sparkle,
  Clock,
  ArrowClockwise,
} from '@phosphor-icons/react';
import { api, apiMode } from '../../api';
import { ApiError } from '../../api/errors';
import type { Answer, Conversation, QueryRequest } from '../../api/schemas';
import { queryRequestSchema } from '../../api/schemas';
import { useAuth, useWorkspace } from '../../app/state';
import { useData } from '../../app/hooks';
import { RecordCard } from '../../components/Cards';
import { dateLabel, timeLabel } from '../../components/format';
import { EmptyState, ErrorNotice, Notice, Skeleton } from '../../components/ui';

const examples = [
  {
    icon: CalendarBlank,
    title: 'Find your next thing',
    text: 'Any AI workshops this week?',
    style: 'lavender',
  },
  {
    icon: DoorOpen,
    title: 'Make room for ideas',
    text: 'A room in B Block today from 2 to 3 PM',
    style: 'peach',
  },
  {
    icon: ChalkboardTeacher,
    title: 'Find a time to talk',
    text: 'Professor Rao’s office hours tomorrow',
    style: 'mint',
  },
];
const fieldNames: Record<string, string> = {
  department_id: 'Department',
  year: 'Year',
  date: 'Date',
  event_type: 'Type',
  topic: 'Topic',
  free: 'Cost',
  faculty_id: 'Faculty',
  building_id: 'Building',
  capacity: 'Seats',
  starts_at: 'From',
  ends_at: 'Until',
};
const originNames = {
  explicit_question: 'From your question',
  override: 'Your override',
  profile: 'Your profile',
  prior_turn: 'Previous question',
  default: 'Default assumption',
};
function draftRead(key: string) {
  try {
    return sessionStorage.getItem(key) || '';
  } catch {
    return '';
  }
}
export function Assistant() {
  const { id } = useParams();
  const { user } = useAuth();
  const { references, revision } = useWorkspace();
  const navigate = useNavigate();
  const key = `campus.draft:${user!.id}:${id || 'new'}`;
  const outboxKey = `campus.pending:${user!.id}:${id || 'new'}`;
  const [text, setText] = useState(() => draftRead(key));
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [pendingText, setPendingText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [retry, setRetry] = useState<QueryRequest | null>(null);
  const [showContext, setShowContext] = useState(true);
  const controller = useRef<AbortController | null>(null);
  const busyRef = useRef(false);
  const active = useRef(true);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const history = useData(
    (signal) => (id ? api.conversation(id, signal) : Promise.resolve(null)),
    [id],
  );
  const events = useData((signal) => api.events(null, signal), [revision]);
  useEffect(() => {
    setConversation(history.data);
  }, [history.data]);
  useEffect(() => {
    setText(draftRead(key));
    setError(null);
    setRetry(null);
  }, [key]);
  useEffect(() => {
    let cancelled = false;
    const raw = draftRead(outboxKey);
    if (!raw) return;
    let recovered: QueryRequest;
    try {
      recovered = queryRequestSchema.parse(JSON.parse(raw));
    } catch {
      sessionStorage.removeItem(outboxKey);
      return;
    }
    void (async () => {
      try {
        if (recovered.conversation_id) {
          const current = await api.conversation(recovered.conversation_id);
          if (cancelled) return;
          setConversation(current);
          if (current.turns.some((t) => t.answer.request_id === recovered.client_request_id)) {
            sessionStorage.removeItem(outboxKey);
            return;
          }
        } else await api.conversations();
        if (!cancelled) {
          setRetry(recovered);
          setError(
            new Error(
              'A previous request stopped waiting. Stored conversation state has been checked. Retry safely to retrieve its result.',
            ),
          );
        }
      } catch (e) {
        if (!cancelled) {
          setError(e);
          setRetry(recovered);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [outboxKey]);
  useEffect(() => {
    try {
      sessionStorage.setItem(key, text);
    } catch {
      /* draft preservation unavailable */
    }
  }, [key, text]);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      controller.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (conversation?.turns.length)
      bottom.current?.scrollIntoView({ behavior: 'instant', block: 'nearest' });
  }, [conversation?.turns.length, busy]);
  const latest = conversation?.turns.at(-1)?.answer;
  async function send(request: QueryRequest) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    setPendingText(request.text);
    controller.current = new AbortController();
    try {
      sessionStorage.setItem(outboxKey, JSON.stringify(request));
    } catch {
      /* retry still works within the open page */
    }
    try {
      const answer = await api.query(request, controller.current.signal);
      if (!active.current) return;
      const full = await api.conversation(answer.conversation_id);
      setConversation(full);
      setText('');
      setRetry(null);
      try {
        sessionStorage.removeItem(key);
        sessionStorage.removeItem(outboxKey);
      } catch {
        /* unavailable */
      }
      if (!id) navigate('/app/conversations/' + answer.conversation_id, { replace: true });
    } catch (e) {
      if (!active.current) return;
      if (e instanceof Error && e.name === 'AbortError') {
        if (request.conversation_id) {
          try {
            setConversation(await api.conversation(request.conversation_id));
          } catch {
            /* error below */
          }
        }
        setError(
          new Error(
            'The request stopped waiting. Conversation state has been refreshed; retry safely with the same request ID.',
          ),
        );
        setRetry(request);
      } else {
        const retryable = e instanceof ApiError && [0, 429, 500, 502, 503, 504].includes(e.status);
        setError(e);
        setRetry(retryable ? request : null);
        if (!retryable && !(e instanceof ApiError && e.status === 401)) {
          try {
            sessionStorage.removeItem(outboxKey);
          } catch {
            /* unavailable */
          }
        }
      }
    } finally {
      if (active.current) {
        setBusy(false);
        setPendingText('');
      }
      busyRef.current = false;
    }
  }
  const newRequest = (
    value: string,
    optionId?: string,
    overrides: QueryRequest['context_overrides'] = {},
  ) => ({
    text: value,
    conversation_id: conversation?.id || id || null,
    client_request_id: crypto.randomUUID(),
    context_overrides: overrides,
    clarification: latest?.clarification
      ? { id: latest.clarification.id, ...(optionId ? { option_id: optionId } : {}) }
      : null,
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim()) void send(newRequest(text.trim()));
  };
  const chooseExample = (value: string) => {
    setText(value);
    textarea.current?.focus();
  };
  function contextLabel(field: string, value: unknown) {
    if (value === null) return 'Not specified';
    if (field === 'department_id')
      return references?.departments.find((d) => d.id === value)?.label || String(value);
    if (field === 'building_id')
      return references?.buildings.find((d) => d.id === value)?.label || String(value);
    if (field === 'topic')
      return references?.topics.find((d) => d.id === value)?.label || String(value);
    if (field === 'faculty_id')
      return latest?.results.find((c) => c.record_id === value)?.title || String(value);
    if (field === 'free') return 'Free events';
    return Array.isArray(value) ? value.join(', ') : String(value);
  }
  const home = !id && !conversation;
  return (
    <div className={`assistant-page ${home ? 'home' : 'has-conversation'}`}>
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {busy
          ? 'Searching campus records.'
          : latest
            ? `${latest.message} ${latest.results.length} result cards.`
            : ''}
      </div>
      <div className="assistant-heading">
        <div>
          {home ? (
            <>
              <p className="greeting">Good to see you, {user!.name.split(' ')[0]}</p>
              <h1>What’s on your mind?</h1>
              <p>Discover what’s happening. Find a space. Get connected.</p>
            </>
          ) : (
            <>
              <Link className="back-link" to="/app/history">
                Conversations
              </Link>
              <h1>{conversation?.title || 'Your conversation'}</h1>
              <p>Follow up to refine your search, or start something new.</p>
            </>
          )}
        </div>
        {!home && (
          <Link className="button secondary" to="/app">
            <Plus size={17} /> New conversation
          </Link>
        )}
      </div>
      {id && history.loading && !conversation && <Skeleton />}
      {id && !!history.error && <ErrorNotice error={history.error} retry={history.reload} />}
      {conversation && (
        <section className="conversation" aria-label="Conversation">
          {id && (
            <Notice>
              Previous answers are timestamped snapshots. Follow up or refresh for current
              information.
            </Notice>
          )}
          {conversation.turns.map((turn, index) => (
            <div className="turn" key={turn.id}>
              <div className="user-question">
                <span className="question-avatar">{user!.name[0]}</span>
                <p>{turn.question}</p>
              </div>
              <div className="assistant-answer">
                <div className="answer-brand">
                  <span className="answer-mark">
                    <Sparkle size={17} weight="fill" />
                  </span>
                  <strong>Companion</strong>
                  <small>
                    {dateLabel(turn.answer.answered_at, turn.answer.campus_timezone)},{' '}
                    {timeLabel(turn.answer.answered_at, turn.answer.campus_timezone)}
                  </small>
                </div>
                <AnswerBody answer={turn.answer} snapshot={index < conversation.turns.length - 1} />
                {index === conversation.turns.length - 1 &&
                turn.answer.clarification?.options.length ? (
                  <div className="clarification-options">
                    {turn.answer.clarification.options.map((option) => (
                      <button
                        key={option.id}
                        className="button secondary"
                        disabled={busy}
                        onClick={() => void send(newRequest(option.label, option.id))}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          ))}
          {busy && (
            <div className="pending-turn">
              <p className="pending-question">{pendingText}</p>
              <Skeleton count={1} />
            </div>
          )}
          <div ref={bottom} />
        </section>
      )}
      {!!error && <ErrorNotice error={error} retry={retry ? () => void send(retry) : undefined} />}
      {latest && Object.keys(latest.applied_context).length > 0 && (
        <section className="context-panel" aria-label="Applied context">
          <button
            className="text-button"
            onClick={() => setShowContext((v) => !v)}
            aria-expanded={showContext}
          >
            <FunnelSimple size={16} /> Context used for this answer
          </button>
          {showContext && (
            <div className="context-chips">
              {Object.entries(latest.applied_context).map(([field, item]) => (
                <span key={field} className="context-chip" title={originNames[item.origin]}>
                  <span>
                    <small>
                      {fieldNames[field] || field} · {originNames[item.origin]}
                    </small>
                    {contextLabel(field, item.value)}
                  </span>
                  <button
                    className="icon-button"
                    aria-label={`Clear ${fieldNames[field] || field} filter`}
                    disabled={busy}
                    onClick={() => {
                      const request = newRequest(
                        'Update the search without this filter.',
                        undefined,
                        { [field]: null },
                      );
                      request.clarification = null;
                      void send(request);
                    }}
                  >
                    <X size={13} />
                  </button>
                </span>
              ))}
            </div>
          )}
        </section>
      )}
      {(!id || !history.error) && (
        <form className="composer" onSubmit={submit}>
          <label className="sr-only" htmlFor="question">
            Ask your campus companion
          </label>
          <textarea
            ref={textarea}
            id="question"
            placeholder={
              latest?.clarification
                ? latest.clarification.prompt
                : 'Ask anything about your campus…'
            }
            value={text}
            maxLength={2000}
            rows={home ? 3 : 2}
            disabled={busy || !!(id && history.loading)}
            onChange={(e) => {
              setText(e.target.value);
              setRetry(null);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                if (text.trim() && !busy) void send(newRequest(text.trim()));
              }
            }}
          />
          <div className="composer-bottom">
            <span>
              <span className="composer-status" />
              Events, rooms & office hours{apiMode === 'mock' && <small> · Demo answers</small>}
            </span>
            <div>
              <span className="char-count">
                {text.length > 1800 ? `${text.length}/2000` : 'Enter to send'}
              </span>
              <button
                type="submit"
                className="send-button"
                disabled={busy || !text.trim() || !!(id && history.loading)}
                aria-label="Send question"
              >
                <ArrowUp size={21} weight="bold" />
              </button>
            </div>
          </div>
        </form>
      )}
      {home && (
        <>
          <div className="suggestions" aria-label="Example questions">
            {examples.map(({ icon: Icon, title, text, style }) => (
              <button
                className={`suggestion ${style}`}
                key={title}
                onClick={() => chooseExample(text)}
              >
                <span className="suggestion-icon">
                  <Icon size={23} />
                </span>
                <strong>{title}</strong>
                <span>{text}</span>
                <ArrowUpRight className="suggestion-arrow" size={18} />
              </button>
            ))}
          </div>
          <section className="upcoming-section">
            <div className="section-heading">
              <div>
                <h2>Around campus</h2>
                <p>A few things to make room for.</p>
              </div>
              <button
                className="text-button"
                onClick={() => chooseExample('What events are happening this week?')}
              >
                Explore events
                <ArrowUpRight size={16} />
              </button>
            </div>
            {events.loading && !events.data ? (
              <Skeleton />
            ) : events.error ? (
              <ErrorNotice error={events.error} retry={events.reload} />
            ) : events.data?.items.length ? (
              <div className="event-grid">
                {events.data.items.slice(0, 3).map((card) => (
                  <RecordCard card={card} compact key={card.record_id} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="The next good thing is on its way"
                icon={<CalendarBlank size={26} />}
              >
                Published upcoming events will appear here.
              </EmptyState>
            )}
          </section>
          <div className="home-footnote">
            <Clock size={15} />
            <p>
              Answers include sources and update times. Room availability is based on scheduled
              bookings.
            </p>
          </div>
        </>
      )}
      {!home && latest && !busy && (
        <div className="conversation-actions">
          <button
            className="text-button"
            onClick={() => {
              const request = newRequest('Refresh these results.');
              request.clarification = null;
              void send(request);
            }}
          >
            <ArrowClockwise size={16} /> Refresh with current records
          </button>
          <span>Shift + Enter for a new line</span>
        </div>
      )}
    </div>
  );
}
function AnswerBody({ answer, snapshot }: { answer: Answer; snapshot: boolean }) {
  return (
    <>
      <p className="answer-message">{answer.message}</p>
      {answer.results.length > 0 && (
        <div className={`answer-cards ${answer.results.length === 1 ? 'single' : ''}`}>
          {answer.results.map((card, i) => (
            <RecordCard card={card} key={card.record_id + i} snapshot={snapshot} />
          ))}
        </div>
      )}
      {answer.status === 'no_results' && (
        <div className="answer-hint">Try a wider date range or clear one of the filters below.</div>
      )}
      {answer.status === 'information_unavailable' && (
        <Notice tone="warning">
          {answer.data_coverage.message} Please check with the campus administrator.
        </Notice>
      )}
      {answer.status === 'unsupported' && (
        <div className="answer-hint">
          Try “Any workshops this week?” or “A room today from 2 to 3 PM”.
        </div>
      )}
      {answer.warnings.map((warning, i) => (
        <Notice key={i} tone="warning">
          {warning}
        </Notice>
      ))}
      {answer.data_coverage.status === 'partial' &&
        !answer.warnings.includes(answer.data_coverage.message) && (
          <Notice tone="warning">{answer.data_coverage.message}</Notice>
        )}
      <small className="answer-time">
        Answered {dateLabel(answer.answered_at, answer.campus_timezone, true)} at{' '}
        {timeLabel(answer.answered_at, answer.campus_timezone)} · {answer.campus_timezone}
      </small>
    </>
  );
}
