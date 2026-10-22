export const defaultClientSearchUrl='https://www.google.com/search?q={client}'
export function clientSearchUrl(template,client){
 if(!template||!client?.trim())return ''
 if(typeof template!=='string'||template.length>2000||(/\s/.test(template)||template.includes('\\')||[...template].some(c=>c.charCodeAt(0)<32))||!template.includes('{client}')||/[{}]/.test(template.replaceAll('{client}','')))return ''
 try{
  const url=new URL(template.replaceAll('{client}',encodeURIComponent(client.trim()).replace(/[!'()*]/g,c=>'%'+c.charCodeAt(0).toString(16).toUpperCase())))
  const authority=template.match(/^https?:\/\/([^/?#]+)/i)?.[1]||''
  if(!authority||!['http:','https:'].includes(url.protocol)||!url.hostname||url.username||url.password||authority.includes('{client}'))return ''
  return url.href
 }catch{return ''}
}
