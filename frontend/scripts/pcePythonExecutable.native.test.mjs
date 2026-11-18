import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import {resolvePcePythonRuntime} from './pcePythonExecutable.mjs'
const root=path.resolve('..'),env={PCE_SERVER_CHECKPOINT_BINDING:process.env.PCE_SERVER_CHECKPOINT_BINDING}
test('explicit native binding resolves original interpreter and isolated DB',()=>{const r=resolvePcePythonRuntime(root,env);assert.ok(r.executable.endsWith('python.exe'));assert.ok(r.env.PCE_DATABASE_PATH.endsWith('validation.sqlite3'));assert.equal(r.env.PYTHONIOENCODING,'utf-8')})
test('another source root cannot use this acceptance binding',()=>assert.throws(()=>resolvePcePythonRuntime(path.join(root,'other'),env),/binding invalid/))
test('conflicting database is rejected',()=>assert.throws(()=>resolvePcePythonRuntime(root,{...env,PCE_DATABASE_PATH:path.join(root,'other.sqlite3')}),/conflicts/))
test('existing explicit interpreter preference remains intact',()=>assert.equal(resolvePcePythonRuntime(root,{PCE_PYTHON:'existing-explicit-python'}).executable,'existing-explicit-python'))
test('unbound runtime retains original fallback behavior',()=>assert.equal(resolvePcePythonRuntime(path.join(root,'nonexistent-source'),{}).executable,'python'))
