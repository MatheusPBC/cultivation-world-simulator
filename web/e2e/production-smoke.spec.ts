import { expect, test } from '@playwright/test'

function readDay(text: string | null): number {
  const match = text?.match(/\d+/)
  if (!match) throw new Error(`Missing day in UI text: ${text}`)
  return Number(match[0])
}

test('Medieval observer renders against the real v2 production contract', async ({ page }) => {
  const pageErrors: string[] = []
  const failedRequests: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('requestfailed', request => failedRequests.push(`${request.method()} ${request.url()}`))

  await page.goto('/', { waitUntil: 'networkidle' })
  await expect(page.locator('.subtitle, .eyebrow').filter({ hasText: 'MEDIEVAL WORLD SIMULATOR' }).first()).toBeVisible()
  expect((await page.request.get('/api/health')).ok()).toBeTruthy()
  expect((await page.request.get('/api/v2/query/status')).ok()).toBeTruthy()

  const create = page.locator('form[data-testid="create-world"]')
  await expect(create).toBeVisible()
  await create.locator('input[name="seed"]').fill('73')
  await create.locator('input[name="character_count"]').fill('2')
  await create.getByRole('button', { name: 'Criar mundo', exact: true }).click()
  await expect(page.getByTestId('absolute-day')).toBeVisible()
  const initialDay = readDay(await page.getByTestId('absolute-day').textContent())
  const initial = await page.request.get('/api/v2/query/observatory')
  const initialEnvelope = await initial.json()
  expect(initialEnvelope.data.status.paused).toBe(true)
  expect(initialEnvelope.data.world.config.ai_enabled).toBe(false)
  await expect(page.getByTestId('ai-toggle')).toContainText('IA desligada')
  const revision = initialEnvelope.revision

  await page.getByTestId('step').click()
  await expect.poll(async () => readDay(await page.getByTestId('absolute-day').textContent())).toBeGreaterThan(initialDay)
  const steppedDay = readDay(await page.getByTestId('absolute-day').textContent())
  await page.getByRole('button', { name: 'Continuar', exact: true }).click()
  await expect(page.locator('.status-pill')).toContainText('Em andamento')
  await page.getByRole('button', { name: 'Pausar', exact: true }).click()
  await expect(page.locator('.status-pill')).toContainText('Pausado')
  const savedWorldDay = readDay(await page.getByTestId('absolute-day').textContent())
  expect(savedWorldDay).toBeGreaterThanOrEqual(steppedDay)

  await page.getByTestId('open-saves').click()
  await page.getByTestId('save-world').locator('input[name="save_id"]').fill('e358-smoke')
  await page.getByTestId('save-world').getByRole('button', { name: 'Salvar mundo', exact: true }).click()
  await expect(page.getByTestId('save-world').getByRole('status')).toBeVisible()
  await page.getByTestId('close-saves').click()

  await page.getByTestId('step').click()
  await expect.poll(async () => readDay(await page.getByTestId('absolute-day').textContent())).toBeGreaterThan(savedWorldDay)
  await page.getByTestId('open-saves').click()
  await page.locator('[data-load="e358-smoke"]').click()
  await page.getByTestId('confirm-load').click()
  await expect(page.getByTestId('close-saves')).toBeHidden()
  await expect.poll(async () => readDay(await page.getByTestId('absolute-day').textContent())).toBe(savedWorldDay)
  const loaded = await page.request.get('/api/v2/query/observatory')
  const loadedEnvelope = await loaded.json()
  expect(loadedEnvelope.data.status.paused).toBe(true)
  expect(loadedEnvelope.data.world.day).toBe(savedWorldDay)
  expect(loadedEnvelope.data.world.config.ai_enabled).toBe(false)
  expect(loadedEnvelope.revision).toBeGreaterThan(revision)
  expect(pageErrors).toEqual([])
  expect(failedRequests).toEqual([])
})
