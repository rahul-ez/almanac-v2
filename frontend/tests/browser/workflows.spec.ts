import { test, expect, type Page } from '@playwright/test';

async function login(page: Page, role: 'student' | 'admin' = 'student') {
  await page.goto('/login');
  await page.getByRole('button', { name: `Use ${role} demo` }).click();
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(role === 'admin' ? /\/admin$/ : /\/app$/);
}
async function nav(page: Page, name: string) {
  const menu = page.getByRole('button', { name: 'Open navigation' });
  if ((page.viewportSize()?.width || 1280) <= 800) {
    await menu.click();
    await page
      .getByRole('dialog', { name: 'Navigation' })
      .getByRole('link', { name, exact: true })
      .click();
  } else await page.locator('.sidebar').getByRole('link', { name, exact: true }).click();
}
async function ask(page: Page, text: string) {
  await page.getByRole('textbox', { name: 'Ask your campus companion' }).fill(text);
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByRole('button', { name: 'Send question' })).toBeDisabled();
  await expect(page.locator('.assistant-answer').last()).toBeVisible();
  await expect(page.locator('.pending-turn')).toHaveCount(0);
}

test('student home is responsive, accessible by keyboard, and has no runtime errors', async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await login(page);
  await expect(page.getByRole('heading', { name: 'What’s on your mind?' })).toBeVisible();
  await expect(page.getByText('Demo mode', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Design beyond the screen' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `test-results/${info.project.name}-home.png`, fullPage: true });
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  expect(errors).toEqual([]);
});

test('clarifies faculty, keeps compatible follow-ups, and resets filters on a domain switch', async ({
  page,
}) => {
  await login(page);
  await ask(page, 'Any workshops this week?');
  await expect(page.getByRole('heading', { name: 'Build something with AI' }).last()).toBeVisible();
  await ask(page, 'Only Friday');
  await expect(
    page
      .locator('.assistant-answer')
      .last()
      .getByRole('heading', { name: 'Build something with AI' }),
  ).toBeVisible();
  await ask(page, 'Professor Rao office hours tomorrow');
  await expect(
    page
      .locator('.assistant-answer')
      .last()
      .getByText('Which Professor Rao do you mean?', { exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: /Dr. Anil Rao · AI/ }).click();
  await expect(
    page.locator('.assistant-answer').last().getByRole('heading', { name: 'Dr. Anil Rao' }),
  ).toBeVisible();
  await expect(page.locator('.context-panel')).not.toContainText('Type');
  await page.reload();
  await expect(
    page.locator('.assistant-answer').last().getByRole('heading', { name: 'Dr. Anil Rao' }),
  ).toBeVisible();
});

test('room interval clarification, schedule coverage, and unsupported answers are distinct', async ({
  page,
}) => {
  await login(page);
  await ask(page, 'Find a room in B Block');
  await expect(page.locator('.assistant-answer').last()).toContainText('What date and time');
  await ask(page, 'today from 2 to 3 PM');
  await expect(
    page.locator('.assistant-answer').last().getByRole('heading', { name: 'B-204' }),
  ).toBeVisible();
  await expect(page.locator('.assistant-answer').last()).toContainText(
    'Physical vacancy is not guaranteed',
  );
  await ask(page, 'Room in A Block today from 2 to 3 PM');
  await expect(page.locator('.assistant-answer').last()).toContainText(
    'not enough published information',
  );
  await ask(page, 'What is the weather?');
  await expect(page.locator('.assistant-answer').last()).toContainText(
    'I can help with campus events',
  );
});

test('saves reconcile, profile persists, and conversation deletion works', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: 'Save Build something with AI', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Unsave Build something with AI' })).toBeVisible();
  await nav(page, 'Saved items');
  await expect(page.getByRole('heading', { name: 'Build something with AI' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Build something with AI' })).toBeVisible();
  await nav(page, 'My profile');
  await page.getByLabel('Section', { exact: false }).fill('C');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.getByText('Profile updated.', { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Section', { exact: false })).toHaveValue('C');
  await nav(page, 'Ask companion');
  await ask(page, 'Any workshops this week?');
  await nav(page, 'Conversations');
  await page.getByRole('button', { name: 'Delete Any workshops this week?' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Your next question starts here' })).toBeVisible();
});

test('profile warns before discarding unsaved changes and students cannot enter admin routes', async ({
  page,
}) => {
  await login(page);
  await nav(page, 'My profile');
  await page.getByLabel('Section', { exact: false }).fill('Z');
  await nav(page, 'Saved items');
  await expect(page.getByRole('dialog', { name: 'Leave without saving?' })).toBeVisible();
  await page.getByRole('button', { name: 'Keep editing' }).click();
  await expect(page).toHaveURL(/\/app\/profile$/);
  await nav(page, 'Saved items');
  await page.getByRole('button', { name: 'Discard changes' }).click();
  await expect(page).toHaveURL(/\/app\/saved$/);
  await page.goto('/admin/events');
  await expect(page).toHaveURL(/\/app$/);
});

test('admin creates an event and a student retrieves it through the assistant', async ({
  page,
}) => {
  await login(page, 'admin');
  await page.goto('/admin/events/new');
  await page.getByLabel('Event title').fill('Campus test workshop');
  await page
    .getByLabel('Description', { exact: false })
    .fill('A workshop published through the admin interface.');
  await page.getByLabel('Venue', { exact: false }).fill('Demo auditorium');
  await page.getByLabel('Starts', { exact: false }).fill('2026-11-06T09:00');
  await page.getByLabel('Ends', { exact: false }).fill('2026-11-06T10:00');
  await page.getByLabel('Source label', { exact: false }).fill('Demo student council');
  await page.getByLabel('Publication status').selectOption('published');
  await page.getByLabel('Eligibility', { exact: true }).selectOption('all_students');
  await page.getByRole('button', { name: 'Create record', exact: true }).click();
  await expect(page).toHaveURL(/\/admin\/events$/);
  await expect(page.getByRole('link', { name: 'Campus test workshop', exact: true })).toBeVisible();
  await page.goto('/admin');
  const menu = page.getByRole('button', { name: 'Open navigation' });
  if ((page.viewportSize()?.width || 1280) <= 800) await menu.click();
  await page
    .getByRole('button', { name: 'Sign out', exact: true })
    .filter({ visible: true })
    .click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page);
  await ask(page, 'What workshops are happening this week?');
  await expect(
    page.locator('.assistant-answer').last().getByRole('heading', { name: 'Campus test workshop' }),
  ).toBeVisible();
});

test('event detail dialog restores focus, and admin forms cover every resource', async ({
  page,
}, info) => {
  test.setTimeout(60_000);
  await login(page);
  const details = page.getByRole('button', { name: 'View details for Build something with AI' });
  await details.click();
  const dialog = page.getByRole('dialog', { name: 'Event details' });
  await expect(dialog).toContainText('Record updated');
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(details).toBeFocused();
  if ((page.viewportSize()?.width || 1280) <= 800)
    await page.getByRole('button', { name: 'Open navigation' }).click();
  await page
    .getByRole('button', { name: 'Sign out', exact: true })
    .filter({ visible: true })
    .click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page, 'admin');
  for (const [resource, label] of [
    ['rooms', 'Room code'],
    ['bookings', 'Purpose'],
    ['booking-exceptions', 'Parent booking'],
    ['room-closures', 'Reason for closure'],
    ['faculty', 'Full name'],
    ['office-hours', 'Faculty member'],
    ['office-hour-exceptions', 'Parent office-hour rule'],
    ['aliases', 'Alternative name or abbreviation'],
  ]) {
    await page.goto('/admin/' + resource + '/new');
    await expect(page.getByLabel(label, { exact: false })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create record' })).toBeEnabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
  await page.goto('/admin/events/new');
  await expect(page.getByLabel('Event title')).toBeVisible();
  await page.screenshot({
    path: `test-results/${info.project.name}-admin-form.png`,
    fullPage: true,
  });
});

test('an expired session preserves the unsent question', async ({ page }) => {
  await login(page);
  await page
    .getByRole('textbox', { name: 'Ask your campus companion' })
    .fill('My unsent campus question');
  await page.evaluate(() => {
    const current = JSON.parse(localStorage.getItem('campus.demo.session')!);
    current.expires = 0;
    localStorage.setItem('campus.demo.session', JSON.stringify(current));
  });
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
  await login(page);
  await expect(page.getByRole('textbox', { name: 'Ask your campus companion' })).toHaveValue(
    'My unsent campus question',
  );
});
