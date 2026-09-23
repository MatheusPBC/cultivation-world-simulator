import { expect, test } from '@playwright/test'

test('preserves the paused world through a named save and load', async ({ page }) => {
  test.setTimeout(120_000)

  await page.goto('/', { waitUntil: 'domcontentloaded' })

  const createForm = page.locator('form[data-testid="create-world"]')
  if (!(await createForm.isVisible().catch(() => false))) {
    // A live server can retain a previous run.  Replace it only after bringing
    // the real runtime to its required paused state.
    const pause = page.getByRole('button', { name: 'Pausar', exact: true })
    if (await pause.isVisible().catch(() => false)) {
      await pause.click()
      await expect(page.locator('.status-pill')).toHaveText('Pausado', { timeout: 30_000 })
    }
    await page.getByRole('button', { name: 'Novo mundo', exact: true }).click()
  }

  await expect(createForm).toBeVisible({ timeout: 60_000 })
  await createForm.locator('input[name="seed"]').fill('7317')
  await createForm.locator('input[name="character_count"]').fill('2')
  const replace = createForm.locator('input[type="checkbox"]')
  if (await replace.isVisible().catch(() => false)) await replace.check()
  await createForm.getByRole('button', { name: 'Criar mundo', exact: true }).click()

  await expect(page.locator('.timebar')).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('.status-pill')).toHaveText('Pausado')

  const initial = await page.request.get('/api/v2/query/observatory')
  expect(initial.ok()).toBeTruthy()
  const initialEnvelope = await initial.json() as {
    data: { world: { day: number }; status: { paused: boolean } }
    revision: number
  }
  const savedDay = initialEnvelope.data.world.day
  const initialRevision = initialEnvelope.revision
  expect(savedDay).toBe(0)
  expect(initialEnvelope.data.status.paused).toBeTruthy()

  const saveId = `e2e-save-load-${Date.now()}`
  await page.getByTestId('open-saves').click()
  const savePanel = page.getByRole('dialog', { name: 'Arquivos do mundo' })
  await expect(savePanel).toBeVisible()
  await savePanel.locator('input[name="save_id"]').fill(saveId)
  await savePanel.getByRole('button', { name: 'Salvar mundo', exact: true }).click()
  await expect(savePanel.getByRole('status')).toHaveText('Mundo salvo.', { timeout: 60_000 })
  await expect(savePanel.locator(`[data-load="${saveId}"]`)).toBeVisible({ timeout: 30_000 })

  // Mutate the paused world after the save, so loading proves that the file is
  // restored instead of merely re-reading the current in-memory snapshot.
  await page.getByTestId('close-saves').click()
  await page.getByTestId('step').click()
  await expect(page.getByTestId('absolute-day')).toContainText('30', { timeout: 60_000 })
  const stepped = await page.request.get('/api/v2/query/observatory')
  expect(stepped.ok()).toBeTruthy()
  const steppedEnvelope = await stepped.json() as {
    data: { world: { day: number }; status: { paused: boolean } }
    revision: number
  }
  expect(steppedEnvelope.data.world.day).toBe(30)
  expect(steppedEnvelope.data.status.paused).toBeTruthy()
  expect(steppedEnvelope.revision).toBeGreaterThanOrEqual(initialRevision)
  await page.getByTestId('open-saves').click()
  await expect(page.locator(`[data-load="${saveId}"]`)).toBeVisible({ timeout: 30_000 })
  await page.locator(`[data-load="${saveId}"]`).click()
  await expect(page.getByTestId('confirm-load')).toBeVisible()
  await page.getByTestId('confirm-load').click()

  await expect(page.locator('.status-pill')).toHaveText('Pausado', { timeout: 60_000 })
  await expect(page.getByTestId('absolute-day')).toHaveText(`Dia absoluto ${savedDay}`)
  const loaded = await page.request.get('/api/v2/query/observatory')
  expect(loaded.ok()).toBeTruthy()
  const loadedEnvelope = await loaded.json() as {
    data: { world: { day: number }; status: { paused: boolean } }
    revision: number
  }
  expect(loadedEnvelope.data.world.day).toBe(savedDay)
  expect(loadedEnvelope.data.status.paused).toBeTruthy()
  // Runtime revisions are monotonic session revisions; loading creates a new
  // activation revision while the saved world day remains the same.
  expect(loadedEnvelope.revision).toBeGreaterThan(steppedEnvelope.revision)

  await page.getByRole('button', { name: 'Continuar', exact: true }).click()
  await expect(page.locator('.status-pill')).toHaveText('Em andamento', { timeout: 30_000 })

  // Leave the shared live runtime safe for the next observer/test.
  await page.getByRole('button', { name: 'Pausar', exact: true }).click()
  await expect(page.locator('.status-pill')).toHaveText('Pausado', { timeout: 30_000 })
})
