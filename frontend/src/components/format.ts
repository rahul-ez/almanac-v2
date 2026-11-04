export const DEFAULT_ZONE = 'Asia/Kolkata';
export function dateLabel(value: string, zone = DEFAULT_ZONE, full = false) {
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: zone,
    day: 'numeric',
    month: full ? 'long' : 'short',
    year: full ? 'numeric' : undefined,
  }).format(new Date(value));
}
export function timeLabel(value: string, zone = DEFAULT_ZONE) {
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: zone,
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(new Date(value));
}
export function intervalLabel(start: string, end: string, zone = DEFAULT_ZONE) {
  return `${dateLabel(start, zone)}, ${timeLabel(start, zone)} – ${dateLabel(start, zone) === dateLabel(end, zone) ? '' : dateLabel(end, zone) + ', '}${timeLabel(end, zone)}`;
}
export function localInput(value: string, zone = DEFAULT_ZONE) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: zone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(value));
  const p = Object.fromEntries(parts.map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
// Campus-local controls use an IANA zone. Iterative conversion handles non-India campuses too.
export function inputInstant(value: string, zone = DEFAULT_ZONE) {
  if (!value) return null;
  const wanted = Date.parse(value + ':00Z');
  if (!Number.isFinite(wanted)) return null;
  let guess = wanted;
  for (let i = 0; i < 3; i++) {
    const represented = Date.parse(localInput(new Date(guess).toISOString(), zone) + ':00Z');
    guess += wanted - represented;
  }
  const result = new Date(guess).toISOString();
  return localInput(result, zone) === value ? result : null;
}
export function safeSource(value: string | null) {
  if (!value) return null;
  try {
    const u = new URL(value);
    return ['https:', 'http:'].includes(u.protocol) ? u.href : null;
  } catch {
    return null;
  }
}
export function priceLabel(amount: number | null, currency: string) {
  if (amount === null) return 'Price not published';
  if (amount === 0) return 'Free';
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(amount / 100);
  } catch {
    return `${amount / 100} ${currency}`;
  }
}
