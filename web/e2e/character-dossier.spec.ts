import { expect, test } from '@playwright/test'

test('character dossier navigates to the causal source in the chronicle', async ({ page }) => {
  test.setTimeout(90_000)

  await page.goto('/', { waitUntil: 'domcontentloaded' })

  // The live runtime may already have a paused world from a previous session.
  // In that case open the same create form and explicitly replace it; no API
  // state is injected by this test.
  const createForm = page.locator('form[data-testid="create-world"]')
  const existingWorld = page.getByRole('button', { name: 'Novo mundo', exact: true })
  if (!(await createForm.isVisible().catch(() => false))) {
    await expect(existingWorld).toBeVisible({ timeout: 60_000 })
    await existingWorld.click()
  }

  await expect(createForm).toBeVisible({ timeout: 60_000 })
  await createForm.locator('input[name="seed"]').fill('73')
  await createForm.locator('input[name="character_count"]').fill('2')

  const replace = createForm.locator('input[type="checkbox"]')
  if (await replace.isVisible().catch(() => false)) await replace.check()

  await createForm.getByRole('button', { name: 'Criar mundo', exact: true }).click()
  await expect(page.locator('[data-testid="inspector"]')).toBeVisible({ timeout: 60_000 })

  // One real monthly jump refreshes local character observations, which are
  // the factual entries rendered in the character dossier.
  await page.getByTestId('step').click()
  await expect(page.getByTestId('absolute-day')).toContainText('30', { timeout: 60_000 })

  await page.getByRole('button', { name: 'Personagens', exact: true }).click()
  const character = page.locator('.person-row').first()
  await expect(character).toBeVisible({ timeout: 30_000 })
  await character.click()

  await expect(page.getByRole('heading', { name: 'Dossiê conhecido', exact: true })).toBeVisible()
  const dossierEntry = page.locator('[data-dossier-entry]').first()
  await expect(dossierEntry).toBeVisible({ timeout: 30_000 })
  await expect(dossierEntry).toContainText(/.+/)

  const source = dossierEntry.getByRole('button', { name: 'Ver causa', exact: true })
  await expect(source).toBeVisible()
  await source.click()

  const causalDetail = page.getByTestId('causal-detail')
  await expect(causalDetail).toBeVisible({ timeout: 30_000 })
  await expect(causalDetail).toContainText('Por que aconteceu?')
  await expect(causalDetail).toContainText('Causas diretas')
})
