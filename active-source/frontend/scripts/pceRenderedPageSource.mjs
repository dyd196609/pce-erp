import fs from 'node:fs'
import path from 'node:path'
// Follow only rendered, explicitly imported business Content SFCs. Generic shells
// and arbitrary unused imports cannot contribute another page's list controls.
export function readRenderedPageSource(root,relative,readFile=file=>fs.readFileSync(file,'utf8')) {
 const visited=new Set(),parts=[]
 function visit(file){
  const absolute=path.resolve(root,file),within=path.relative(root,absolute)
  if(within.startsWith('..')||path.isAbsolute(within))throw Error('rendered source outside frontend')
  if(visited.has(absolute))return
  if(visited.size>=16)throw Error('rendered content dependency limit exceeded')
  visited.add(absolute);const source=readFile(absolute);parts.push(source)
  for(const match of source.matchAll(/import\s+(\w+Content)\s+from\s+['"]([^'"]+\.vue)['"]/g)){
   if(!new RegExp('<'+match[1]+'(?:\\s|/|>)').test(source))continue
   const target=match[2].startsWith('@/')?path.resolve(root,'src',match[2].slice(2)):path.resolve(path.dirname(absolute),match[2])
   visit(target)
  }
 }
 visit(relative)
 return {source:parts.join('\n'),files:[...visited].map(file=>path.relative(root,file).replaceAll('\\','/'))}
}
export function hasDirectListPageShell(source){return /<PceListPageShell(?:\s|>)/.test(source)&&/import\s+PceListPageShell\s+from\s+['"]@\/meta\/components\/PceListPageShell\.vue['"]/.test(source)&&/:module-id=/.test(source)}
