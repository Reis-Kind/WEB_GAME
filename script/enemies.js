// All opponents use the same drawn-outline -> 3D mesh pipeline as the player.
// Uneven closed contours and the default pen color/width match player drawings.
// Paths stay deterministic so preview, 3D silhouette, and AI input always agree.
function sketch({outline, hair = '', eyes, nose, mouth, extras = ''}) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640"><g fill="none" stroke="#292d36" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">${hair}${eyes}${nose}${mouth}${extras}<path d="${outline}"/></g></svg>`;
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
}
const dots = '<path d="M251 302l1 8m134-9-1 8" stroke-width="16"/>';
const littleNose = '<path d="M322 326l-9 35 18 2"/>';
export const ENEMIES = [
  {id:'mame', name:'まめお', description:'少しゆがんだ丸顔・点の目・ちょこんと曲がった鼻', hint:'目、豆じゃん', image:sketch({
    outline:'M319 118Q355 109 386 127Q427 137 450 174Q480 202 483 246Q498 276 489 317Q497 355 478 390Q470 432 438 459Q415 493 372 503Q340 527 303 518Q265 527 231 504Q189 489 171 451Q143 417 149 376Q133 343 146 307Q135 267 153 231Q162 188 198 163Q227 133 269 129Q293 117 319 118Z',
    hair:'<path d="M251 142l18 35 27-48 30 40 29-43 24 30"/>', eyes:dots, nose:littleNose,
    mouth:'<path d="M249 410q69 65 139-7"/>'})},
  {id:'nobio', name:'のびお', description:'縦にのびた顔・短い横目・長い鼻', hint:'鼻、ながっ', image:sketch({
    outline:'M316 76Q351 69 376 93Q408 109 407 146Q425 180 413 218Q422 250 415 288Q426 324 418 359Q431 394 421 429Q425 471 402 501Q393 541 360 555Q335 577 307 565Q275 571 253 546Q224 522 225 484Q212 451 221 414Q210 376 219 338Q210 304 218 269Q207 235 216 201Q209 159 232 132Q242 96 276 88Q297 74 316 76Z',
    hair:'<path d="M260 95l18 65 28-80 24 77 29-68 22 68"/>', eyes:'<path d="M249 272l38 3m60-2 39-3"/>',
    nose:'<path d="M319 297l-8 111 27-3"/>',mouth:'<path d="M283 466q37-12 72 0"/>'})},
  {id:'kakube', name:'かくべえ', description:'ゆがんだ四角い顔・四角い目・一直線の口', hint:'顔、食パンじゃん', image:sketch({
    outline:'M168 157Q208 149 249 157Q290 145 332 153Q371 145 411 151Q446 142 470 159Q488 184 478 219Q492 252 484 288Q495 323 485 360Q494 400 483 436Q491 468 468 487Q434 494 400 485Q364 498 327 489Q288 500 251 489Q213 500 181 490Q151 489 158 456Q145 420 156 385Q145 347 154 310Q146 274 153 239Q145 207 152 181Q149 164 168 157Z',
    hair:'<path d="M161 201l48-35 47 34 48-37 47 36 48-39 69 32"/>',
    eyes:'<path d="M214 277l54 2-1 52-51-2ZM368 275l54-2 2 54-53 2Z"/><path d="M241 300v7m155-8v7" stroke-width="14"/>',
    nose:'<path d="M304 349l30 0 0 31-30 0Z"/>',mouth:'<path d="M245 430l151-3"/>'})},
  {id:'pote', name:'ぽてすけ', description:'横に広い顔・離れた目・小さな丸い口', hint:'顔、横にのびすぎ', image:sketch({
    outline:'M319 181Q362 172 401 183Q447 177 480 201Q521 215 537 249Q558 278 549 309Q562 343 543 371Q534 407 495 421Q465 450 421 449Q379 471 337 460Q294 476 252 463Q210 473 172 450Q129 442 109 410Q80 388 91 353Q78 326 92 298Q85 265 112 241Q130 212 168 205Q199 183 243 188Q280 175 319 181Z',
    hair:'<path d="M247 186q12 61 43-6q20 64 44-4q23 64 48 4"/>',
    eyes:'<path d="M172 304v14m296-14v14" stroke-width="15"/>',nose:'<path d="M321 313l-8 25 19 1"/>',
    mouth:'<path d="M323 375q-24-2-22 19q1 20 23 18q21-1 20-20q-1-17-21-17Z"/>'})},
  {id:'sankichi', name:'さんきち', description:'三角の顔・つり目・への字の口', hint:'顔、おにぎりじゃん', image:sketch({
    outline:'M318 102Q335 97 342 125Q363 153 372 184Q395 213 401 246Q425 275 433 307Q456 336 464 368Q487 399 494 431Q520 455 525 484Q532 507 503 509Q468 522 431 513Q395 524 357 515Q319 524 281 516Q243 528 207 519Q168 526 135 515Q108 512 119 484Q126 455 146 433Q151 399 174 370Q182 337 204 310Q213 277 234 248Q243 213 265 185Q276 150 297 127Q304 105 318 102Z',
    hair:'<path d="M271 184l30 25 23-67 22 65 28-20"/>',
    eyes:'<path d="M240 337l49 17m68 0 47-21"/>',nose:'<path d="M321 367l-14 38 27-2"/>',
    mouth:'<path d="M270 460l52-20 52 17"/>'})},
  {id:'higemochi', name:'ひげもち', description:'もち形の顔・丸いメガネ・くるんとしたひげ', hint:'ひげ、くるんくるん', image:sketch({
    outline:'M315 137Q350 126 379 147Q418 155 436 188Q459 215 456 249Q470 279 467 311Q489 341 485 371Q508 397 494 428Q491 461 456 478Q431 509 393 507Q355 526 320 514Q281 531 247 516Q206 523 182 494Q145 478 142 445Q124 418 143 390Q149 359 164 333Q170 304 172 275Q176 240 196 212Q203 180 235 163Q268 138 315 137Z',
    hair:'<path d="M268 153q3 49 31 5m20-19q-1 46 27 20m14-14q-1 38 25 26"/>',
    eyes:'<path d="M282 300q0-49-49-48q-47 1-45 49q0 47 48 46q48 0 46-47Zm167 1q0-49-49-48q-47 1-45 49q0 47 48 46q48 0 46-47ZM283 297q35-20 71 1"/><path d="M236 294v11m163-10v11" stroke-width="14"/>',
    nose:'<path d="M320 319l-15 46 28 1"/>',mouth:'<path d="M292 453q29 15 58-2"/>',
    extras:'<path d="M321 408q-61-55-86-15q-14 28 23 21q30-10 63-6q36-6 65 7q37 5 23-22q-26-41-88 15Z"/>'})},
];
export function chooseEnemy(id, previousId = '') {
  if (id !== 'random') return ENEMIES.find(enemy => enemy.id === id) || ENEMIES[0];
  const pool = ENEMIES.filter(enemy => enemy.id !== previousId);
  return pool[Math.floor(Math.random() * pool.length)];
}
