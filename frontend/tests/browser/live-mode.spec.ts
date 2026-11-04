import { test, expect } from '@playwright/test';
import { answerFixtures } from '../../src/api/fixtures';
import { defaultProfile, demoUsers, referenceData } from '../../src/api/seed';

test('live service failures stay errors and retries reuse the assistant request ID', async ({
  page,
}) => {
  let loggedIn = false;
  let queryCount = 0;
  const ids: string[] = [];
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace('/api/v1', '');
    const send = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    const error = (status: number) =>
      send(
        {
          error: {
            code: status === 401 ? 'unauthenticated' : 'service_unavailable',
            message: status === 401 ? 'Sign in.' : 'Campus API is temporarily unavailable.',
            field_errors: {},
            request_id: 'test-server-id',
          },
        },
        status,
      );
    if (path === '/auth/me') return loggedIn ? send(demoUsers[0]) : error(401);
    if (path === '/auth/csrf') return send({ csrf_token: 'csrf-live-test' });
    if (path === '/auth/login') {
      loggedIn = true;
      expect(route.request().headers()['x-csrf-token']).toBe('csrf-live-test');
      return send(demoUsers[0]);
    }
    if (path === '/reference-data') return send(referenceData);
    if (path === '/me/profile') return send(defaultProfile);
    if (path === '/events') return error(503);
    if (path === '/assistant/query') {
      queryCount++;
      ids.push(route.request().postDataJSON().client_request_id);
      if (queryCount === 1) return error(503);
      return send({ ...answerFixtures['no-matches'], request_id: ids.at(-1) });
    }
    if (path.startsWith('/conversations/'))
      return send({
        id: 'fixture-conversation',
        title: 'Any workshops?',
        updated_at: answerFixtures['no-matches'].answered_at,
        turn_count: 1,
        turns: [
          { id: 'fixture-turn', question: 'Any workshops?', answer: answerFixtures['no-matches'] },
        ],
      });
    return send({ items: [], next_cursor: null });
  });
  await page.goto('http://127.0.0.1:5174/login');
  await expect(page.getByRole('button', { name: 'Use student demo' })).toHaveCount(0);
  await page.getByLabel('Campus email').fill('student@campus.demo');
  await page.getByLabel('Password', { exact: true }).fill('test-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByText('Live campus data', { exact: true })).toBeVisible();
  await expect(page.getByText('Campus API is temporarily unavailable.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Build something with AI' })).toHaveCount(0);
  await page.getByRole('textbox', { name: 'Ask your campus companion' }).fill('Any workshops?');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByText('Campus API is temporarily unavailable.')).toHaveCount(2);
  await page.reload();
  await expect(
    page.getByText('A previous request stopped waiting.', { exact: false }),
  ).toBeVisible();
  await page
    .locator('.assistant-page > .error-notice')
    .getByRole('button', { name: 'Try again' })
    .click();
  await expect(page.locator('.assistant-answer')).toContainText('No matching events');
  expect(ids.length).toBe(2);
  expect(ids[0]).toBe(ids[1]);
});

test('every assistant fixture renders safely in live mode', async ({ page }, info) => {
  const answers = Object.entries(answerFixtures).map(([name, answer], i) => ({
    id: 'turn-' + i,
    question: name,
    answer: { ...answer, turn_id: 'turn-' + i },
  }));
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const data = path.endsWith('/auth/me')
      ? demoUsers[0]
      : path.endsWith('/reference-data')
        ? referenceData
        : path.includes('/conversations/')
          ? {
              id: 'fixture-conversation',
              title: 'Contract fixture gallery',
              updated_at: answers[0].answer.answered_at,
              turn_count: answers.length,
              turns: answers,
            }
          : { items: [], next_cursor: null };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
  });
  await page.goto('http://127.0.0.1:5174/app/conversations/fixture-conversation');
  await expect(page.locator('.turn')).toHaveCount(10);
  await expect(page.getByText('B-204 has no scheduled booking for your interval.')).toBeVisible();
  await expect(page.getByText('A Block timetable coverage is incomplete.')).toBeVisible();
  await expect(page.getByText('Showing the first 6 matches.', { exact: false })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `test-results/${info.project.name}-fixtures.png`, fullPage: true });
});
