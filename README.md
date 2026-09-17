# BIG dctap2shacl Custom Parser
Code repository for the BIBFRAME InterOp Group's custom DCTap-to-SHACL parser.

## Command Line Usage
After installing, convert one or more BIBFRAME DCTap files to a SHACL validation
graph from the command:

- If installed with [uv][uv], `uv run dctap2shacl --dctap admin_metadata.tsv`
- If installed with pip, `dctap2shacl --dctap admin_metadata.tsv`

This will create and save a turtle file, `bf-validation.ttl` in the same directory.

### Options
- `-h`, `--help` Displays help
- `-i`, `--dctap` One or more DCTap files, seperated by commas
- `-o`, `--shacl` Optional, file name for the validation graph
- `-fmt`, `--format` Optional, RDF serialization format, can be one of the following:
  - `turtle`: Turtle (default)
  - `xml` or `pretty-xml`: XML
  - `json-ld`: JSON Linked Data format
  - `nt`: N-triples

## DCTap Column Support

### Alternative properties

Two ways of saying "either of these properties satisfies the constraint", both of
which generate a `sh:or` list on the node shape:

- **Same `valueNodeType`** — list the properties semi-colon separated in a single
  `propertyID` cell. Every branch shares that one row's constraints.
- **Different `valueNodeType`** (e.g. one expects a literal and the other an IRI)
  — give each property its own row and name the alternative in an `sh:or` column.
  Each branch keeps the constraints of its own row, so the literal and IRI
  alternatives can differ in `valueNodeType`, `valueShape`, and so on.

The `sh:or` column is normally filled in reciprocally, each row naming the other,
and the paired rows do not have to be adjacent. Alternatives are matched within a
single `shapeID`, so paired rows must agree on their `shapeID`. If an `sh:or`
names a property that has no row of its own, that alternative is emitted with
only its `sh:path`.

### valueNodeType

`valueNodeType` maps to `sh:nodeKind`. Multiple types are semi-colon separated
(`IRI ; bnode`), and `bnode` may also be written `blank node` or `blankNode`.

| `valueNodeType` | `sh:nodeKind` |
| --- | --- |
| `literal` | `sh:Literal` |
| `IRI` | `sh:IRI` |
| `bnode` | `sh:BlankNode` |
| `IRI ; bnode` | `sh:BlankNodeOrIRI` |
| `IRI ; literal` | `sh:IRIOrLiteral` |
| `bnode ; literal` | `sh:BlankNodeOrLiteral` |

An empty, unrecognized, or fully unconstrained (all three types) cell produces no
`sh:nodeKind`.


[uv]: https://docs.astral.sh/uv/
