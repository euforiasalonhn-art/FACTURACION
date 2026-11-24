"""Cobro de envío separado del ingreso por productos."""
SERVICES={'Comer aquí':'COMER AQUI','Para llevar':'PARA LLEVAR','Domicilio':'PARA ENVIO','COMER AQUI':'COMER AQUI','COMER AQUÍ':'COMER AQUI','PARA LLEVAR':'PARA LLEVAR','ENVIO':'PARA ENVIO','PARA ENVIO':'PARA ENVIO'}
def service(d):
 value=SERVICES.get(d.get('service','Comer aquí'))
 if not value:raise ValueError('Selecciona COMER AQUI, PARA LLEVAR o ENVIO')
 return value

def fee(d,money):
 amount=money(d.get('delivery_fee',0))
 if amount and service(d)!='PARA ENVIO':raise ValueError('El importe de envío solo corresponde a pedidos PARA ENVIO')
 if amount and (d.get('employee_meal') or d.get('special_order')):raise ValueError('El envío con cobro debe registrarse en una venta, separado del consumo gratis')
 return amount

def apply(calc,d,money):
 amount=fee(d,money);calc=dict(calc);calc['sales_total']=calc['total'];calc['delivery_fee']=amount;calc['total']+=amount
 if calc['total']>10000000000:raise ValueError('El total con envío supera el máximo permitido')
 return calc

def split_payments(payments,amount):
 total=sum(payments.values())
 if not amount or not total:return dict(payments),{k:0 for k in payments}
 parts={k:divmod(v*amount,total) for k,v in payments.items()};fees={k:v[0] for k,v in parts.items()}
 for k in sorted(parts,key=lambda k:parts[k][1],reverse=True)[:amount-sum(fees.values())]:fees[k]+=1
 return {k:v-fees[k] for k,v in payments.items()},fees
