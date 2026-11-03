import * as THREE from 'three';
import {OrbitControls} from './vendor/three/OrbitControls.js';
import {OBJLoader} from './vendor/three/OBJLoader.js';
import {MTLLoader} from './vendor/three/MTLLoader.js';
const $ = s => document.querySelector(s), panel = $('#focus-panel');
let selected=null, generation=null, tab='crop', latest=null, meta=null, inFlight=false, cropPending=false, modelKey=null, modelToken=0;
let renderer, scene, camera, controls, poseGroup, assetGroup, animation=0;
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
function numbers(id, values, suffix='') {
 const el=$(id); if (!values) {el.textContent='-';return;}
 if (el.children.length!==values.length) {el.replaceChildren(...values.map(()=>document.createElement('span')));}
 [...el.children].forEach((child,i)=> {const old=Number(child.dataset.v)||0, value=Number(values[i]); child.dataset.v=value;
 if(window.Motion&&!reduced&&Math.abs(old-value)>.001) window.Motion.animate(old,value,{duration:.26,onUpdate:v=>child.textContent=v.toFixed(1)+(i<values.length-1?' / ':suffix)});
 else child.textContent=value.toFixed(1)+(i<values.length-1?' / ':suffix);
 });
}
function disposeModel(){if(!assetGroup)return;assetGroup.traverse(n=>{n.geometry?.dispose();const mats=Array.isArray(n.material)?n.material:[n.material];mats.forEach(m=>{if(!m)return;Object.values(m).forEach(v=>{if(v?.isTexture)v.dispose();});m.dispose();});});poseGroup.remove(assetGroup);assetGroup=null;}
function hide(){selected=null;meta=null;modelKey=null;modelToken++;panel.hidden=true;$('#focus-image').removeAttribute('src');disposeModel();cancelAnimationFrame(animation);animation=0;}
function initViewer(){
 if(renderer)return;
 renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));$('#focus-canvas').append(renderer.domElement);
 scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(40,1,.0001,100);camera.up.set(0,0,1);
 controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.autoRotateSpeed=1.2;
 scene.add(new THREE.HemisphereLight(0xdcecff,0x39334a,2.4));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(2,-3,4);scene.add(light);
 poseGroup=new THREE.Group();scene.add(poseGroup);scene.add(new THREE.AxesHelper(.07));
 new ResizeObserver(()=>{if(tab!=='model'||panel.hidden)return;const box=$('#focus-canvas');renderer.setSize(box.clientWidth,box.clientHeight,false);camera.aspect=box.clientWidth/box.clientHeight;camera.updateProjectionMatrix();}).observe($('#focus-canvas'));
}
function render(){if(tab!=='model'||panel.hidden||document.hidden){animation=0;return;}animation=requestAnimationFrame(render);controls.autoRotate=$('#focus-rotate').checked;controls.update();renderer.render(scene,camera);}
async function loadModel(data){
 initViewer();if(modelKey===data.mesh_url)return;modelKey=data.mesh_url;const token=++modelToken;disposeModel();$('#focus-model-note').textContent='모델 불러오는 중';
 try{
  const url=data.mesh_url, base=url.substring(0,url.lastIndexOf('/')+1), text=await fetch(url).then(r=>{if(!r.ok)throw Error('mesh');return r.text();});
  const loader=new OBJLoader(), match=text.match(/^mtllib\s+(.+)$/m);
  if(match){try{const mtl=await new MTLLoader().setResourcePath(base).loadAsync(base+match[1].trim());mtl.preload();loader.setMaterials(mtl);}catch(e){/* Plain material fallback for optional MTL. */}}
  const model=loader.parse(text);if(token!==modelToken)return;
  model.traverse(n=>{if(n.isMesh){const materials=Array.isArray(n.material)?n.material:[n.material];materials.forEach(m=>{m.side=THREE.DoubleSide;m.opacity=1;m.transparent=false;m.depthWrite=true;if(m.map)m.map.colorSpace=THREE.SRGBColorSpace;});}});
  const bounds=new THREE.Box3().setFromObject(model), center=bounds.getCenter(new THREE.Vector3()), size=bounds.getSize(new THREE.Vector3());
  // Preserve the mesh's registry origin: estimated rotation applies in world axes.
  assetGroup=model;poseGroup.add(model);controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(1,-1,.65).multiplyScalar(Math.max(size.length(),.03)*1.7));controls.update();
  $('#focus-model-note').textContent='추정 월드 방향 · 드래그: 회전 · 휠: 확대';updateRotation();
 }catch(e){if(token===modelToken){modelKey=null;$('#focus-model-note').textContent='모델을 불러오지 못했어요. 다시 탭을 선택해 주세요.';}}
}
function updateRotation(){if(!poseGroup||!meta?.T_world_obj_est)return;const m=new THREE.Matrix4().set(...meta.T_world_obj_est.flat());m.setPosition(0,0,0);poseGroup.setRotationFromMatrix(m);}
function switchTab(next){tab=next;$('#focus-crop').hidden=next!=='crop';$('#focus-model').hidden=next!=='model';for(const n of ['crop','model']){$(`#focus-${n}-tab`).classList.toggle('active',n===next);$(`#focus-${n}-tab`).setAttribute('aria-selected',String(n===next));}if(next==='model'&&meta){try{loadModel(meta);if(!animation)render();}catch(e){$('#focus-model-note').textContent='WebGL을 사용할 수 없습니다.';}}else crop();}
$('#focus-crop-tab').onclick=()=>switchTab('crop');$('#focus-model-tab').onclick=()=>switchTab('model');
async function crop(){if(!selected||tab!=='crop'||document.hidden||cropPending)return;cropPending=true;const name=selected,gen=generation;
 try{const r=await fetch('/focus.jpg',{cache:'no-store'});if(r.status===200){const blob=await r.blob();if(name===selected&&gen===generation){const url=URL.createObjectURL(blob),img=$('#focus-image');img.onload=()=>URL.revokeObjectURL(url);img.src=url;}}}catch(e){}finally{cropPending=false;}}
window.addEventListener('robot-status',async e=>{
 latest=e.detail; if(!latest.selected_object){hide();return;}if(inFlight||document.hidden)return;inFlight=true;
 try{const data=await fetch('/focus/status',{cache:'no-store'}).then(r=>r.json());if(!data.selected||latest.selected_object!==data.selected)return;
 const changed=selected!==data.selected||generation!==data.generation;selected=data.selected;generation=data.generation;meta=data;
 if(panel.hidden){panel.hidden=false;if(window.Motion&&!reduced)window.Motion.animate(panel,{opacity:[0,1],y:[16,0],filter:['blur(5px)','blur(0px)']},{duration:.4});}
 $('#focus-name').textContent=selected;numbers('#focus-size',data.size_mm);numbers('#focus-position',data.T_world_obj_est?.slice(0,3).map(r=>r[3]*1000));numbers('#focus-rotation',data.rpy_deg);
 numbers('#focus-error',latest.pose?[latest.pose.error_mm,latest.pose.error_deg]:null);numbers('#focus-iou',latest.pose?.mask_iou!=null?[latest.pose.mask_iou*100]:null,'%');
 $('#focus-tracking').textContent=latest.tracking_state==='paused'?'일시정지 · 마지막 추정':latest.tracking_state==='tracking'?'추적 중':'대기';$('#focus-grasp').textContent=data.grasp_mode||latest.grasp_mode||'정보 없음';
 updateRotation();if(tab==='model'&&(changed||modelKey!==data.mesh_url)){await loadModel(data);if(!animation)render();}if(changed)crop();
 }catch(e){}finally{inFlight=false;}
});
setInterval(crop,150);document.addEventListener('visibilitychange',()=>{if(!document.hidden&&tab==='model'&&renderer&&!animation)render();});
for(const id of ['reset','randomize'])$("#"+id).addEventListener('click',hide);
