"""C-11 `senas-mercadopago` — dominio de señas y pagos de Mercado Pago.

Módulos:
- `regla`: regla efectiva de la seña (PO-01 / RN-SE-05).
- `puertos`: entidades, protocolos y adaptadores en memoria + pasarela fake.

La frontera de red es **sólo** `AdaptadorPasarelaHTTP` (implementado en una capa
posterior); todos los tests usan `AdaptadorPasarelaFake`. Sin PHI en logs.
"""
