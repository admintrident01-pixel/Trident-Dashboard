import {compareValues} from './tableSort'
import {Children,cloneElement,isValidElement,useState} from 'react'
import './SortableTable.css'
import HistoryPagination from './HistoryPagination'
import {pageWindow,orderedPage} from './pagination'
const elements=node=>Children.toArray(node).filter(isValidElement)
const text=node=>typeof node==='string'||typeof node==='number'?String(node):isValidElement(node)?text(node.props.children):Array.isArray(node)?node.map(text).join(' '):''
function cellValue(cell){return cell?.props['data-sort-value']??text(cell?.props.children)}
export default function SortableTable({children,groupSize=1,paginate=false,paginationLabel='records',paginationReset='',...props}){
 const [sort,setSort]=useState(null),[paging,setPaging]=useState({key:'',page:1,size:10})
 const parts=elements(children),head=parts.find(p=>p.type==='thead'),headRow=head&&elements(head.props.children)[0],headers=headRow?elements(headRow.props.children):[]
 const body=parts.find(part=>part.type==='tbody'),bodyRows=body?elements(body.props.children):[],datasetKey=JSON.stringify([paginationReset,bodyRows.map(row=>row.key)])
 const range=pageWindow(Math.ceil(bodyRows.length/groupSize),paging.key===datasetKey?paging.page:1,paging.size)
 const changePage=page=>setPaging(current=>({...current,key:datasetKey,page}))
 const changeSize=size=>setPaging({key:datasetKey,page:1,size})
 const labels=headers.map(h=>text(h.props.children))
 function change(index){changePage(1);setSort(current=>({index,direction:current?.index===index&&current.direction==='asc'?'desc':'asc'}))}
 return <>{paginate&&<HistoryPagination range={range} label={paginationLabel} onPage={changePage} onSize={changeSize}/>}<table {...props}>{parts.map(part=>{
  if(part.type==='thead'&&headRow)return cloneElement(part,{},cloneElement(headRow,{},headers.map((h,i)=>h.props['data-sort-disabled']||/^(Actions?|Select|Pass|Fail|N\/A)$/i.test(labels[i])?h:cloneElement(h,{'aria-sort':sort?.index===i?sort.direction==='asc'?'ascending':'descending':'none'},<button className="table-sort" type="button" aria-label={`Sort by ${labels[i]} ${sort?.index===i&&sort.direction==='asc'?'descending':'ascending'}`} onClick={()=>change(i)}>{h.props.children}<span className={`sort-triangles ${sort?.index===i?sort.direction:'neutral'}`} aria-hidden="true"><i className="sort-up"/><i className="sort-down"/></span></button>))))
  if(part.type==='tbody'&&(sort||paginate)){
   const groups=Array.from({length:Math.ceil(bodyRows.length/groupSize)},(_,i)=>bodyRows.slice(i*groupSize,(i+1)*groupSize)).map((group,index)=>({group,index}))
   const compare=sort?(a,b)=>{const x=elements(a.group[0].props.children)[sort.index],y=elements(b.group[0].props.children)[sort.index];return compareValues(cellValue(x),cellValue(y))*(sort.direction==='asc'?1:-1)||a.index-b.index}:null
   const result=paginate?orderedPage(groups,compare,range.page,range.size).rows:compare?groups.sort(compare):groups
   return cloneElement(part,{},result.flatMap(item=>item.group))
  }
  return part
 })}</table></>
}
