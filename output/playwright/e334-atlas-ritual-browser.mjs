import { chromium } from '../../web/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';

const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];
page.on('pageerror',error=>errors.push(error.message));
try {
  await page.goto('http://127.0.0.1:8764/',{waitUntil:'networkidle'});
  console.log(JSON.stringify({stage:'initial-snapshot',text:(await page.locator('body').innerText()).slice(0,300)}));
  await page.getByTestId('open-saves').click();
  await page.locator('[data-load="ritual-pending"]').click();
  await page.getByTestId('confirm-load').click();
  await page.getByRole('dialog',{name:'Arquivos do mundo'}).waitFor({state:'hidden'});
  const snapshot=(await (await page.request.get('http://127.0.0.1:8764/api/v2/query/observatory')).json()).data;
  const place=snapshot.society.settlements.find(item=>item.id==='pedraclara');
  const site=snapshot.map.sites.find(item=>item.id==='hospicio-da-aurora');
  let tile;
  for(let y=0;y<snapshot.map.height;y++)for(let x=0;x<snapshot.map.width;x++){
    if(!tile&&snapshot.map.region_rows[y][x]===place.region_id)tile={x,y};
  }
  assert.ok(tile);
  const host=page.locator('.map-canvas');
  await host.locator('canvas').waitFor();
  await host.scrollIntoViewIfNeeded();
  const box=await host.boundingBox();
  const scale=Math.min(box.width/(snapshot.map.width*40),box.height/(snapshot.map.height*40));
  await host.click({position:{x:(box.width-snapshot.map.width*40*scale)/2+(tile.x+.5)*40*scale,
    y:(box.height-snapshot.map.height*40*scale)/2+(tile.y+.5)*40*scale}});
  const inspector=page.getByTestId('inspector');
  await inspector.getByRole('heading',{name:place.name,exact:true}).waitFor();
  await inspector.locator('[data-rite-execution="rite:event:110"]').waitFor();
  await inspector.getByRole('button',{name:site.name+' →',exact:true}).click();
  await inspector.getByRole('heading',{name:site.name,exact:true,level:2}).waitFor();
  const rite=inspector.locator('[data-rite-execution="rite:event:110"]');
  assert.match(await rite.innerText(),/efeito ainda não confirmado/);
  await rite.getByRole('button',{name:'Acompanhar oficiante',exact:true}).click();
  await inspector.getByRole('heading',{name:'Fenn Valverde',exact:true}).waitFor();
  const own=inspector.locator('[data-dossier-entry="rite:event:110"]');
  await own.waitFor();
  await own.getByRole('button',{name:'Ver causa',exact:true}).click();
  await page.getByTestId('causal-detail').waitFor();
  assert.match(await page.getByTestId('causal-detail').innerText(),/Causas diretas/);
  await page.screenshot({path:'output/playwright/e334-atlas-ritual.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({ok:true,flow:'Atlas → Pedraclara → Hospício → Oficiante → Dossiê → Why',day:snapshot.world.day,errors}));
} finally {await browser.close()}
