export const contactKinds=[
 {key:'voicemail',label:'Left Vmail',off:'No voicemail left',icon:'custom-contact-voicemail',legacy:/^left\s+(?:vmail|voicemail|voice mail)\b/im},
 {key:'text',label:'Left Text',off:'No text sent',icon:'custom-contact-text',legacy:/^left\s+text\b/im},
 {key:'email',label:'Left email',off:'No email sent',icon:'custom-contact-email',legacy:/^left\s+email\b/im},
]
export function contactMarked(row,kind){
 const value=row.contactStatus?.[kind.key]
 return typeof value==='boolean'?value:kind.legacy.test(row.notes||'')
}
export function withContactMark(row,key){
 const kind=contactKinds.find(k=>k.key===key)
 if(!kind)return row
 return {...row,contactStatus:{...row.contactStatus,[key]:!contactMarked(row,kind)}}
}
