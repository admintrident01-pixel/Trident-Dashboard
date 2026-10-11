import {compareValues} from './tableSort'
import {Children,cloneElement,isValidElement,useState} from 'react'
import './SortableTable.css'
const elements=node=>Children.toArray(node).filter(isValidElement)
const text=node=>typeof node==='string'||typeof node==='number'?String(node):isValidElement(node)?text(node.props.children):Array.isArray(node)?node.map(text).join(' '):''
function cellValue(cell){return cell?.props['data-sort-value']??text(cell?.props.children)}
export default function SortableTable({children,...props}){
 const [sort,setSort]=useState(null)
 const parts=elements(children),head=parts.find(p=>p.type==='thead'),headRow=head&&elements(head.props.children)[0],headers=headRow?elements(headRow.props.children):[]
 const labels=headers.map(h=>text(h.props.children))
 function change(index){setSort(current=>({index,direction:current?.index===index&&current.direction==='asc'?'desc':'asc'}))}
 return <table {...props}>{parts.map(part=>{
  if(part.type==='thead'&&headRow)return cloneElement(part,{},cloneElement(headRow,{},headers.map((h,i)=>h.props['data-sort-disabled']||/^(Actions?|Select|Pass|Fail|N\/A)$/i.test(labels[i])?h:cloneElement(h,{'aria-sort':sort?.index===i?sort.direction==='asc'?'ascending':'descending':'none'},<button className="table-sort" type="button" aria-label={`Sort by ${labels[i]} ${sort?.index===i&&sort.direction==='asc'?'descending':'ascending'}`} onClick={()=>change(i)}>{h.props.children}<span className={`sort-triangles ${sort?.index===i?sort.direction:'neutral'}`} aria-hidden="true"><i className="sort-up"/><i className="sort-down"/></span></button>))))
  if(part.type==='tbody'&&sort){const rows=elements(part.props.children);return cloneElement(part,{},rows.map((r,index)=>({r,index})).sort((a,b)=>{const x=elements(a.r.props.children)[sort.index],y=elements(b.r.props.children)[sort.index];return compareValues(cellValue(x),cellValue(y))*(sort.direction==='asc'?1:-1)||a.index-b.index}).map(x=>x.r))}
  return part
 })}</table>
}
