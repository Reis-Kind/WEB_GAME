// Small WebGL renderer: a closed drawn contour becomes a rounded, two-sided mesh.
// The source image is never changed; judges continue receiving the original PNG.
const SIZE = 160;
const TAU = Math.PI * 2;

export function contourFromImage(source) {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = SIZE;
  const ctx = canvas.getContext('2d', {willReadFrequently:true});
  ctx.fillStyle = '#fff'; ctx.fillRect(0,0,SIZE,SIZE); ctx.drawImage(source,0,0,SIZE,SIZE);
  const pixels = ctx.getImageData(0,0,SIZE,SIZE).data;
  const ink = new Uint8Array(SIZE*SIZE), wall = new Uint8Array(SIZE*SIZE);
  for(let i=0;i<ink.length;i++) ink[i] = Math.min(pixels[i*4],pixels[i*4+1],pixels[i*4+2]) < 215 ? 1 : 0;
  // Join tiny antialiasing gaps, without treating a visibly open outline as closed.
  for(let y=1;y<SIZE-1;y++) for(let x=1;x<SIZE-1;x++) {
    const i=y*SIZE+x;
    if(ink[i]) for(let dy=-1;dy<=1;dy++) for(let dx=-1;dx<=1;dx++) wall[i+dy*SIZE+dx]=1;
  }
  const outside = new Uint8Array(ink.length), queue = new Int32Array(ink.length);
  let tail=0, head=0;
  const add = i => {if(!wall[i]&&!outside[i]) {outside[i]=1;queue[tail++]=i;}};
  for(let k=0;k<SIZE;k++){add(k);add((SIZE-1)*SIZE+k);add(k*SIZE);add(k*SIZE+SIZE-1);}
  while(head<tail){const i=queue[head++],x=i%SIZE,y=(i/SIZE)|0;if(x) add(i-1);if(x<SIZE-1)add(i+1);if(y)add(i-SIZE);if(y<SIZE-1)add(i+SIZE);}
  // Pick the largest enclosed free region: eyes and mouths must not become heads.
  const seen = new Uint8Array(ink.length); let largest=[];
  for(let i=0;i<ink.length;i++) {
    if(wall[i]||outside[i]||seen[i])continue;
    head=0;tail=1;queue[0]=i;seen[i]=1;
    while(head<tail){const j=queue[head++],x=j%SIZE,y=(j/SIZE)|0;
      for(const n of [x?j-1:-1,x<SIZE-1?j+1:-1,y?j-SIZE:-1,y<SIZE-1?j+SIZE:-1])
        if(n>=0&&!wall[n]&&!outside[n]&&!seen[n]){seen[n]=1;queue[tail++]=n;}
    }
    if(tail>largest.length)largest=Array.from(queue.subarray(0,tail));
  }
  let detected=largest.length>SIZE*SIZE*.045;
  if(!detected){
    // Bucket-filled faces have no large empty interior. Recognize a substantial,
    // dense connected ink region as the silhouette instead of reverting to round.
    const visited=new Uint8Array(ink.length);
    for(let i=0;i<wall.length;i++){
      if(!wall[i]||visited[i])continue;
      head=0;tail=1;queue[0]=i;visited[i]=1;
      let minX=SIZE,maxX=0,minY=SIZE,maxY=0;
      while(head<tail){const j=queue[head++],x=j%SIZE,y=(j/SIZE)|0;
        minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
        for(const n of [x?j-1:-1,x<SIZE-1?j+1:-1,y?j-SIZE:-1,y<SIZE-1?j+SIZE:-1])
          if(n>=0&&wall[n]&&!visited[n]){visited[n]=1;queue[tail++]=n;}
      }
      const width=maxX-minX+1,height=maxY-minY+1;
      if(tail>SIZE*SIZE*.045&&width>=SIZE*.25&&height>=SIZE*.3&&tail/(width*height)>.55&&tail>largest.length){
        largest=Array.from(queue.subarray(0,tail));detected=true;
      }
    }
  }
  const mask=new Uint8Array(ink.length);
  if(detected){
    // Include connected hair/accessories and the other enclosed facial regions.
    head=0;tail=1;queue[0]=largest[0];mask[largest[0]]=1;
    while(head<tail){const j=queue[head++],x=j%SIZE,y=(j/SIZE)|0;
      for(const n of [x?j-1:-1,x<SIZE-1?j+1:-1,y?j-SIZE:-1,y<SIZE-1?j+SIZE:-1])
        if(n>=0&&!mask[n]&&(wall[n]||!outside[n])){mask[n]=1;queue[tail++]=n;}
    }
  }else{
    // A clear, predictable fallback for open lines or drawings without an outline.
    for(let y=0;y<SIZE;y++)for(let x=0;x<SIZE;x++)if(((x-80)/70)**2+((y-80)/73)**2<=1)mask[y*SIZE+x]=1;
  }
  let sx=0,sy=0,count=0,minX=SIZE,minY=SIZE,maxX=0,maxY=0;
  mask.forEach((v,i)=>{if(v){const x=i%SIZE,y=(i/SIZE)|0;sx+=x;sy+=y;count++;minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);}});
  let cx=sx/count,cy=sy/count;
  if(!mask[Math.round(cy)*SIZE+Math.round(cx)]) {
    let best=Infinity;
    mask.forEach((v,i)=>{if(v){const x=i%SIZE,y=(i/SIZE)|0,d=(x-cx)**2+(y-cy)**2;if(d<best){best=d;sx=x;sy=y;}}});cx=sx;cy=sy;
  }
  const radii=[];
  for(let a=0;a<128;a++){
    const t=a*TAU/128;let radius=1;
    for(let r=1;r<SIZE;r+=.5){const x=Math.round(cx+Math.cos(t)*r),y=Math.round(cy+Math.sin(t)*r);if(x<0||x>=SIZE||y<0||y>=SIZE)break;if(mask[y*SIZE+x])radius=r;}
    radii.push(radius);
  }
  const smooth=radii.map((r,i)=>(radii[(i+127)%128]+2*r+radii[(i+1)%128])/4);
  return {detected,cx,cy,originX:(minX+maxX)/2,originY:(minY+maxY)/2,radii:smooth,scale:1.72/Math.max(maxX-minX+1,maxY-minY+1),width:maxX-minX+1,height:maxY-minY+1};
}

export function buildFaceGeometry(contour) {
  const {cx,cy,originX=cx,originY=cy,radii,scale}=contour, segments=128,rings=24;
  const positions=[],uv=[],front=[],indices=[];
  for(let side=0;side<2;side++)for(let ring=0;ring<=rings;ring++)for(let a=0;a<=segments;a++){
    const theta=a*TAU/segments, radius=radii[a%segments],fraction=Math.sin(ring/rings*Math.PI/2);
    const x=cx+Math.cos(theta)*radius*fraction,y=cy+Math.sin(theta)*radius*fraction;
    positions.push((x-originX)*scale,-(y-originY)*scale,(side?-1:1)*.48*Math.cos(ring/rings*Math.PI/2));
    uv.push(x/SIZE,y/SIZE);front.push(side?0:1);
  }
  const stride=segments+1, sideCount=(rings+1)*stride;
  for(let side=0;side<2;side++)for(let r=0;r<rings;r++)for(let a=0;a<segments;a++){
    const p=side*sideCount+r*stride+a,q=p+stride;
    indices.push(...(side?[p,q,p+1,p+1,q,q+1]:[p,p+1,q,p+1,q+1,q]));
  }
  const normals=new Float32Array(positions.length);
  for(let i=0;i<indices.length;i+=3){
    const a=indices[i]*3,b=indices[i+1]*3,c=indices[i+2]*3;
    const ux=positions[b]-positions[a],uy=positions[b+1]-positions[a+1],uz=positions[b+2]-positions[a+2];
    const vx=positions[c]-positions[a],vy=positions[c+1]-positions[a+1],vz=positions[c+2]-positions[a+2];
    const nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx;
    for(const k of [a,b,c]){normals[k]+=nx;normals[k+1]+=ny;normals[k+2]+=nz;}
  }
  for(let i=0;i<normals.length;i+=3){const len=Math.hypot(normals[i],normals[i+1],normals[i+2])||1;normals[i]/=len;normals[i+1]/=len;normals[i+2]/=len;}
  // Weld the seam and use a shared pole normal to avoid radial lighting streaks.
  for(let side=0;side<2;side++)for(let r=0;r<=rings;r++){
    const base=(side*sideCount+r*stride)*3;
    if(r===0)for(let a=0;a<=segments;a++){normals[base+a*3]=0;normals[base+a*3+1]=0;normals[base+a*3+2]=side?-1:1;}
    else for(let k=0;k<3;k++){const value=(normals[base+k]+normals[base+segments*3+k])/2;normals[base+k]=normals[base+segments*3+k]=value;}
  }
  return {positions:new Float32Array(positions),normals,uv:new Float32Array(uv),front:new Float32Array(front),indices:new Uint16Array(indices)};
}

const VERTEX=`attribute vec3 position;attribute vec3 normal;attribute vec2 uv;attribute float front;
uniform vec2 turn;varying vec3 n;varying vec2 tex;varying float face;
void main(){float a=turn.x,b=turn.y;mat3 ry=mat3(cos(a),0.,-sin(a),0.,1.,0.,sin(a),0.,cos(a));mat3 rx=mat3(1.,0.,0.,0.,cos(b),sin(b),0.,-sin(b),cos(b));vec3 p=rx*ry*position;n=rx*ry*normal;tex=uv;face=front;gl_Position=vec4(p.xy*1.04,-p.z*.15,1.);}`;
const FRAGMENT=`precision mediump float;uniform sampler2D drawing;varying vec3 n;varying vec2 tex;varying float face;
void main(){vec3 normal=normalize(n);float light=.63+.37*max(0.,dot(normal,normalize(vec3(-.5,.75,1.))));vec3 art=texture2D(drawing,tex).rgb;vec3 clay=vec3(1.,.94,.80);vec3 color=clay*mix(vec3(1.),art,face);float shine=pow(max(0.,dot(reflect(-normalize(vec3(-.5,.75,1.)),normal),vec3(0.,0.,1.))),28.)*.10;gl_FragColor=vec4(color*light+shine,1.);}`;

const viewers=new Set();let ticker=0;
function tick(now){ticker=requestAnimationFrame(tick);if(document.hidden)return;for(const view of viewers){if(view.active&&view.ready&&now-view.lastDraw>33)view.draw(now);}}
export class FaceMesh {
  constructor(image){
    this.image=image;this.head=image.closest('.clay-head');this.lastDraw=0;this.active=true;this.ready=false;
    this.canvas=document.createElement('canvas');this.canvas.className='mesh-view';this.canvas.hidden=true;this.canvas.setAttribute('aria-hidden','true');
    let gl;try{gl=this.canvas.getContext('webgl',{alpha:true,antialias:true,premultipliedAlpha:false});}catch{gl=null;}
    if(!gl){this.useContourFallback();return;}this.available=true;image.dataset.rendering='mesh';this.gl=gl;
    const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error('3D shader');return s;};
    try{
      this.program=gl.createProgram();gl.attachShader(this.program,shader(gl.VERTEX_SHADER,VERTEX));gl.attachShader(this.program,shader(gl.FRAGMENT_SHADER,FRAGMENT));gl.linkProgram(this.program);if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error('3D program');
      this.buffers={};for(const name of ['position','normal','uv','front'])this.buffers[name]=gl.createBuffer();this.index=gl.createBuffer();this.texture=gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D,this.texture);for(const name of [gl.TEXTURE_WRAP_S,gl.TEXTURE_WRAP_T])gl.texParameteri(gl.TEXTURE_2D,name,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
      this.turn=gl.getUniformLocation(this.program,'turn');this.head.append(this.canvas);
      image.addEventListener('load',()=>this.update());
      image.addEventListener('error',()=>this.hide());
      new MutationObserver(()=>{if(image.hidden||!image.getAttribute('src'))this.hide();}).observe(image,{attributes:true,attributeFilter:['hidden','src']});
      this.observer=new IntersectionObserver(entries=>{this.active=entries[0].isIntersecting;});this.observer.observe(this.head);
      this.canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();this.hide();this.available=false;this.image.dataset.rendering='flat';this.image.dispatchEvent(new CustomEvent('facegeometry',{detail:{detected:false,available:false}}));});
      this.canvas.addEventListener('webglcontextrestored',()=>{this.canvas.remove();this.observer.disconnect();viewers.delete(this);new FaceMesh(image);});
      viewers.add(this);if(!ticker)ticker=requestAnimationFrame(tick);
      if(image.complete&&image.naturalWidth)this.update();
    }catch{this.canvas.remove();this.useContourFallback();}
  }
  // Keep the drawn silhouette even on devices without WebGL. Never put the
  // drawing back on the old circular CSS head when GPU rendering is unavailable.
  useContourFallback(){
    this.available=false;this.image.dataset.rendering='contour-2d';
    this.canvas=document.createElement('canvas');this.canvas.className='mesh-view';
    this.canvas.setAttribute('aria-hidden','true');this.canvas.hidden=true;
    this.head.append(this.canvas);
    const render=()=>{
      if(this.image.hidden||!this.image.getAttribute('src')){this.hide();return;}
      if(!this.image.complete||!this.image.naturalWidth)return;
      try{
        const c=contourFromImage(this.image),size=512,ctx=this.canvas.getContext('2d');
        this.canvas.width=this.canvas.height=size;
        const scale=c.scale*size*.52,ox=size/2-c.originX*scale,oy=size/2-c.originY*scale;
        ctx.save();ctx.beginPath();
        c.radii.forEach((r,i)=>{const angle=i*TAU/c.radii.length,x=ox+(c.cx+Math.cos(angle)*r)*scale,y=oy+(c.cy+Math.sin(angle)*r)*scale;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});
        ctx.closePath();ctx.clip();
        ctx.fillStyle='#fff0cc';ctx.fillRect(0,0,size,size);
        ctx.globalCompositeOperation='multiply';ctx.drawImage(this.image,ox,oy,SIZE*scale,SIZE*scale);
        const shade=ctx.createRadialGradient(size*.32,size*.25,0,size*.48,size*.48,size*.65);
        shade.addColorStop(0,'#ffffff');shade.addColorStop(.5,'#f3ead7');shade.addColorStop(1,'#ac9470');
        ctx.fillStyle=shade;ctx.fillRect(0,0,size,size);ctx.restore();
        this.canvas.hidden=false;this.ready=true;this.head.classList.add('has-mesh');this.head.dataset.contour=c.detected?'drawn':'round';
      }catch{this.hide();}
    };
    this.image.addEventListener('load',render);this.image.addEventListener('error',()=>this.hide());
    new MutationObserver(render).observe(this.image,{attributes:true,attributeFilter:['hidden','src']});
    render();
  }
  hide(){this.canvas.hidden=true;this.ready=false;this.head.classList.remove('has-mesh');this.head.removeAttribute('data-contour');}
  update(){
    if(!this.available||!this.image.naturalWidth||this.image.hidden)return;
    try{
      const contour=contourFromImage(this.image),mesh=buildFaceGeometry(contour),gl=this.gl;
      gl.useProgram(this.program);
      for(const [name,data,size] of [['position',mesh.positions,3],['normal',mesh.normals,3],['uv',mesh.uv,2],['front',mesh.front,1]]){
        gl.bindBuffer(gl.ARRAY_BUFFER,this.buffers[name]);gl.bufferData(gl.ARRAY_BUFFER,data,gl.DYNAMIC_DRAW);const a=gl.getAttribLocation(this.program,name);gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,size,gl.FLOAT,false,0,0);
      }
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,this.index);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,mesh.indices,gl.DYNAMIC_DRAW);this.count=mesh.indices.length;
      const texture=document.createElement('canvas');texture.width=texture.height=512;const ctx=texture.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,512,512);ctx.drawImage(this.image,0,0,512,512);
      gl.bindTexture(gl.TEXTURE_2D,this.texture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,texture);
      this.ready=true;this.canvas.hidden=false;this.head.classList.add('has-mesh');this.head.dataset.contour=contour.detected?'drawn':'round';this.draw(performance.now());
      this.image.dispatchEvent(new CustomEvent('facegeometry',{detail:{detected:contour.detected}}));
    }catch{this.hide();}
  }
  draw(now){
    this.lastDraw=now;const gl=this.gl,rect=this.head.getBoundingClientRect();
    const size=Math.min(512,Math.max(128,Math.ceil(Math.max(rect.width,rect.height)*Math.min(devicePixelRatio||1,2))));
    if(this.canvas.width!==size){this.canvas.width=this.canvas.height=size;}gl.viewport(0,0,size,size);
    gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.useProgram(this.program);
    const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
    const stage=this.head.closest('.face-stage');const tilt=stage?getComputedStyle(stage):null;
    const yaw=reduced?0:(parseFloat(tilt?.getPropertyValue('--tilt-y'))||0)*Math.PI/180+Math.sin(now/2800)*.12;
    const pitch=reduced?0:(parseFloat(tilt?.getPropertyValue('--tilt-x'))||0)*Math.PI/180;
    gl.uniform2f(this.turn,yaw,pitch);gl.bindTexture(gl.TEXTURE_2D,this.texture);gl.drawElements(gl.TRIANGLES,this.count,gl.UNSIGNED_SHORT,0);
  }
}
