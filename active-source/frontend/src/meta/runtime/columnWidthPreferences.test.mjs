import assert from 'node:assert/strict'
import test from 'node:test'
import {
  columnPreferenceKey,
  columnWidthStorageKey,
  createColumnWidthPreferenceRuntime,
} from './columnWidthPreferences.js'

function memoryStorage() {
  const values = new Map()
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
    values,
  }
}

function table(columns) {
  return { columns, layouts: 0, doLayout() { this.layouts += 1 } }
}

test('preference key is isolated by user, page and table', () => {
  assert.notEqual(
    columnWidthStorageKey({ userKey: 21, pageId: 'pde', tableId: 'fixed' }),
    columnWidthStorageKey({ userKey: 22, pageId: 'pde', tableId: 'fixed' }),
  )
  assert.notEqual(
    columnWidthStorageKey({ userKey: 21, pageId: 'pde', tableId: 'fixed' }),
    columnWidthStorageKey({ userKey: 21, pageId: 'pde', tableId: 'other' }),
  )
})

test('stable column identity does not depend on column position', () => {
  assert.equal(columnPreferenceKey({ columnKey: 'responsible_employee', label: '责任人' }), 'key:responsible_employee')
  assert.equal(columnPreferenceKey({ property: 'signedAt', label: '签认日期' }), 'prop:signedAt')
})

test('dragged width persists, restores after refresh and ignores new columns safely', () => {
  const storage = memoryStorage()
  const first = table([
    { columnKey: 'employee', width: 180, minWidth: 140 },
    { columnKey: 'roles', width: 220, minWidth: 180 },
  ])
  const runtime = createColumnWidthPreferenceRuntime({ storage, userKey: 21, pageId: 'access', tableId: 'users' })
  runtime.capture(first)
  runtime.persist(420, first.columns[0])

  const refreshed = table([
    { columnKey: 'roles', width: 220, minWidth: 180 },
    { columnKey: 'employee', width: 180, minWidth: 140 },
    { columnKey: 'new-column', width: 150, minWidth: 100 },
  ])
  const refreshedRuntime = createColumnWidthPreferenceRuntime({ storage, userKey: 21, pageId: 'access', tableId: 'users' })
  assert.equal(refreshedRuntime.apply(refreshed), 1)
  assert.equal(refreshed.columns[1].width, 420)
  assert.equal(refreshed.columns[2].width, 150)
})

test('reset removes preference and restores captured defaults', () => {
  const storage = memoryStorage()
  const target = table([{ columnKey: 'action', width: 180, minWidth: 120 }])
  const runtime = createColumnWidthPreferenceRuntime({ storage, userKey: 'admin', pageId: 'access', tableId: 'users' })
  runtime.capture(target)
  runtime.persist(360, target.columns[0])
  assert.equal(target.columns[0].width, 360)
  runtime.reset(target)
  assert.equal(target.columns[0].width, 180)
  assert.equal(storage.getItem(runtime.storageKey), null)
})

test('invalid legacy preference is ignored', () => {
  const storage = memoryStorage()
  const runtime = createColumnWidthPreferenceRuntime({ storage, userKey: 21, pageId: 'pde', tableId: 'fixed' })
  storage.setItem(runtime.storageKey, '{broken')
  const target = table([{ columnKey: 'item', width: 320 }])
  assert.equal(runtime.apply(target), 0)
  assert.equal(target.columns[0].width, 320)
})

