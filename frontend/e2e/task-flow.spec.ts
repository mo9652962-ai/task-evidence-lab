import { expect, test } from '@playwright/test'

test('creates, edits, archives, restores visibility, and deletes one task', async ({ page }) => {
  const title = `E2E 任务 ${Date.now()}`
  await page.goto('/')
  await page.getByRole('button', { name: '＋ 新建任务' }).click()
  await page.locator('.modal').getByRole('textbox').nth(0).fill(title)
  await page.locator('.modal').getByRole('textbox').nth(1).fill('E2E 任务目标')
  await page.locator('.modal').getByRole('textbox').nth(2).fill('人工确认 E2E')
  await page.getByRole('button', { name: '创建任务' }).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()

  await page.getByRole('button', { name: '编辑任务' }).click()
  await page.locator('.modal').getByRole('textbox').nth(0).fill(`${title}（已编辑）`)
  await page.getByRole('button', { name: '保存修改' }).click()
  await expect(page.getByRole('heading', { name: `${title}（已编辑）` })).toBeVisible()
  await expect(page.locator('.audit-entry').filter({ hasText: '更新任务' })).toBeVisible()

  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '归档' }).click()
  await page.getByLabel('含已归档').check()
  await expect(page.getByRole('button', { name: new RegExp(`${title}（已编辑）`) })).toBeVisible()
  await page.getByRole('button', { name: new RegExp(`${title}（已编辑）`) }).click()

  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '删除' }).click()
  await expect(page.getByRole('button', { name: new RegExp(`${title}（已编辑）`) })).toHaveCount(0)
})

test('creates a task from a reusable template', async ({ page }) => {
  const templateName = `E2E 模板 ${Date.now()}`
  const taskTitle = `模板实例 ${Date.now()}`
  await page.goto('/')
  await page.getByRole('button', { name: /任务模板/ }).click()
  await page.locator('.template-form input').nth(0).fill(templateName)
  await page.locator('.template-form textarea').nth(0).fill('开发交付任务模板')
  await page.locator('.template-form textarea').nth(2).fill('功能已实现\n测试已通过')
  await page.locator('.template-form input').nth(1).fill('测试输出, Git diff')
  await page.locator('.template-form').getByRole('button', { name: '保存模板' }).click()

  const card = page.locator('.template-card').filter({ hasText: templateName })
  await expect(card).toBeVisible()
  await card.locator('input').fill(taskTitle)
  await card.getByRole('button', { name: '用此模板创建' }).click()
  await expect(page.getByRole('heading', { name: taskTitle })).toBeVisible()
  await expect(page.locator('.evidence').filter({ hasText: '待补充：测试输出' })).toBeVisible()

  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '删除' }).click()
  await page.getByRole('button', { name: /任务模板/ }).click()
  const createdCard = page.locator('.template-card').filter({ hasText: templateName })
  page.once('dialog', (dialog) => dialog.accept())
  await createdCard.getByRole('button', { name: '删除模板' }).click()
  await expect(createdCard).toHaveCount(0)
})

test('searches tasks by title and description', async ({ page }) => {
  const title = `E2E 搜索任务 ${Date.now()}`
  await page.goto('/')
  await page.getByRole('button', { name: '＋ 新建任务' }).click()
  await page.locator('.modal').getByRole('textbox').nth(0).fill(title)
  await page.locator('.modal').getByRole('textbox').nth(1).fill('服务端搜索关键词')
  await page.getByRole('button', { name: '创建任务' }).click()
  await page.getByLabel('搜索任务').fill('服务端搜索关键词')
  await expect(page.getByRole('button', { name: new RegExp(title) })).toBeVisible()

  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: '删除' }).click()
})
