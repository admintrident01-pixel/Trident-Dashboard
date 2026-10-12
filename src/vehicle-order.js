export function moveVehicle(rows,index,direction){
 const target=index+direction
 if(index<0||index>=rows.length||target<0||target>=rows.length)return rows
 const moved=[...rows];[moved[index],moved[target]]=[moved[target],moved[index]]
 return moved
}
