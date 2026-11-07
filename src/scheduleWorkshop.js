export function workshopLocationForm(form,checked,workshopAddress){
 return checked?{...form,_clientAddress:form.address,address:workshopAddress||'',workshopLocation:true,includeWorkshopTravel:false}:
  {...form,address:form._clientAddress||'',workshopLocation:false,includeWorkshopTravel:false}
}
