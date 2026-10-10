const key='trident-session-v1'
export function loadSession(){
 try{const value=JSON.parse(sessionStorage.getItem(key)||localStorage.getItem(key)||'null');return value?.token?.startsWith('trident_')?value:null}catch{return null}
}
export function saveSession(value){
 try{
  sessionStorage.removeItem(key);localStorage.removeItem(key)
  if(value?.token?.startsWith('trident_'))(value.remember?localStorage:sessionStorage).setItem(key,JSON.stringify(value))
 }catch{/* Storage may be disabled; in-memory login still works. */}
}
