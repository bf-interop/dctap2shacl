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


[uv]: https://docs.astral.sh/uv/
