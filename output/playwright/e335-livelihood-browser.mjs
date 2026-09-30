import { chromium } from '../../web/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];
page.on('pageerror',error=>errors.push(error.message));
try{
  await page.goto('http://127.0.0.1:8764/',{waitUntil:'networkidle'});
  console.log(JSON.stringify({stage:'initial',text:(await page.locator('body').innerText()).slice(0,180)}));
  for(const branch of ['blocked','control']){
    await page.getByTestId('open-saves').click();
    await page.locator(`[data-load="composed-integrated-${branch}"]`).click();
    await page.getByTestId('confirm-load').click();
    await page.getByRole('dialog',{name:'Arquivos do mundo'}).waitFor({state:'hidden'});
    const data=(await (await page.request.get('http://127.0.0.1:8764/api/v2/query/observatory')).json()).data;
    assert.equal(data.world.day,240);
    const line=data.economy.facilities.find(f=>f.site_id.startsWith('site:pedraclara:')&&f.recipe_id==='toolmaking');
    assert.ok(line);
    const inspector=page.getByTestId('inspector');
    await inspector.getByRole('button',{name:'Finanças',exact:true}).click();
    const payroll=inspector.locator(`[data-payroll="${line.id}"]`);
    await payroll.waitFor();
    assert.ok(Number((await payroll.getByTestId('gross').innerText()).replace(/\D/g,''))>0);
    console.log(JSON.stringify({stage:'payroll-snapshot',branch,text:await payroll.innerText()}));
    await payroll.getByRole('button',{name:'Ver causa',exact:true}).click();
    const why=page.getByTestId('causal-detail');
    await why.filter({hasText:'household:pop:pedraclara:'}).waitFor();
    assert.match(await why.innerText(),/Causas diretas/);
    assert.match(await why.innerText(),/balance/);
    assert.match(await why.innerText(),/famílias consumiram.*rações por.*moedas/i);
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({ok:true,day:240,flow:'Finanças → folha da oficina → why → saldo familiar/compra',errors}));
}finally{await browser.close()}
