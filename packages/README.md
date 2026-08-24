# Packages

Shared prototype-only packages live here.

Do not treat packages in this repo as governed production libraries until they
graduate.

`prototype_delivery_packet/` owns deterministic production and validation of
the Prototype source packet used by the governed Delivery ingress path. It does
not own target admission or Delivery mutation.
