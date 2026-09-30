// Ad-hoc browser verification against the isolated loopback runtime only.
import { chromium } from '../../web/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';

const browser = await chromium.launch({headless:true});
const page = await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];
page.on('pageerror', error=>errors.push(error.message));
const snapshot=async(label)=>console.log(JSON.stringify({label,text:(await page.locator('body').innerText()).slice(0,500)}));
const view=async()=> (await (await page.request.get('http://127.0.0.1:8764/api/v2/query/observatory')).json()).data;
const load=async(id)=>{
  await page.getByTestId('open-saves').click();
  await page.locator(`[data-load="${id}"]`).click();
  await page.getByTestId('confirm-load').click();
  await page.locator('.status-pill').filter({hasText:'Pausado'}).waitFor();
  await page.getByRole('dialog',{name:'Arquivos do mundo'}).waitFor({state:'hidden'});
};
const character=async()=>{
  await page.getByRole('button',{name:'Personagens',exact:true}).click();
  await page.locator('.person-row').filter({hasText:'Fenn Valverde'}).click();
  await page.locator('[data-dossier-entry="rite:event:110"]').waitFor();
};
try {
  await page.goto('http://127.0.0.1:8764/',{waitUntil:'networkidle'});
  await snapshot('initial-runtime');
  await load('ritual-pending');
  assert.equal((await view()).world.day,0);
  await character();
  const activity=page.locator('[data-dossier-entry="rite:event:110"]');
  assert.match(await activity.innerText(),/Oficiante/);
  assert.match(await activity.innerText(),/Materiais previstos/);
  await activity.getByRole('button',{name:'Ver causa',exact:true}).click();
  await page.getByTestId('causal-detail').waitFor();
  await snapshot('pending-dossier-to-why');
  for(let i=0;i<8 && (await view()).research.rites[0].stage!=='completed';i++){
    const before=(await view()).world.day;
    await page.getByTestId('step').click();
    await page.waitForFunction(day=>Number(document.querySelector('[data-testid="absolute-day"]').textContent.replace(/\D/g,''))>day,before);
  }
  const done=await view();
  assert.equal(done.research.rites[0].stage,'completed');
  await character();
  assert.match(await activity.innerText(),/Execução material concluída/);
  await activity.getByRole('button',{name:'Ver causa',exact:true}).click();
  await page.getByTestId('causal-detail').filter({hasText:'health'}).waitFor();
  await snapshot('material-completion-why');
  await page.screenshot({path:'output/playwright/e334-ritual-completed.png',fullPage:true});
  await load('ritual-pending');
  assert.equal((await view()).research.rites[0].stage,'officiating');
  assert.equal((await view()).world.day,0);
  await page.getByRole('button',{name:'Continuar',exact:true}).click();
  await page.locator('.status-pill').filter({hasText:'Em andamento'}).waitFor();
  await page.waitForFunction(()=>Number(document.querySelector('[data-testid="absolute-day"]').textContent.replace(/\D/g,''))>=10);
  await page.getByRole('button',{name:'Pausar',exact:true}).click();
  await page.locator('.status-pill').filter({hasText:'Pausado'}).waitFor();
  assert.equal((await view()).research.rites[0].stage,'completed');
  assert.deepEqual(errors,[]);
  await snapshot('loaded-and-resumed-rite-completed');
  console.log(JSON.stringify({ok:true,day:(await view()).world.day,rite:'rite:event:110',pageErrors:errors}));
} finally {await browser.close()}
