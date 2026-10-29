'use strict';
// Horizontal capsule chains use the same centerlines and radii as the renderer.
window.CushionPhysics = (() => {
  function drawingShape(points,scale){
    if(!points.length)return [];
    let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
    for(const p of points){minX=Math.min(minX,p.x);maxX=Math.max(maxX,p.x);minY=Math.min(minY,p.y);maxY=Math.max(maxY,p.y);}
    const axis=maxX-minX>=maxY-minY?'x':'y',side=axis==='x'?'y':'x';
    let root=0;
    for(let i=1;i<points.length;i++)if(points[i][axis]<points[root][axis])root=i;
    const anchor=points[root],step=Math.max(1,Math.ceil(points.length/512));
    const raw=points.filter((_,i)=>i%step===0||i===root||i===points.length-1)
      .map(p=>({x:(p[side]-anchor[side])*scale,y:.95,z:Math.max(0,p[axis]-anchor[axis])*scale}));
    const rootIndex=raw.findIndex(p=>p.x===0&&p.z===0);
    let tolerance=.006,result;
    do{
      const keep=new Set([0,rootIndex,raw.length-1]);
      const stack=[[0,rootIndex],[rootIndex,raw.length-1]];
      while(stack.length){
        const [first,last]=stack.pop();let best=tolerance,index=-1;
        for(let i=first+1;i<last;i++){const d=pointDistance(raw[i],raw[first],raw[last]);if(d>best){best=d;index=i;}}
        if(index>=0){keep.add(index);stack.push([first,index],[index,last]);}
      }
      result=[...keep].sort((a,b)=>a-b).map(i=>raw[i]);tolerance*=1.5;
    }while(result.length>128);
    return result;
  }
  function tubeMesh(path,r,sides=12){
    if(path.length<2)return [];
    const rings=path.map((p,i)=>{
      const a=path[Math.max(0,i-1)],b=path[Math.min(path.length-1,i+1)];
      let dx=b.x-a.x,dz=b.z-a.z,len=Math.hypot(dx,dz);
      if(len<1e-8){dx=1;dz=0;len=1;}
      return Array.from({length:sides},(_,j)=>{const t=j/sides*Math.PI*2;return{x:p.x-dz/len*Math.cos(t)*r,y:p.y+Math.sin(t)*r,z:p.z+dx/len*Math.cos(t)*r};});
    });
    const faces=[];
    for(let i=1;i<rings.length;i++)for(let j=0;j<sides;j++)faces.push({points:[rings[i-1][j],rings[i-1][(j+1)%sides],rings[i][(j+1)%sides],rings[i][j]],light:.85+.22*Math.sin(j/sides*Math.PI*2)});
    // Hemisphere ends share the tube's equator so previews and battle meshes
    // have identical, smoothly rounded tips (also matching capsule collisions).
    const closed=Math.hypot(path[0].x-path.at(-1).x,path[0].z-path.at(-1).z)<1e-6;
    if(!closed)for(const i of [0,path.length-1]){
      const p=path[i];let neighbour=i===0?1:i-1;
      while(neighbour>0&&neighbour<path.length-1&&Math.hypot(p.x-path[neighbour].x,p.z-path[neighbour].z)<1e-8)neighbour+=i===0?1:-1;
      let dx=p.x-path[neighbour].x,dz=p.z-path[neighbour].z,len=Math.hypot(dx,dz);
      if(len<1e-8){dx=i===0?-1:1;dz=0;len=1;}
      dx/=len;dz/=len;let previous=rings[i];
      for(let k=1;k<=6;k++){
        const angle=k/6*Math.PI/2;
        const next=rings[i].map(v=>({x:p.x+dx*r*Math.sin(angle)+(v.x-p.x)*Math.cos(angle),y:p.y+(v.y-p.y)*Math.cos(angle),z:p.z+dz*r*Math.sin(angle)+(v.z-p.z)*Math.cos(angle)}));
        for(let j=0;j<sides;j++)faces.push({points:k===6?[previous[j],previous[(j+1)%sides],next[j]]:[previous[j],previous[(j+1)%sides],next[(j+1)%sides],next[j]],light:(.85+.22*Math.sin(j/sides*Math.PI*2))*(1+.08*Math.sin(angle))});
        previous=next;
      }
    }
    return faces;
  }
  function pointDistance(p,a,b) {
    const x=b.x-a.x,z=b.z-a.z;
    const t=Math.max(0,Math.min(1,((p.x-a.x)*x+(p.z-a.z)*z)/(x*x+z*z||1)));
    return Math.hypot(p.x-a.x-t*x,p.z-a.z-t*z);
  }
  function segmentDistance(a,b,c,d) {
    const rx=b.x-a.x,rz=b.z-a.z,sx=d.x-c.x,sz=d.z-c.z;
    const cross=rx*sz-rz*sx;
    if(Math.abs(cross)>1e-10) {
      const qx=c.x-a.x,qz=c.z-a.z;
      const t=(qx*sz-qz*sx)/cross,u=(qx*rz-qz*rx)/cross;
      if(t>=0&&t<=1&&u>=0&&u<=1)return 0;
    }
    return Math.min(pointDistance(a,c,d),pointDistance(b,c,d),pointDistance(c,a,b),pointDistance(d,a,b));
  }
  function overlap(a,b,radius) {
    let depth=0;
    for(let i=1;i<a.length;i++)for(let j=1;j<b.length;j++)
      depth=Math.max(depth,radius-segmentDistance(a[i-1],a[i],b[j-1],b[j]));
    return depth;
  }
  function separate(a,b,makeWeapon,radii) {
    const radius=()=>typeof radii==='function'?radii(a,false)+radii(b,true):radii;
    const depth=()=>overlap(makeWeapon(a,false),makeWeapon(b,true),radius());
    if(depth()<=0)return false;
    // Cushion contact bends/compresses the weapons, never displaces the fighters.
    for(const p of [a,b]){p.bend??=0;p.fold??=1;}
    for(let i=0;i<12&&depth()>.001;i++){
      const oldA=a.bend,oldB=b.bend;
      let best=depth(),chosen=0;
      for(const sign of [-1,1]){
        a.bend=Math.max(-1.5,Math.min(1.5,oldA+sign*.18));
        b.bend=Math.max(-1.5,Math.min(1.5,oldB+sign*.18));
        const value=depth();if(value<best){best=value;chosen=sign;}
      }
      a.bend=Math.max(-1.5,Math.min(1.5,oldA+chosen*.18));
      b.bend=Math.max(-1.5,Math.min(1.5,oldB+chosen*.18));
      if(!chosen){a.fold=Math.max(.04,a.fold*.78);b.fold=Math.max(.04,b.fold*.78);}
    }
    return true;
  }
  return {drawingShape,tubeMesh,pointDistance,segmentDistance,overlap,separate};
})();
