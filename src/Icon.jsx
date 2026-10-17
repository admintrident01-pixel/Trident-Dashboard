import './Icon.css'
// Shared Feather icon primitive. Keep visible button text or an accessible label.
export default function Icon({name,size=16,className='',style}){
 return <svg className={'app-icon '+className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" style={style}><use href={name.startsWith('custom-')?'/icons/custom-sprite.svg#'+name.slice(7):'/icons/feather-sprite.svg#'+name}/></svg>
}
