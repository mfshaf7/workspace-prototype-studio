# Prototype Devint Preview

`prototype-devint` is a lane class, not a new environment name.

The technical environment remains `dev-integration`. The lane class tells the
operator that the runtime is for prototype preview and is not governed stage,
prod, or release evidence.

Prototype devint profiles must declare:

- source repos
- runtime shape
- data mode
- mutation boundary
- persistence model
- cleanup owner
- TTL or retirement rule
- promotion or graduation path

