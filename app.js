"use strict";
const {profiles, calendarStart, calendarEnd} = window.HACKALEM_DATA;
const $ = id => document.getElementById(id);
const money = n => new Intl.NumberFormat('ru-RU').format(n) + ' ₸';
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const unique = key => [...new Set(profiles.flatMap(p => p[key]))].sort((a,b) => a.localeCompare(b,'ru'));
for (const [id,key] of [['city','city'],['format','formats'],['category','categories'],['language','languages']]) {
  for (const value of unique(key)) { const option = new Option(value,value); $(id).add(option); }
}
$('total').textContent = profiles.length;
$('category-count').textContent = unique('categories').length;
let limit = 12;
let lastResults = [];
function readFilters() {
  return Object.fromEntries(['city','format','category','budget','date','language','duration','search','sort'].map(id => [id,$(id).value.trim()]));
}
function matches(p,f) {
  return (!f.city || p.city === f.city) && (!f.format || p.formats.includes(f.format)) &&
    (!f.category || p.categories.includes(f.category)) && (!f.budget || p.price_kzt <= Number(f.budget)) &&
    (!f.date || !p.busy_dates.includes(f.date)) && (!f.language || p.languages.includes(f.language)) &&
    (!f.duration || p.max_hours === null || p.max_hours >= Number(f.duration)) &&
    (!f.search || [p.name,p.id,p.description,...p.categories].join(' ').toLocaleLowerCase('ru').includes(f.search.toLocaleLowerCase('ru')));
}
function flags(p) {
  return [p.synthetic ? '<span class="tag warning">Синтетическая анкета</span>' : '',p.price_imputed ? '<span class="tag warning">Оценочная цена</span>':'',p.city_imputed ? '<span class="tag warning">Город из подготовки базы</span>':''].join('');
}
function card(p,f) {
  const initials = p.name.split(/\s+/).slice(0,2).map(v=>v[0]).join('');
  return `<article class="card"><div class="card-cover" aria-hidden="true"><span class="initials">${escapeHTML(initials)}</span><span class="symbol">✳</span></div><div class="card-body"><div class="category-label">${escapeHTML(p.categories.join(' · '))}</div><h3>${escapeHTML(p.name)}</h3><div class="city">${escapeHTML(p.city)} · ${escapeHTML(p.languages.join(', '))}</div><p class="description">${escapeHTML(p.description)}</p><div class="tags">${flags(p)}</div><div class="availability">${f.date ? '○ Не занят по календарю базы' : '○ Выберите дату для проверки'}</div><div class="price-row"><span>от</span><strong>${money(p.price_kzt)}</strong></div><button class="details-button" data-id="${escapeHTML(p.id)}" aria-label="Подробнее: ${escapeHTML(p.name)}">Об анкете <span>↗</span></button></div></article>`;
}
function render() {
  const f = readFilters();
  let error = '';
  for (const [id,label] of [['budget','Бюджет'],['duration','Длительность']]) if (!$(id).validity.valid) error = label + ': введите положительное целое число в допустимом диапазоне.';
  if (!$('date').validity.valid || (f.date && (f.date < calendarStart || f.date > calendarEnd))) error = 'Расписание доступно только с 23.09 по 31.12.2026. Выберите дату в этом периоде.';
  $('filter-error').textContent = error; $('filter-error').hidden = !error;
  lastResults = error ? [] : profiles.filter(p => matches(p,f));
  lastResults.sort(f.sort === 'name' ? (a,b)=>a.name.localeCompare(b.name,'ru') : (a,b)=>a.price_kzt-b.price_kzt || a.id.localeCompare(b.id));
  $('count').textContent = error ? 'Проверьте параметры поиска' : `Найдено: ${lastResults.length} · Показано: ${Math.min(limit,lastResults.length)}`;
  $('cards').innerHTML = lastResults.slice(0,limit).map(p=>card(p,f)).join('');
  $('empty').hidden = !!error || lastResults.length > 0;
  $('more').hidden = lastResults.length <= limit;
}
function reset() { $('filters').reset(); $('search').value=''; $('sort').value='price'; limit=12; render(); }
$('reset').addEventListener('click',reset); $('empty-reset').addEventListener('click',reset);
$('filters').addEventListener('submit',e=>e.preventDefault());
for (const id of ['filters','search','sort']) $(id).addEventListener('input',()=>{limit=12;render();});
$('more').addEventListener('click',()=>{limit+=12;render();});
$('cards').addEventListener('click',e=>{
  const button=e.target.closest('[data-id]'); if(!button) return;
  const p=profiles.find(p=>p.id===button.dataset.id);
  $('profile-content').innerHTML = `<p class="eyebrow">АНОНИМНАЯ АНКЕТА · ${escapeHTML(p.id)}</p><h2 class="profile-title">${escapeHTML(p.name)}</h2><p>${escapeHTML(p.categories.join(' · '))}</p><div class="tags">${flags(p)}</div><p class="profile-meta">${escapeHTML(p.city)} · <strong>от ${money(p.price_kzt)}</strong><br>Форматы: ${escapeHTML(p.formats.join(', '))}<br>Языки: ${escapeHTML(p.languages.join(', '))}<br>${p.max_hours === null ? 'Лимит часов не применим к этой анкете' : 'Длительность: до '+p.max_hours+' ч.'}</p><p class="profile-description">${escapeHTML(p.description)}</p><div class="profile-note">Имена анонимизированы, контактов в базе нет. ${p.synthetic ? 'Эта анкета синтетическая. ' : ''}${p.price_imputed ? 'Цену добавили при подготовке датасета. ' : ''}${p.city_imputed ? 'Город добавили при подготовке датасета. ' : ''}Календарь: 23.09–31.12.2026. Цена указана «от», окончательная стоимость и доступность не подтверждены.</div>`;
  $('profile-dialog').showModal();
});
document.querySelector('.close').addEventListener('click',()=>$('profile-dialog').close());
$('profile-dialog').addEventListener('click',e=>{if(e.target===$('profile-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
render();
