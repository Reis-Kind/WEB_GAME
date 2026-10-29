export class Drawing {
  constructor(canvas, onChange) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d', {willReadFrequently: true});
    this.onChange = onChange;
    this.strokes = [];
    this.past = [];
    this.color = '#292d36';
    this.size = 7;
    this.tool = 'pen';
    this.pointer = null;
    this.hasInk = false;
    canvas.addEventListener('pointerdown', e => this.down(e));
    canvas.addEventListener('pointermove', e => this.move(e));
    for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) canvas.addEventListener(name, e => this.up(e));
  }
  point(e) {
    const r = this.canvas.getBoundingClientRect();
    return {x: (e.clientX - r.left) * this.canvas.width / r.width, y: (e.clientY - r.top) * this.canvas.height / r.height};
  }
  remember() { this.past.push(this.strokes.slice()); if (this.past.length > 50) this.past.shift(); }
  down(e) {
    if (this.pointer !== null || (e.pointerType === 'mouse' && e.button !== 0)) return;
    e.preventDefault();
    const point=this.point(e);
    if(this.tool==='bucket'){this.fill(point);return;}
    if(this.tool==='picker'){
      const x=Math.max(0,Math.min(this.canvas.width-1,Math.floor(point.x))),y=Math.max(0,Math.min(this.canvas.height-1,Math.floor(point.y)));
      const pixel=this.ctx.getImageData(x,y,1,1).data,a=pixel[3]/255;
      this.onPickColor?.('#'+Array.from(pixel.slice(0,3),v=>Math.round(v*a+255*(1-a)).toString(16).padStart(2,'0')).join(''));
      return;
    }
    this.pointer = e.pointerId;
    this.canvas.setPointerCapture(e.pointerId);
    this.remember();
    this.strokes.push({tool: this.tool, color: this.color, size: this.size, points: [this.point(e)]});
    this.render();
    this.check();
  }
  move(e) {
    if (e.pointerId !== this.pointer) return;
    e.preventDefault();
    const stroke = this.strokes.at(-1);
    if(stroke.tool==='line'||stroke.tool==='circle')stroke.points[1]=this.point(e);
    else for (const event of (e.getCoalescedEvents?.() || [e])) stroke.points.push(this.point(event));
    this.render();
  }
  up(e) {
    if (e.pointerId !== this.pointer) return;
    this.pointer = null;
    if (this.canvas.hasPointerCapture(e.pointerId)) this.canvas.releasePointerCapture(e.pointerId);
    this.check();
  }
  render() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.lineCap = ctx.lineJoin = 'round';
    for (const s of this.strokes) {
      ctx.globalCompositeOperation = s.tool === 'eraser' ? 'destination-out' : 'source-over';
      ctx.strokeStyle = ctx.fillStyle = s.color;
      ctx.lineWidth = s.size;
      if(s.tool==='bucket'){
        for(let i=0;i<s.runs.length;i+=3)ctx.fillRect(s.runs[i],s.runs[i+1],s.runs[i+2],1);
        continue;
      }
      ctx.beginPath();
      if(s.tool==='circle'&&s.points.length>1){
        const a=s.points[0],b=s.points[1];ctx.ellipse((a.x+b.x)/2,(a.y+b.y)/2,Math.max(.1,Math.abs(b.x-a.x)/2),Math.max(.1,Math.abs(b.y-a.y)/2),0,0,Math.PI*2);ctx.stroke();
      }
      else if (s.points.length === 1) { ctx.arc(s.points[0].x, s.points[0].y, s.size / 2, 0, Math.PI * 2); ctx.fill(); }
      else { ctx.moveTo(s.points[0].x, s.points[0].y); for (const p of s.points.slice(1)) ctx.lineTo(p.x, p.y); ctx.stroke(); }
    }
    ctx.globalCompositeOperation = 'source-over';
    this.onRender?.(this);
  }
  fill(point){
    const width=this.canvas.width,height=this.canvas.height,x=Math.floor(point.x),y=Math.floor(point.y);
    if(x<0||x>=width||y<0||y>=height)return;
    const data=this.ctx.getImageData(0,0,width,height).data,start=y*width+x,target=Array.from(data.slice(start*4,start*4+4));
    const replacement=[1,3,5].map(offset=>parseInt(this.color.slice(offset,offset+2),16));
    if(target[3]===255&&replacement.every((v,i)=>Math.abs(v-target[i])<=2))return;
    const mask=new Uint8Array(width*height),queue=new Int32Array(width*height);let head=0,tail=1;queue[0]=start;mask[start]=1;
    const add=index=>{
      if(mask[index])return;
      const offset=index*4;
      if(Math.abs(data[offset+3]-target[3])>24)return;
      if(target[3]>24&&(Math.abs(data[offset]-target[0])>24||Math.abs(data[offset+1]-target[1])>24||Math.abs(data[offset+2]-target[2])>24))return;
      mask[index]=1;queue[tail++]=index;
    };
    while(head<tail){const index=queue[head++],px=index%width,py=(index/width)|0;
      if(px)add(index-1);if(px<width-1)add(index+1);if(py)add(index-width);if(py<height-1)add(index+width);
    }
    // Store horizontal spans, not full bitmap copies or a new flood fill per render.
    const runs=[];
    for(let py=0;py<height;py++)for(let px=0;px<width;px++)if(mask[py*width+px]){
      const first=px;while(px+1<width&&mask[py*width+px+1])px++;runs.push(first,py,px-first+1);
    }
    this.remember();this.strokes.push({tool:'bucket',color:this.color,runs:new Int32Array(runs)});this.render();this.check();
  }
  check() {
    const pixels = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height).data;
    this.hasInk = false;
    for (let i = 3; i < pixels.length; i += 4) { if (pixels[i] > 0 && Math.min(pixels[i-3],pixels[i-2],pixels[i-1]) < 250) { this.hasInk = true; break; } }
    this.onChange?.(this);
  }
  undo() { if (this.pointer !== null || !this.past.length) return; this.strokes = this.past.pop(); this.render(); this.check(); }
  clear() { if (this.pointer !== null || !this.strokes.length) return; this.remember(); this.strokes = []; this.render(); this.check(); }
  image(size = 640) { const out = document.createElement('canvas'); out.width = out.height = size; const ctx = out.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, size, size); ctx.drawImage(this.canvas, 0, 0, size, size); return out.toDataURL('image/png'); }
}
