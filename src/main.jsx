import { createRoot } from 'react-dom/client'
import App from './App.jsx'
createRoot(document.getElementById('root')).render(<App />)

const boot=document.getElementById('td-boot')
if(boot){
  requestAnimationFrame(()=>{
    boot.classList.add('is-done')
    window.setTimeout(()=>boot.remove(),400)
  })
}
