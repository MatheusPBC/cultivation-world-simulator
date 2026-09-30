// Real UI/API over an isolated, prepared world; no decisions or HTTP mocks.
import { chromium } from '../../web/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];
page.on('pageerror',error=>errors.push(error.message));
const inspector=page.getByTestId('inspector');
const detail=page.getByTestId('causal-detail');
async function load(id){
  await page.getByTestId('open-saves').click();
  await page.locator(`[data-load="${id}"]`).click();
  await page.getByTestId('confirm-load').click();
  await page.getByRole('dialog',{name:'Arquivos do mundo'}).waitFor({state:'hidden'});
  return (await (await page.request.get('http://127.0.0.1:8764/api/v2/query/observatory')).json()).data;
}
async function place(snapshot,id){
  const settlement=snapshot.society.settlements.find(item=>item.id===id);
  let tile;
  for(let y=0;y<snapshot.map.height;y++)for(let x=0;x<snapshot.map.width;x++){
    if(!tile&&snapshot.map.region_rows[y][x]===settlement.region_id)tile={x,y};
  }
  assert.ok(tile);
  const host=page.locator('.map-canvas');
  await host.locator('canvas').waitFor();
  await host.scrollIntoViewIfNeeded();
  const box=await host.boundingBox();
  const scale=Math.min(box.width/(snapshot.map.width*40),box.height/(snapshot.map.height*40));
  await host.click({position:{x:(box.width-snapshot.map.width*40*scale)/2+(tile.x+.5)*40*scale,
    y:(box.height-snapshot.map.height*40*scale)/2+(tile.y+.5)*40*scale}});
  await inspector.getByRole('heading',{name:settlement.name,exact:true,level:2}).waitFor();
}
try{
  await page.goto('http://127.0.0.1:8764/',{waitUntil:'networkidle'});
  console.log(JSON.stringify({stage:'initial',text:(await page.locator('body').innerText()).slice(0,200)}));
  const blocked=await load('composed-blocked');
  assert.equal(blocked.world.day,90);
  await place(blocked,'pedraclara');
  const failed=blocked.research.rites.find(item=>item.stage==='failed');
  const completed=blocked.research.rites.find(item=>item.stage==='completed');
  assert.ok(failed&&completed);
  const card=inspector.locator(`[data-rite-execution="${failed.id}"]`);
  await card.getByRole('button',{name:'Ver causa',exact:true}).click();
  await detail.filter({hasText:'nenhum efeito foi produzido'}).waitFor();
  assert.match(await detail.innerText(),/rito concluído; alívio/);
  const consumption=detail.getByRole('button').filter({hasText:'rito concluído; alívio'});
  await consumption.click();
  await detail.filter({hasText:'reagents'}).waitFor();
  assert.match(await detail.innerText(),/crystals/);
  await card.getByRole('button',{name:'Acompanhar oficiante',exact:true}).click();
  const person=blocked.society.characters.find(item=>item.id===failed.officiant_id);
  await inspector.getByRole('heading',{name:person.name,exact:true}).waitFor();
  await inspector.locator(`[data-dossier-entry="${failed.id}"]`).waitFor();
  await place(blocked,'portovelho');
  console.log(JSON.stringify({stage:'portovelho',buttons:await inspector.getByRole('button').allTextContents()}));
  await inspector.getByRole('button',{name:'Via fluvial · 0 volume/dia →',exact:true}).click();
  const routeKnowledge=inspector.locator('details').filter({has:page.locator('[data-route-report]')}).first();
  await routeKnowledge.locator('summary').click();
  const report=inspector.locator('[data-route-report]').first();
  await report.waitFor();
  await report.getByRole('button',{name:'Ver causa',exact:true}).click();
  await detail.filter({hasText:'Causas diretas'}).waitFor();
  assert.match(await inspector.innerText(),/Capacidade observada/);
  // Government mandate exposes the same historical column even after disbanding.
  await inspector.getByRole('button',{name:'Governos',exact:true}).click();
  await inspector.locator('[data-polity="valedouro"]').getByRole('button',{name:'Inspecionar →',exact:true}).click();
  await inspector.locator('details').filter({hasText:'Mandato militar'}).first().locator('summary').click();
  const plan=inspector.locator('[data-defense-plan]').filter({has:page.getByRole('button',{name:'Coluna vinculada →',exact:true})});
  await plan.getByRole('button',{name:'Coluna vinculada →',exact:true}).click();
  await inspector.getByTestId('detachment-last-source').click();
  await detail.filter({hasText:'Causas diretas'}).waitFor();
  assert.match(await detail.innerText(),/Sem provisões/);
  const control=await load('composed-control');
  assert.equal(control.world.day,90);
  await inspector.getByRole('button',{name:'Diplomacia',exact:true}).click();
  const withdrawal=inspector.locator('[data-term]').filter({hasText:'Retirar a coluna'}).first();
  console.log(JSON.stringify({stage:'control-diplomacy',text:(await inspector.innerText()).slice(0,1800)}));
  await withdrawal.getByRole('button',{name:'Ver execução material',exact:true}).click();
  await detail.filter({hasText:'Causas diretas'}).waitFor();
  assert.match(await detail.innerText(),/retir|desmobil/i);
  console.log(JSON.stringify({ok:true,day:blocked.world.day,failed:failed.id,completed:completed.id,errors}));
  assert.deepEqual(errors,[]);
}finally{await browser.close()}
