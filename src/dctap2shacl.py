import csv

import rdflib

from dataclasses import dataclass, field
from typing import Union


BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
BFLC = rdflib.Namespace("http://id.loc.gov/ontologies/bflc/")


def init_shacl() -> rdflib.Graph:
    graph = rdflib.Graph()
    graph.namespace_manager.bind("bf", BF)
    graph.namespace_manager.bind("bflc", BFLC)
    return graph


def prop_id_to_rdf_node(property_id):
    if ":" in property_id:
        namespace, suffix = property_id.split(":")
        namespace = namespace.strip()
        suffix = suffix.strip()
        match namespace:
            case "bf":
                path_object = getattr(BF, suffix)

            case "bflc":
                path_object = getattr(BFLC, suffix)

            case "rdf":
                path_object = getattr(rdflib.RDF, suffix)

            case "rdfs":
                path_object = getattr(rdflib.RDFS, suffix)

    elif property_id.startswith("http"):
        path_object = rdflib.URIRef(property_id)

    else:
        path_object = rdflib.Literal(property_id)

    return path_object


@dataclass
class DCTap2SHACLTransformer:
    dctap: list[dict] = field(default_factory=list)
    graph: rdflib.Graph = field(default_factory=init_shacl)

    def sh_datatype(self, datatype: str, property_bnode: rdflib.BNode):
        """Adds a rdflib.SH datatype to a property shape"""
        match datatype:
            case "rdf:langString":
                self.graph.add(
                    (property_bnode, rdflib.SH.datatype, rdflib.RDF.langString)
                )

            case "xsd:string":
                self.graph.add((property_bnode, rdflib.SH.datatype, rdflib.XSD.string))

    def sh_property_shape(self, shape_id: rdflib.Node, label: str) -> rdflib.BNode:
        """Adds rdflib.SH Property Shape"""
        property_bnode = rdflib.BNode()
        self.graph.add((shape_id, rdflib.SH.property, property_bnode))
        self.graph.add((property_bnode, rdflib.RDF.type, rdflib.SH.PropertyShape))
        self.graph.add((property_bnode, rdflib.RDFS.label, rdflib.Literal(label)))
        return property_bnode

    def sh_severity(self, property_bnode: rdflib.BNode, severity: Union[str, None]):
        """Checks and adds severity to property"""
        if severity:
            match severity.strip().casefold():
                case "violation":
                    severity_level = rdflib.SH.Violation

                case "warning":
                    severity_level = rdflib.SH.Warning

                case _:
                    severity_level = rdflib.SH.Info

            self.graph.add((property_bnode, rdflib.SH.severity, severity_level))

    def sh_value_constaint(
        self,
        value_constraint: str,
        value_constraint_type: str,
        property_bnode: rdflib.BNode,
    ):
        """Adds a value constraint type to a property shape"""
        predicate = None
        match value_constraint_type:
            case "picklist" | "IRIstem" | "languageTag":
                pass

            case "pattern":
                predicate = rdflib.SH.pattern

            case "minLength":
                predicate = rdflib.SH.minLength

            case "maxLength":
                predicate = rdflib.SH.maxLength

            case "minInclusive":
                predicate = rdflib.SH.minInclusive

            case "maxInclusive":
                predicate = rdflib.SH.maxInclusive

        if predicate:
            self.graph.add(
                (property_bnode, predicate, rdflib.Literal(value_constraint))
            )

    def add_property(self, row: dict):
        """Adds a rdflib.SH Node Property to the shape graph"""
        shape_id = rdflib.URIRef(row["shapeID"])
        node_shape = self.graph.value(subject=shape_id, predicate=rdflib.RDF.type)
        if (
            node_shape is None
        ):  # rdflib.SH Node Shape not in graph, adds shape_id as a rdflib.SH graph
            self.graph.add((shape_id, rdflib.RDF.type, rdflib.SH.NodeShape))
            self.graph.add(
                (shape_id, rdflib.RDFS.label, rdflib.Literal(row["shapeLabel"]))
            )
        property_bnode = self.sh_property_shape(shape_id, row["propertyLabel"])
        path_object = prop_id_to_rdf_node(row["propertyID"])
        self.graph.add((property_bnode, rdflib.SH.path, path_object))
        self.sh_severity(property_bnode, row.get("severity"))
        if row["mandatory"].startswith("true"):
            self.graph.add((property_bnode, rdflib.SH.minCount, rdflib.Literal(1)))
        if row["repeatable"].startswith("false"):
            self.graph.add((property_bnode, rdflib.SH.maxCount, rdflib.Literal(1)))
        value_shape = row.get("valueShape")
        if isinstance(value_shape, str) and len(value_shape.strip()) > 0:
            self.graph.add((property_bnode, rdflib.SH.node, rdflib.URIRef(value_shape)))
        if "valueDataType" in row:
            self.sh_datatype(row["valueDataType"], property_bnode)
