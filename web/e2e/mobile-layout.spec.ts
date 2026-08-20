import { expect, test } from '@playwright/test'

test.use({
  viewport: { width: 360, height: 800 },
  deviceScaleFactor: 1,
  hasTouch: true,
  isMobile: true,
})

test('mobile game shell keeps every visible element inside the viewport', async ({ page }) => {
  test.setTimeout(90_000)
  await page.goto('/')
  await expect(page.locator('.mobile-shell')).toBeVisible({ timeout: 60_000 })
  await page.getByTestId('journal-tab-timeline').click()
  const eventContent = page.locator('.event-stream-list__content').first()
  await expect(eventContent).toBeVisible()
  await eventContent.evaluate((element) => {
    element.append(' foundation_establishment_item_label_elixir_without_breaks_'.repeat(4))
  })

  const layout = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth
    const offenders = [...document.querySelectorAll('body *')]
      .filter((element): element is HTMLElement => element instanceof HTMLElement)
      .filter((element) => {
        const style = getComputedStyle(element)
        if (style.display === 'none' || style.visibility === 'hidden') return false
        const rect = element.getBoundingClientRect()
        return rect.width > 0 && (rect.left < -0.5 || rect.right > viewportWidth + 0.5)
      })
      .map((element) => {
        const rect = element.getBoundingClientRect()
        return {
          tag: element.tagName.toLowerCase(),
          classes: element.className,
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
        }
      })
      .slice(0, 20)

    const clippedText = [...document.querySelectorAll('.event-stream-list__content')]
      .filter((element): element is HTMLElement => element instanceof HTMLElement)
      .filter((element) => element.scrollWidth > element.clientWidth + 1)
      .map((element) => ({
        classes: element.className,
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
      }))
      .slice(0, 20)

    return {
      viewportWidth,
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
      offenders,
      clippedText,
    }
  })

  expect(layout, JSON.stringify(layout, null, 2)).toEqual({
    viewportWidth: 360,
    documentWidth: 360,
    bodyWidth: 360,
    offenders: [],
    clippedText: [],
  })
})
