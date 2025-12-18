import argparse

from dctap2shacl import DCTap2SHACLTransformer


def main():
    parser = argparse.ArgumentParser(
        description="Tranform DCTap TSV files to SHACL BIBFRAME validation graph."
    )
    parser.add_argument("-i", "--dctap", help="One or more DCTap files, seperated by commas")
    parser.add_argument(
        "-o", "--shacl", default="bf-validation.ttl", help="Output SHACL validation file"
    )
    parser.add_argument(
        "-fmt", "--format", default="turtle", help="Serialization format for SHAC, default is turtle"
    )

    args = parser.parse_args()
    dctap_files = args.dctap.split(",")
    shacl = args.shacl
    rdf_format = args.format
    transformer = DCTap2SHACLTransformer()
    for dctap in dctap_files:
        transformer.run(dctap)
    with open(shacl, "w+") as fo:
        fo.write(transformer.graph.serialize(format=rdf_format))


if __name__ == "__main__":
    main()