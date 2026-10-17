export function parseClientAddress(value){
 const parts=String(value).trim().split(/\s+[-–—]\s+/).map(part=>part.trim())
 if(parts.length<3||parts.some(part=>!part))return null
 const client=parts[0],address=parts.slice(1,-1).join(' - ')+', '+parts.at(-1)
 return client.length<=160&&address.length<=500?{client,address}:null
}
