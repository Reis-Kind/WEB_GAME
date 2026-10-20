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
    for (const event of (e.getCoalescedEvents?.() || [e])) stroke.points.push(this.point(event));
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
    ctx.clearRect(0, 0, 640, 640);
    ctx.lineCap = ctx.lineJoin = 'round';
    for (const s of this.strokes) {
      ctx.globalCompositeOperation = s.tool === 'eraser' ? 'destination-out' : 'source-over';
      ctx.strokeStyle = ctx.fillStyle = s.color;
      ctx.lineWidth = s.size;
      ctx.beginPath();
      if (s.points.length === 1) { ctx.arc(s.points[0].x, s.points[0].y, s.size / 2, 0, Math.PI * 2); ctx.fill(); }
      else { ctx.moveTo(s.points[0].x, s.points[0].y); for (const p of s.points.slice(1)) ctx.lineTo(p.x, p.y); ctx.stroke(); }
    }
    ctx.globalCompositeOperation = 'source-over';
  }
  check() {
    const pixels = this.ctx.getImageData(0, 0, 640, 640).data;
    this.hasInk = false;
    for (let i = 3; i < pixels.length; i += 4) { if (pixels[i] > 0) { this.hasInk = true; break; } }
    this.onChange?.(this);
  }
  undo() { if (this.pointer !== null || !this.past.length) return; this.strokes = this.past.pop(); this.render(); this.check(); }
  clear() { if (this.pointer !== null || !this.strokes.length) return; this.remember(); this.strokes = []; this.render(); this.check(); }
  image() { const out = document.createElement('canvas'); out.width = out.height = 640; const ctx = out.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 640, 640); ctx.drawImage(this.canvas, 0, 0); return out.toDataURL('image/png'); }
}
